"""Multi-agent swarm orchestrator.

    User Request → Planner → [parallel research workers] → Builder → Synthesizer

  • Planner       — decomposes the request into role-tagged subtasks (JSON).
  • Workers       — researcher / architect subtasks run CONCURRENTLY with a
                    read-only toolset (safe to parallelize, no file races).
  • Builder       — coder / debugger phase: one full-toolkit agentic loop that
                    actually writes files, runs code and produces artifacts,
                    using the workers' findings. The user's permission gate
                    still applies here.
  • Synthesizer   — streams the final, clean answer to the user.

Falls back to the single-agent loop if planning fails, so the swarm can never
leave the user worse off. Concurrency is bounded and every model call goes
through the same rate-limited pool, so the swarm never threatens the RPM budget.
"""
import json
import asyncio

from agents.agent import agentic_loop, _status_ev, _ev, _compose_system, _env_preamble
from tools.tool_router import AVAILABLE_TOOLS, TOOL_META, READ_KINDS

MAX_PARALLEL_WORKERS = 3
WORKER_MAX_STEPS = 6

# Read-only subset is safe to run in parallel (no workspace mutations).
READONLY_TOOLS = [
    t for t in AVAILABLE_TOOLS
    if TOOL_META.get(t["function"]["name"], {}).get("kind") in READ_KINDS
]

_PLANNER_SYSTEM = (
    "You are the PLANNER of a multi-agent engineering swarm. Decompose the user's "
    "request into a small set of focused subtasks and assign each to a role.\n"
    "Roles: 'researcher' (gather facts/web/docs), 'architect' (inspect the "
    "workspace, design the approach), 'coder' (write/modify code & files), "
    "'debugger' (run, test, fix).\n"
    "Return STRICT JSON only, no prose, no code fence:\n"
    '{"plan":"one-sentence approach","subtasks":[{"id":1,"role":"researcher",'
    '"title":"short title","detail":"what to do","parallel":true}]}\n'
    "Rules: 2-5 subtasks. Mark researcher/architect subtasks parallel:true; "
    "coder/debugger parallel:false. Keep titles under 6 words."
)

_RESEARCH_SYSTEM = (
    "You are the {role} worker in an engineering swarm. Do ONLY your assigned "
    "subtask using read-only tools (read files, list/tree the workspace, search, "
    "web search/fetch). Do not write files or run commands. Finish with a tight, "
    "factual report of what you found that the builder can act on."
)

_BUILDER_SYSTEM = (
    "You are the BUILDER of an engineering swarm. Using the plan and the research "
    "reports provided, implement the task end-to-end: write/modify files, run and "
    "test code, create archives, and verify your work with the full toolkit. Be "
    "decisive and thorough. When done, briefly note what you produced."
)

_SYNTH_SYSTEM = (
    "You are the SYNTHESIZER of an engineering swarm. Write the final answer to the "
    "user. Summarize clearly what was accomplished, the key results and artifacts, "
    "and how to use them. Base everything strictly on the build log and reports "
    "provided — do not invent results. Be warm, concise and well-formatted Markdown."
)


def _extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


