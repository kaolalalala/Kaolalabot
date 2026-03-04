import { useEffect, useMemo, useState } from 'react';

import { socketService } from '../services/socket';
import { phaseConfig, theme, type Phase } from '../styles/theme';

interface ThinkStep {
  id: string;
  phase: Phase;
  content: string;
  reasoning?: string;
  confidence?: number;
  tool_used?: string;
  result?: string;
  timestamp: number;
  thinking_id: string;
}

interface ThinkChain {
  id: string;
  steps: ThinkStep[];
  startTime: number;
  isComplete: boolean;
}

function createStep(params: {
  phase: Phase;
  content: string;
  thinkingId: string;
  reasoning?: string;
  confidence?: number;
  toolUsed?: string;
  result?: string;
  id?: string;
}): ThinkStep {
  return {
    id: params.id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    phase: params.phase,
    content: params.content,
    reasoning: params.reasoning,
    confidence: params.confidence,
    tool_used: params.toolUsed,
    result: params.result,
    timestamp: Date.now(),
    thinking_id: params.thinkingId,
  };
}

function sortByPhaseThenTime(a: ThinkStep, b: ThinkStep): number {
  const order: Phase[] = ['observe', 'reason', 'act', 'reflect'];
  const phaseDelta = order.indexOf(a.phase) - order.indexOf(b.phase);
  if (phaseDelta !== 0) {
    return phaseDelta;
  }
  return a.timestamp - b.timestamp;
}

export function ThinkPanel() {
  const [chains, setChains] = useState<ThinkChain[]>([]);
  const [activeChainId, setActiveChainId] = useState<string | null>(null);

  useEffect(() => {
    socketService.connect();

    const upsertChainStep = (step: ThinkStep) => {
      setChains((prev) => {
        const existing = prev.find((chain) => chain.id === step.thinking_id);
        if (!existing) {
          return [
            ...prev,
            {
              id: step.thinking_id,
              steps: [step],
              startTime: Date.now(),
              isComplete: false,
            },
          ];
        }

        const existingStepIdx = existing.steps.findIndex((s) => s.id === step.id);
        const nextSteps = existingStepIdx >= 0
          ? existing.steps.map((s, i) => (i === existingStepIdx ? step : s))
          : [...existing.steps, step];

        return prev.map((chain) => (
          chain.id === step.thinking_id
            ? { ...chain, steps: nextSteps.sort(sortByPhaseThenTime) }
            : chain
        ));
      });
      setActiveChainId(step.thinking_id);
    };

    const onThinkingStep = (data: {
      id?: string;
      phase: Phase;
      content: string;
      reasoning?: string;
      confidence?: number;
      tool_used?: string;
      result?: string;
      thinking_id?: string;
    }) => {
      const thinkingId = data.thinking_id || `chain-${Date.now()}`;
      upsertChainStep(createStep({
        id: data.id,
        phase: data.phase,
        content: data.content,
        reasoning: data.reasoning,
        confidence: data.confidence,
        toolUsed: data.tool_used,
        result: data.result,
        thinkingId,
      }));
    };

    const onProgress = (data: { content: string; session_id: string; tool_hint?: boolean }) => {
      upsertChainStep(createStep({
        phase: data.tool_hint ? 'act' : 'reason',
        content: data.content,
        thinkingId: data.session_id,
      }));
    };

    const onChatMessage = (data: { session_id: string; thinking_id?: string }) => {
      const chainId = data.thinking_id || data.session_id;
      setChains((prev) => prev.map((chain) => (
        chain.id === chainId ? { ...chain, isComplete: true } : chain
      )));
      setActiveChainId(chainId);
    };

    socketService.on('thinking:step', onThinkingStep);
    socketService.on('chat:progress', onProgress);
    socketService.on('chat:message', onChatMessage);

    return () => {
      socketService.off('thinking:step', onThinkingStep);
      socketService.off('chat:progress', onProgress);
      socketService.off('chat:message', onChatMessage);
    };
  }, []);

  const activeChain = useMemo(() => {
    if (activeChainId) {
      return chains.find((chain) => chain.id === activeChainId) || null;
    }
    return chains.length > 0 ? chains[chains.length - 1] : null;
  }, [activeChainId, chains]);

  const renderConfidence = (confidence?: number) => {
    if (confidence == null) {
      return null;
    }
    const percentage = Math.round(confidence * 100);
    return <span style={{ fontSize: '11px', color: theme.colors.textMuted }}>{percentage}%</span>;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: theme.colors.surface }}>
      <div
        style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${theme.colors.border}`,
          background: `linear-gradient(135deg, ${theme.colors.surface} 0%, ${theme.colors.background} 100%)`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: theme.colors.text }}>思维链</h2>
            <p style={{ fontSize: '11px', color: theme.colors.textMuted, margin: 0 }}>Realtime Reasoning Timeline</p>
          </div>
          {chains.length > 1 && (
            <select
              value={activeChainId || ''}
              onChange={(e) => setActiveChainId(e.target.value)}
              style={{
                backgroundColor: theme.colors.background,
                border: `1px solid ${theme.colors.border}`,
                borderRadius: theme.borderRadius.md,
                padding: '6px 12px',
                color: theme.colors.text,
                fontSize: '12px',
              }}
            >
              {chains.map((chain) => (
                <option key={chain.id} value={chain.id}>
                  {chain.id.slice(0, 12)}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {!activeChain || activeChain.steps.length === 0 ? (
          <div style={{ textAlign: 'center', color: theme.colors.textMuted, paddingTop: '60px' }}>
            <div style={{ fontSize: '48px', marginBottom: '20px', opacity: 0.5 }}>🧠</div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: theme.colors.textSecondary, marginBottom: '8px' }}>
              等待推理数据...
            </h3>
            <p style={{ fontSize: '13px', lineHeight: 1.6, maxWidth: '240px', margin: '0 auto' }}>
              聊天过程中，模型的中间进度会实时显示在这里。
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeChain.steps.map((step, index) => {
              const config = phaseConfig[step.phase] || phaseConfig.reason;
              return (
                <div
                  key={step.id}
                  style={{
                    padding: '14px',
                    borderRadius: theme.borderRadius.lg,
                    backgroundColor: theme.colors.surface,
                    borderLeft: `4px solid ${config.color}`,
                    boxShadow: theme.shadows.sm,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ color: config.color, fontWeight: 600, fontSize: '13px' }}>
                      {index + 1}. {config.label}
                    </div>
                    {renderConfidence(step.confidence)}
                  </div>
                  <div style={{ color: theme.colors.text, fontSize: '14px', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                    {step.content}
                  </div>
                  {step.reasoning && (
                    <div
                      style={{
                        marginTop: '8px',
                        color: theme.colors.textSecondary,
                        fontFamily: theme.fonts.mono,
                        fontSize: '12px',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {step.reasoning}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div
        style={{
          padding: '12px 20px',
          borderTop: `1px solid ${theme.colors.border}`,
          fontSize: '11px',
          color: theme.colors.textMuted,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>{activeChain?.steps.length || 0} steps</span>
        <span>{activeChain?.isComplete ? '已完成' : '进行中'}</span>
      </div>
    </div>
  );
}

