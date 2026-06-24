# onaiagents — full project map (for humans and AIs)

This repository is the **complete source** for two things that ship from one codebase:

1. **onaiagents.com** — a hosted suite of **six AI tools** (a static front-end in `site/` + a
   FastAPI back-end in `backend/`).
2. **AgentStudio** — an autonomous coding agent (a React/Vite app in `frontend/` + the same
   FastAPI back-end). It runs locally on a desktop *and* hosted under `onaiagents.com/agentstudio`.

Everything is editable and pullable. If you are an AI asked to change something, read this file
first, then jump to the specific module named below.

---

## The six tools (and where each lives)

| Tool | Page (front-end) | Back-end endpoint(s) | Model / provider |
|------|------------------|----------------------|------------------|
| Image Generation | `site/playground.html` | `POST /api/site/generate` (`tool:"image"`) | xAI `grok-imagine-image` (admin key) |
| 8K Upscaler | `site/upscaler.html` | `POST /api/site/generate` (`tool:"upscale"`) | local **Pillow** Lanczos (no external call) |
| Deconstruct (image→prompt) | `site/deconstruct.html` | `POST /api/site/generate` (`tool:"deconstruct"`) | xAI `grok-4.3` vision (admin key) |
| AI Friends (voice companions) | `site/ai-friends.html` | `/api/site/friends`, `/api/site/chat`, `/api/site/tts` | xAI `grok-4.3` chat + xAI TTS (71 voices) |
| Social Media Automation | `site/linkedin.html` | `/api/site/linkedin/research`, `/api/site/linkedin/run` | NVIDIA `gpt-oss-120b` (BYOK) → falls back to the xAI provider |
| AgentStudio (coding agent) | `frontend/` (React app, served at `/agentstudio`) | `/api/chat`, `/api/conversations`, … | NVIDIA NIM (bring-your-own key) |

**Provider model:** the **xAI key is set by the admin** (powers image / vision / voice / friends, and is the
Social-Media fallback). **NVIDIA is bring-your-own-key** (AgentStudio + Social Media `gpt-oss-120b`).

---

## Repository layout

```
backend/                 FastAPI app (the API + static serving)
  main.py                app entry: DB init + lightweight migrations, seeds admin, mounts routers,
                         serves site/ at "/" and the AgentStudio build at "/agentstudio"
  api/
    site.py              ★ the onaiagents site API (prefix /api/site): accounts, credits, admin
                         settings, all tool endpoints, Google OAuth, AgentStudio session billing
    chat.py              AgentStudio agent chat (hosted mode = login + per-session billing + isolation)
    conversations.py     AgentStudio chat history, scoped per site-user via the session cookie
    settings.py, files.py, permissions.py, search.py, skills.py   AgentStudio support routers
  database/
    site_models.py       SiteUser, CreditTxn, Order, Friend, AgentStudioSession, SiteSetting,
                         DEFAULT_SETTINGS (every admin-tunable key + its default)
    models.py            AgentStudio models: Setting, Conversation (has user_id), Message
  services/
    site_auth.py         stdlib pbkdf2 password hashing + HMAC-signed `oa_session` cookie
    studio_billing.py    AgentStudio per-session billing (ensure_session) + admin usage rollup
  config/, requirements.txt

site/                    the onaiagents.com static site (HTML/CSS/JS, no build step)
  index.html             home (dark, Three.js hero)
  playground / upscaler / deconstruct / ai-friends / linkedin .html   the six tool pages
  login / account / admin / pricing / terms / privacy / refund / contact .html
  styles.css             shared design system for the login/account/admin/legal pages
  nav.js                 turns the nav "Sign in" into Account + a credits pill + Admin link
  favicon.svg, spark-white.svg, assets/   brand marks + sample images

frontend/                AgentStudio React + Vite source (built to frontend/dist in Docker)
docker-compose.yml, Dockerfile, wp-stack.yml   hosting
install.* / run.* / START.*    one-command local install/run for the desktop agent
docs/                    screenshots + skill docs
```

---

## Back-end conventions

- **Auth & credits.** Email/password or Google sign-in → an HttpOnly, HMAC-signed `oa_session`
  cookie (`services/site_auth.py`). Each account has a `credits` balance; tools deduct credits
  (`_grant(db, user, -cost, reason)` writes a `CreditTxn` ledger row). **Admins are unlimited**
  (every credit-gated endpoint sets `cost = 0` when `user.is_admin`).
- **Settings.** Everything tunable lives in `DEFAULT_SETTINGS` (`database/site_models.py`) and is
  editable at **`/admin`**. Read with `_settings(db)` (DB overrides the defaults). Costs are the
  `cost_*` keys; provider keys are `img_*` (xAI) and `nvidia_*`; payments are `razorpay_*`/`stripe_*`;
  Google is `google_*`; AI-Friend persona rules are `friend_*_rules` (appended live to every chat).
- **Reply parsing.** AI-Friend replies come back as the theme's JSON contract; `_parse_friend_reply`
  returns a clean `{reply, tts}` and `_clean_tts` strips markup so the voice never reads tags aloud.
- **Adding a tool:** add a page in `site/`, an endpoint in `api/site.py`, a `cost_*` default in
  `DEFAULT_SETTINGS`, and an admin field in `site/admin.html` (`data-k="cost_*"`).

## AgentStudio hosting

`backend/api/chat.py` and `conversations.py` switch on the env var **`AGENT_STUDIO_HOSTED`**:
- unset → the original **single-user, no-login, free** desktop agent;
- set (`=1`, as on the VPS) → **login required, billed once per session** (`cost_agentstudio_session`,
  12-hour idle window), **per-user isolated** workspace + conversation history, and every session is
  tracked in the `/admin` dashboard (`services/studio_billing.py`).

## Theme

Dark by default: deep blue-black base `--bg:#070A14`, white text, white CTA buttons, a white asterisk
logo (`spark-white.svg`), credits shown as a gradient pill, and a Three.js particle hero on the home.
Design tokens live in each page's inline `:root` (the tool pages) or in `site/styles.css`.

---

## Run it

**Hosted (Docker, what onaiagents.com runs):**
```bash
docker compose up -d --build        # builds the React app + serves FastAPI behind Caddy
# env on the app service: ADMIN_PASSWORD, AGENT_STUDIO_SECRET, AGENT_STUDIO_HOSTED=1
```
The container builds `frontend/` to `frontend/dist`, then `backend/main.py` serves `site/` at `/`
and the agent app at `/agentstudio`. A fresh install boots keyless and prompts for keys in `/admin`.

**Desktop AgentStudio (no accounts, bring your own NVIDIA NIM key):** see `README.md` and run
`./install.sh` (macOS/Linux) or `install.ps1` (Windows), then `./run.command` / `run.bat`.

**Local dev:**
```bash
cd frontend && npm install && npm run dev     # AgentStudio UI on :5173
cd backend  && pip install -r requirements.txt && python main.py   # API on :8000
```
