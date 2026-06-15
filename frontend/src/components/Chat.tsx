import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowUp, Square, AlertTriangle, Settings as Cog, User, Wand2, FileSearch,
  Globe2, Rocket, Paperclip, X as XIcon, ChevronDown, Cpu, Database,
  Lock, Monitor, Briefcase, Puzzle, Loader2
} from 'lucide-react';
import { useStore } from '../store/useStore';
import type { Message, Block, ToolBlock } from '../store/useStore';
import { api } from '../lib/api';
import Blocks from './Blocks';
import AgentOrb from './AgentOrb';
import PermissionDialog from './PermissionDialog';
import AccessDialog from './AccessDialog';

const SUGGESTIONS = [
  { icon: Wand2,      text: 'Build a small website in the workspace and run it' },
  { icon: FileSearch, text: 'List the files in my workspace and summarize the project' },
  { icon: Globe2,     text: 'Research the latest React 19 features and write notes.md' },
  { icon: Rocket,     text: 'Build a REST API, run it, and test the endpoints' },
];

const MODES = [
  { id: 'sandbox',   label: 'Sandbox',   icon: Lock,      desc: 'Isolated workspace folder · asks before risky actions' },
  { id: 'desktop',   label: 'Desktop',   icon: Monitor,   desc: 'Full access to your Desktop · auto-approves actions' },
  { id: 'workspace', label: 'Workspace', icon: Briefcase, desc: 'Full access to your home folder · auto-approves actions' },
];

const MODELS = [
  { id: 'openai/gpt-oss-120b',                        short: 'GPT-OSS 120B',  caps: ['fastest','coding','tools'] },
  { id: 'moonshotai/kimi-k2.6',                       short: 'Kimi K2.6',     caps: ['agentic','tools','multimodal'] },
  { id: 'openai/gpt-oss-20b',                         short: 'GPT-OSS 20B',   caps: ['fast','coding','tools'] },
  { id: 'meta/llama-3.3-70b-instruct',                short: 'Llama 3.3 70B', caps: ['tools','coding'] },
  { id: 'nvidia/llama-3.3-nemotron-super-49b-v1.5',   short: 'Nemotron 49B',  caps: ['reasoning','tools'] },
  { id: 'qwen/qwen3-next-80b-a3b-instruct',           short: 'Qwen3 Next 80B',caps: ['coding','reasoning'] },
];

// Streamlined live status: just "Thinking…" (or the running tool's label) — no
// inline icon, since the message's spark already spins while the agent works.
function LiveStatus({ blocks, pending }: { blocks: Block[]; pending: boolean }) {
  const last = blocks[blocks.length - 1];
  let label = 'Thinking';
  if (pending) {
    label = 'Awaiting your approval';
  } else if (last?.type === 'tool' && (last as ToolBlock).status === 'running') {
    label = (last as ToolBlock).label;
  }

  return (
    <div className="live-status flex items-center gap-1.5 mt-2 px-3 py-1.5 rounded-lg bg-[var(--color-panel)] border border-[var(--color-border-soft)] text-[13px] text-[var(--color-muted)] w-fit max-w-full">
      <span className="truncate">{label}</span>
      <span className="flex gap-0.5 ml-0.5">
        <span className="dot-a">·</span>
        <span className="dot-b">·</span>
        <span className="dot-c">·</span>
      </span>
    </div>
  );
}

