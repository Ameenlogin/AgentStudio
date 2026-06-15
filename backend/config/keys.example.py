"""Local credential wiring (TEMPLATE).

Copy this file to `keys.py` and fill in your own NVIDIA NIM API key.
`keys.py` is gitignored so your real key never enters version control.

This is a LOCAL, single-user project: the NVIDIA API key is read here and
seeded into the settings database on startup. The app runs on ONE key, held
to ~40 RPM by the rate-aware pool.
"""

# NVIDIA NIM API key (get one at https://build.nvidia.com).
NVIDIA_API_KEYS = [
    "nvapi-YOUR_KEY_HERE",
]

# Per-key request budget (NVIDIA's hard limit is 40 RPM). The sliding-window
# pool self-throttles below this and backs off on any 429.
RPM_PER_KEY = 40

BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "moonshotai/kimi-k2.6"
