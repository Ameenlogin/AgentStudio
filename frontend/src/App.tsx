import { useStore } from './store/useStore';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import Settings from './components/Settings';
import SwarmPanel from './components/SwarmPanel';

export default function App() {
  const view = useStore((s) => s.view);
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
