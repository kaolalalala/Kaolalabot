import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type { Message, ThinkStep, Memory, MemoryLevel } from '../types';

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  sessionId: string;
  
  addMessage: (message: Message) => void;
  setLoading: (loading: boolean) => void;
  setSessionId: (sessionId: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  subscribeWithSelector((set) => ({
    messages: [],
    isLoading: false,
    sessionId: '',

    addMessage: (message) =>
      set((state) => ({
        messages: [...state.messages, message]
      })),

    setLoading: (loading) =>
      set({ isLoading: loading }),

    setSessionId: (sessionId) =>
      set({ sessionId }),

    clearMessages: () =>
      set({ messages: [] })
  }))
);

interface ThinkingState {
  steps: ThinkStep[];
  currentStepId: string | null;
  thinkingId: string | null;
  isThinking: boolean;

  addStep: (step: ThinkStep) => void;
  updateStep: (id: string, updates: Partial<ThinkStep>) => void;
  setThinking: (thinking: boolean) => void;
  setThinkingId: (id: string | null) => void;
  clearThinking: () => void;
}

export const useThinkingStore = create<ThinkingState>()((set) => ({
  steps: [],
  currentStepId: null,
  thinkingId: null,
  isThinking: false,

  addStep: (step) =>
    set((state) => ({
      steps: [...state.steps, step],
      currentStepId: step.id,
      isThinking: step.status !== 'completed'
    })),

  updateStep: (id, updates) =>
    set((state) => ({
      steps: state.steps.map((s) => 
        s.id === id ? { ...s, ...updates } : s
      )
    })),

  setThinking: (thinking) =>
    set({ isThinking: thinking }),

  setThinkingId: (id) =>
    set({ thinkingId: id }),

  clearThinking: () =>
    set({ steps: [], currentStepId: null, thinkingId: null, isThinking: false })
}));

interface MemoryState {
  working: Memory[];
  episodic: Memory[];
  semantic: Memory[];
  selectedLevel: MemoryLevel;
  searchQuery: string;

  setWorking: (memories: Memory[]) => void;
  setEpisodic: (memories: Memory[]) => void;
  setSemantic: (memories: Memory[]) => void;
  setSelectedLevel: (level: MemoryLevel) => void;
  setSearchQuery: (query: string) => void;
  clearAll: () => void;
}

export const useMemoryStore = create<MemoryState>()((set) => ({
  working: [],
  episodic: [],
  semantic: [],
  selectedLevel: 'working',
  searchQuery: '',

  setWorking: (memories) => set({ working: memories }),
  setEpisodic: (memories) => set({ episodic: memories }),
  setSemantic: (memories) => set({ semantic: memories }),
  setSelectedLevel: (level) => set({ selectedLevel: level }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  clearAll: () => set({ working: [], episodic: [], semantic: [] })
}));
