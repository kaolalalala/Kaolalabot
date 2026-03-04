export const theme = {
  colors: {
    background: '#0f172a',
    surface: '#1e293b',
    surfaceHover: '#334155',
    border: '#334155',
    primary: '#3b82f6',
    primaryHover: '#2563eb',
    accent: '#06b6d4',
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    textMuted: '#64748b',
    
    // Phase colors
    observe: '#38bdf8',
    reason: '#22c55e',
    act: '#facc15',
    reflect: '#a855f7',
    
    // Status colors
    success: '#22c55e',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
  },
  
  fonts: {
    primary: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: '"SF Mono", "Fira Code", "Monaco", "Consolas", monospace',
  },
  
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
  },
  
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
  
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    glow: '0 0 20px rgba(59, 130, 246, 0.3)',
  },
  
  transitions: {
    fast: '150ms ease',
    normal: '250ms ease',
    slow: '350ms ease',
  },
};

export const phaseConfig = {
  observe: {
    label: '观察',
    icon: '👁️',
    color: theme.colors.observe,
    description: '收集信息，理解问题',
  },
  reason: {
    label: '推理', 
    icon: '🧠',
    color: theme.colors.reason,
    description: '分析推理，制定策略',
  },
  act: {
    label: '行动',
    icon: '⚡',
    color: theme.colors.act,
    description: '执行工具，调用函数',
  },
  reflect: {
    label: '反思',
    icon: '🔄',
    color: theme.colors.reflect,
    description: '评估结果，优化方案',
  },
};

export type Theme = typeof theme;
export type Phase = keyof typeof phaseConfig;
