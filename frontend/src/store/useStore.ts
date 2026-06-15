import { create } from 'zustand';

export type ToolStatus = 'running' | 'done' | 'error';

export interface ToolBlock {
  type: 'tool';
  id: string;            // tool call id
  name: string;
  label: string;
  icon: string;
  kind: string;          // read | write | shell | web
  args: Record<string, unknown>;
  status: ToolStatus;
  result: string;
  stream?: string;       // live stdout/stderr while running
  agent?: string;        // swarm worker id, if produced by a worker
}
export interface TextBlock { type: 'text'; text: string; }
export interface ThinkBlock { type: 'thinking'; text: string; }
export type Block = TextBlock | ThinkBlock | ToolBlock;

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  blocks: Block[];
}

export interface ConversationMeta { id: number; title: string; updated_at?: string; }

export interface SkillMeta { name: string; display: string; description: string; }

export type Effort = 'medium' | 'high' | 'max';
const loadEffort = (): Effort => {
  try {
    const v = localStorage.getItem('agentstudio.effort');
    if (v === 'medium' || v === 'high' || v === 'max') return v;
  } catch { /* ignore */ }
  return 'medium';
};

export interface PermissionRequest {
  id: string;
  call_id: string;
  name: string;
  label: string;
  icon: string;
  kind: string;
  args: Record<string, unknown>;
}

export interface SwarmAgent {
  id: number;
  rpm_used: number;
  rpm_limit: number;
  status: 'idle' | 'active' | 'deprioritized';
  headroom: number;
}

export interface SwarmStatus {
  agents: SwarmAgent[];
  total_rpm: number;
  total_limit: number;
}

export interface SwarmWorker {
  id: string;
  role: string;          // researcher | architect | coder | debugger | synthesizer
  title: string;
  status: 'planned' | 'running' | 'done' | 'error';
}

export interface SwarmPlan {
  plan: string;
  subtasks: { id: string; role: string; title: string }[];
}

interface State {
  view: 'chat' | 'settings';
  setView: (v: 'chat' | 'settings') => void;

  pendingPermission: PermissionRequest | null;
  setPendingPermission: (p: PermissionRequest | null) => void;

  messages: Message[];
  currentId: number | null;
  setCurrentId: (id: number | null) => void;

  conversations: ConversationMeta[];
  setConversations: (c: ConversationMeta[]) => void;

  newChat: () => void;
  loadMessages: (m: Message[]) => void;

  pushUser: (text: string) => void;
  startAssistant: () => string;
  appendText: (id: string, delta: string) => void;
  appendThinking: (id: string, delta: string) => void;
  startTool: (id: string, tool: Omit<ToolBlock, 'type' | 'status' | 'result'>) => void;
  appendToolStream: (id: string, callId: string, delta: string) => void;
  finishTool: (id: string, callId: string, ok: boolean, result: string) => void;

  selectedModel: string;
  setSelectedModel: (m: string) => void;

  skills: SkillMeta[];
  setSkills: (s: SkillMeta[]) => void;
  composerInsert: string | null;        // sidebar → composer (e.g. "/design ")
  setComposerInsert: (v: string | null) => void;

  effort: Effort;                       // Medium | High | Max — how hard the agent works
  setEffort: (e: Effort) => void;

  swarmStatus: SwarmStatus | null;
  setSwarmStatus: (s: SwarmStatus | null) => void;
  showSwarmPanel: boolean;
  toggleSwarmPanel: () => void;

  swarmPlan: SwarmPlan | null;
  swarmWorkers: SwarmWorker[];
  setSwarmPlan: (p: SwarmPlan) => void;
  updateSwarmWorker: (w: SwarmWorker) => void;
  resetSwarm: () => void;
}

const updateMsg = (msgs: Message[], id: string, fn: (b: Block[]) => Block[]) =>
  msgs.map((m) => (m.id === id ? { ...m, blocks: fn(m.blocks) } : m));

