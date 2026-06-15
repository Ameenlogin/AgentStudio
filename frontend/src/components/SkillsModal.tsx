import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, X as XIcon, Plus, ArrowRight } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../lib/api';

/**
 * SkillsModal — opened by the sidebar "Skills" button. Lists every installed
 * skill; "Use this skill" opens a fresh conversation with "/<name> " queued in
 * the composer so the next message runs that skill.
 */
export default function SkillsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { skills, setSkills, newChat, setView, setComposerInsert } = useStore();

  const refresh = () =>
    fetch(api('/api/skills/')).then((r) => r.json()).then((d) => setSkills(d.skills || [])).catch(() => {});

  useEffect(() => { if (open) refresh(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const use = (name: string) => {
    newChat();
    setComposerInsert('/' + name + ' ');
    setView('chat');
    onClose();
  };

  const install = async () => {
    const url = window.prompt('Install a skill from a public GitHub repo URL:\n(e.g. https://github.com/owner/skill-repo)');
    if (!url) return;
    try {
      await fetch(api('/api/skills/install'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
      });
    } catch { /* ignore */ }
    refresh();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }}
            className="relative w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-panel)] shadow-[var(--shadow-lift)] overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border-soft)]">
              <div className="flex items-center gap-2.5">
                <span className="grid place-items-center w-8 h-8 rounded-lg bg-[var(--color-copper-wash)]">
                  <Sparkles className="w-4 h-4 text-[var(--color-copper)]" />
                </span>
                <div className="leading-tight">
                  <div className="font-display font-semibold text-[15px]">Skills</div>
                  <div className="text-[11.5px] text-[var(--color-muted)]">Reusable expertise packs — pick one to start a session with it</div>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={install}
                  className="flex items-center gap-1.5 text-[12px] font-medium rounded-lg border border-[var(--color-border)] bg-[var(--color-elevated)] px-2.5 py-1.5 text-[var(--color-muted)] hover:text-[var(--color-copper)] hover:border-[var(--color-copper)] transition"
                >
                  <Plus className="w-3.5 h-3.5" /> Install
                </button>
                <button onClick={onClose} className="p-1.5 rounded-lg text-[var(--color-faint)] hover:text-[var(--color-text)] hover:bg-[var(--color-elevated)] transition">
                  <XIcon className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="overflow-y-auto p-4 grid sm:grid-cols-2 gap-2.5">
              {skills.length === 0 && (
                <div className="col-span-full text-center text-sm text-[var(--color-muted)] py-12">
                  No skills installed yet.<br />
                  <span className="text-[12px] text-[var(--color-faint)]">Click <span className="text-[var(--color-copper)]">Install</span> to add one from a GitHub repo.</span>
                </div>
              )}
              {skills.map((s) => (
                <div
                  key={s.name}
                  className="group flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] p-3.5 hover:border-[var(--color-copper)] hover:shadow-[var(--shadow-card)] transition"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-[var(--color-copper)] flex-shrink-0" />
                    <span className="font-semibold text-[13.5px] truncate">{s.display || s.name}</span>
                    <span className="ml-auto font-mono text-[10.5px] text-[var(--color-faint)] flex-shrink-0">/{s.name}</span>
                  </div>
                  <p className="text-[12px] text-[var(--color-muted)] leading-snug flex-1 mb-3 line-clamp-3">
                    {s.description || 'No description provided.'}
                  </p>
                  <button
                    onClick={() => use(s.name)}
                    className="flex items-center justify-center gap-1.5 w-full rounded-lg bg-gradient-to-br from-[var(--color-copper)] to-[var(--color-copper-lo)] text-white text-[12.5px] font-semibold py-2 hover:shadow-[var(--shadow-lift)] active:scale-[0.98] transition-all"
                  >
                    Use this skill <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
