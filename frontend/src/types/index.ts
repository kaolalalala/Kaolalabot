// Message types
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  thinking_id?: string;
}

// Think step types
export type ThinkPhase = 'observe' | 'reason' | 'act' | 'reflect';

export interface ThinkStep {
  id: string;
  phase: ThinkPhase;
  content: string;
  reasoning: string;
  confidence: number;
  tool_used?: string;
  result?: string;
  thinking_id: string;
  parent_id?: string;
  children_ids?: string[];
  status?: 'pending' | 'active' | 'completed' | 'error';
}

// Memory types
export type MemoryLevel = 'working' | 'episodic' | 'semantic';
export type MemoryPriority = 1 | 2 | 3 | 4;

export interface Memory {
  id: string;
  content: string;
  memory_level: MemoryLevel;
  priority: MemoryPriority;
  created_at: string;
  updated_at: string;
  accessed_at: string;
  access_count: number;
  tags: string[];
  source_session?: string;
  source_type: string;
  title?: string;
  summary?: string;
  is_fact?: boolean;
  confidence?: number;
}

// WebSocket event types
export interface ChatRequest {
  message: string;
  sessionId?: string;
}

export interface ChatResponse {
  content: string;
  session_id: string;
  thinking_steps?: ThinkStep[];
  thinking_id?: string;
}

export interface SocketEvents {
  connected: { sid: string };
  'thinking:step': ThinkStep;
  'chat:message': {
    content: string;
    session_id: string;
    thinking_id?: string;
  };
  'chat:progress': {
    content: string;
    session_id: string;
    tool_hint?: boolean;
  };
  'memory:updated': { session_id: string };
  'memory:results': {
    query: string;
    results: { content: string; level: MemoryLevel }[];
  };
  error: {
    code: string;
    message: string;
  };
}

// API Response types
export interface ApiResponse<T> {
  data?: T;
  error?: string;
}