export const useStore = create<State>((set) => ({
  view: 'chat',
  setView: (v) => set({ view: v }),

  pendingPermission: null,
  setPendingPermission: (p) => set({ pendingPermission: p }),

  messages: [],
  currentId: null,
  setCurrentId: (id) => set({ currentId: id }),

  conversations: [],
  setConversations: (c) => set({ conversations: c }),

  newChat: () => set({ messages: [], currentId: null, view: 'chat', swarmStatus: null, swarmPlan: null, swarmWorkers: [] }),
  loadMessages: (m) => set({ messages: m, view: 'chat', swarmStatus: null, swarmPlan: null, swarmWorkers: [] }),

  pushUser: (text) =>
    set((s) => ({
      messages: [...s.messages, { id: `u${Date.now()}`, role: 'user', blocks: [{ type: 'text', text }] }],
    })),

  startAssistant: () => {
    const id = `a${Date.now()}`;
    set((s) => ({ messages: [...s.messages, { id, role: 'assistant', blocks: [] }] }));
    return id;
  },

  appendText: (id, delta) =>
    set((s) => ({
      messages: updateMsg(s.messages, id, (blocks) => {
        const last = blocks[blocks.length - 1];
        if (last && last.type === 'text') {
          return [...blocks.slice(0, -1), { type: 'text', text: last.text + delta }];
        }
        return [...blocks, { type: 'text', text: delta }];
      }),
    })),

  appendThinking: (id, delta) =>
    set((s) => ({
      messages: updateMsg(s.messages, id, (blocks) => {
        const last = blocks[blocks.length - 1];
        if (last && last.type === 'thinking') {
          return [...blocks.slice(0, -1), { type: 'thinking', text: last.text + delta }];
        }
        return [...blocks, { type: 'thinking', text: delta }];
      }),
    })),

  startTool: (id, tool) =>
    set((s) => ({
      messages: updateMsg(s.messages, id, (blocks) => [
        ...blocks,
        { type: 'tool', status: 'running', result: '', stream: '', ...tool },
      ]),
    })),

  appendToolStream: (id, callId, delta) =>
    set((s) => ({
      messages: updateMsg(s.messages, id, (blocks) =>
        blocks.map((b) =>
          b.type === 'tool' && b.id === callId
            ? { ...b, stream: ((b as ToolBlock).stream || '') + delta }
            : b
        )
      ),
    })),

  finishTool: (id, callId, ok, result) =>
    set((s) => ({
      messages: updateMsg(s.messages, id, (blocks) =>
        blocks.map((b) =>
          b.type === 'tool' && b.id === callId
            ? { ...b, status: ok ? 'done' : 'error', result }
            : b
        )
      ),
    })),

  selectedModel: 'openai/gpt-oss-120b',
  setSelectedModel: (m) => set({ selectedModel: m }),

  skills: [],
  setSkills: (skills) => set({ skills }),
  composerInsert: null,
  setComposerInsert: (composerInsert) => set({ composerInsert }),

  effort: loadEffort(),
  setEffort: (effort) => {
    try { localStorage.setItem('agentstudio.effort', effort); } catch { /* ignore */ }
    set({ effort });
  },

  swarmStatus: null,
  setSwarmStatus: (s) => set({ swarmStatus: s }),
  showSwarmPanel: false,
  toggleSwarmPanel: () => set((s) => ({ showSwarmPanel: !s.showSwarmPanel })),

  swarmPlan: null,
  swarmWorkers: [],
  setSwarmPlan: (p) =>
    set({
      swarmPlan: p,
      swarmWorkers: p.subtasks.map((s) => ({
        id: s.id, role: s.role, title: s.title, status: 'planned' as const,
      })),
    }),
  updateSwarmWorker: (w) =>
    set((s) => {
      const exists = s.swarmWorkers.some((x) => x.id === w.id);
      return {
        swarmWorkers: exists
          ? s.swarmWorkers.map((x) => (x.id === w.id ? { ...x, ...w } : x))
          : [...s.swarmWorkers, w],
      };
    }),
  resetSwarm: () => set({ swarmPlan: null, swarmWorkers: [] }),
}));
