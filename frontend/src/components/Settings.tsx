import { useEffect, useState } from 'react';
import { Eye, EyeOff, Save, Check, Key, Globe, Cpu, FolderCog, Wrench, RotateCcw, ShieldCheck, Boxes } from 'lucide-react';
import { api } from '../lib/api';

const DEFAULTS = {
  base_url: 'https://integrate.api.nvidia.com/v1',
  model_name: 'openai/gpt-oss-120b',
  temperature: 0.6,
  max_steps: 50,
  tools_enabled: true,
  workspace_path: './workspace',
  permission_mode: 'ask',
  swarm_mode: 'auto',
};

const MODELS = [
  { id: 'openai/gpt-oss-120b', short: 'GPT-OSS 120B', provider: 'OpenAI', desc: 'Fastest responses · strong coding + tools', size: '128k', caps: ['fastest', 'coding', 'tools'] },
  { id: 'moonshotai/kimi-k2.6', short: 'Kimi K2.6', provider: 'Moonshot AI', desc: 'Best agentic coding, 1T MoE, multimodal', size: '256k', caps: ['agentic', 'tools', 'multimodal'] },
  { id: 'openai/gpt-oss-20b', short: 'GPT-OSS 20B', provider: 'OpenAI', desc: 'Fast open-weight model with tools', size: '128k', caps: ['fast', 'coding', 'tools'] },
  { id: 'meta/llama-3.3-70b-instruct', short: 'Llama 3.3 70B', provider: 'Meta', desc: 'Strong tool-calling, well-tested', size: '128k', caps: ['tools', 'coding'] },
  { id: 'nvidia/llama-3.3-nemotron-super-49b-v1.5', short: 'Nemotron 49B', provider: 'NVIDIA', desc: 'NVIDIA-tuned reasoning + tools', size: '128k', caps: ['reasoning', 'tools'] },
  { id: 'qwen/qwen3-next-80b-a3b-instruct', short: 'Qwen3 Next 80B', provider: 'Alibaba Qwen', desc: 'Latest Qwen, coding + reasoning MoE', size: '256k', caps: ['coding', 'reasoning'] },
];

type SaveStatus = 'idle' | 'saving' | 'saved';

function Card({ icon: Icon, title, children }: any) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-panel)] p-5">
      <h3 className="flex items-center gap-2 text-sm font-display font-semibold mb-4">
        <Icon className="w-4 h-4 text-[var(--color-copper)]" /> {title}
      </h3>
      {children}
    </div>
  );
}

const inputCls =
  'w-full px-3.5 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-copper)] focus:shadow-[0_0_0_3px_rgba(217,119,87,0.16)] transition font-mono';

