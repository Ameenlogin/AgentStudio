import { useEffect, useState } from 'react';
import { Eye, EyeOff, Save, Check, Key, Globe, Cpu, FolderCog, Wrench, RotateCcw, ShieldCheck, Boxes, Heart, Plus, Trash2, X } from 'lucide-react';
import { api } from '../lib/api';
import { useStore } from '../store/useStore';

type CustomModel = { id: string; label: string };

// Where the heart "Support Creator" link sends people.
const SUPPORT_URL = 'https://pages.razorpay.com/pl_T1zknR655GpRoS/view';

const DEFAULTS = {
  base_url: 'https://integrate.api.nvidia.com/v1',
  model_name: 'openai/gpt-oss-120b',
  custom_models: [] as CustomModel[],
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
  const [newModelId, setNewModelId] = useState('');
  const [newModelLabel, setNewModelLabel] = useState('');
  const set = (k: string, v: any) => setS((p: any) => ({ ...p, [k]: v }));

  const customModels: CustomModel[] = Array.isArray(s.custom_models) ? s.custom_models : [];
  const builtinIds = new Set(MODELS.map((m) => m.id));

  // Add a custom model to the picker (deduped, never shadowing a built-in) and
  // select it immediately. It persists once you hit Save.
  const addCustomModel = () => {
    const id = newModelId.trim();
    if (!id) return;
    const label = newModelLabel.trim() || id.split('/').pop() || id;
    const exists = customModels.some((m) => m.id === id) || builtinIds.has(id);
    const next = exists ? customModels : [...customModels, { id, label }];
    setS((p: any) => ({ ...p, custom_models: next, model_name: id }));
    setNewModelId('');
    setNewModelLabel('');
  };

  const removeCustomModel = (id: string) => {
    const next = customModels.filter((m) => m.id !== id);
    setS((p: any) => ({
      ...p,
      custom_models: next,
      // If we just deleted the selected model, fall back to the default.
      model_name: p.model_name === id ? DEFAULTS.model_name : p.model_name,
    }));
  };

  const clearCustomModels = () => {
    setS((p: any) => ({
      ...p,
      custom_models: [],
      model_name: customModels.some((m) => m.id === p.model_name) ? DEFAULTS.model_name : p.model_name,
    }));
  };

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
      // Push the model picks to the live store so the composer reflects them
      // immediately (custom models become selectable in chat right away).
      useStore.getState().setCustomModels(customModels);
      useStore.getState().setSelectedModel(s.model_name);
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
        <div className="flex items-center gap-4">
          <a
            href={SUPPORT_URL}
            target="_blank"
            rel="noreferrer"
            title="Support the creator"
            className="flex items-center gap-1.5 text-xs text-[var(--color-muted)] hover:text-[var(--color-text)] transition"
          >
            <Heart className="w-3.5 h-3.5 text-[var(--color-red)] fill-[var(--color-red)]" /> Support Creator
          </a>
          <button onClick={() => setS({ ...DEFAULTS, api_key: s.api_key, api_key_2: s.api_key_2, api_key_3: s.api_key_3, custom_models: s.custom_models })} className="flex items-center gap-1.5 text-xs text-[var(--color-muted)] hover:text-[var(--color-text)] transition">
            <RotateCcw className="w-3.5 h-3.5" /> Reset defaults
          </button>
        </div>
      </div>

      <div className="flex-1 px-6 py-6">
        <div className="max-w-5xl mx-auto grid lg:grid-cols-2 gap-4 items-start">
          {/* API key section */}
          <div className="lg:col-span-2">
          <Card icon={Key} title="NVIDIA NIM API Key">
            <p className="text-xs text-[var(--color-muted)] mb-4">
              Get a free API key at{' '}
              <a href="https://build.nvidia.com" target="_blank" rel="noreferrer" className="text-[var(--color-cyan)] underline underline-offset-2">build.nvidia.com</a>. Each key is paced to ~36 RPM, safely under NVIDIA's 40/key limit. Add up to 3 keys for more head-room.
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
          </div>

          <div className="lg:col-span-2">
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

              {/* User-added custom models — selectable cards, each removable. */}
              {customModels.map((m) => {
                const isSelected = s.model_name === m.id;
                return (
                  <div
                    key={m.id}
                    onClick={() => set('model_name', m.id)}
                    className={`group relative text-left rounded-xl border p-3.5 transition flex flex-col justify-between cursor-pointer ${
                      isSelected
                        ? 'border-[var(--color-copper)] bg-[var(--color-copper-wash)] shadow-sm'
                        : 'border-dashed border-[var(--color-border)] bg-[var(--color-elevated)] hover:border-[var(--color-faint)]'
                    }`}
                  >
                    <button
                      type="button"
                      title="Remove this custom model"
                      onClick={(e) => { e.stopPropagation(); removeCustomModel(m.id); }}
                      className="absolute top-2 right-2 p-1 rounded-md text-[var(--color-faint)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-red)] hover:bg-[var(--color-bg)] transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <div>
                      <div className="flex items-center justify-between w-full mb-1 pr-5">
                        <span className="text-xs font-semibold text-[var(--color-muted)]">Custom</span>
                      </div>
                      <h4 className="text-[14px] font-bold text-[var(--color-text)] mb-1">{m.label}</h4>
                      <p className="text-[11px] text-[var(--color-muted)] leading-relaxed mb-3 font-mono break-all">{m.id}</p>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-auto">
                      <span className="cap-badge capitalize">✨ custom</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Add a custom model: it joins the picker above and is saved on Save. */}
            <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-3.5">
              <div className="flex items-center justify-between mb-2">
                <label className="text-[11px] font-semibold text-[var(--color-muted)] block">Add a custom model</label>
                {customModels.length > 0 && (
                  <button
                    type="button"
                    onClick={clearCustomModels}
                    title="Remove all custom models"
                    className="flex items-center gap-1 text-[11px] text-[var(--color-muted)] hover:text-[var(--color-red)] transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Clear all ({customModels.length})
                  </button>
                )}
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  value={newModelId}
                  onChange={(e) => setNewModelId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomModel(); } }}
                  placeholder="Model ID — e.g. meta/llama-3.1-405b-instruct"
                  className={inputCls + ' flex-[2]'}
                />
                <input
                  value={newModelLabel}
                  onChange={(e) => setNewModelLabel(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomModel(); } }}
                  placeholder="Display name (optional)"
                  className={inputCls + ' flex-1'}
                />
                <button
                  type="button"
                  onClick={addCustomModel}
                  disabled={!newModelId.trim()}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition bg-[var(--color-copper)] text-white hover:shadow-[var(--shadow-lift)] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Plus className="w-4 h-4" /> Add
                </button>
              </div>
              <p className="text-[11px] text-[var(--color-faint)] mt-2">
                Paste any model ID your NVIDIA endpoint serves. It’s added to the picker above, selected, and kept here for next time once you press <span className="font-semibold">Save settings</span>.
              </p>
            </div>
          </Card>
          </div>

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

          <div className="lg:col-span-2">
            <a
              href={SUPPORT_URL}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-3 rounded-2xl border border-[var(--color-copper)]/30 bg-[var(--color-copper-wash)] p-5 transition hover:border-[var(--color-copper)] hover:shadow-[var(--shadow-card)]"
            >
              <Heart className="w-6 h-6 flex-shrink-0 text-[var(--color-red)] fill-[var(--color-red)]" />
              <span className="flex flex-col">
                <span className="text-sm font-display font-semibold text-[var(--color-text)]">Support Creator</span>
                <span className="text-xs text-[var(--color-muted)]">Agent Studio is free &amp; open source. If it helps you, please support the creator — it keeps the project alive. 💖</span>
              </span>
            </a>
          </div>

          <div className="pb-10 pt-1 lg:col-span-2">
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
