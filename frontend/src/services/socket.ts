import { io, Socket } from 'socket.io-client';
import type { 
  ThinkStep, 
  Memory 
} from '../types';

type EventCallback = (...args: any[]) => void;

class SocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();

  connect() {
    if (this.socket?.connected) return;

    this.socket = io('/agent', {
      transports: ['websocket'],
      autoConnect: true,
    });

    this.socket.on('connect', () => {
      console.log('Connected to server');
      this.emit('connected', { sid: this.socket?.id });
    });

    this.socket.on('disconnect', () => {
      console.log('Disconnected from server');
    });

    this.socket.on('thinking:step', (data: ThinkStep) => {
      this.emit('thinking:step', data);
    });

    this.socket.on('chat:message', (data: ChatResponse) => {
      this.emit('chat:message', data);
    });

    this.socket.on('chat:progress', (data: { content: string; session_id: string; tool_hint?: boolean }) => {
      this.emit('chat:progress', data);
    });

    this.socket.on('memory:updated', (data: { session_id: string }) => {
      this.emit('memory:updated', data);
    });

    this.socket.on('memory:results', (data: { query: string; results: Memory[] }) => {
      this.emit('memory:results', data);
    });

    this.socket.on('error', (data: { code: string; message: string }) => {
      console.error('Socket error:', data);
      this.emit('error', data);
    });
  }

  disconnect() {
    this.socket?.disconnect();
    this.socket = null;
  }

  sendMessage(message: string, sessionId?: string) {
    this.socket?.emit('chat:start', { message, sessionId });
  }

  queryMemory(query: string, sessionId?: string) {
    this.socket?.emit('memory:query', { query, sessionId });
  }

  clearMemory(sessionId?: string) {
    this.socket?.emit('memory:clear', { sessionId });
  }

  on(event: string, callback: EventCallback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }

  off(event: string, callback: EventCallback) {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach(callback => callback(data));
  }

  isConnected() {
    return this.socket?.connected ?? false;
  }
}

export const socketService = new SocketService();

interface ChatResponse {
  content: string;
  session_id: string;
  thinking_id?: string;
}
