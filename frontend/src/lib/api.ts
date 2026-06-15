// In production the app is served by the backend on the same origin, so
// relative URLs just work. In `npm run dev` (port 5173) we hit the backend
// on 8000 directly.
export const API =
  import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

export const api = (path: string) => `${API}${path}`;
