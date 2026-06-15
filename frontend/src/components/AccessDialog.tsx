import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { FolderLock, Monitor, ShieldCheck, Zap, Check } from 'lucide-react';
import { api } from '../lib/api';
import AgentOrb from './AgentOrb';

type Paths = Record<string, string>;

export default function AccessDialog({ onDone }: { onDone: () => void }) {
  const [paths, setPaths] = useState<Paths>({});
  const [scope, setScope] = useState<'workspace' | 'desktop' | 'documents' | 'home'>('workspace');
  const [mode, setMode] = useState<'ask' | 'auto'>('ask');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(api('/api/files/paths')).then((r) => r.json()).then(setPaths).catch(() => {});
  }, []);

  const chosenPath =
    scope === 'workspace' ? (paths.workspace || './workspace')
    : scope === 'desktop' ? paths.desktop
    : scope === 'documents' ? paths.documents
    : paths.home;

  const grant = () => {
    setSaving(true);
    fetch(api('/api/settings/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_path: chosenPath,
        permission_mode: mode,
        desktop_granted: true,
      }),
    }).finally(() => { setSaving(false); onDone(); });
  };

  const scopes = [
    { id: 'workspace', icon: FolderLock, title: 'Workspace folder only', desc: 'Safest — Agent Studio can only touch its own folder.' },
    { id: 'desktop', icon: Monitor, title: 'My Desktop', desc: 'Read & write files on your Desktop.' },
    { id: 'documents', icon: FolderLock, title: 'My Documents', desc: 'Read & write files in Documents.' },
    { id: 'home', icon: Monitor, title: 'My whole home folder', desc: 'Full access to your user folder.' },
  ] as const;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 backdrop">
      <motion.div
        initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        className="modal-card w-full max-w-lg rounded-2xl bg-[var(--color-elevated)] border border-[var(--color-border)] overflow-hidden"
      >
        <div className="flex items-center gap-3 px-6 pt-6 pb-2">
          <div className="w-11 h-11 rounded-xl grid place-items-center bg-[var(--color-copper-wash)] border border-[#EEDDD3]">
            <AgentOrb size={22} state="idle" />
          </div>
          <div>
            <h2 className="font-display text-xl leading-tight">Give Agent Studio access</h2>
            <p className="text-[13px] text-[var(--color-muted)]">Choose where the agent may read and write files.</p>
          </div>
        </div>

        <div className="px-6 py-3 space-y-2">
          {scopes.map((s) => {
            const active = scope === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setScope(s.id)}
                className={`w-full flex items-start gap-3 text-left rounded-xl border px-4 py-3 transition ${
                  active ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'
                }`}
              >
                <s.icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${active ? 'text-[var(--color-copper-lo)]' : 'text-[var(--color-faint)]'}`} />
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-medium">{s.title}</div>
                  <div className="text-[12px] text-[var(--color-muted)]">{s.desc}</div>
                </div>
                {active && <Check className="w-4 h-4 text-[var(--color-copper)] flex-shrink-0 mt-0.5" />}
              </button>
            );
          })}
          <p className="text-[11px] text-[var(--color-faint)] font-mono px-1 truncate" title={chosenPath}>
            → {chosenPath}
          </p>
        </div>

        <div className="px-6 pb-2">
          <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--color-faint)] mb-2">When Agent Studio acts</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setMode('ask')}
              className={`flex items-start gap-2 text-left rounded-xl border px-3 py-2.5 transition ${
                mode === 'ask' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'
              }`}
            >
              <ShieldCheck className="w-4 h-4 mt-0.5 text-[var(--color-copper-lo)]" />
              <div>
                <div className="text-[13px] font-medium">Ask first</div>
                <div className="text-[11px] text-[var(--color-muted)]">Approve each write or command.</div>
              </div>
            </button>
            <button
              onClick={() => setMode('auto')}
              className={`flex items-start gap-2 text-left rounded-xl border px-3 py-2.5 transition ${
                mode === 'auto' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'
              }`}
            >
              <Zap className="w-4 h-4 mt-0.5 text-[var(--color-copper-lo)]" />
              <div>
                <div className="text-[13px] font-medium">Allow all</div>
                <div className="text-[11px] text-[var(--color-muted)]">Run autonomously, no prompts.</div>
              </div>
            </button>
          </div>
        </div>

        <div className="p-6 pt-3">
          <button
            onClick={grant}
            disabled={saving}
            className="w-full py-3 rounded-xl text-sm font-medium bg-gradient-to-br from-[var(--color-copper)] to-[var(--color-copper-lo)] text-white hover:shadow-[var(--shadow-lift)] transition disabled:opacity-50"
          >
            {saving ? 'Granting…' : 'Allow & continue'}
          </button>
          <p className="text-center text-[11px] text-[var(--color-faint)] mt-2">
            You can change this anytime in Settings.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
