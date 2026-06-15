"""Non-secret defaults, safe to commit and ship publicly.

The actual API key is NOT here — users add their NVIDIA NIM key in the in-app
Settings screen on first run (or, optionally, in a local gitignored keys.py).
"""

# NVIDIA NIM (OpenAI-compatible) endpoint.
BASE_URL = "https://integrate.api.nvidia.com/v1"

# Default model — GPT-OSS 120B on NVIDIA NIM (fastest responses). Users can
# switch to Kimi K2.6 or any other supported model in the UI.
DEFAULT_MODEL = "openai/gpt-oss-120b"
