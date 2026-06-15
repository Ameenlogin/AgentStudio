import { useState, useEffect, useRef, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import {
  ChevronRight, Check, Copy, Download,
  FileText, FilePlus, FilePen, Folder, FolderPlus, Search, Terminal, Globe, Link as LinkIcon, Wrench,
  Trash2, Archive, FolderTree, Files, FileDiff, GitBranch, ListChecks, Monitor, FileCode2
} from 'lucide-react';
import type { Block, ToolBlock, ThinkBlock } from '../store/useStore';
import { api } from '../lib/api';

const ICONS: Record<string, any> = {
  'file-text': FileText, 'file-plus': FilePlus, 'file-pen': FilePen,
  folder: Folder, 'folder-plus': FolderPlus, search: Search,
  terminal: Terminal, globe: Globe, link: LinkIcon, wrench: Wrench,
  trash: Trash2, copy: Copy, download: Download, archive: Archive,
  'folder-tree': FolderTree, 'files': Files, 'diff': FileDiff, 'git-branch': GitBranch,
  'list-checks': ListChecks,
};

function downloadablePath(b: ToolBlock): string | null {
  const a = b.args as any;
  if (['write_file', 'append_file', 'edit_file', 'batch_write_files', 'pdf_create'].includes(b.name)) return a.path || null;
  if (b.name === 'create_zip') return a.output || null;
  if (['move_path', 'copy_path'].includes(b.name)) return a.dest || null;
  if (b.name === 'download_file') return a.dest || null;
  if (['zip_write', 'zip_edit', 'zip_remove'].includes(b.name)) return a.path || null;
  return null;
}

function langFromPath(path: string): string {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'tsx', jsx: 'jsx',
    html: 'html', css: 'css', scss: 'scss', json: 'json', md: 'markdown',
    sh: 'bash', yml: 'yaml', yaml: 'yaml', sql: 'sql', go: 'go', rs: 'rust',
    java: 'java', c: 'c', cpp: 'cpp', rb: 'ruby', php: 'php',
  };
  return map[ext] || '';
}

// Cap a long preview so a big file doesn't blow up the window.
function clip(code: string, max = 48): string {
  const lines = code.split('\n');
  return lines.length > max ? lines.slice(0, max).join('\n') + `\n… (+${lines.length - max} more lines)` : code;
}

