import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronRight, Check, Copy, Download,
  FileText, FilePlus, FilePen, Folder, FolderPlus, Search, Terminal, Globe, Link as LinkIcon, Wrench,
  Trash2, Archive, FolderTree, Files, FileDiff, GitBranch, ListChecks, Monitor, FileCode2,
  MousePointerClick, Keyboard, Camera, Eye, ScanText, AppWindow, Upload, Timer, Save, Power,
  RotateCw, ArrowLeft, ArrowRight, Move, Loader2
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
  // Browser actions
  'mouse-pointer': MousePointerClick, keyboard: Keyboard, camera: Camera, eye: Eye,
  scan: ScanText, 'app-window': AppWindow, upload: Upload, timer: Timer, save: Save,
  power: Power, refresh: RotateCw, 'arrow-left': ArrowLeft, 'arrow-right': ArrowRight, move: Move,
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
function CodeBlock({ children, lang, collapsible = true }: { children: string; lang?: string; collapsible?: boolean }) {
  const [copied, setCopied] = useState(false);
  const lineCount = children.split('\n').length;
  const COLLAPSE_AT = 14;
  const [expanded, setExpanded] = useState(!collapsible || lineCount <= COLLAPSE_AT);
  const copy = () => {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  // Long code is never dumped into the chat — show a short head and let the user
  // expand. (Inside the Agent Computer's Editor we pass collapsible=false.)
  const shown = expanded ? children : children.split('\n').slice(0, 12).join('\n');
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
      <pre><code>{shown}</code></pre>
      {!expanded && (
        <button className="code-block-more" onClick={() => setExpanded(true)}>
          Show {lineCount - 12} more lines
        </button>
      )}
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
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

// Real-Chrome control tools (kind "system") and the lightweight web tools both
// live in the Browser app.
const isBrowserTool = (t: ToolBlock) =>
  t.name.startsWith('browser_') || t.kind === 'system' || t.kind === 'web';

function appOf(t: ToolBlock): AppId {
  if (isBrowserTool(t)) return 'browser';
  if (TERMINAL_TOOLS.includes(t.name)) return 'terminal';
  if (EDITOR_TOOLS.includes(t.name)) return 'editor';
  return 'files';
}

// Pull a screenshot path out of a browser tool result ("IMAGE: <relpath>").
function shotPath(t: ToolBlock): string | null {
  const m = (t.result || '').match(/^IMAGE:\s*(.+?)\s*$/m);
  return m ? m[1] : null;
}
// The page URL a browser action touched (explicit arg, else parsed from result).
function browserUrl(t: ToolBlock): string {
  const a = t.args as any;
  if (a?.url) return String(a.url);
  const m = (t.result || '').match(/—\s*(https?:\/\/\S+)/);
  if (m) return m[1];
  if (a?.query) return `search · ${a.query}`;
  return '';
}
// Result text minus the status header line and the IMAGE: marker.
function browserText(t: ToolBlock): string {
  return (t.result || '')
    .replace(/^IMAGE:.*$/m, '')
    .replace(/^●.*$/m, '')
    .replace(/^\[\d+ tab\(s\) open\]$/m, '')
    .replace(/^--- (PAGE TEXT|ACCESSIBILITY TREE) ---$/m, '')
    .trim();
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
            ? <CodeBlock lang={cur.lang} collapsible={false}>{clip(cur.code, 600)}</CodeBlock>
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

function BrowserApp({ tools, live }: { tools: ToolBlock[]; live: boolean }) {
  const [sel, setSel] = useState(tools.length - 1);
  const filmRef = useRef<HTMLDivElement>(null);
  // Follow the latest action while the agent is working; let the user scrub when idle.
  useEffect(() => { setSel(tools.length - 1); }, [tools.length]);
  useEffect(() => {
    if (filmRef.current) filmRef.current.scrollLeft = filmRef.current.scrollWidth;
  }, [tools.length]);

  const idx = Math.min(Math.max(sel, 0), tools.length - 1);
  const cur = tools[idx];
  const loading = live && cur?.status === 'running';

  // The page view: the selected action's screenshot, or the most recent one before it.
  let shot: string | null = cur ? shotPath(cur) : null;
  if (!shot) {
    for (let i = idx; i >= 0; i--) { const s = shotPath(tools[i]); if (s) { shot = s; break; } }
  }
  // Carry the last known URL forward (an action like "click" has no URL of its own).
  let url = cur ? browserUrl(cur) : '';
  if (!url) {
    for (let i = idx; i >= 0; i--) { const u = browserUrl(tools[i]); if (u) { url = u; break; } }
  }
  const text = cur ? browserText(cur) : '';
  // Click/type actions get a target-reticle overlay on the screenshot.
  const isPointer = cur && ['mouse-pointer', 'keyboard'].includes(cur.icon);

  return (
    <div className="ac-browser">
      <div className="ac-urlbar">
        <span className="ac-url-ctrls">
          <ArrowLeft className="w-3 h-3" /><ArrowRight className="w-3 h-3" /><RotateCw className="w-3 h-3" />
        </span>
        <span className={`ac-url ${loading ? 'loading' : ''}`}>
          {loading ? <Loader2 className="w-3 h-3 ac-spin" /> : <Globe className="w-3 h-3" />}
          {url || 'about:blank'}
        </span>
      </div>

      <div className="ac-viewport">
        {shot ? (
          <div className="ac-shot-wrap">
            <img className="ac-shot" src={api(`/api/files/raw?path=${encodeURIComponent(shot)}`)} alt="page" />
            {loading && isPointer && <span className="ac-reticle" />}
            {loading && <span className="ac-scanline" />}
          </div>
        ) : (
          <pre className="ac-page">{text || (loading ? 'Loading…' : '(no page captured yet)')}</pre>
        )}
        {shot && text && <pre className="ac-page ac-page-under">{text}</pre>}
      </div>

      {tools.length > 1 && (
        <div className="ac-film" ref={filmRef}>
          {tools.map((t, i) => {
            const Ic = ICONS[t.icon] || Globe;
            const running = t.status === 'running';
            const err = t.status === 'error';
            return (
              <button
                key={t.id}
                className={`ac-film-item ${i === idx ? 'on' : ''} ${running ? 'run' : ''} ${err ? 'err' : ''}`}
                onClick={() => setSel(i)}
                title={`${t.label}${url ? '' : ''}`}
              >
                <Ic className="w-3 h-3" />
                <span className="ac-film-label">{t.label}</span>
              </button>
            );
          })}
        </div>
      )}
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
  const autoClosed = useRef(false);
  useEffect(() => { if (!picked) setActive(lastApp); }, [lastApp, picked]);

  const shown: AppId = groups[active].length ? active : lastApp;
  const Meta = APP_META[shown];
  const runningCount = tools.filter((t) => t.status === 'running').length;
  const done = !live && runningCount === 0;
  const actions = `${tools.length} action${tools.length !== 1 ? 's' : ''}`;

  // Open while working, then auto-close shortly after the task finishes — one box,
  // opened once and put away when done (re-openable, and it won't auto-close again
  // once the user has re-opened it).
  useEffect(() => {
    if (done && !autoClosed.current) {
      autoClosed.current = true;
      const t = setTimeout(() => setClosed(true), 2600);
      return () => clearTimeout(t);
    }
  }, [done]);

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
      className={`agent-computer ${live ? 'working' : ''} ${done ? 'done' : ''}`}
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
        <span className={`ac-meta ${done ? 'fin' : ''}`}>
          {done ? <><Check className="w-3.5 h-3.5" /> Finished</> : <><span className="ac-live-dot" /> Working</>}
          <span className="ac-meta-sep">·</span> {actions}
        </span>
      </div>

      <div className="ac-menubar">
        <Meta.icon className="w-3 h-3" style={{ color: Meta.accent }} />
        <strong>{Meta.name}</strong>
        <span>File</span><span>Edit</span><span>View</span><span>Go</span>
      </div>
      {live && <div className="ac-progress" />}

      <div className="ac-screen">
        {/* A fixed-size "monitor": the screen height never changes, so streaming
            output and app-switches scroll INSIDE it instead of resizing the box
            and shaking the page. Keying on `shown` remounts (a clean fade-in)
            without an empty-screen gap. */}
        <motion.div
          key={shown}
          className="ac-window"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
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
            {shown === 'browser' && <BrowserApp tools={groups.browser} live={live} />}
          </div>
        </motion.div>
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
// Three clean zones per message, in a fixed order:
//   1. Thinking (the reasoning chain, with its connecting rail) — ABOVE
//   2. The single Agent Computer (ALL tool actions folded into one box) — MIDDLE
//   3. The final answer — BELOW
// Reordering into zones (rather than following the model's interleaving) keeps
// the layout stable: the computer never gets shoved around by late "Thought
// process" blocks, the reasoning always reads above it, and the answer below.
// The rail lives only behind the thinking steps, so it never crosses the
// full-width computer box.
export default function Blocks({ blocks, streaming }: { blocks: Block[]; streaming: boolean }) {
  const lastIdx = blocks.length - 1;
  const allTools = blocks.filter((b) => b.type === 'tool') as ToolBlock[];
  const thinking = blocks
    .map((b, i) => ({ b, i }))
    .filter((x) => x.b.type === 'thinking');
  const answers = blocks
    .map((b, i) => ({ b, i }))
    .filter((x) => x.b.type === 'text');

  return (
    <div className="timeline">
      {thinking.length > 0 && (
        <div className="think-rail">
          {thinking.map(({ b, i }) => (
            <Thinking key={i} block={b as ThinkBlock} live={streaming && i === lastIdx} />
          ))}
        </div>
      )}

      {allTools.length > 0 && <AgentComputer key="agent-computer" tools={allTools} live={streaming} />}

      {answers.map(({ b, i }) => (
        <div key={i} className="answer">
          <Markdown text={(b as { text: string }).text} />
          {streaming && i === lastIdx && <span className="caret" />}
        </div>
      ))}
    </div>
  );
}
