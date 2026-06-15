import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import {
  ChevronRight, Check, X, Copy, Download,
  FileText, FilePlus, FilePen, Folder, FolderPlus, Search, Terminal, Globe, Link as LinkIcon, Wrench,
  Trash2, Archive, FolderTree, Files, FileDiff, GitBranch, ListChecks
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

// ── Tool — flat activity row, expand for detail ─────────────────────────────
const KIND_COLOR: Record<string, string> = {
  read:  'var(--color-cyan)',
  write: 'var(--color-copper)',
  shell: 'var(--color-violet)',
  web:   'var(--color-green)',
};

function codePreview(b: ToolBlock): { code: string; lang: string } | null {
  const a = b.args as any;
  if (['write_file', 'append_file', 'zip_write'].includes(b.name) && typeof a.content === 'string') {
    return { code: a.content, lang: langFromPath(a.path || a.inner || '') };
  }
  if (b.name === 'python_exec' && typeof a.code === 'string') return { code: a.code, lang: 'python' };
  if (b.name === 'run_command' && typeof a.command === 'string') return { code: a.command, lang: 'bash' };
  if (b.name === 'apply_patch' && typeof a.diff === 'string') return { code: a.diff, lang: 'diff' };
  if (b.name === 'edit_file' && typeof a.replace === 'string') return { code: a.replace, lang: langFromPath(a.path || '') };
  return null;
}

function Tool({ block }: { block: ToolBlock }) {
  const [open, setOpen] = useState(false);
  const Icon = ICONS[block.icon] || Wrench;
  const color = KIND_COLOR[block.kind] || 'var(--color-muted)';
  const dlPath = block.status === 'done' ? downloadablePath(block) : null;
  const preview = codePreview(block);
  const showLive = block.status === 'running' && !!block.stream;

  const a = block.args as any;
  const summary =
    a.path || a.command || a.query || a.url || a.src || a.output || a.inner ||
    (a.paths ? `${(a.paths as any[]).length} files` : '') ||
    (a.diff ? 'patch' : '') ||
    (a.message ? `"${a.message}"` : '');

  const metaArgs = Object.entries(block.args)
    .filter(([k]) => ![
      'content', 'code', 'command', 'replace', 'diff',
      'path', 'query', 'url', 'src', 'output', 'message', 'paths', 'inner',
    ].includes(k))
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join('   ');

  return (
    <div className="step">
      <span className={`step-node ${
        block.status === 'running' ? 'node-running'
        : block.status === 'error' ? 'node-error'
        : 'node-done'
      }`}>
        {block.status === 'running'
          ? <span className="dot-spin" />
          : block.status === 'error'
          ? <X className="w-2.5 h-2.5 text-[var(--color-red)]" strokeWidth={3} />
          : <Check className="w-2.5 h-2.5 text-[var(--color-green)]" strokeWidth={3} />}
      </span>
      <div className="step-body">
        <div className="tool-line">
          <button onClick={() => setOpen(v => !v)} className="tool-line-main">
            <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color }} />
            <span className="tool-name">{block.label}</span>
            {summary && <span className="tool-arg">{summary}</span>}
          </button>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {dlPath && (
              <a
                href={api(`/api/files/download?path=${encodeURIComponent(dlPath)}`)}
                download onClick={e => e.stopPropagation()}
                className="dl-btn" title={`Download ${dlPath}`}
              >
                <Download className="w-3 h-3" /><span>Download</span>
              </a>
            )}
            <button onClick={() => setOpen(v => !v)} className="p-0.5">
              <ChevronRight className={`w-3.5 h-3.5 text-[var(--color-faint)] chevron-r ${open ? 'open' : ''}`} />
            </button>
          </div>
        </div>

        {showLive && (
          <pre className="tool-stream tool-stream-live">{block.stream}<span className="cursor" /></pre>
        )}

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }}
              className="overflow-hidden"
            >
              <div className="pt-1.5">
                {metaArgs && <div className="text-[11px] text-[var(--color-faint)] font-mono mb-2">{metaArgs}</div>}
                {preview && <div className="mb-2"><CodeBlock lang={preview.lang}>{preview.code}</CodeBlock></div>}
                {(block.result || block.status !== 'running') && (
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-faint)] font-semibold mb-1">Output</div>
                    <pre className="tool-result-pre">
                      {block.result || (block.status === 'running' ? '⟳ running…' : '(no output)')}
                    </pre>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Main export ──────────────────────────────────────────────────────────────
export default function Blocks({ blocks, streaming }: { blocks: Block[]; streaming: boolean }) {
  return (
    <div className="timeline">
      {blocks.map((b, i) => {
        const isLast = i === blocks.length - 1;
        if (b.type === 'thinking') return <Thinking key={i} block={b} live={streaming && isLast} />;
        if (b.type === 'tool')     return <Tool key={i} block={b} />;
        return (
          <div key={i} className="answer">
            <Markdown text={b.text} />
            {streaming && isLast && <span className="caret" />}
          </div>
        );
      })}
    </div>
  );
}