async def _plan(client, messages, temperature) -> dict | None:
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    request = (last_user.get("content") if last_user else "") or ""
    convo = [{"role": "system", "content": _env_preamble() + _PLANNER_SYSTEM},
             {"role": "user", "content": request[:6000]}]
    parts = []
    try:
        async for chunk in client.stream_guarded(convo, tools=None, temperature=0.2, thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
    except Exception:
        return None
    data = _extract_json("".join(parts))
    if not data or not isinstance(data.get("subtasks"), list) or not data["subtasks"]:
        return None
    return data


async def _research_worker(worker, client, pool, temperature, queue):
    aid = f"w{worker['id']}"
    role = worker.get("role", "researcher")
    title = worker.get("title", "Research")
    await queue.put(_ev({"type": "swarm_agent", "id": aid, "role": role,
                         "title": title, "status": "running"}))
    convo = [
        {"role": "system", "content": _env_preamble() + _RESEARCH_SYSTEM.format(role=role)},
        {"role": "user", "content": worker.get("detail") or title},
    ]
    report = []
    try:
        async for ev in agentic_loop(client, pool, convo, READONLY_TOOLS, temperature,
                                     WORKER_MAX_STEPS, "auto", agent_id=aid,
                                     allow_all_override=True):
            d = json.loads(ev)
            t = d.get("type")
            if t == "content":
                report.append(d.get("delta", ""))
            elif t in ("tool_start", "tool_result", "tool_stream", "reasoning"):
                await queue.put(ev)
    except Exception as e:
        report.append(f"(worker error: {e})")
    await queue.put(_ev({"type": "swarm_agent", "id": aid, "role": role,
                         "title": title, "status": "done"}))
    return {"role": role, "title": title, "report": "".join(report).strip()}


async def run_swarm(messages, *, client, pool, model_name, temperature,
                    system_prompt, max_steps, permission_mode):
    yield _status_ev(pool)

    plan = await _plan(client, messages, temperature)
    if not plan:
        # Planning failed — degrade gracefully to the normal agentic loop.
        base = [{"role": "system", "content": system_prompt or
                 "You are Agent Studio, an autonomous software-and-research agent."}]
        base.extend(messages)
        async for ev in agentic_loop(client, pool, base, AVAILABLE_TOOLS,
                                     temperature, max_steps, permission_mode):
            yield ev
        return

    subtasks = plan["subtasks"][:5]
    for i, st in enumerate(subtasks, 1):
        st.setdefault("id", i)
    yield _ev({"type": "swarm_plan", "plan": plan.get("plan", ""),
               "subtasks": [{"id": f"w{s['id']}", "role": s.get("role", "researcher"),
                             "title": s.get("title", "Subtask")} for s in subtasks]})

    research = [s for s in subtasks
                if s.get("parallel") and s.get("role") in ("researcher", "architect")][:MAX_PARALLEL_WORKERS]
    build_tasks = [s for s in subtasks if s not in research]

    # ---- Parallel research workers -----------------------------------------
    reports = []
    if research:
        queue: asyncio.Queue = asyncio.Queue()
        tasks = [asyncio.create_task(_research_worker(w, client, pool, temperature, queue))
                 for w in research]
        ticks = 0
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=0.15)
                yield ev
                continue
            except asyncio.TimeoutError:
                pass
            ticks += 1
            if ticks % 12 == 0:
                yield _status_ev(pool)
            if all(t.done() for t in tasks) and queue.empty():
                break
        for t in tasks:
            try:
                reports.append(t.result())
            except Exception:
                pass

    # ---- Builder phase (full toolkit, permission gate active) --------------
    yield _ev({"type": "swarm_agent", "id": "builder", "role": "coder",
               "title": "Builder", "status": "running"})

    brief_lines = [f"PLAN: {plan.get('plan','')}"]
    if build_tasks:
        brief_lines.append("BUILD SUBTASKS:")
        for s in build_tasks:
            brief_lines.append(f"- [{s.get('role','coder')}] {s.get('title','')}: {s.get('detail','')}")
    if reports:
        brief_lines.append("\nRESEARCH FINDINGS:")
        for r in reports:
            brief_lines.append(f"### {r['title']} ({r['role']})\n{r['report'][:2500]}")
    brief = "\n".join(brief_lines)

    convo = [{"role": "system", "content": _compose_system(_BUILDER_SYSTEM)}]
    convo.extend(messages)
    convo.append({"role": "user", "content":
                  "Use this swarm plan and research to complete the task:\n\n" + brief})

    build_summary = []
    async for ev in agentic_loop(client, pool, convo, AVAILABLE_TOOLS, temperature,
                                 max_steps, permission_mode):
        d = json.loads(ev)
        t = d.get("type")
        if t == "content":
            build_summary.append(d.get("delta", ""))   # captured, synthesized below
            continue
        if t == "done":
            continue
        yield ev  # forward reasoning, tool_*, permission_request, status, heartbeat

    yield _ev({"type": "swarm_agent", "id": "builder", "role": "coder",
               "title": "Builder", "status": "done"})

    # ---- Synthesizer phase --------------------------------------------------
    yield _ev({"type": "swarm_agent", "id": "synth", "role": "synthesizer",
               "title": "Synthesizer", "status": "running"})

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    request = (last_user.get("content") if last_user else "") or ""
    synth_input = (
        f"USER REQUEST:\n{request[:2000]}\n\n"
        f"BUILD LOG:\n{''.join(build_summary)[:6000]}\n\n"
        f"PLAN: {plan.get('plan','')}"
    )
    synth_convo = [{"role": "system", "content": _SYNTH_SYSTEM},
                   {"role": "user", "content": synth_input}]
    produced = False
    try:
        async for chunk in client.stream_guarded(synth_convo, tools=None,
                                                 temperature=min(temperature, 0.5),
                                                 thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                produced = True
                yield _ev({"type": "content", "delta": chunk.choices[0].delta.content})
    except Exception:
        pass

    if not produced:
        # Fallback: surface the build log so the user always gets the result.
        yield _ev({"type": "content", "delta": "".join(build_summary) or
                   "Task completed by the swarm."})

    yield _ev({"type": "swarm_agent", "id": "synth", "role": "synthesizer",
               "title": "Synthesizer", "status": "done"})
    yield _ev({"type": "done"})
