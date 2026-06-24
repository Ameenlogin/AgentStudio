import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useStore } from './store/useStore';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import Settings from './components/Settings';
import SwarmPanel from './components/SwarmPanel';
import { getConfig, loginUrl } from './lib/session';

export default function App() {
  const view = useStore((s) => s.view);
  const setAccount = useStore((s) => s.setAccount);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    const sync = (refresh = false) =>
      getConfig()
        .then((c) => {
          if (!alive) return;
          // Hosted + signed out → bounce to the site sign-in (10 cr/session app).
          if (c.studio_requires_login && !c.logged_in) {
            location.href = loginUrl();
            return; // keep the boot screen up until navigation happens
          }
          if (c.user) {
            setAccount({ email: c.user.email, credits: c.user.credits, is_admin: c.user.is_admin });
          }
          if (!refresh) setReady(true);
        })
        .catch(() => { if (alive && !refresh) setReady(true); }); // desktop / API down → don't block

    sync();
    // Keep the credit balance fresh when the user comes back to the tab.
    const onFocus = () => sync(true);
    window.addEventListener('focus', onFocus);
    return () => { alive = false; window.removeEventListener('focus', onFocus); };
  }, [setAccount]);

  if (!ready) {
    return (
      <div className="flex h-screen w-screen items-center justify-center studio-canvas">
        <Loader2 className="w-7 h-7 animate-spin text-[var(--color-muted)]" />
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen studio-canvas text-[var(--color-text)] overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-row min-w-0 relative">
        {view === 'chat' ? (
          <>
            <Chat />
            <SwarmPanel />
          </>
        ) : (
          <Settings />
        )}
      </main>
    </div>
  );
}