// ── Code Block ──────────────────────────────────────────────────────────────
function CodeBlock({ children, lang }: { children: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || 'code'}</span>
        <button onClick={copy} className="code-block-copy">
          {copied
            ? <><Check className="w-3 h-3" style={{ color: '#7FB069' }} /> Copied</>
            : <><Copy className="w-3 h-3" /> Copy</>}
        </button>
      </div>
      <pre><code>{children}</code></pre>
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        components={{
          code({ node, className, children, ...props }: any) {
            const text = String(children).replace(/\n$/, '');
            const pos = node?.position;
            const oneLine = pos && pos.start.line === pos.end.line;
            if (oneLine) return <code {...props}>{children}</code>;
            const lang = (className || '').replace('language-', '');
            return <CodeBlock lang={lang}>{text}</CodeBlock>;
          },
          pre: ({ children }: any) => <>{children}</>,
          a: ({ ...props }: any) => <a target="_blank" rel="noreferrer" {...props} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

// ── Thinking — flat reasoning lineup (Claude / Perplexity / Kimi style) ──────
function Thinking({ block, live }: { block: ThinkBlock; live: boolean }) {
  const [open, setOpen] = useState(true);
  const [userToggled, setUserToggled] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const bodyRef = useRef<HTMLDivElement>(null);
  const startRef = useRef(Date.now());
  const finalRef = useRef(0);

  useEffect(() => {
    if (!live) return;
    startRef.current = Date.now();
    const t = setInterval(() => {
      const s = Math.floor((Date.now() - startRef.current) / 1000);
      setElapsed(s);
      finalRef.current = s;
    }, 500);
    return () => clearInterval(t);
  }, [live]);

  useEffect(() => {
    if (live && open && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [block.text, live, open]);

  useEffect(() => {
    if (!live && !userToggled) setOpen(false);
  }, [live, userToggled]);

  const lines = block.text.split('\n');
  const dur = finalRef.current || elapsed;
  const summary = live
    ? `Thinking${dur > 0 ? ` · ${dur}s` : ''}`
    : dur > 0 ? `Thought for ${dur}s` : 'Thought process';

  return (
    <div className="step">
      <span className={`step-node ${live ? 'node-think-live' : 'node-think'}`}>
        <span className="think-pip" />
      </span>
      <div className="step-body">
        <button className="step-head" onClick={() => { setOpen(v => !v); setUserToggled(true); }}>
          <span className={live ? 'think-label-live' : 'think-label-done'}>{summary}</span>
          <ChevronRight className={`w-3.5 h-3.5 text-[var(--color-faint)] chevron-r ${open ? 'open' : ''}`} />
        </button>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
              className="overflow-hidden"
            >
              <div ref={bodyRef} className="think-stream" style={{ maxHeight: live ? '210px' : '340px', overflowY: 'auto' }}>
                {lines.map((line, i) =>
                  line === ''
                    ? <span key={i} className="think-line-empty" />
                    : <span key={i} className="think-line">{line}</span>
                )}
                {live && <span className="stream-dot" />}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Agent Computer — a macOS-style desktop the agent works inside ────────────
// Every file / code / shell / web action the agent takes is shown live inside a
// four-corner "computer" with Terminal, Files, Editor and Browser apps. It is
// driven entirely by the tool event stream, so it works for any model with no
// special tool. No skeletons — the active window always streams real output.
type AppId = 'terminal' | 'files' | 'editor' | 'browser';

const APP_META: Record<AppId, { name: string; icon: any; accent: string }> = {
  terminal: { name: 'Terminal', icon: Terminal,  accent: 'var(--color-violet)' },
  files:    { name: 'Files',    icon: FolderTree, accent: 'var(--color-cyan)' },
  editor:   { name: 'Editor',   icon: FileCode2,  accent: 'var(--color-copper)' },
  browser:  { name: 'Browser',  icon: Globe,      accent: 'var(--color-green)' },
};
const APP_ORDER: AppId[] = ['terminal', 'files', 'editor', 'browser'];

const TERMINAL_TOOLS = ['run_command', 'python_exec', 'install_package', 'start_process', 'read_process', 'stop_process', 'list_processes'];
const EDITOR_TOOLS = ['write_file', 'append_file', 'edit_file', 'patch_file', 'apply_patch', 'batch_write_files', 'zip_write', 'zip_edit', 'zip_remove', 'pdf_create', 'create_zip'];

function appOf(t: ToolBlock): AppId {
  if (TERMINAL_TOOLS.includes(t.name)) return 'terminal';
  if (EDITOR_TOOLS.includes(t.name)) return 'editor';
  if (t.kind === 'web') return 'browser';
  return 'files';
}

function TerminalApp({ tools, live }: { tools: ToolBlock[]; live: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [tools, live]);
  return (
    <div ref={ref} className="ac-terminal">
      {tools.map((t) => {
        const a = t.args as any;
        const running = t.status === 'running';
        const cmd =
          a.command ||
          (t.name === 'python_exec' ? 'python ‹snippet›' :
           t.name === 'install_package' ? `pip install ${a.package || ''}` :
           t.label);
        const body = running ? (t.stream || '') : (t.result || t.stream || '');
        return (
          <div key={t.id} className="ac-term-entry">
            <div className="ac-term-cmd">
              <span className="ac-term-arrow">➜</span> <span className="ac-term-dir">workspace</span> {cmd}
            </div>
            {(body || running) && (
              <pre className="ac-term-out">{body}{running && live && <span className="cursor" />}</pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EditorApp({ tools }: { tools: ToolBlock[] }) {
  const files = tools.map((t) => {
    const a = t.args as any;
    let code = '';
    let lang = '';
    if (typeof a.content === 'string') code = a.content;
    else if (typeof a.replace === 'string') code = a.replace;
    else if (typeof a.diff === 'string') { code = a.diff; lang = 'diff'; }
    else if (Array.isArray(a.patches)) code = a.patches.map((p: any) => `- ${p.find}\n+ ${p.replace}`).join('\n\n');
    else if (Array.isArray(a.files)) code = a.files.map((f: any) => `/* ${f.path} */\n${f.content}`).join('\n\n');
    const path = a.path || a.inner || a.output || (Array.isArray(a.files) && a.files[0]?.path) || t.label;
    if (!lang) lang = langFromPath(String(path));
    return { id: t.id, path: String(path), code, lang, block: t };
  });
  const [active, setActive] = useState(files.length - 1);
  useEffect(() => { setActive(files.length - 1); }, [files.length]);
  const idx = Math.min(Math.max(active, 0), files.length - 1);
  const cur = files[idx];
  const dl = cur ? downloadablePath(cur.block) : null;
  return (
    <div className="ac-editor">
      <div className="ac-tabs">
        {files.map((f, i) => (
          <button key={f.id} className={`ac-tab ${i === idx ? 'on' : ''}`} onClick={() => setActive(i)} title={f.path}>
            <FileCode2 className="w-3 h-3" />
            <span className="ac-tab-name">{f.path.split('/').pop()}</span>
          </button>
        ))}
      </div>
      {cur && (
        <div className="ac-editor-body">
          <div className="ac-editor-path">
            <span>{cur.path}</span>
            {dl && (
              <a className="ac-dl" href={api(`/api/files/download?path=${encodeURIComponent(dl)}`)} download>
                <Download className="w-3 h-3" /> Download
              </a>
            )}
          </div>
          {cur.code
            ? <CodeBlock lang={cur.lang}>{clip(cur.code, 600)}</CodeBlock>
            : <div className="ac-empty">{cur.block.result || 'Saved.'}</div>}
        </div>
      )}
    </div>
  );
}

function FilesApp({ tools }: { tools: ToolBlock[] }) {
  const [sel, setSel] = useState(tools.length - 1);
  useEffect(() => { setSel(tools.length - 1); }, [tools.length]);
  const idx = Math.min(Math.max(sel, 0), tools.length - 1);
  const cur = tools[idx];
  const Icon = cur ? (ICONS[cur.icon] || Folder) : Folder;
  const a = (cur?.args || {}) as any;
  const target = a.path || a.pattern || a.query || a.src || cur?.label || '';
  const body = cur ? (cur.result || (cur.status === 'running' ? 'Reading…' : '')) : '';
  return (
    <div className="ac-files">
      <div className="ac-file-list">
        {tools.map((t, i) => {
          const Ic = ICONS[t.icon] || FileText;
          const aa = t.args as any;
          const name = aa.path || aa.pattern || aa.query || aa.src || t.label;
          return (
            <button key={t.id} className={`ac-file-item ${i === idx ? 'on' : ''}`} onClick={() => setSel(i)}>
              <Ic className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="ac-file-name">{String(name).split('/').pop() || t.label}</span>
            </button>
          );
        })}
      </div>
      <div className="ac-file-view">
        <div className="ac-file-head"><Icon className="w-3.5 h-3.5" /> <span>{String(target)}</span></div>
        <pre className="ac-file-body">{body || '(empty)'}</pre>
      </div>
    </div>
  );
}

function BrowserApp({ tools }: { tools: ToolBlock[] }) {
  const [sel, setSel] = useState(tools.length - 1);
  useEffect(() => { setSel(tools.length - 1); }, [tools.length]);
  const idx = Math.min(Math.max(sel, 0), tools.length - 1);
  const cur = tools[idx];
  const a = (cur?.args || {}) as any;
  const url = a.url || (a.query ? `search · ${a.query}` : 'about:blank');
  const loading = cur?.status === 'running';
  const body = cur ? (cur.result || (loading ? 'Loading…' : '')) : '';
  return (
    <div className="ac-browser">
      <div className="ac-urlbar">
        <span className="ac-url-ctrls">
          <ChevronRight className="w-3 h-3 rotate-180" /><ChevronRight className="w-3 h-3" />
        </span>
        <span className={`ac-url ${loading ? 'loading' : ''}`}><Globe className="w-3 h-3" /> {String(url)}</span>
      </div>
      {tools.length > 1 && (
        <div className="ac-tabsrow">
          {tools.map((t, i) => {
            const u = (t.args as any).url || (t.args as any).query || t.label;
            return (
              <button key={t.id} className={`ac-btab ${i === idx ? 'on' : ''}`} onClick={() => setSel(i)} title={String(u)}>
                {String(u).replace(/^https?:\/\//, '').slice(0, 28)}
              </button>
            );
          })}
        </div>
      )}
      <pre className="ac-page">{body || '(no content)'}</pre>
    </div>
  );
}

function AgentComputer({ tools, live }: { tools: ToolBlock[]; live: boolean }) {
  const groups: Record<AppId, ToolBlock[]> = { terminal: [], files: [], editor: [], browser: [] };
  tools.forEach((t) => groups[appOf(t)].push(t));
  const lastApp = tools.length ? appOf(tools[tools.length - 1]) : 'files';

  const [active, setActive] = useState<AppId>(lastApp);
  const [picked, setPicked] = useState(false);
  const [closed, setClosed] = useState(false);
  useEffect(() => { if (!picked) setActive(lastApp); }, [lastApp, picked]);

  const shown: AppId = groups[active].length ? active : lastApp;
  const Meta = APP_META[shown];
  const runningCount = tools.filter((t) => t.status === 'running').length;
  const done = !live && runningCount === 0;
  const actions = `${tools.length} action${tools.length !== 1 ? 's' : ''}`;

  if (closed) {
    return (
      <button className="ac-reopen" onClick={() => setClosed(false)}>
        <Monitor className="w-3.5 h-3.5" /> Agent Computer · {actions}
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    );
  }

  return (
    <motion.div
      className="agent-computer"
      initial={{ opacity: 0, scale: 0.985, y: 4 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.32, 0.72, 0, 1] }}
    >
      <div className="ac-titlebar">
        <span className="ac-lights">
          <button className="tl-dot tl-red" title="Close" onClick={() => setClosed(true)} />
          <span className="tl-dot tl-amber" />
          <span className="tl-dot tl-green" />
        </span>
        <span className="ac-title"><Monitor className="w-3.5 h-3.5" /> Agent Computer</span>
        <span className="ac-meta">
          {done ? '✓ Finished' : <><span className="ac-live-dot" /> Working</>} · {actions}
        </span>
      </div>

      <div className="ac-menubar">
        <Meta.icon className="w-3 h-3" style={{ color: Meta.accent }} />
        <strong>{Meta.name}</strong>
        <span>File</span><span>Edit</span><span>View</span><span>Go</span>
      </div>

      <div className="ac-screen">
        <AnimatePresence mode="wait">
          <motion.div
            key={shown}
            className="ac-window"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
          >
            <div className="ac-window-head">
              <Meta.icon className="w-3.5 h-3.5" style={{ color: Meta.accent }} />
              <span>{Meta.name}</span>
              <span className="ac-window-count">{groups[shown].length}</span>
            </div>
            <div className="ac-window-body">
              {shown === 'terminal' && <TerminalApp tools={groups.terminal} live={live} />}
              {shown === 'files' && <FilesApp tools={groups.files} />}
              {shown === 'editor' && <EditorApp tools={groups.editor} />}
              {shown === 'browser' && <BrowserApp tools={groups.browser} />}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="ac-dock">
        {APP_ORDER.map((app) => {
          const M = APP_META[app];
          const count = groups[app].length;
          const liveApp = live && groups[app].some((t) => t.status === 'running');
          return (
            <button
              key={app}
              disabled={!count}
              className={`ac-dock-app ${app === shown ? 'on' : ''} ${liveApp ? 'bounce' : ''} ${!count ? 'off' : ''}`}
              onClick={() => { setActive(app); setPicked(true); }}
              title={M.name}
              style={{ '--ac-accent': M.accent } as React.CSSProperties}
            >
              <M.icon className="w-4 h-4" />
              {count > 0 && <span className="ac-dock-badge">{count}</span>}
              <span className="ac-dock-label">{M.name}</span>
            </button>
          );
        })}
      </div>

      <div className="ac-statusbar">
        {done ? `Finished — ${actions} completed.` : `Working in ${Meta.name}…`}
      </div>
    </motion.div>
  );
}

// ── Main export ──────────────────────────────────────────────────────────────
export default function Blocks({ blocks, streaming }: { blocks: Block[]; streaming: boolean }) {
  const items: ReactNode[] = [];
  let i = 0;
  while (i < blocks.length) {
    const b = blocks[i];
    if (b.type === 'tool') {
      const start = i;
      const group: ToolBlock[] = [];
      while (i < blocks.length && blocks[i].type === 'tool') {
        group.push(blocks[i] as ToolBlock);
        i++;
      }
      const live = streaming && i === blocks.length;
      items.push(<AgentComputer key={`ac-${start}`} tools={group} live={live} />);
      continue;
    }
    const isLast = i === blocks.length - 1;
    if (b.type === 'thinking') {
      items.push(<Thinking key={i} block={b} live={streaming && isLast} />);
    } else {
      items.push(
        <div key={i} className="answer">
          <Markdown text={b.text} />
          {streaming && isLast && <span className="caret" />}
        </div>
      );
    }
    i++;
  }
  return <div className="timeline">{items}</div>;
}