export default function Chat() {
  const {
    messages, pushUser, startAssistant, appendText, appendThinking,
    startTool, appendToolStream, finishTool, setView, currentId, setCurrentId,
    pendingPermission, setPendingPermission,
    selectedModel, setSelectedModel, swarmStatus, setSwarmStatus,
    showSwarmPanel, toggleSwarmPanel,
    setSwarmPlan, updateSwarmWorker, resetSwarm,
    skills, composerInsert, setComposerInsert,
  } = useStore();

  const [input, setInput]         = useState('');
  const [busy, setBusy]           = useState(false);
  const [hasKey, setHasKey]       = useState(true);
  const [showAccess, setShowAccess] = useState(false);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [mode, setMode]           = useState('sandbox');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const [cacheHit, setCacheHit]   = useState<number | null>(null);
  const [uploads, setUploads]     = useState<{ name: string; path: string }[]>([]);
  const [uploading, setUploading] = useState(0);   // count of files currently uploading
  const endRef  = useRef<HTMLDivElement>(null);
  const taRef   = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadSettings = () =>
    fetch(api('/api/settings/')).then(r => r.json()).then(d => {
      setHasKey(!!d.api_key);
      setShowAccess(!d.desktop_granted);
      if (d.mode) setMode(d.mode);
    }).catch(() => {});

  const changeMode = async (m: string) => {
    setMode(m);
    setShowModeMenu(false);
    try {
      await fetch(api('/api/settings/mode'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: m }),
      });
    } catch {}
  };

  useEffect(() => { loadSettings(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);

  // Sidebar → composer: when a skill is clicked, drop "/<name> " into the box.
  useEffect(() => {
    if (composerInsert != null) {
      setInput((prev) => (prev ? prev + composerInsert : composerInsert));
      setComposerInsert(null);
      requestAnimationFrame(() => taRef.current?.focus());
    }
  }, [composerInsert, setComposerInsert]);
  useEffect(() => {
    if (taRef.current) {
      taRef.current.style.height = 'auto';
      taRef.current.style.height = Math.min(taRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const persist = (msgs: Message[]) => {
    const firstUser = msgs.find(m => m.role === 'user');
    const title = firstUser ? (firstUser.blocks[0] as any).text.slice(0, 60) : 'New chat';
    const payload = {
      id: currentId,
      title,
      messages: msgs.map(m => ({
        role: m.role,
        content: m.blocks.filter((b: any) => b.type === 'text').map((b: any) => b.text).join('\n'),
        blocks: JSON.stringify(m.blocks),
      })),
    };
    fetch(api('/api/conversations/'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    }).then(r => r.json()).then(d => { if (d.id) setCurrentId(d.id); }).catch(() => {});
  };

  // Upload any number of files, a few at a time (bounded concurrency) so 50+
  // files don't open 50 sockets at once or freeze the UI. Each result is added
  // as it lands; failures are skipped quietly.
  const onPickFiles = async (files: FileList | null) => {
    const list = files ? Array.from(files) : [];
    if (!list.length) return;
    setUploading((n) => n + list.length);

    const uploadOne = async (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      try {
        const r = await fetch(api('/api/files/upload'), { method: 'POST', body: fd });
        const d = await r.json();
        if (d.path) setUploads((u) => [...u, { name: file.name, path: d.path }]);
      } catch { /* skip this file */ }
      finally { setUploading((n) => Math.max(0, n - 1)); }
    };

    const CONCURRENCY = 5;
    for (let i = 0; i < list.length; i += CONCURRENCY) {
      await Promise.all(list.slice(i, i + CONCURRENCY).map(uploadOne));
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  const stop = () => { abortRef.current?.abort(); setBusy(false); setPendingPermission(null); };

  // Map a leading "/token" to an installed skill (mirrors the backend resolver:
  // exact → prefix → substring, on folder name or display name).
  const resolveSkill = (token: string): string | null => {
    const q = token.toLowerCase();
    const ss = useStore.getState().skills;
    const exact  = ss.find(s => s.name.toLowerCase() === q || (s.display || '').toLowerCase() === q);
    const prefix = ss.find(s => s.name.toLowerCase().startsWith(q) || (s.display || '').toLowerCase().startsWith(q));
    const sub    = ss.find(s => s.name.toLowerCase().includes(q) || (s.display || '').toLowerCase().includes(q));
    return (exact || prefix || sub)?.name ?? null;
  };

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    let full = text.trim();

    // A leading "/<skill> …" explicitly invokes that skill for this turn.
    let skill: string | null = null;
    const sm = full.match(/^\/([A-Za-z0-9_-]+)(?:\s+|$)/);
    if (sm) skill = resolveSkill(sm[1]);

    if (uploads.length) {
      full += `\n\n(Files uploaded to the workspace: ${uploads.map(u => u.path).join(', ')})`;
    }
    pushUser(full);
    setInput('');
    setUploads([]);
    setBusy(true);
    setCacheHit(null);
    resetSwarm();

    const history = [...messages, { role: 'user', blocks: [{ type: 'text', text: full }] }]
      .map((m: any) => ({
        role: m.role,
        content: m.blocks.filter((b: any) => b.type === 'text').map((b: any) => b.text).join('\n'),
      }))
      .filter(m => m.content);

    const aid  = startAssistant();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch(api('/api/chat/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, model_name: selectedModel, skill }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        appendText(aid, `**Can't reach the model.** ${err.detail || ''}`);
        if (res.status === 400) setHasKey(false);
        setBusy(false);
        return;
      }
      if (!res.body) throw new Error('No response stream');

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          let ev: any;
          try { ev = JSON.parse(line); } catch { continue; }
          switch (ev.type) {
            case 'reasoning':         if (!ev.agent) appendThinking(aid, ev.delta); break;
            case 'content':           appendText(aid, ev.delta); break;
            case 'permission_request': setPendingPermission(ev); break;
            case 'swarm_status':      setSwarmStatus(ev); break;
            case 'cache_hit':         setCacheHit(ev.similarity); break;
            case 'swarm_plan':
              setSwarmPlan({ plan: ev.plan, subtasks: ev.subtasks || [] });
              break;
            case 'swarm_agent':
              updateSwarmWorker({ id: ev.id, role: ev.role, title: ev.title, status: ev.status });
              break;
            case 'tool_start':
              setPendingPermission(null);
              startTool(aid, { id: ev.id, name: ev.name, label: ev.label, icon: ev.icon, kind: ev.kind, args: ev.args || {}, agent: ev.agent });
              break;
            case 'tool_stream':       appendToolStream(aid, ev.id, ev.delta); break;
            case 'tool_result':       finishTool(aid, ev.id, ev.ok, ev.result); break;
            case 'error':             appendText(aid, `\n\n**Error:** ${ev.error}`); break;
            // 'step', 'heartbeat', 'done' — silently consumed
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') appendText(aid, `\n\n**Connection error:** ${e.message}`);
    } finally {
      setBusy(false);
      setPendingPermission(null);
      setTimeout(() => persist(useStore.getState().messages), 50);
    }
  };

  const empty        = messages.length === 0;
  const lastId       = messages.length ? messages[messages.length - 1].id : '';
  const activeModel  = MODELS.find(m => m.id === selectedModel) || MODELS[0];
  const activeMode   = MODES.find(m => m.id === mode) || MODES[0];
  const ModeIcon     = activeMode.icon;

  // Slash-command autocomplete: while typing "/<token>" (before any space),
  // surface matching installed skills so they're discoverable right in chat.
  const slashQuery   = input.startsWith('/') && !input.slice(1).includes(' ')
    ? input.slice(1).toLowerCase() : null;
  const slashMatches = slashQuery !== null
    ? skills.filter(s => s.name.toLowerCase().includes(slashQuery) ||
                         (s.display || '').toLowerCase().includes(slashQuery))
    : [];
  const showSlash    = slashQuery !== null && slashMatches.length > 0;
  const pickSlash    = (name: string) => { setInput('/' + name + ' '); taRef.current?.focus(); };

  return (
    <div className="flex flex-col h-full flex-1">
      <PermissionDialog />
      {showAccess && hasKey && <AccessDialog onDone={() => { setShowAccess(false); loadSettings(); }} />}

      {/* Header — clean, no step counter */}
      <div className="h-14 px-5 flex items-center justify-between border-b border-[var(--color-border-soft)] flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <span className="font-display font-semibold text-[15px] tracking-tight">Workspace</span>
          {busy && (
            <span className="flex items-center gap-1.5 ml-1">
              <AgentOrb size={9} state="working" />
              <span className="text-[11px] text-[var(--color-copper)] font-mono">active</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {cacheHit !== null && (
            <span className="cache-badge" title="Answered instantly from semantic cache">
              <Database className="w-3 h-3" /> from memory · {Math.round(cacheHit * 100)}%
            </span>
          )}
          {swarmStatus && (
            <span className="text-[11px] text-[var(--color-muted)] font-mono bg-[var(--color-panel)] px-2 py-0.5 rounded-md border border-[var(--color-border-soft)]">
              {swarmStatus.total_rpm} / {swarmStatus.total_limit} RPM
            </span>
          )}
          <button
            onClick={toggleSwarmPanel}
            className={`h-7 px-2.5 rounded-lg border flex items-center gap-1.5 text-[11.5px] font-medium transition ${
              showSwarmPanel
                ? 'bg-[var(--color-copper-wash)] border-[var(--color-copper)] text-[var(--color-copper-lo)]'
                : 'bg-[var(--color-elevated)] border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Swarm</span>
          </button>
        </div>
      </div>

      {/* API key warning */}
      {!hasKey && (
        <div className="mx-5 mt-3 flex items-center gap-3 rounded-xl border border-[var(--color-copper)]/30 bg-[var(--color-copper)]/8 px-4 py-2.5">
          <AlertTriangle className="w-4 h-4 text-[var(--color-copper)] flex-shrink-0" />
          <span className="text-sm text-[var(--color-text)] flex-1">Add your NVIDIA API key to start the agent.</span>
          <button
            onClick={() => setView('settings')}
            className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-copper)] hover:underline"
          >
            <Cog className="w-3.5 h-3.5" /> Settings
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {empty ? (
          <div className="relative h-full flex flex-col items-center justify-center px-6">
            <div className="absolute inset-0 dot-grid pointer-events-none" />
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
              className="relative z-10 flex flex-col items-center text-center max-w-xl"
            >
              <div className="spark-hero mb-5">
                <AgentOrb size={52} state={busy ? 'working' : 'idle'} />
              </div>
              <h1 className="font-display text-[30px] font-semibold tracking-tight mb-2.5">Agent Studio</h1>
              <p className="text-[var(--color-muted)] text-[14px] max-w-md mb-8 leading-relaxed">
                An autonomous engineering agent that plans, writes code, runs tools, edits
                archives & PDFs, and ships — ask it anything.
              </p>
              <div className="grid sm:grid-cols-2 gap-2 w-full">
                {SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.06 * i, duration: 0.3 }}
                    onClick={() => send(s.text)}
                    className="flex items-start gap-3 text-left rounded-xl border border-[var(--color-border)] bg-[var(--color-panel)] px-4 py-3 hover:border-[var(--color-copper)] hover:bg-[var(--color-elevated)] transition group"
                  >
                    <s.icon className="w-3.5 h-3.5 text-[var(--color-copper)] mt-0.5 flex-shrink-0" />
                    <span className="text-[12.5px] text-[var(--color-muted)] group-hover:text-[var(--color-text)] leading-snug">{s.text}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-5 py-7 space-y-7">
            {messages.map(m => {
              const isLast   = m.id === lastId;
              const streaming = busy && isLast;
              return (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28, ease: [0.32, 0.72, 0, 1] }}
                >
                  {m.role === 'user' ? (
                    <div className="flex gap-3 justify-end">
                      <div className="rounded-2xl rounded-tr-sm bg-[var(--color-copper-wash)] border border-[#EEDDD3] px-4 py-2.5 text-[14px] max-w-[82%] whitespace-pre-wrap leading-relaxed">
                        {(m.blocks[0] as any).text}
                      </div>
                      <div className="w-7 h-7 rounded-lg grid place-items-center bg-[var(--color-elevated)] border border-[var(--color-border)] flex-shrink-0 mt-0.5">
                        <User className="w-3.5 h-3.5 text-[var(--color-muted)]" />
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-3 items-start">
                      <div className="w-7 grid place-items-center flex-shrink-0 mt-0.5">
                        <AgentOrb size={22} state={streaming ? 'working' : 'idle'} />
                      </div>
                      <div className="flex-1 min-w-0 pt-0.5">
                        <Blocks blocks={m.blocks} streaming={streaming} />
                        {streaming && m.blocks.length === 0 && (
                          <LiveStatus blocks={m.blocks} pending={!!pendingPermission} />
                        )}
                        {streaming && m.blocks.length > 0 && (
                          <AnimatePresence>
                            <LiveStatus blocks={m.blocks} pending={!!pendingPermission} />
                          </AnimatePresence>
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              );
            })}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="px-5 pb-4 pt-2 flex-shrink-0">
        <div className="max-w-3xl mx-auto relative">
          {/* Slash-command menu — installed skills, filtered as you type "/…" */}
          <AnimatePresence>
            {showSlash && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ duration: 0.14 }}
                className="absolute bottom-full left-0 mb-2 z-50 w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] p-1.5 shadow-lg max-h-72 overflow-y-auto"
              >
                <div className="text-[10px] font-semibold text-[var(--color-faint)] px-2.5 py-1.5 border-b border-[var(--color-border-soft)] mb-1 uppercase tracking-[0.1em]">
                  Skills · pick one to use it
                </div>
                {slashMatches.map((s) => (
                  <button
                    key={s.name}
                    onClick={() => pickSlash(s.name)}
                    className="w-full text-left rounded-lg px-2.5 py-2 flex items-start gap-2.5 hover:bg-[var(--color-panel)] transition"
                  >
                    <Puzzle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-[var(--color-copper)]" />
                    <div className="min-w-0">
                      <div className="text-[12.5px] font-semibold text-[var(--color-text)]">
                        {s.display || s.name} <span className="font-mono font-normal text-[var(--color-faint)]">/{s.name}</span>
                      </div>
                      {s.description && (
                        <div className="text-[11px] text-[var(--color-muted)] leading-snug truncate">{s.description}</div>
                      )}
                    </div>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {(uploads.length > 0 || uploading > 0) && (
            <div className="mb-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-panel)] px-2.5 py-2">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-medium text-[var(--color-muted)] flex items-center gap-1.5">
                  {uploading > 0 && <Loader2 className="w-3 h-3 animate-spin text-[var(--color-copper)]" />}
                  {uploading > 0
                    ? `Uploading ${uploading} file${uploading > 1 ? 's' : ''}…`
                    : `${uploads.length} file${uploads.length > 1 ? 's' : ''} attached`}
                </span>
                {uploads.length > 0 && (
                  <button onClick={() => setUploads([])} className="text-[11px] text-[var(--color-faint)] hover:text-[var(--color-red)] transition">
                    Clear all
                  </button>
                )}
              </div>
              {/* Bounded + scrollable so any number of files can't push the input box off-screen */}
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-0.5">
                {uploads.map((u, i) => (
                  <span key={i} className="flex items-center gap-1 text-[11px] rounded-lg border border-[var(--color-border)] bg-[var(--color-elevated)] pl-2 pr-1 py-1 max-w-[170px]">
                    <Paperclip className="w-3 h-3 text-[var(--color-copper)] flex-shrink-0" />
                    <span className="truncate">{u.name}</span>
                    <button
                      onClick={() => setUploads(us => us.filter((_, j) => j !== i))}
                      className="text-[var(--color-faint)] hover:text-[var(--color-red)] flex-shrink-0"
                    >
                      <XIcon className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-end gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-panel)] px-3 py-2 focus-within:border-[var(--color-copper)] focus-within:shadow-[var(--shadow-lift)] transition-all duration-200">
            <input ref={fileRef} type="file" multiple className="hidden" onChange={e => onPickFiles(e.target.files)} />
            <button
              onClick={() => fileRef.current?.click()}
              className="w-8 h-8 rounded-lg grid place-items-center text-[var(--color-muted)] hover:text-[var(--color-copper)] hover:bg-[var(--color-elevated)] transition flex-shrink-0"
              title="Upload files"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <textarea
              ref={taRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (showSlash) { pickSlash(slashMatches[0].name); return; }
                  send(input);
                }
              }}
              placeholder="Ask anything or describe a task…"
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none px-1 py-1.5 text-[14px] placeholder:text-[var(--color-faint)] min-h-[36px] leading-relaxed"
            />

            {/* Mode picker + Model picker + send */}
            <div className="relative flex items-center gap-1 flex-shrink-0">
              {/* Working mode */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => { setShowModeMenu(!showModeMenu); setShowModelMenu(false); }}
                  className="model-pill"
                  title={activeMode.desc}
                >
                  <ModeIcon className="w-3 h-3 text-[var(--color-copper)]" />
                  <span>{activeMode.label}</span>
                  <ChevronDown className="w-3 h-3 text-[var(--color-muted)]" />
                </button>
                <AnimatePresence>
                  {showModeMenu && (
                    <motion.div
                      initial={{ opacity: 0, y: 6, scale: 0.97 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4, scale: 0.97 }}
                      transition={{ duration: 0.16 }}
                      className="absolute bottom-11 right-0 z-50 w-72 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] p-1.5 shadow-lg"
                    >
                      <div className="text-[10px] font-semibold text-[var(--color-faint)] px-2.5 py-1.5 border-b border-[var(--color-border-soft)] mb-1 uppercase tracking-[0.1em]">
                        Working mode
                      </div>
                      {MODES.map(m => {
                        const Icon = m.icon;
                        return (
                          <button
                            key={m.id}
                            onClick={() => changeMode(m.id)}
                            className={`w-full text-left rounded-lg px-2.5 py-2 flex items-start gap-2.5 transition ${
                              mode === m.id ? 'bg-[var(--color-copper-wash)]' : 'hover:bg-[var(--color-panel)]'
                            }`}
                          >
                            <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${mode === m.id ? 'text-[var(--color-copper-lo)]' : 'text-[var(--color-muted)]'}`} />
                            <div className="min-w-0">
                              <div className={`text-[12.5px] font-semibold ${mode === m.id ? 'text-[var(--color-copper-lo)]' : 'text-[var(--color-text)]'}`}>{m.label}</div>
                              <div className="text-[11px] text-[var(--color-muted)] leading-snug">{m.desc}</div>
                            </div>
                          </button>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <button
                type="button"
                onClick={() => { setShowModelMenu(!showModelMenu); setShowModeMenu(false); }}
                className="model-pill"
              >
                <span>{activeModel.short}</span>
                <ChevronDown className="w-3 h-3 text-[var(--color-muted)]" />
              </button>

              <AnimatePresence>
                {showModelMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 4, scale: 0.97 }}
                    transition={{ duration: 0.16 }}
                    className="absolute bottom-11 right-0 z-50 w-60 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] p-1.5 shadow-lg max-h-72 overflow-y-auto"
                  >
                    <div className="text-[10px] font-semibold text-[var(--color-faint)] px-2.5 py-1.5 border-b border-[var(--color-border-soft)] mb-1 uppercase tracking-[0.1em]">
                      Model
                    </div>
                    {MODELS.map(m => (
                      <button
                        key={m.id}
                        onClick={() => { setSelectedModel(m.id); setShowModelMenu(false); }}
                        className={`w-full text-left rounded-lg px-2.5 py-2 text-[12.5px] flex flex-col gap-0.5 transition ${
                          selectedModel === m.id
                            ? 'bg-[var(--color-copper-wash)] text-[var(--color-copper-lo)]'
                            : 'hover:bg-[var(--color-panel)] text-[var(--color-text)]'
                        }`}
                      >
                        <div className="font-semibold">{m.short}</div>
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {m.caps.map(c => (
                            <span key={c} className="cap-badge">{c}</span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              {busy ? (
                <button
                  onClick={stop}
                  className="w-8 h-8 rounded-xl grid place-items-center bg-[var(--color-elevated)] border border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-faint)] transition"
                  title="Stop"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                </button>
              ) : (
                <button
                  onClick={() => send(input)}
                  disabled={!input.trim() || uploading > 0}
                  className="w-8 h-8 rounded-xl grid place-items-center bg-gradient-to-br from-[var(--color-copper)] to-[var(--color-copper-lo)] text-white disabled:opacity-25 disabled:cursor-not-allowed hover:shadow-[var(--shadow-lift)] active:scale-95 transition-all"
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          <p className="text-center text-[10.5px] text-[var(--color-faint)] mt-1.5">
            <ModeIcon className="w-2.5 h-2.5 inline-block mr-1 -mt-0.5 text-[var(--color-copper)]" />
            {activeMode.label} mode · {activeMode.desc}
          </p>
        </div>
      </div>
    </div>
  );
}
