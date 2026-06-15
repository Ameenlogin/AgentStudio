import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Settings as Cog, MessageSquare, Trash2, Cpu, PanelLeftClose, PanelLeft, Puzzle } from 'lucide-react';
import { useStore } from '../store/useStore';
import type { Message } from '../store/useStore';
import { api } from '../lib/api';
import AgentOrb from './AgentOrb';
import SkillsModal from './SkillsModal';

export default function Sidebar() {
  const {
    view, setView, newChat, conversations, setConversations,
    currentId, setCurrentId, loadMessages, swarmStatus, selectedModel,
    skills, setSkills,
  } = useStore();
  const [collapsed, setCollapsed] = useState(false);
  const [showSkills, setShowSkills] = useState(false);

  const refresh = () => {
    fetch(api('/api/conversations/')).then((r) => r.json()).then(setConversations).catch(() => {});
  };
  const refreshSkills = () => {
    fetch(api('/api/skills/')).then((r) => r.json()).then((d) => setSkills(d.skills || [])).catch(() => {});
  };
  useEffect(() => {
    refresh();
    refreshSkills();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  const open = async (id: number) => {
    const d = await fetch(api(`/api/conversations/${id}`)).then((r) => r.json());
    const msgs: Message[] = (d.messages || []).map((m: any, i: number) => ({
      id: `${m.role}${i}`,
      role: m.role,
      blocks: m.blocks ? JSON.parse(m.blocks) : [{ type: 'text', text: m.content || '' }],
    }));
    setCurrentId(id);
    loadMessages(msgs);
  };

  const del = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    await fetch(api(`/api/conversations/${id}`), { method: 'DELETE' });
    if (currentId === id) newChat();
    refresh();
  };

  const modelShort = (selectedModel || '').split('/').pop() || 'GPT-OSS 120B';

  if (collapsed) {
    return (
      <div className="w-14 border-r border-[var(--color-border)] bg-[var(--color-panel)] flex flex-col items-center py-4 gap-3">
        <button onClick={() => setCollapsed(false)} className="p-2 rounded-lg text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-elevated)] transition">
          <PanelLeft className="w-5 h-5" />
        </button>
        <button onClick={newChat} className="p-2 rounded-lg text-[var(--color-copper)] hover:bg-[var(--color-elevated)] transition" title="New chat">
          <Plus className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <aside className="w-64 border-r border-[var(--color-border)] bg-[var(--color-panel)] flex flex-col flex-shrink-0">
      <div className="px-4 h-16 flex items-center justify-between border-b border-[var(--color-border-soft)]">
        <div className="flex items-center gap-2.5">
          <div className="sidebar-mark">
            <AgentOrb size={26} state="idle" />
          </div>
          <div className="leading-none">
            <div className="font-display font-semibold text-[15px]">Agent Studio</div>
          </div>
        </div>
        <button onClick={() => setCollapsed(true)} className="p-1.5 rounded-md text-[var(--color-faint)] hover:text-[var(--color-text)] hover:bg-[var(--color-elevated)] transition">
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3">
        <button
          onClick={newChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium border border-[var(--color-border)] bg-[var(--color-elevated)] hover:border-[var(--color-copper)] hover:shadow-[var(--shadow-card)] transition-all"
        >
          <Plus className="w-4 h-4 text-[var(--color-copper)]" /> New session
        </button>
      </div>

      <div className="px-3 pb-1">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--color-faint)] px-1 mb-1">History</div>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 space-y-0.5">
        <AnimatePresence initial={false}>
          {conversations.length === 0 && (
            <div className="text-xs text-[var(--color-faint)] px-3 py-4">No sessions yet.</div>
          )}
          {conversations.map((c) => (
            <motion.button
              key={c.id}
              layout
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, height: 0 }}
              onClick={() => open(c.id)}
              className={`group w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-[13px] transition ${
                currentId === c.id && view === 'chat'
                  ? 'bg-[var(--color-elevated)] text-[var(--color-text)] shadow-[var(--shadow-card)]'
                  : 'text-[var(--color-muted)] hover:bg-[var(--color-elevated)]/60 hover:text-[var(--color-text)]'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-[var(--color-faint)]" />
              <span className="truncate flex-1">{c.title}</span>
              <span onClick={(e) => del(e, c.id)} className="opacity-0 group-hover:opacity-100 text-[var(--color-faint)] hover:text-[var(--color-red)] transition">
                <Trash2 className="w-3.5 h-3.5" />
              </span>
            </motion.button>
          ))}
        </AnimatePresence>
      </nav>

      <div className="p-3 border-t border-[var(--color-border-soft)] space-y-2">
        {swarmStatus && swarmStatus.total_rpm > 0 && (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-[var(--color-copper-wash)] border border-[var(--color-copper)]/15 rounded-lg text-[10px] text-[var(--color-copper-lo)] font-mono font-semibold">
            <span className="live-status-dot w-1.5 h-1.5" />
            <span>Swarm Active: {swarmStatus.total_rpm} RPM</span>
          </div>
        )}
        <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-[var(--color-elevated)] text-[11px] text-[var(--color-muted)] font-mono">
          <Cpu className="w-3.5 h-3.5 text-[var(--color-cyan)] flex-shrink-0" />
          <span className="truncate" title={selectedModel}>{modelShort}</span>
        </div>
        <button
          onClick={() => setShowSkills(true)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-[var(--color-muted)] hover:bg-[var(--color-elevated)]/60 hover:text-[var(--color-text)] transition"
        >
          <Puzzle className="w-4 h-4 text-[var(--color-copper)]" /> Skills
          {skills.length > 0 && (
            <span className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-[var(--color-copper-wash)] text-[var(--color-copper-lo)]">{skills.length}</span>
          )}
        </button>
        <button
          onClick={() => setView('settings')}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition ${
            view === 'settings' ? 'bg-[var(--color-elevated)] text-[var(--color-text)] shadow-[var(--shadow-card)]' : 'text-[var(--color-muted)] hover:bg-[var(--color-elevated)]/60 hover:text-[var(--color-text)]'
          }`}
        >
          <Cog className="w-4 h-4" /> Settings
        </button>
      </div>

      <SkillsModal open={showSkills} onClose={() => setShowSkills(false)} />
    </aside>
  );
}
