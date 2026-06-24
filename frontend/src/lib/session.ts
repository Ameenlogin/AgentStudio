// Hosted Agent Studio is login-gated. This talks to the marketing-site API
// (/api/site) to learn whether a sign-in is required and who the visitor is.
import { api } from './api';

export interface SiteUser {
  id: number;
  email: string;
  name: string;
  credits: number;
  is_admin: boolean;
}

export interface SiteConfig {
  logged_in: boolean;
  user?: SiteUser | null;
  studio_requires_login?: boolean;
  costs?: Record<string, number>;
}

export async function getConfig(): Promise<SiteConfig> {
  const r = await fetch(api('/api/site/config'), { credentials: 'include' });
  if (!r.ok) throw new Error('config ' + r.status);
  return r.json();
}

// Send the visitor to the site sign-in, returning to Agent Studio afterwards.
export function loginUrl(): string {
  const path = (typeof location !== 'undefined' && location.pathname) || '/agentstudio';
  const next = path.startsWith('/agentstudio') ? path : '/agentstudio';
  return '/login?next=' + encodeURIComponent(next);
}
