import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, Check, CheckCheck, X, Terminal, FilePen, Globe, Archive } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../lib/api';

const KIND_ICON: Record<string, any> = {
  write: FilePen, shell: Terminal, web: Globe, system: ShieldCheck, archive: Archive,
};

const KIND_VERB: Record<string, string> = {
  write: 'modify files on your machine',
  shell: 'run a command on your machine',
  web: 'access the network',
  system: 'access your system',
};

export default function PermissionDialog() {
  const { pendingPermission: p, setPendingPermission } = useStore();

  const decide = (decision: 'allow' | 'allow_all' | 'deny') => {
    if (!p) return;
    fetch(api('/api/permissions/resolve'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: p.id, decision }),
    }).catch(() => {});
    setPendingPermission(null);
  };

  const Icon = p ? (KIND_ICON[p.kind] || ShieldCheck) : ShieldCheck;
  const detail = p
    ? Object.entries(p.args)
        .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join('\n')
    : '';

  return (
    <AnimatePresence>
      {p && (
        <motion.div
          className="fixed inset-0 z-50 grid place-items-center p-4 backdrop"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="modal-card w-full max-w-md rounded-2xl bg-[var(--color-elevated)] border border-[var(--color-border)] overflow-hidden">
            <div className="flex items-start gap-3 px-5 pt-5 pb-3">
              <div className="w-10 h-10 rounded-xl grid place-items-center bg-[var(--color-copper-wash)] border border-[#EEDDD3] flex-shrink-0">
                <Icon className="w-5 h-5 text-[var(--color-copper-lo)]" />
              </div>
              <div className="min-w-0">
                <h3 className="font-display text-lg leading-tight">Permission needed</h3>
                <p className="text-[13px] text-[var(--color-muted)] mt-0.5">
                  Agent Studio wants to <span className="font-medium text-[var(--color-text)]">{p.label.toLowerCase()}</span>
                  {' '}— this will {KIND_VERB[p.kind] || 'act on your machine'}.
                </p>
              </div>
            </div>

            <div className="px-5">
              <pre className="max-h-44 overflow-auto rounded-lg bg-[var(--color-panel)] border border-[var(--color-border-soft)] p-3 text-[12px] leading-relaxed font-mono text-[var(--color-text)] whitespace-pre-wrap">
                {detail || '(no arguments)'}
              </pre>
            </div>

            <div className="flex flex-col gap-2 p-5 pt-4">
              <button
                onClick={() => decide('allow')}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-br from-[var(--color-copper)] to-[var(--color-copper-lo)] text-white hover:shadow-[var(--shadow-lift)] transition"
              >
                <Check className="w-4 h-4" /> Allow once
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => decide('allow_all')}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-[13px] font-medium border border-[var(--color-border)] bg-[var(--color-elevated)] hover:border-[var(--color-copper)] transition"
                >
                  <CheckCheck className="w-4 h-4 text-[var(--color-copper)]" /> Allow all this run
                </button>
                <button
                  onClick={() => decide('deny')}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-[13px] font-medium border border-[var(--color-border)] text-[var(--color-muted)] hover:border-[var(--color-red)] hover:text-[var(--color-red)] transition"
                >
                  <X className="w-4 h-4" /> Deny
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
