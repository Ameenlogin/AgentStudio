// In production the app is served by the backend on the same origin, so
// relative URLs just work. In `npm run dev` (port 5173) we hit the backend
// on 8000 directly.
export const API =
  import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

export const api = (path: string) => `${API}${path}`;

// ── Bring-your-own-key (browser-local credentials) ───────────────────────────
// On the hosted site there's no login and no shared server key. Each visitor
// stores their own NVIDIA NIM key in *their own browser* (localStorage) and it
// rides along with every chat request — so two people on the same deployment
// never share a key or overwrite each other's. Nothing secret is persisted on
// the server.
export type Creds = {
  api_key?: string;
  api_key_2?: string;
  api_key_3?: string;
  base_url?: string;
  model_name?: string;
};

const CREDS_KEY = 'agentstudio.creds';

export function getCreds(): Creds {
  try {
    return JSON.parse(localStorage.getItem(CREDS_KEY) || '{}') as Creds;
  } catch {
    return {};
  }
}

export function setCreds(c: Creds): void {
  try {
    localStorage.setItem(CREDS_KEY, JSON.stringify(c));
  } catch {
    /* storage unavailable (private mode) — keys just won't persist */
  }
}

export function hasLocalKey(): boolean {
  return !!(getCreds().api_key || '').trim();
}

// Non-empty keys, in priority order, for the chat request body.
export function credKeys(): string[] {
  const c = getCreds();
  return [c.api_key, c.api_key_2, c.api_key_3].filter(
    (k): k is string => typeof k === 'string' && k.trim().length > 0,
  );
}
