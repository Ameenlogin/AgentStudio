import { X, Activity, Cpu, Zap } from 'lucide-react';
import { motion } from 'framer-motion';
import { useStore } from '../store/useStore';

export default function SwarmPanel() {
  const { swarmStatus, showSwarmPanel, toggleSwarmPanel, messages, swarmPlan, swarmWorkers } = useStore();

  if (!showSwarmPanel) return null;

  const getRpmClass = (used: number) => (used < 20 ? 'rpm-low' : used < 30 ? 'rpm-medium' : 'rpm-high');
  const activeCount = swarmStatus?.agents.filter(a => a.status === 'active' || a.rpm_used > 0).length || 0;

  const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
  const latestThinking = lastAssistant?.blocks.find(b => b.type === 'thinking') as any;
  const thinkSnippet = latestThinking?.text?.trim().slice(-240) || null;

  return (
    <motion.aside
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 300, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
      className="swarm-panel h-full flex flex-col flex-shrink-0 overflow-hidden"
      style={{ minWidth: 0 }}
    >
      <div className="h-14 px-4 flex items-center justify-between border-b border-[var(--color-border-soft)] flex-shrink-0">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[var(--color-copper)]" />
          <h2 className="font-display font-semibold text-[14px] tracking-tight">Swarm Engine</h2>
        </div>
        <button
          onClick={toggleSwarmPanel}
          className="p-1.5 rounded-lg text-[var(--color-faint)] hover:text-[var(--color-text)] hover:bg-[var(--color-elevated)] transition"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
        {/* Orchestrator workers (when a complex task is decomposed) */}
        {swarmPlan && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-faint)] font-semibold px-0.5 mb-1.5 flex items-center gap-1.5">
              <Cpu className="w-2.5 h-2.5" /> Orchestrator
            </div>
            {swarmPlan.plan && (
              <p className="text-[12px] text-[var(--color-muted)] leading-relaxed mb-2.5 px-0.5">{swarmPlan.plan}</p>
            )}
            <div className="space-y-1.5">
              {swarmWorkers.map(w => (
                <div key={w.id} className={`worker-row ${w.status}`}>
                  <span className="worker-status-dot" />
                  <span className="worker-role">{w.role}</span>
                  <span className="text-[12px] text-[var(--color-text)] truncate flex-1">{w.title}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Total swarm rate (key-pool transparency) */}
        <div className="rounded-xl bg-[var(--color-elevated)] border border-[var(--color-border)] p-3.5">
          <div className="flex justify-between items-baseline mb-2">
            <span className="text-[11px] text-[var(--color-muted)] font-medium">Request rate</span>
            <span className="text-[11px] font-mono font-semibold text-[var(--color-copper-lo)]">
              {swarmStatus?.total_rpm ?? 0} / {swarmStatus?.total_limit ?? 40} RPM
            </span>
          </div>
          <div className="rpm-bar w-full">
            <div
              className={`rpm-bar-fill ${getRpmClass(swarmStatus?.total_rpm ?? 0)}`}
              style={{ width: `${Math.min(100, ((swarmStatus?.total_rpm ?? 0) / (swarmStatus?.total_limit ?? 40)) * 100)}%` }}
            />
          </div>
          <p className="text-[10px] text-[var(--color-faint)] mt-2 leading-relaxed">
            A 60-second sliding window self-throttles below 40 RPM and backs off automatically on any 429.
          </p>
        </div>

        {thinkSnippet && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-faint)] font-semibold px-0.5 mb-1.5 flex items-center gap-1.5">
              <Zap className="w-2.5 h-2.5" /> Live reasoning
            </div>
            <div className="agent-think-stream">{thinkSnippet}</div>
          </div>
        )}

        {/* Per-key health */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-faint)] font-semibold px-0.5 mb-2">
            API keys — {activeCount} active
          </div>
          <div className="space-y-2">
            {(swarmStatus?.agents || []).map(agent => {
              const used = agent.rpm_used ?? 0;
              const limit = agent.rpm_limit ?? 40;
              const pct = Math.min(100, (used / limit) * 100);
              const throttled = agent.status === 'deprioritized';
              return (
                <div key={agent.id} className={`rounded-xl border p-3 transition ${
                  throttled ? 'border-[var(--color-red)]/25 bg-[var(--color-red)]/5' : 'border-[var(--color-border)] bg-[var(--color-elevated)]'
                }`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[12px] font-semibold text-[var(--color-text)]">Key {agent.id}</span>
                    <span className={`text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded font-bold font-mono ${
                      throttled ? 'bg-[var(--color-red)]/10 text-[var(--color-red)]'
                      : (agent.status === 'active' || used > 0) ? 'bg-[var(--color-copper-wash)] text-[var(--color-copper-lo)]'
                      : 'bg-[var(--color-panel)] text-[var(--color-faint)]'
                    }`}>{throttled ? 'cooldown' : agent.status}</span>
                  </div>
                  <div className="flex justify-between text-[10.5px] font-mono text-[var(--color-muted)] mb-1">
                    <span>{used} / {limit} RPM</span>
                    <span>{agent.headroom} free</span>
                  </div>
                  <div className="rpm-bar w-full">
                    <div className={`rpm-bar-fill ${getRpmClass(used)}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
            {!swarmStatus?.agents?.length && (
              <div className="text-[11px] text-[var(--color-faint)] px-1 py-2">Idle — send a task to see the pool work.</div>
            )}
          </div>
        </div>
      </div>
    </motion.aside>
  );
}
