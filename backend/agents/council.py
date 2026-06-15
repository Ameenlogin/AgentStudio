"""Model Council — a reverse-engineered take on Perplexity's "Model Council".

Idea: instead of trusting one model, convene a *council* of diverse models.
Each member answers the question independently; a chair then critically reviews
every answer (peer review) and synthesizes a single best response that combines
their strengths and discards their mistakes. Diversity + peer review reliably
beats any single model.

Everything runs through the one rate-limited NVIDIA key: members answer
concurrently (the pool throttles to ~40 RPM and backs off on 429), then the
chair streams the final answer. Events let the UI show the council deliberating.

Protocol events (NDJSON):
  {"type":"council_start","members":[{"id","model","label"}]}
  {"type":"council_member","id","model","status":"answering"|"done","preview"}
  {"type":"content","delta": "..."}      # the chair's synthesized final answer
  {"type":"done"}
"""
import asyncio
from services.kimi_client import KimiClient


# A small, diverse, all-verified council. The chair is the strongest member.
COUNCIL_MODELS = [
    ("moonshotai/kimi-k2.6", "Kimi K2.6"),
    ("openai/gpt-oss-120b", "GPT-OSS 120B"),
    ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B"),
]
CHAIR_MODEL = "moonshotai/kimi-k2.6"

_MEMBER_SYSTEM = (
    "You are a member of an expert council answering a user's question. Give your "
    "best, most accurate and complete answer. Be concise and concrete. If you are "
    "unsure, say so rather than guessing."
)

_CHAIR_SYSTEM = (
    "You are the CHAIR of an expert model council. You are given the user's question "
    "and several council members' independent answers. Critically evaluate them: note "
    "where they agree (high confidence), catch errors or omissions, and combine their "
    "strengths. Then write the single best final answer for the user — accurate, "
    "complete, and well-structured Markdown. Do not mention the council or the members "
    "by name; just deliver the best answer."
)


def _ev(obj):
    import json
    return json.dumps(obj, ensure_ascii=False) + "\n"


async def _member_answer(model, label, mid, messages, pool, base_url, temperature, queue):
    await queue.put(_ev({"type": "council_member", "id": mid, "model": model,
                         "label": label, "status": "answering"}))
    client = KimiClient(pool=pool, base_url=base_url, model_name=model)
    convo = [{"role": "system", "content": _MEMBER_SYSTEM}]
    convo.extend(messages)
    parts = []
    try:
        async for chunk in client.stream_guarded(convo, tools=None,
                                                 temperature=min(temperature, 0.7),
                                                 thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
    except Exception as e:
        parts.append(f"(no answer: {e})")
    answer = "".join(parts).strip()
    await queue.put(_ev({"type": "council_member", "id": mid, "model": model,
                         "label": label, "status": "done",
                         "preview": answer[:160]}))
    return {"label": label, "model": model, "answer": answer}


async def run_council(messages, *, pool, base_url, model_name, temperature=0.5):
    members = COUNCIL_MODELS
    yield _ev({"type": "council_start",
               "members": [{"id": f"m{i}", "model": m, "label": lbl}
                           for i, (m, lbl) in enumerate(members)]})

    # ---- Round 1: members answer concurrently (pool throttles to ~40 RPM) ----
    queue: asyncio.Queue = asyncio.Queue()
    tasks = [asyncio.create_task(
                _member_answer(m, lbl, f"m{i}", messages, pool, base_url, temperature, queue))
             for i, (m, lbl) in enumerate(members)]
    while True:
        try:
            ev = await asyncio.wait_for(queue.get(), timeout=0.15)
            yield ev
            continue
        except asyncio.TimeoutError:
            pass
        if all(t.done() for t in tasks) and queue.empty():
            break
    answers = []
    for t in tasks:
        try:
            answers.append(t.result())
        except Exception:
            pass
    answers = [a for a in answers if a.get("answer") and not a["answer"].startswith("(no answer")]

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    question = (last_user.get("content") if last_user else "") or ""

    if not answers:
        # Whole council failed — fall back to a single chair answer.
        chair = KimiClient(pool=pool, base_url=base_url, model_name=CHAIR_MODEL)
        async for chunk in chair.stream_guarded(
                [{"role": "system", "content": _MEMBER_SYSTEM}] + messages,
                tools=None, temperature=temperature, thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                yield _ev({"type": "content", "delta": chunk.choices[0].delta.content})
        yield _ev({"type": "done"})
        return

    # ---- Round 2: the chair reviews + synthesizes (streamed) ----------------
    brief = [f"USER QUESTION:\n{question[:4000]}\n\nCOUNCIL ANSWERS:"]
    for i, a in enumerate(answers, 1):
        brief.append(f"\n--- Member {i} ({a['label']}) ---\n{a['answer'][:4000]}")
    chair = KimiClient(pool=pool, base_url=base_url, model_name=CHAIR_MODEL)
    chair_convo = [{"role": "system", "content": _CHAIR_SYSTEM},
                   {"role": "user", "content": "\n".join(brief)}]
    produced = False
    try:
        async for chunk in chair.stream_guarded(chair_convo, tools=None,
                                               temperature=min(temperature, 0.5),
                                               thinking=False):
            if chunk.choices and chunk.choices[0].delta.content:
                produced = True
                yield _ev({"type": "content", "delta": chunk.choices[0].delta.content})
    except Exception:
        pass
    if not produced:
        yield _ev({"type": "content", "delta": answers[0]["answer"]})
    yield _ev({"type": "done"})
