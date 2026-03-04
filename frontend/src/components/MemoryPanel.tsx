import { useEffect, useState } from 'react';

import { socketService } from '../services/socket';

interface Memory {
  id: string;
  content: string;
  memory_level: 'working' | 'episodic' | 'semantic';
  created_at: string;
  access_count: number;
}

const levelLabels: Record<string, string> = {
  working: '工作记忆',
  episodic: '情景记忆',
  semantic: '语义记忆',
};

const levelColors: Record<string, string> = {
  working: '#60a5fa',
  episodic: '#4ade80',
  semantic: '#c084fc',
};

export function MemoryPanel() {
  const [selectedLevel, setSelectedLevel] = useState<'working' | 'episodic' | 'semantic'>('working');
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMemories = async (level: 'working' | 'episodic' | 'semantic') => {
    setLoading(true);
    try {
      let url = '/api/memory/short';
      if (level === 'episodic') url = '/api/memory/mid';
      if (level === 'semantic') url = '/api/memory/long';
      const res = await fetch(url);
      const data = await res.json();
      setMemories(data.memories || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories(selectedLevel);
  }, [selectedLevel]);

  useEffect(() => {
    socketService.connect();
    const onMemoryUpdated = () => {
      void fetchMemories(selectedLevel);
    };
    socketService.on('memory:updated', onMemoryUpdated);
    return () => {
      socketService.off('memory:updated', onMemoryUpdated);
    };
  }, [selectedLevel]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#111827' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #374151' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: '#c084fc' }}>记忆系统</h2>
      </div>

      <div style={{ display: 'flex', borderBottom: '1px solid #374151' }}>
        {(['working', 'episodic', 'semantic'] as const).map((level) => (
          <button
            key={level}
            onClick={() => setSelectedLevel(level)}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: 'transparent',
              border: 'none',
              borderBottom: selectedLevel === level ? `2px solid ${levelColors[level]}` : '2px solid transparent',
              color: selectedLevel === level ? levelColors[level] : '#9ca3af',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            {levelLabels[level]}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: '#6b7280', paddingTop: '32px' }}>加载中...</div>
        ) : memories.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#6b7280', paddingTop: '32px' }}>
            <p>暂无{levelLabels[selectedLevel]}</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {memories.map((memory) => (
              <div
                key={memory.id}
                style={{
                  padding: '12px',
                  backgroundColor: '#1f2937',
                  borderRadius: '8px',
                  borderLeft: `3px solid ${levelColors[selectedLevel]}`,
                }}
              >
                <div style={{ fontSize: '14px', color: '#e5e7eb', marginBottom: '4px' }}>
                  {memory.content.length > 100 ? `${memory.content.substring(0, 100)}...` : memory.content}
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  {formatDate(memory.created_at)}
                  {memory.access_count > 0 ? ` · 访问${memory.access_count}次` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: '12px', borderTop: '1px solid #374151', fontSize: '12px', color: '#6b7280' }}>
        共 {memories.length} 条{levelLabels[selectedLevel]}
      </div>
    </div>
  );
}

