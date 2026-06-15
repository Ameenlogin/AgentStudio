"""Non-secret defaults, safe to commit and ship publicly.

The actual API key is NOT here — users add their NVIDIA NIM key in the in-app
Settings screen on first run (or, optionally, in a local gitignored keys.py).
"""

# NVIDIA NIM (OpenAI-compatible) endpoint.
BASE_URL = "https://integrate.api.nvidia.com/v1"

# Default model — Moonshot Kimi K2.6 on NVIDIA NIM.
DEFAULT_MODEL = "moonshotai/kimi-k2.6"
