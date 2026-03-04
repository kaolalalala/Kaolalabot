import { theme } from './theme';

export const globalStyles = `
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  
  html, body, #root {
    height: 100%;
    width: 100%;
    overflow: hidden;
  }
  
  body {
    font-family: ${theme.fonts.primary};
    background-color: ${theme.colors.background};
    color: ${theme.colors.text};
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  
  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  
  ::-webkit-scrollbar-track {
    background: ${theme.colors.background};
  }
  
  ::-webkit-scrollbar-thumb {
    background: ${theme.colors.border};
    border-radius: 4px;
  }
  
  ::-webkit-scrollbar-thumb:hover {
    background: ${theme.colors.surfaceHover};
  }
  
  /* Selection */
  ::selection {
    background: ${theme.colors.primary};
    color: white;
  }
  
  /* Focus outline */
  :focus-visible {
    outline: 2px solid ${theme.colors.primary};
    outline-offset: 2px;
  }
  
  /* Animations */
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  @keyframes slideIn {
    from { 
      opacity: 0;
      transform: translateY(10px);
    }
    to { 
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  @keyframes thinking {
    0% { content: '.'; }
    33% { content: '..'; }
    66% { content: '...'; }
  }
  
  .animate-fade-in {
    animation: fadeIn 0.3s ease;
  }
  
  .animate-slide-in {
    animation: slideIn 0.3s ease;
  }
  
  .animate-pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  
  .animate-spin {
    animation: spin 1s linear infinite;
  }
  
  /* Code blocks */
  code {
    font-family: ${theme.fonts.mono};
    background: ${theme.colors.background};
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  
  pre {
    font-family: ${theme.fonts.mono};
    background: ${theme.colors.background};
    padding: ${theme.spacing.md};
    border-radius: ${theme.borderRadius.md};
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.5;
  }
`;

export const panelStyles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
    backgroundColor: theme.colors.surface,
  },
  header: {
    padding: theme.spacing.md,
    borderBottom: `1px solid ${theme.colors.border}`,
    background: `linear-gradient(180deg, ${theme.colors.surface} 0%, ${theme.colors.background} 100%)`,
  },
  content: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: theme.spacing.md,
  },
  footer: {
    padding: theme.spacing.md,
    borderTop: `1px solid ${theme.colors.border}`,
  },
};

export const buttonStyles = {
  primary: {
    backgroundColor: theme.colors.primary,
    color: 'white',
    border: 'none',
    padding: `${theme.spacing.sm} ${theme.spacing.md}`,
    borderRadius: theme.borderRadius.md,
    cursor: 'pointer',
    transition: `all ${theme.transitions.fast}`,
    fontWeight: 500,
    '&:hover': {
      backgroundColor: theme.colors.primaryHover,
    },
    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
  secondary: {
    backgroundColor: 'transparent',
    color: theme.colors.textSecondary,
    border: `1px solid ${theme.colors.border}`,
    padding: `${theme.spacing.sm} ${theme.spacing.md}`,
    borderRadius: theme.borderRadius.md,
    cursor: 'pointer',
    transition: `all ${theme.transitions.fast}`,
    '&:hover': {
      backgroundColor: theme.colors.surfaceHover,
      borderColor: theme.colors.textSecondary,
    },
  },
};

export const inputStyles = {
  base: {
    backgroundColor: theme.colors.background,
    border: `1px solid ${theme.colors.border}`,
    borderRadius: theme.borderRadius.md,
    padding: `${theme.spacing.sm} ${theme.spacing.md}`,
    color: theme.colors.text,
    outline: 'none',
    transition: `all ${theme.transitions.fast}`,
    fontSize: '14px',
    '&:focus': {
      borderColor: theme.colors.primary,
      boxShadow: `0 0 0 3px rgba(59, 130, 246, 0.1)`,
    },
    '&::placeholder': {
      color: theme.colors.textMuted,
    },
  },
};