export default function Settings() {
  const [s, setS] = useState<any>({ ...DEFAULTS, api_key: '', api_key_2: '', api_key_3: '' });
  const [showKey, setShowKey] = useState(false);
  const [save, setSave] = useState<SaveStatus>('idle');
  const [loading, setLoading] = useState(true);
  const set = (k: string, v: any) => setS((p: any) => ({ ...p, [k]: v }));

  useEffect(() => {
    fetch(api('/api/settings/')).then((r) => r.json()).then((d) => {
      setS({ ...DEFAULTS, ...Object.fromEntries(Object.entries(d).filter(([, v]) => v != null)) });
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const onSave = async () => {
    setSave('saving');
    try {
      await fetch(api('/api/settings/'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(s),
      });
      setSave('saved');
    } catch { setSave('saved'); }
    setTimeout(() => setSave('idle'), 2000);
  };

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-[var(--color-muted)]">
        <div className="w-7 h-7 border-2 border-[var(--color-copper)] border-t-transparent rounded-full animate-spin" />
      </div>
    );

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="h-16 px-6 flex items-center justify-between border-b border-[var(--color-border-soft)] sticky top-0 bg-[var(--color-bg)]/80 backdrop-blur z-10">
        <span className="font-display font-semibold text-[15px]">Settings</span>
        <button onClick={() => setS({ ...DEFAULTS, api_key: s.api_key, api_key_2: s.api_key_2, api_key_3: s.api_key_3 })} className="flex items-center gap-1.5 text-xs text-[var(--color-muted)] hover:text-[var(--color-text)] transition">
          <RotateCcw className="w-3.5 h-3.5" /> Reset defaults
        </button>
      </div>

      <div className="flex-1 px-6 py-6">
        <div className="max-w-2xl mx-auto space-y-4">
          {/* API key section */}
          <Card icon={Key} title="NVIDIA NIM API Key">
            <p className="text-xs text-[var(--color-muted)] mb-4">
              Get a free API key at{' '}
              <a href="https://build.nvidia.com" target="_blank" rel="noreferrer" className="text-[var(--color-cyan)] underline underline-offset-2">build.nvidia.com</a>. Runs on a single key at ~40 RPM.
            </p>
            <div>
              <label className="text-[11px] font-semibold text-[var(--color-muted)] mb-1 block">API Key</label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'} value={s.api_key || ''}
                  onChange={(e) => set('api_key', e.target.value)}
                  placeholder="nvapi-••••••••••••••••••••••••"
                  className={inputCls + ' pr-10'}
                />
                <button onClick={() => setShowKey((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)] hover:text-[var(--color-copper)]">
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </Card>

          <Card icon={Cpu} title="Select Model">
            <div className="grid sm:grid-cols-2 gap-3 mb-2">
              {MODELS.map((m) => {
                const isSelected = s.model_name === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => set('model_name', m.id)}
                    className={`text-left rounded-xl border p-3.5 transition flex flex-col justify-between ${
                      isSelected
                        ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)] shadow-sm'
                        : 'border-[var(--color-border)] bg-[var(--color-elevated)] hover:border-[var(--color-faint)]'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between w-full mb-1">
                        <span className="text-xs font-semibold text-[var(--color-muted)]">{m.provider}</span>
                        <span className="text-[10px] text-[var(--color-faint)] font-mono">ctx: {m.size}</span>
                      </div>
                      <h4 className="text-[14px] font-bold text-[var(--color-text)] mb-1">{m.short}</h4>
                      <p className="text-[11px] text-[var(--color-muted)] leading-relaxed mb-3">{m.desc}</p>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-auto">
                      {m.caps.map((cap) => (
                        <span key={cap} className="cap-badge capitalize">
                          {cap === 'coding' ? '💻 ' : cap === 'tools' ? '🔧 ' : cap === 'reasoning' ? '🧠 ' : cap === 'multimodal' ? '🖼️ ' : cap === 'fast' ? '⚡ ' : '💡 '}
                          {cap}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="mt-3">
              <label className="text-[11px] font-semibold text-[var(--color-muted)] mb-1 block">Custom Model Name Override</label>
              <input
                value={s.model_name}
                onChange={(e) => set('model_name', e.target.value)}
                placeholder="e.g. meta/llama-3.1-405b"
                className={inputCls}
              />
            </div>
          </Card>

          <Card icon={Globe} title="Endpoint">
            <input value={s.base_url} onChange={(e) => set('base_url', e.target.value)} className={inputCls} />
          </Card>

          <Card icon={FolderCog} title="Workspace folder">
            <input value={s.workspace_path} onChange={(e) => set('workspace_path', e.target.value)} className={inputCls} />
            <p className="text-xs text-[var(--color-faint)] mt-2">The only folder the agent can read, write and run commands in. Relative paths are based on the backend folder.</p>
          </Card>


          <Card icon={Wrench} title="Tools">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm text-[var(--color-muted)]">Let the agent use file, shell and web tools</span>
              <button
                onClick={() => set('tools_enabled', !s.tools_enabled)}
                className={`w-11 h-6 rounded-full transition relative ${s.tools_enabled ? 'bg-[var(--color-copper)]' : 'bg-[var(--color-border)]'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${s.tools_enabled ? 'left-[22px]' : 'left-0.5'}`} />
              </button>
            </label>
          </Card>

          <Card icon={ShieldCheck} title="Permissions">
            <p className="text-sm text-[var(--color-muted)] mb-3">How Agent Studio handles actions that write files or run commands.</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => set('permission_mode', 'ask')}
                className={`text-left rounded-xl border px-3.5 py-3 transition ${s.permission_mode !== 'auto' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'}`}
              >
                <div className="text-[14px] font-medium">Ask first</div>
                <div className="text-[12px] text-[var(--color-muted)]">Approve each risky action.</div>
              </button>
              <button
                onClick={() => set('permission_mode', 'auto')}
                className={`text-left rounded-xl border px-3.5 py-3 transition ${s.permission_mode === 'auto' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'}`}
              >
                <div className="text-[14px] font-medium">Allow all</div>
                <div className="text-[12px] text-[var(--color-muted)]">Run autonomously, no prompts.</div>
              </button>
            </div>
          </Card>

          <Card icon={Boxes} title="Multi-agent swarm">
            <p className="text-sm text-[var(--color-muted)] mb-3">
              For complex, multi-part tasks, decompose the work across a planner, parallel
              research workers, a builder and a synthesizer. Simple tasks always use the fast single agent.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => set('swarm_mode', 'auto')}
                className={`text-left rounded-xl border px-3.5 py-3 transition ${s.swarm_mode !== 'off' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'}`}
              >
                <div className="text-[14px] font-medium">Auto</div>
                <div className="text-[12px] text-[var(--color-muted)]">Swarm complex tasks automatically.</div>
              </button>
              <button
                onClick={() => set('swarm_mode', 'off')}
                className={`text-left rounded-xl border px-3.5 py-3 transition ${s.swarm_mode === 'off' ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)]' : 'border-[var(--color-border)] hover:border-[var(--color-faint)]'}`}
              >
                <div className="text-[14px] font-medium">Off</div>
                <div className="text-[12px] text-[var(--color-muted)]">Always use a single agent.</div>
              </button>
            </div>
          </Card>

          <div className="pb-10 pt-1">
            <button
              onClick={onSave} disabled={save === 'saving'}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                save === 'saved' ? 'bg-[var(--color-green)] text-white' : 'bg-gradient-to-r from-[var(--color-copper)] to-[var(--color-copper-lo)] text-white hover:shadow-[var(--shadow-lift)]'
              }`}
            >
              {save === 'saving' ? <><div className="w-4 h-4 border-2 border-current/40 border-t-current rounded-full animate-spin" /> Saving…</>
                : save === 'saved' ? <><Check className="w-4 h-4" /> Saved</>
                : <><Save className="w-4 h-4" /> Save settings</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
