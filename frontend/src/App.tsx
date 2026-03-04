import ErrorBoundary from './components/ErrorBoundary';
import { ChatPanel } from './components/ChatPanel';
import { ThinkPanel } from './components/ThinkPanel';
import { MemoryPanel } from './components/MemoryPanel';
import { theme } from './styles/theme';

export default function App() {
  return (
    <ErrorBoundary>
      <div style={{ 
        display: 'flex', 
        height: '100vh', 
        backgroundColor: theme.colors.background, 
        color: theme.colors.text,
        overflow: 'hidden',
      }}>
        {/* Left - Chat */}
        <div style={{ 
          width: '33.333%',
          minWidth: '320px',
          borderRight: `1px solid ${theme.colors.border}`,
          flexShrink: 0,
        }}>
          <ChatPanel />
        </div>
        
        {/* Middle - Thinking */}
        <div style={{ 
          width: '33.333%',
          minWidth: '320px',
          borderRight: `1px solid ${theme.colors.border}`,
          flexShrink: 0,
        }}>
          <ThinkPanel />
        </div>
        
        {/* Right - Memory */}
        <div style={{ 
          width: '33.333%',
          minWidth: '320px',
          flex: 1,
        }}>
          <MemoryPanel />
        </div>
      </div>
    </ErrorBoundary>
  );
}
