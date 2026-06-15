"""Fast request triage — the key to a snappy agent.

The agent has two modes:

  • simple   — conversational / knowledge replies. Answered in ONE streaming
               call with NO tools attached and a lightweight prompt, so a
               "hi" comes back in ~1s instead of 40s.
  • agentic  — anything that needs to touch files, run code, search the web,
               or otherwise act on the workspace. Runs the full tool loop.

Classification is a cheap, robust heuristic. As a safety net the simple path
is told it may emit the sentinel ``NEEDS_TOOLS`` if it realises mid-answer
that it actually needs to act — the caller then transparently escalates to
the full agent loop, so a mis-classification never produces a wrong answer.
"""
import re

# ── Signals that strongly imply the agent must ACT on the environment ────────
_AGENTIC_PATTERNS = [
    # explicit build / create / implement something concrete
    r"\b(build|create|make|generate|implement|scaffold|set\s?up|develop|write)\b"
    r"[^.!?]*\b(app|application|website|site|web\s?page|script|program|server|api|"
    r"component|function|class|module|project|game|tool|cli|bot|library|package|"
    r"file|test|config|dockerfile|readme|notebook)\b",

    # run / execute / launch / test / debug
    r"\b(run|execute|launch|start|serve|deploy|test|debug|profile|benchmark|compile)\b",

    # fix / change existing code or files
    r"\b(fix|repair|patch|refactor|optimi[sz]e|update|modify|change|edit|rename|"
    r"delete|remove|move|rewrite)\b[^.!?]*\b(file|code|bug|error|function|script|"
    r"directory|folder|project|repo|class|method|import|test)\b",

    # web / research actions
    r"\b(search|google|look\s?up|research|scrape|crawl|fetch|download|browse)\b"
    r"[^.!?]*\b(web|online|internet|latest|news|article|url|site|page|http|docs?)\b",

    # filesystem / workspace inspection
    r"\b(list|show|read|open|cat|inspect|summari[sz]e|analy[sz]e|explore|review|check)\b"
    r"[^.!?]*\b(file|files|directory|folder|workspace|project|repo|repository|"
    r"codebase|tree|archive|zip)\b",

    # version control
    r"\bgit\b|\bcommit\b|\bpush\b|\bpull request\b|\bbranch\b",

    # package managers / installs
    r"\b(install|pip|npm|yarn|pnpm|apt|brew|cargo|go get)\b",

    # explicit environment nouns
    r"\b(workspace|terminal|shell|command line|bash|stdout|stderr)\b",

    # a URL
    r"https?://",

    # a code fence
    r"```",

    # a filename with a common code/data extension
    r"\b[\w\-/]+\.(py|js|ts|tsx|jsx|html?|css|scss|json|ya?ml|toml|md|txt|csv|tsv|"
    r"sh|bash|go|rs|java|kt|cpp|cc|c|hpp|rb|php|sql|ipynb|env|cfg|ini|xml|svg)\b",
]
_AGENTIC_RE = re.compile("|".join(_AGENTIC_PATTERNS), re.IGNORECASE)

# Phrases that, even if long, are clearly conversational / knowledge questions
_SIMPLE_LEADS = (
    "what is", "what are", "what's", "who is", "who are", "who's", "whats",
    "explain", "define", "describe", "tell me about", "how does", "how do",
    "why is", "why does", "why do", "when did", "where is", "compare",
    "difference between", "pros and cons", "summarize this", "translate",
    "what do you think", "your opinion", "can you explain", "help me understand",
)

# Tiny / greeting messages
_TRIVIAL = {
    "hi", "hii", "hiii", "hey", "heya", "hello", "yo", "sup", "hi there",
    "hello there", "hey there", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "thx", "ty", "thank u", "cheers", "ok", "okay", "k",
    "cool", "nice", "great", "awesome", "got it", "gotcha", "no", "yes", "yep",
    "nope", "yeah", "sure", "lol", "haha", "bye", "goodbye", "see ya", "gn",
    "good night", "test", "ping", "?", "??", "who are you", "what can you do",
    "what are you", "help", "how are you", "whats up", "what's up", "wassup",
}


def classify(messages: list[dict]) -> str:
    """Return 'simple' or 'agentic' for the latest user message in context."""
    # last user turn
    last_user = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user:
        return "simple"
    text = (last_user.get("content") or "").strip()
    low = text.lower().strip(" .!?")

    if not text:
        return "simple"

    # 1) trivial greetings / acks → always simple
    if low in _TRIVIAL:
        return "simple"

    # 2) a workspace file was attached in this turn → almost certainly agentic
    if "uploaded to the workspace" in text.lower():
        return "agentic"

    # 3) explicit agentic signal anywhere → agentic
    if _AGENTIC_RE.search(text):
        return "agentic"

    # 4) starts like a knowledge / conversational question → simple
    if low.startswith(_SIMPLE_LEADS):
        return "simple"

    # 5) short and no agentic signal → simple
    word_count = len(text.split())
    if word_count <= 18:
        return "simple"

    # 6) longer prose with no agentic signal — lean simple but the NEEDS_TOOLS
    #    escape hatch in the simple path will rescue any true edge case.
    return "simple"


# ── Swarm eligibility ─────────────────────────────────────────────────────────
# A task is worth decomposing across a multi-agent swarm when it is clearly
# multi-part / large in scope. Cheap heuristic; the orchestrator still falls
# back to the single-agent loop for anything that doesn't benefit.
_MULTIPART_RE = re.compile(
    r"\b(and then|then|after that|also|additionally|as well as|followed by)\b"
    r"|[1-9]\s*[\).]\s|\bsteps?\b|\bfirst\b.*\bthen\b",
    re.IGNORECASE,
)
_BIG_BUILD_RE = re.compile(
    r"\b(full|complete|entire|end[- ]to[- ]end|production|multi[- ]?(file|page|step)|"
    r"app|application|website|platform|system|pipeline|dashboard|backend|frontend|"
    r"full[- ]stack|micro[- ]?service)\b",
    re.IGNORECASE,
)


def is_complex(messages: list[dict]) -> bool:
    """Heuristic: should this request fan out to the swarm orchestrator?"""
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_user:
        return False
    text = (last_user.get("content") or "").strip()
    if len(text.split()) < 8:
        return False
    signals = 0
    if _MULTIPART_RE.search(text):
        signals += 1
    if _BIG_BUILD_RE.search(text):
        signals += 1
    if len(text.split()) > 45:
        signals += 1
    if text.count("\n") >= 3:
        signals += 1
    return signals >= 2


# System prompt for the fast conversational path.
SIMPLE_SYSTEM = (
    "You are Agent Studio, a warm, sharp assistant. Answer the user directly "
    "and concisely in clean Markdown. Do not narrate a plan, do not describe "
    "your process, and do not pad the reply.\n\n"
    "You also have a powerful toolkit available (files, shell, Python, web, git) "
    "but it is NOT attached right now. If — and only if — properly answering this "
    "message genuinely requires acting on the workspace (reading or writing files, "
    "running code or commands, searching or fetching the web, or git), then reply "
    "with EXACTLY the single token `NEEDS_TOOLS` and nothing else, so the full "
    "agent can take over. For ordinary questions, chit-chat, explanations, math, "
    "writing, or advice, just answer — never emit that token."
)

NEEDS_TOOLS_SENTINEL = "NEEDS_TOOLS"
