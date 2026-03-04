import React, { useEffect, useMemo, useRef, useState } from 'react';

import { socketService } from '../services/socket';
import { theme } from '../styles/theme';
import { useChatStore } from '../stores';
import type { Message } from '../types';

function createMessage(role: Message['role'], content: string, thinkingId?: string): Message {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    timestamp: Date.now(),
    thinking_id: thinkingId,
  };
}

export function ChatPanel() {
  const [input, setInput] = useState('');
  const {
    messages,
    isLoading,
    sessionId,
    addMessage,
    setLoading,
    setSessionId,
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isConnected = useMemo(() => socketService.isConnected(), [messages.length, isLoading]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    socketService.connect();

    const onChatMessage = (data: { content: string; session_id: string; thinking_id?: string }) => {
      addMessage(createMessage('assistant', data.content, data.thinking_id));
      setSessionId(data.session_id);
      setLoading(false);
    };

    const onError = (data: { message?: string }) => {
      addMessage(createMessage('assistant', data?.message || '抱歉，发生了一些错误，请稍后重试。'));
      setLoading(false);
    };

    socketService.on('chat:message', onChatMessage);
    socketService.on('error', onError);

    return () => {
      socketService.off('chat:message', onChatMessage);
      socketService.off('error', onError);
    };
  }, [addMessage, setLoading, setSessionId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const userMessage = input.trim();
    if (!userMessage || isLoading) {
      return;
    }

    setInput('');
    addMessage(createMessage('user', userMessage));
    setLoading(true);

    if (!socketService.isConnected()) {
      socketService.connect();
    }
    socketService.sendMessage(userMessage, sessionId || undefined);
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderMessage = (msg: Message, index: number) => {
    const isUser = msg.role === 'user';

    return (
      <div
        key={msg.id}
        className="message-item"
        style={{
          display: 'flex',
          gap: '12px',
          marginBottom: '20px',
          flexDirection: isUser ? 'row-reverse' : 'row',
          animation: 'slideIn 0.3s ease',
          animationDelay: `${index * 0.05}s`,
          animationFillMode: 'both',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: isUser
              ? 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
              : `linear-gradient(135deg, ${theme.colors.surfaceHover} 0%, ${theme.colors.border} 100%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            flexShrink: 0,
            boxShadow: isUser ? theme.shadows.md : 'none',
          }}
        >
          {isUser ? 'U' : 'AI'}
        </div>

        <div
          style={{
            maxWidth: '70%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: isUser ? 'flex-end' : 'flex-start',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '12px', color: theme.colors.textMuted }}>{isUser ? '你' : 'AI助手'}</span>
            <span style={{ fontSize: '10px', color: theme.colors.textMuted }}>{formatTime(msg.timestamp)}</span>
          </div>

          <div
            style={{
              display: 'inline-block',
              padding: '14px 18px',
              borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
              background: isUser
                ? 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
                : `linear-gradient(135deg, ${theme.colors.surface} 0%, ${theme.colors.surfaceHover} 100%)`,
              color: theme.colors.text,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              boxShadow: theme.shadows.sm,
              lineHeight: 1.6,
              fontSize: '14px',
            }}
          >
            {msg.content}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: theme.colors.background }}>
      <div
        style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${theme.colors.border}`,
          background: `linear-gradient(180deg, ${theme.colors.surface} 0%, ${theme.colors.background} 100%)`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '24px' }}>💬</span>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: theme.colors.text }}>对话</h2>
              <p style={{ fontSize: '11px', color: theme.colors.textMuted, margin: 0 }}>Realtime Chat Interface</p>
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              backgroundColor: theme.colors.surface,
              borderRadius: theme.borderRadius.full,
              fontSize: '11px',
              color: theme.colors.textMuted,
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isLoading ? theme.colors.warning : isConnected ? theme.colors.success : theme.colors.error,
                animation: isLoading ? 'pulse 1.5s ease infinite' : 'none',
              }}
            />
            {isLoading ? '思考中...' : isConnected ? '在线' : '未连接'}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: theme.colors.textMuted, paddingTop: '80px' }}>
            <div style={{ fontSize: '64px', marginBottom: '20px', opacity: 0.6 }}>✨</div>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: theme.colors.textSecondary, marginBottom: '8px' }}>
              欢迎使用 Kaolalabot
            </h3>
            <p style={{ fontSize: '13px', lineHeight: 1.6, maxWidth: '280px', margin: '0 auto' }}>
              在下方输入框发送消息，开始与 AI 助手对话。
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => renderMessage(msg, idx))
        )}

        {isLoading && (
          <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${theme.colors.surface} 0%, ${theme.colors.border} 100%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
              }}
            >
              AI
            </div>
            <div
              style={{
                padding: '14px 18px',
                borderRadius: '18px 18px 18px 4px',
                background: `linear-gradient(135deg, ${theme.colors.surface} 0%, ${theme.colors.surfaceHover} 100%)`,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              思考中...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        style={{
          padding: '16px 20px',
          borderTop: `1px solid ${theme.colors.border}`,
          backgroundColor: theme.colors.surface,
        }}
      >
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="输入消息... (Enter 发送 / Shift+Enter 换行)"
              rows={1}
              style={{
                width: '100%',
                backgroundColor: theme.colors.background,
                border: `1px solid ${theme.colors.border}`,
                borderRadius: theme.borderRadius.lg,
                padding: '14px 18px',
                color: theme.colors.text,
                outline: 'none',
                resize: 'none',
                fontSize: '14px',
                fontFamily: theme.fonts.primary,
                lineHeight: 1.5,
                transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
                minHeight: '52px',
                maxHeight: '120px',
              }}
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            style={{
              background: `linear-gradient(135deg, ${theme.colors.primary} 0%, ${theme.colors.primaryHover} 100%)`,
              padding: '14px 24px',
              borderRadius: theme.borderRadius.lg,
              border: 'none',
              color: 'white',
              cursor: !input.trim() || isLoading ? 'not-allowed' : 'pointer',
              opacity: !input.trim() || isLoading ? 0.5 : 1,
              fontWeight: 600,
              fontSize: '14px',
              transition: 'all 0.2s ease',
              boxShadow: input.trim() && !isLoading ? theme.shadows.glow : 'none',
            }}
          >
            发送
          </button>
        </div>
      </form>
    </div>
  );
}
