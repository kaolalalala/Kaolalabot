# Kaolalabot 技术增强方案规格说明书

> 版本: 1.0.0
> 日期: 2026-03-02
> 状态: 规划中

---

## 目录

1. [系统架构设计](#1-系统架构设计)
2. [React前端实现方案](#2-react前端实现方案)
3. [CoT思维链机制](#3-cot思维链机制)
4. [记忆分层系统设计](#4-记忆分层系统设计)
5. [技术栈选型与实现路径](#5-技术栈选型与实现路径)
6. [性能优化与扩展性](#6-性能优化与扩展性)
7. [测试策略与验收标准](#7-测试策略与验收标准)

---

## 1. 系统架构设计

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端 (Browser)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        React Frontend                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │   │
│  │  │ ChatPanel    │  │ ThinkPanel   │  │ MemoryPanel            │ │   │
│  │  │ 对话界面      │  │ 思维链可视化  │  │ 记忆管理                │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │   │
│  │         │                 │                     │                   │   │
│  │         └─────────────────┼─────────────────────┘                   │   │
│  │                           │                                         │   │
│  │                    ┌──────▼──────┐                                  │   │
│  │                    │ State Store │ (Zustand)                        │   │
│  │                    │ 状态管理    │                                  │   │
│  │                    └──────┬──────┘                                  │   │
│  └───────────────────────────┼─────────────────────────────────────────┘   │
│                              │ WebSocket / HTTP                          │
├──────────────────────────────┼───────────────────────────────────────────┤
│                              │                                            │
│                    ┌─────────▼─────────┐                                 │
│                    │   Gateway API     │                                 │
│                    │   (FastAPI)       │                                 │
│                    └─────────┬─────────┘                                 │
│                              │                                            │
│      ┌───────────────────────┼───────────────────────┐                   │
│      │                       │                       │                   │
│ ┌────▼────┐          ┌──────▼──────┐        ┌──────▼──────┐            │
│ │ Channel │          │ Agent Core  │        │ Memory     │            │
│ │ Manager │          │  + CoT      │        │ System     │            │
│ └─────────┘          └─────────────┘        └────────────┘            │
│                              │                                            │
│                    ┌─────────▼─────────┐                                 │
│                    │  LLM Providers    │                                 │
│                    │ (LiteLLM)         │                                 │
│                    └───────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流向

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  React Frontend                                                          │
│  1. StateStore 接收输入                                                  │
│  2. 发送到 Gateway API (WebSocket)                                       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Gateway API                                                             │
│  1. 验证请求                                                             │
│  2. 转发到 Agent Core                                                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent Core + CoT Engine                                                │
│  1. 接收用户消息                                                         │
│  2. 从 Memory System 检索上下文                                          │
│  3. 构建 CoT 推理链                                                      │
│  4. 调用 LLM (流式响应)                                                  │
│  5. 实时推送思维过程到前端                                               │
│  6. 保存结果到 Memory System                                             │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Working Memory │  │ Episodic       │  │ Semantic       │
│ (当前会话)      │  │ Memory         │  │ Memory         │
│                 │  │ (短期记忆)     │  │ (长期记忆)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 1.3 核心模块交互关系

| 模块 | 职责 | 依赖模块 | 通信方式 |
|------|------|----------|----------|
| React Frontend | UI渲染、用户交互 | Gateway API | WebSocket/HTTP |
| Gateway API | 请求路由、认证 | Agent Core | 内部调用 |
| Agent Core | 任务处理、CoT推理 | Memory System, LLM | 内部调用 |
| Memory System | 记忆存储检索 | 数据库/向量库 | 内部调用 |
| Channel Manager | 消息通道管理 | Agent Core | 内部调用 |

---

## 2. React前端实现方案

### 2.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.x | UI框架 |
| TypeScript | 5.x | 类型安全 |
| Zustand | 4.x | 状态管理 |
| React Query | 5.x | 数据获取/缓存 |
| Tailwind CSS | 3.x | 样式框架 |
| React Flow | 11.x | 思维链可视化 |
| Socket.io-client | 4.x | WebSocket通信 |
| shadcn/ui | latest | UI组件库 |

### 2.2 组件结构

```
src/
├── components/
│   ├── chat/
│   │   ├── ChatPanel.tsx          # 主聊天面板
│   │   ├── MessageBubble.tsx      # 消息气泡
│   │   ├── InputArea.tsx          # 输入区域
│   │   └── TypingIndicator.tsx    # 打字动画
│   │
│   ├── thinking/
│   │   ├── ThinkPanel.tsx        # 思维链面板
│   │   ├── ThinkNode.tsx          # 思维节点
│   │   ├── ThinkEdge.tsx          # 思维连线
│   │   └── ThinkTree.tsx          # 思维树可视化
│   │
│   ├── memory/
│   │   ├── MemoryPanel.tsx        # 记忆面板
│   │   ├── ShortTermList.tsx      # 短期记忆列表
│   │   ├── MidTermList.tsx        # 中期记忆列表
│   │   ├── LongTermList.tsx       # 长期记忆列表
│   │   └── MemoryItem.tsx         # 记忆条目
│   │
│   └── common/
│       ├── Button.tsx
│       ├── Input.tsx
│       ├── Modal.tsx
│       └── Tooltip.tsx
│
├── stores/
│   ├── chatStore.ts               # 对话状态
│   ├── thinkingStore.ts           # 思维链状态
│   ├── memoryStore.ts             # 记忆状态
│   └── settingsStore.ts           # 设置状态
│
├── hooks/
│   ├── useChat.ts                 # 对话逻辑
│   ├── useThinking.ts             # 思维链逻辑
│   ├── useMemory.ts               # 记忆逻辑
│   └── useWebSocket.ts            # WebSocket连接
│
├── services/
│   ├── api.ts                    # HTTP API
│   └── socket.ts                  # WebSocket服务
│
├── types/
│   ├── message.ts                # 消息类型
│   ├── thinking.ts               # 思维链类型
│   └── memory.ts                 # 记忆类型
│
└── App.tsx
```

### 2.3 状态管理策略

```typescript
// stores/chatStore.ts
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  currentSessionId: string | null;
  
  // Actions
  addMessage: (message: Message) => void;
  setLoading: (loading: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  subscribeWithSelector((set) => ({
    messages: [],
    isLoading: false,
    currentSessionId: null,
    
    addMessage: (message) =>
      set((state) => ({
        messages: [...state.messages, message]
      })),
    
    setLoading: (loading) =>
      set({ isLoading: loading }),
    
    clearMessages: () =>
      set({ messages: [] })
  }))
);

// stores/thinkingStore.ts
interface ThinkingState {
  thinkingSteps: ThinkStep[];
  currentStepId: string | null;
  
  // Actions
  addStep: (step: ThinkStep) => void;
  updateStep: (id: string, updates: Partial<ThinkStep>) => void;
  setCurrentStep: (id: string | null) => void;
  clearThinking: () => void;
}
```

### 2.4 API接口设计

#### 2.4.1 HTTP API

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /api/chat/send | 发送消息 | `{ message, sessionId? }` | `{ response, sessionId }` |
| GET | /api/chat/history | 获取历史 | `{ sessionId, limit }` | `{ messages }` |
| GET | /api/memory/short | 获取短期记忆 | `{ sessionId }` | `{ memories }` |
| GET | /api/memory/mid | 获取中期记忆 | `{ limit, offset }` | `{ memories }` |
| GET | /api/memory/long | 获取长期记忆 | `{ query?, limit }` | `{ memories }` |
| DELETE | /api/memory/{id} | 删除记忆 | - | `{ success }` |
| POST | /api/memory/{id}/promote | 提升记忆级别 | - | `{ success, memory }` |
| GET | /api/status | 系统状态 | - | `{ status, version }` |

#### 2.4.2 WebSocket事件

| 事件名 | 方向 | 描述 | 载荷 |
|--------|------|------|------|
| `chat:start` | Client→Server | 开始对话 | `{ message, sessionId }` |
| `chat:message` | Server→Client | 新消息 | `{ content, thinking }` |
| `thinking:step` | Server→Client | 思维步骤 | `{ step, status }` |
| `thinking:complete` | Server→Client | 思维完成 | `{ final }` |
| `memory:updated` | Server→Client | 记忆更新 | `{ memory }` |
| `error` | Server→Client | 错误 | `{ code, message }` |

### 2.5 用户界面设计

```tsx
// App.tsx 主布局
export default function App() {
  return (
    <div className="h-screen flex">
      {/* 左侧：聊天面板 */}
      <div className="w-1/3 border-r">
        <ChatPanel />
      </div>
      
      {/* 中间：思维链可视化 */}
      <div className="w-1/3 border-r">
        <ThinkPanel />
      </div>
      
      {/* 右侧：记忆管理 */}
      <div className="w-1/3">
        <MemoryPanel />
      </div>
    </div>
  );
}
```

---

## 3. CoT思维链机制

### 3.1 思维链数据模型

```typescript
// types/thinking.ts

// 思维步骤类型
enum ThinkStepType {
  OBSERVATION = "observation",   // 观察
  ANALYSIS = "analysis",         // 分析
  REASONING = "reasoning",      // 推理
  ACTION = "action",           // 行动
  RESULT = "result",           // 结果
  REFLECTION = "reflection"     // 反思
}

// 思维步骤
interface ThinkStep {
  id: string;
  type: ThinkStepType;
  content: string;              // 思考内容
  timestamp: number;
  parentId: string | null;      // 父步骤（用于树形结构）
  childrenIds: string[];        // 子步骤
  status: 'pending' | 'active' | 'completed' | 'error';
  metadata?: {
    toolUsed?: string;
    confidence?: number;
    evidence?: string[];
  };
}

// 思维链
interface ThinkChain {
  id: string;
  sessionId: string;
  steps: Map<string, ThinkStep>;  // 步骤映射
  rootId: string | null;          // 根步骤
  currentId: string | null;       // 当前步骤
  createdAt: number;
  updatedAt: number;
}

// LLM响应（包含思维链）
interface LLMResponse {
  content: string;
  thinking: {
    steps: ThinkStep[];
    finalConfidence: number;
  };
  toolCalls?: ToolCall[];
  finishReason: string;
}
```

### 3.2 思维链生成机制

```python
# agent/cot/engine.py

from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator
import asyncio

class ThinkPhase(Enum):
    """思维阶段"""
    OBSERVE = "observe"       # 观察理解
    REASON = "reason"         # 推理分析
    ACT = "act"               # 行动执行
    REFLECT = "reflect"       # 反思总结

@dataclass
class ThinkStep:
    """思维步骤"""
    phase: ThinkPhase
    content: str
    reasoning: str = ""
    confidence: float = 1.0
    tool_used: str | None = None
    result: str | None = None

class CoTEngine:
    """
    Chain of Thought 思维链引擎
    
    工作流程:
    1. OBSERVE - 理解用户输入
    2. REASON - 逐步推理
    3. ACT - 执行行动(工具调用)
    4. REFLECT - 反思结果
    """
    
    def __init__(
        self,
        llm_provider,
        tools: ToolRegistry,
        max_iterations: int = 10,
        enable_reflection: bool = True,
    ):
        self.llm = llm_provider
        self.tools = tools
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
    
    async def think(
        self,
        user_input: str,
        context: list[dict],
        session_id: str,
    ) -> AsyncGenerator[ThinkStep, None]:
        """
        执行思维链
        
        Yields:
            ThinkStep: 思维步骤
        """
        # 阶段1: OBSERVE - 理解输入
        observe_step = await self._observe(user_input, context)
        yield observe_step
        
        # 阶段2: REASON - 推理分析
        reason_steps = await self._reason(user_input, context, observe_step)
        for step in reason_steps:
            yield step
        
        # 阶段3: ACT - 行动执行
        act_step = await self._act(user_input, context, reason_steps)
        yield act_step
        
        # 阶段4: REFLECT - 反思总结
        if self.enable_reflection:
            reflect_step = await self._reflect(
                user_input, context, 
                [*reason_steps, act_step]
            )
            yield reflect_step
    
    async def _observe(self, user_input: str, context: list[dict]) -> ThinkStep:
        """观察阶段 - 理解用户输入"""
        prompt = f"""你是一个AI助手。请分析以下用户输入:

用户输入: {user_input}

请用一句话描述:
1. 用户想要什么?
2. 需要什么信息?
3. 可能需要什么工具?"""
        
        response = await self.llm.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ])
        
        return ThinkStep(
            phase=ThinkPhase.OBSERVE,
            content=response.content,
            reasoning="理解用户意图和需求"
        )
    
    async def _reason(
        self, 
        user_input: str, 
        context: list[dict],
        observe_step: ThinkStep
    ) -> list[ThinkStep]:
        """推理阶段 - 多步推理"""
        steps = []
        
        prompt = f"""用户输入: {user_input}

上一步理解: {observe_step.content}

请进行推理，列出解决问题的步骤。
每个步骤用"步骤N:"开头。"""
        
        response = await self.llm.chat([
            {"role": "system", "content": prompt},
            *context
        ])
        
        # 解析推理步骤
        for i, line in enumerate(response.content.split('\n')):
            if line.strip().startswith('步骤'):
                steps.append(ThinkStep(
                    phase=ThinkPhase.REASON,
                    content=line,
                    reasoning=f"推理步骤 {i+1}",
                    confidence=0.9 - (i * 0.1)  # 置信度递减
                ))
        
        return steps
    
    async def _act(
        self,
        user_input: str,
        context: list[dict],
        reason_steps: list[ThinkStep]
    ) -> ThinkStep:
        """行动阶段 - 执行工具调用"""
        
        # 判断是否需要工具
        needs_tool = await self._check_needs_tool(user_input, reason_steps)
        
        if needs_tool:
            tool_name, params = await self._plan_tool_call(user_input, reason_steps)
            result = await self.tools.execute(tool_name, params)
            
            return ThinkStep(
                phase=ThinkPhase.ACT,
                content=f"调用工具: {tool_name}",
                tool_used=tool_name,
                result=result,
                confidence=0.8
            )
        else:
            return ThinkStep(
                phase=ThinkPhase.ACT,
                content="无需外部工具，直接生成回答",
                confidence=0.9
            )
    
    async def _reflect(
        self,
        user_input: str,
        context: list[dict],
        all_steps: list[ThinkStep]
    ) -> ThinkStep:
        """反思阶段 - 审视结果"""
        
        prompt = f"""请反思以下思考过程和结果:

用户输入: {user_input}

思考步骤:
{chr(10).join([s.content for s in all_steps])}

这个结果是否正确?有什么可以改进的?"""
        
        response = await self.llm.chat([
            {"role": "system", "content": prompt},
            *context
        ])
        
        return ThinkStep(
            phase=ThinkPhase.REFLECT,
            content=response.content,
            reasoning="反思整个思考过程"
        )
```

### 3.3 思维链可视化

```tsx
// components/thinking/ThinkTree.tsx
import React, { useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useThinkingStore } from '../../stores/thinkingStore';

export function ThinkTree() {
  const { thinkingSteps, currentStepId } = useThinkingStore();
  
  // 转换思维步骤为React Flow节点
  const { nodes, edges } = useMemo(() => {
    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];
    
    thinkingSteps.forEach((step, index) => {
      // 创建节点
      flowNodes.push({
        id: step.id,
        position: { x: 250, y: index * 100 },
        data: { 
          label: step.content,
          type: step.phase,
          status: step.id === currentStepId ? 'active' : step.status
        },
        type: 'thinkNode',
      });
      
      // 创建连线
      if (step.parentId) {
        flowEdges.push({
          id: `${step.parentId}-${step.id}`,
          source: step.parentId,
          target: step.id,
          animated: step.id === currentStepId,
        });
      }
    });
    
    return { nodes: flowNodes, edges: flowEdges };
  }, [thinkingSteps, currentStepId]);
  
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
    >
      <Background />
      <Controls />
    </ReactFlow>
  );
}

// 自定义思维节点组件
function ThinkNode({ data }) {
  const colors = {
    observe: 'bg-blue-100 border-blue-500',
    reason: 'bg-green-100 border-green-500',
    act: 'bg-yellow-100 border-yellow-500',
    reflect: 'bg-purple-100 border-purple-500',
  };
  
  return (
    <div className={`p-3 rounded-lg border-2 ${colors[data.type]} ${data.status === 'active' ? 'ring-2 ring-blue-400' : ''}`}>
      <div className="text-xs uppercase text-gray-500">{data.type}</div>
      <div className="text-sm">{data.label}</div>
    </div>
  );
}
```

### 3.4 错误处理与回溯

```python
# agent/cot/error_handling.py

class CoTError(Exception):
    """CoT引擎错误基类"""
    pass

class ToolExecutionError(CoTError):
    """工具执行错误"""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")

class ReasoningError(CoTError):
    """推理错误"""
    pass

class MaxIterationsError(CoTError):
    """最大迭代次数超出"""
    pass

class CoTErrorHandler:
    """思维链错误处理器"""
    
    def __init__(self, engine: CoTEngine):
        self.engine = engine
        self.error_history: list[dict] = []
    
    async def handle_error(
        self, 
        error: Exception, 
        current_step: ThinkStep
    ) -> ThinkStep:
        """
        处理错误并尝试恢复
        
        策略:
        1. 记录错误
        2. 分析错误原因
        3. 尝试回溯或重试
        4. 返回恢复后的步骤
        """
        error_info = {
            "error_type": type(error).__name__,
            "message": str(error),
            "step": current_step.content,
            "timestamp": datetime.now().isoformat()
        }
        self.error_history.append(error_info)
        
        # 策略1: 重试
        if isinstance(error, ToolExecutionError):
            return await self._retry_tool(current_step, error)
        
        # 策略2: 回溯
        if isinstance(error, ReasoningError):
            return await self._backtrack(current_step)
        
        # 策略3: 降级处理
        return await self._fallback(current_step, error)
    
    async def _retry_tool(
        self, 
        step: ThinkStep, 
        error: ToolExecutionError
    ) -> ThinkStep:
        """重试工具调用"""
        logger.warning(f"Retrying tool: {error.tool_name}")
        
        # 更换参数或工具
        new_params = await self._modify_params(step, error)
        result = await self.engine.tools.execute(
            error.tool_name, 
            new_params
        )
        
        return ThinkStep(
            phase=ThinkPhase.ACT,
            content=f"重试成功: {error.tool_name}",
            tool_used=error.tool_name,
            result=result,
            confidence=0.6  # 降低置信度
        )
    
    async def _backtrack(self, step: ThinkStep) -> ThinkStep:
        """回溯到之前的步骤"""
        logger.warning("Backtracking to previous reasoning step")
        
        # 返回一个反思步骤
        return ThinkStep(
            phase=ThinkPhase.REFLECT,
            content="检测到推理错误，回溯重新分析",
            reasoning="错误恢复 - 回溯策略"
        )
    
    async def _fallback(
        self, 
        step: ThinkStep, 
        error: Exception
    ) -> ThinkStep:
        """降级处理 - 直接生成回答"""
        logger.error(f"Falling back due to: {error}")
        
        return ThinkStep(
            phase=ThinkPhase.REFLECT,
            content="遇到无法解决的问题，生成直接回答",
            reasoning="错误恢复 - 降级策略",
            confidence=0.3
        )
```

---

## 4. 记忆分层系统设计

### 4.1 记忆层次划分

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          记忆系统架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Working Memory (工作记忆)                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ • 容量: 10-20 条消息                                        │ │   │
│  │  │ • 存储: 内存 (Python list)                                  │ │   │
│  │  │ • 生命周期: 当前会话                                        │ │   │
│  │  │ • 访问速度: 纳秒级                                          │ │   │
│  │  │ • 淘汰策略: FIFO (先进先出)                                  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Episodic Memory (情景记忆)                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ • 存储: JSONL 文件 (workspace/memory/episodic/)             │ │   │
│  │  │ • 生命周期: 7-30 天                                        │ │   │
│  │  │ • 访问速度: 毫秒级                                          │ │   │
│  │  │ • 淘汰策略: 基于时间+重要性                                  │ │   │
│  │  │ • 检索方式: 关键词 + 语义                                   │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Semantic Memory (语义记忆)                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ • 存储: ChromaDB 向量数据库                                  │ │   │
│  │  │ • 生命周期: 永久                                            │ │   │
│  │  │ • 访问速度: 毫秒级 (向量相似度)                              │ │   │
│  │  │ • 淘汰策略: 用户手动删除                                     │ │   │
│  │  │ • 检索方式: 语义向量相似度                                   │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 记忆数据模型

```python
# memory/models.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

class MemoryLevel(Enum):
    """记忆级别"""
    WORKING = "working"      # 工作记忆
    EPISODIC = "episodic"    # 情景记忆
    SEMANTIC = "semantic"    # 语义记忆

class MemoryPriority(Enum):
    """记忆优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Memory:
    """记忆基类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_level: MemoryLevel = MemoryLevel.WORKING
    priority: MemoryPriority = MemoryPriority.NORMAL
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    
    # 内容特征
    tags: list[str] = field(default_factory=list)
    embedding: list[float] | None = None  # 向量嵌入
    
    # 来源信息
    source_session: str | None = None
    source_type: str = "conversation"  # conversation, tool, manual
    
    # 关联
    related_memory_ids: list[str] = field(default_factory=list)

@dataclass
class WorkingMemory(Memory):
    """工作记忆 - 当前会话"""
    memory_level: MemoryLevel = MemoryLevel.WORKING
    
    # 附加: 对话角色
    role: str = "user"  # user, assistant

@dataclass  
class EpisodicMemory(Memory):
    """情景记忆 - 会话历史"""
    memory_level: MemoryLevel = MemoryLevel.EPISODIC
    
    # 附加
    session_id: str = ""
    turn_index: int = 0
    expires_at: datetime | None = None  # 过期时间

@dataclass
class SemanticMemory(Memory):
    """语义记忆 - 持久知识"""
    memory_level: MemoryLevel = MemoryLevel.SEMANTIC
    
    # 附加
    title: str = ""
    summary: str = ""
    is_fact: bool = False  # 是否是事实
    confidence: float = 1.0  # 置信度
```

### 4.3 记忆存储结构

```python
# memory/storage.py

from pathlib import Path
from typing import AsyncGenerator
import json
import asyncio

class MemoryStorage:
    """记忆存储抽象基类"""
    
    async def save(self, memory: Memory) -> None:
        raise NotImplementedError
    
    async def get(self, memory_id: str) -> Memory | None:
        raise NotImplementedError
    
    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError
    
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        **filters
    ) -> list[Memory]:
        raise NotImplementedError


class WorkingMemoryStorage(MemoryStorage):
    """工作记忆存储 - 内存"""
    
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._memories: list[WorkingMemory] = []
        self._index: dict[str, int] = {}
    
    async def save(self, memory: WorkingMemory) -> None:
        # 添加到末尾
        self._memories.append(memory)
        self._index[memory.id] = len(self._memories) - 1
        
        # 超过容量则淘汰
        if len(self._memories) > self.max_size:
            removed = self._memories.pop(0)
            self._rebuild_index()
    
    async def get(self, memory_id: str) -> WorkingMemory | None:
        idx = self._index.get(memory_id)
        if idx is not None and idx < len(self._memories):
            memory = self._memories[idx]
            memory.accessed_at = datetime.now()
            memory.access_count += 1
            return memory
        return None
    
    async def get_all(self) -> list[WorkingMemory]:
        return self._memories.copy()
    
    async def clear(self) -> None:
        self._memories.clear()
        self._index.clear()
    
    def _rebuild_index(self) -> None:
        self._index = {
            m.id: i for i, m in enumerate(self._memories)
        }


class EpisodicMemoryStorage(MemoryStorage):
    """情景记忆存储 - JSONL文件"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = storage_dir / "episodic.jsonl"
        
        # 内存缓存
        self._cache: dict[str, EpisodicMemory] = {}
        self._load_to_cache()
    
    async def save(self, memory: EpisodicMemory) -> None:
        # 写入文件 (追加模式)
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(memory.__dict__, ensure_ascii=False) + '\n')
        
        # 更新缓存
        self._cache[memory.id] = memory
    
    async def get(self, memory_id: str) -> EpisodicMemory | None:
        return self._cache.get(memory_id)
    
    async def delete(self, memory_id: str) -> bool:
        # 标记删除 (不真正删除，重建文件)
        if memory_id in self._cache:
            self._cache[memory_id].is_deleted = True
            await self._rebuild_file()
            return True
        return False
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        session_id: str | None = None,
        since: datetime | None = None,
    ) -> list[EpisodicMemory]:
        results = []
        
        for memory in self._cache.values():
            # 过滤条件
            if memory.is_deleted:
                continue
            if session_id and memory.session_id != session_id:
                continue
            if since and memory.created_at < since:
                continue
            
            # 简单关键词匹配 (可升级为向量搜索)
            if query.lower() in memory.content.lower():
                results.append(memory)
            
            if len(results) >= limit:
                break
        
        return results
    
    async def get_recent(
        self, 
        days: int = 7, 
        limit: int = 100
    ) -> list[EpisodicMemory]:
        cutoff = datetime.now() - timedelta(days=days)
        return await self.search("", limit=limit, since=cutoff)
    
    def _load_to_cache(self) -> None:
        """加载到内存缓存"""
        if not self.file_path.exists():
            return
            
        with open(self.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    memory = EpisodicMemory(**data)
                    self._cache[memory.id] = memory


class SemanticMemoryStorage(MemoryStorage):
    """语义记忆存储 - ChromaDB向量数据库"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        import chromadb
        from chromadb.config import Settings
        
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="semantic_memory",
            metadata={"description": "Semantic memory storage"}
        )
        
        # 内存缓存
        self._cache: dict[str, SemanticMemory] = {}
    
    async def save(self, memory: SemanticMemory) -> None:
        # 生成向量嵌入
        if memory.embedding is None:
            memory.embedding = await self._generate_embedding(memory.content)
        
        # 存储到ChromaDB
        self.collection.upsert(
            ids=[memory.id],
            embeddings=[memory.embedding],
            documents=[memory.content],
            metadatas=[{
                "title": memory.title,
                "tags": ",".join(memory.tags),
                "is_fact": str(memory.is_fact),
                "priority": memory.priority.value
            }]
        )
        
        # 更新缓存
        self._cache[memory.id] = memory
    
    async def get(self, memory_id: str) -> SemanticMemory | None:
        if memory_id in self._cache:
            return self._cache[memory_id]
        
        # 从ChromaDB获取
        result = self.collection.get(ids=[memory_id])
        if result['ids']:
            return self._build_from_chroma(result)
        return None
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
        is_fact: bool | None = None,
    ) -> list[SemanticMemory]:
        # 生成查询向量
        query_embedding = await self._generate_embedding(query)
        
        # 向量相似度搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"is_fact": str(is_fact)} if is_fact is not None else None
        )
        
        memories = []
        for i, id_ in enumerate(results['ids'][0]):
            memory = await self.get(id_)
            if memory:
                memories.append(memory)
        
        return memories
    
    async def _generate_embedding(self, text: str) -> list[float]:
        """生成文本向量嵌入"""
        # 使用简单实现，生产环境可用 OpenAI/HuggingFace
        # 这里简化处理
        import hashlib
        vec = [float(c) / 255.0 for c in hashlib.md5(text.encode()).digest()[:32]]
        return vec + [0.0] * (32 - len(vec))  # 补齐到32维
```

### 4.4 记忆管理系统

```python
# memory/manager.py

from datetime import datetime, timedelta
from typing import AsyncGenerator
import asyncio

class MemoryManager:
    """
    记忆管理器 - 统一接口
    
    职责:
    1. 协调三层记忆
    2. 记忆检索
    3. 记忆整合
    4. 记忆淘汰
    """
    
    def __init__(
        self,
        workspace: Path,
        working_capacity: int = 20,
        episodic_retention_days: int = 30,
    ):
        self.workspace = workspace
        
        # 初始化各层存储
        self.working = WorkingMemoryStorage(max_size=working_capacity)
        self.episodic = EpisodicMemoryStorage(
            workspace / "memory" / "episodic"
        )
        self.semantic = SemanticMemoryStorage(
            str(workspace / "memory" / "chroma")
        )
        
        # 配置
        self.episodic_retention_days = episodic_retention_days
        
        # 启动后台任务
        self._consolidation_task = None
    
    async def add(
        self,
        content: str,
        memory_level: MemoryLevel = MemoryLevel.WORKING,
        **metadata
    ) -> Memory:
        """添加记忆"""
        if memory_level == MemoryLevel.WORKING:
            memory = WorkingMemory(
                content=content,
                **metadata
            )
            await self.working.save(memory)
            
        elif memory_level == MemoryLevel.EPISODIC:
            memory = EpisodicMemory(
                content=content,
                expires_at=datetime.now() + timedelta(days=self.episodic_retention_days),
                **metadata
            )
            await self.episodic.save(memory)
            
        elif memory_level == MemoryLevel.SEMANTIC:
            memory = SemanticMemory(
                content=content,
                **metadata
            )
            await self.semantic.save(memory)
        
        return memory
    
    async def recall(
        self,
        query: str,
        session_id: str | None = None,
    ) -> list[Memory]:
        """
        检索记忆 - 跨三层搜索
        
        策略:
        1. 先搜索工作记忆 (最高优先级)
        2. 再搜索情景记忆
        3. 最后搜索语义记忆
        """
        results = []
        
        # 1. 工作记忆
        working_results = await self.working.get_all()
        for m in working_results:
            if query.lower() in m.content.lower():
                results.append(m)
        
        # 2. 情景记忆
        episodic_results = await self.episodic.search(
            query, session_id=session_id
        )
        results.extend(episodic_results)
        
        # 3. 语义记忆 (向量搜索)
        semantic_results = await self.semantic.search(query)
        results.extend(semantic_results)
        
        return results
    
    async def consolidate(self) -> None:
        """
        记忆整合 - 定期执行
        
        任务:
        1. 将重要的情景记忆转为语义记忆
        2. 清理过期记忆
        3. 更新记忆重要性
        """
        # 获取近期重要记忆
        recent = await self.episodic.get_recent(days=7, limit=100)
        
        for memory in recent:
            # 计算重要性
            importance = self._calculate_importance(memory)
            
            # 高重要性 -> 转为语义记忆
            if importance > 0.7:
                semantic = SemanticMemory(
                    content=memory.content,
                    title=self._extract_title(memory.content),
                    summary=await self._generate_summary(memory.content),
                    is_fact=self._is_fact(memory.content),
                    tags=memory.tags,
                    priority=MemoryPriority.HIGH
                )
                await self.semantic.save(semantic)
                logger.info(f"Consolidated memory {memory.id} to semantic")
        
        # 清理过期记忆
        await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> None:
        """清理过期记忆"""
        now = datetime.now()
        
        # 扫描过期记忆
        for memory_id in list(self.episodic._cache.keys()):
            memory = self.episodic._cache[memory_id]
            if memory.expires_at and memory.expires_at < now:
                await self.episodic.delete(memory_id)
                logger.info(f"Deleted expired memory {memory_id}")
    
    def _calculate_importance(self, memory: Memory) -> float:
        """计算记忆重要性"""
        score = 0.5
        
        # 基于访问频率
        score += min(memory.access_count * 0.05, 0.3)
        
        # 基于优先级
        score += (memory.priority.value - 2) * 0.1
        
        # 基于内容关键词
        important_keywords = ["记住", "重要", "偏好", "不要忘记", "关键"]
        for kw in important_keywords:
            if kw in memory.content:
                score += 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def _extract_title(self, content: str) -> str:
        """提取标题"""
        # 简单实现：取前50字符
        return content[:50] + ("..." if len(content) > 50 else "")
    
    async def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        # 可调用LLM生成摘要
        return content[:200] + ("..." if len(content) > 200 else "")
    
    def _is_fact(self, content: str) -> bool:
        """判断是否是事实"""
        fact_indicators = ["是", "位于", "等于", "叫做", "称为"]
        return any(ind in content for ind in fact_indicators)
```

---

## 5. 技术栈选型与实现路径

### 5.1 技术栈总览

| 层级 | 技术选型 | 理由 |
|------|----------|------|
| **前端框架** | React 18 + TypeScript | 成熟稳定，生态丰富 |
| **状态管理** | Zustand | 轻量、简单、符合直觉 |
| **UI组件库** | shadcn/ui | 现代设计、可定制性强 |
| **可视化** | React Flow | 专业的节点图库 |
| **通信** | Socket.io | 双向通信、WebSocket封装 |
| **后端框架** | FastAPI | 高性能、异步支持 |
| **向量数据库** | ChromaDB | 轻量、易用、Python原生 |
| **LLM调用** | LiteLLM | 多提供商统一接口 |

### 5.2 实现路径规划

```
Phase 1: 基础架构 (第1-2周)
├── 搭建FastAPI后端骨架
├── 创建WebSocket通信层
├── 设计数据库模型
└── 搭建React前端基础

Phase 2: CoT思维链 (第3-4周)
├── 实现CoT引擎
├── 思维步骤数据模型
├── 思维链可视化组件
└── 与LLM集成

Phase 3: 记忆分层 (第5-6周)
├── Working Memory实现
├── Episodic Memory实现
├── Semantic Memory实现 (ChromaDB)
└── 记忆整合机制

Phase 4: 前端集成 (第7-8周)
├── ChatPanel组件
├── ThinkTree可视化
├── MemoryPanel组件
└── 状态管理集成

Phase 5: 优化与测试 (第9周)
├── 性能优化
├── 单元测试
├── 集成测试
└── Bug修复
```

### 5.3 关键文件结构

```
kaolalabot/
├── backend/                      # 新增后端服务
│   ├── main.py                  # FastAPI入口
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py          # 对话API
│   │   │   └── memory.py        # 记忆API
│   │   └── deps.py              # 依赖注入
│   ├── socket/
│   │   └── handler.py           # WebSocket处理
│   ├── agent/
│   │   ├── cot/
│   │   │   ├── engine.py        # CoT引擎
│   │   │   ├── prompts.py        # CoT提示词
│   │   │   └── error_handling.py
│   │   └── memory/
│   │       ├── models.py         # 记忆模型
│   │       ├── storage.py        # 存储实现
│   │       └── manager.py        # 记忆管理
│   └── services/
│       └── llm_service.py       # LLM服务
│
├── frontend/                     # React前端
│   ├── src/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
│
├── kaolalabot/                  # 原有核心模块
│   ├── bus/
│   ├── channels/
│   ├── providers/
│   └── ...
│
└── pyproject.toml
```

---

## 6. 性能优化与扩展性

### 6.1 性能优化策略

| 优化点 | 策略 | 预期效果 |
|--------|------|----------|
| **LLM调用** | 流式响应 + 批量处理 | 减少等待时间 |
| **向量检索** | 缓存 + 近似最近邻(ANN) | 毫秒级响应 |
| **记忆存储** | 分层缓存 + 异步写入 | 减少IO阻塞 |
| **前端渲染** | Virtual List + 懒加载 | 流畅滚动 |
| **WebSocket** | 连接池 + 心跳保活 | 稳定连接 |

### 6.2 扩展性设计

```python
# 可扩展设计示例

# 1. Provider插件化
class LLMProviderRegistry:
    """LLM提供商注册表"""
    _providers: dict[str, type[LLMProvider]] = {}
    
    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]):
        cls._providers[name] = provider_cls
    
    @classmethod
    def create(cls, name: str, **kwargs) -> LLMProvider:
        return cls._providers[name](**kwargs)

# 注册新提供商
LLMProviderRegistry.register("openai", OpenAIProvider)
LLMProviderRegistry.register("anthropic", AnthropicProvider)

# 2. 工具插件化
class ToolRegistry:
    """工具注册表 - 可动态加载"""
    _tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
    
    def load_from_module(self, module_path: str):
        """从模块动态加载工具"""
        import importlib
        module = importlib.import_module(module_path)
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, Tool):
                self.register(obj())

# 3. 记忆存储后端可插拔
class MemoryBackend(Protocol):
    async def save(self, memory: Memory): ...
    async def get(self, id: str) -> Memory | None: ...
    async def search(self, query: str) -> list[Memory]: ...

# 可以切换不同后端
class ChromaBackend(MemoryBackend): ...
class PineconeBackend(MemoryBackend): ...
class WeaviateBackend(MemoryBackend): ...
```

---

## 7. 测试策略与验收标准

### 7.1 测试金字塔

```
           ┌─────────────┐
           │   E2E测试   │  ← 少量，覆盖核心流程
          ┌──────────────┐
          │  集成测试    │  ← 中量，模块交互
         ┌───────────────┐
         │   单元测试    │  ← 大量，每个模块
        ┌────────────────┐
        │   静态检查    │  ← lint, type check
```

### 7.2 测试覆盖要求

| 模块 | 测试类型 | 覆盖率目标 | 关键测试用例 |
|------|----------|------------|--------------|
| CoT Engine | 单元+集成 | ≥80% | 推理链生成、错误回溯 |
| Memory System | 单元+集成 | ≥85% | 三层存储、检索、整合 |
| API | 集成 | ≥90% | 端点正确性、错误处理 |
| Frontend | E2E | 关键路径 | 发送消息、查看思维链 |

### 7.3 验收标准

#### 功能验收

- [ ] 用户可以发送消息并收到回复
- [ ] 思维链可以正确显示推理步骤
- [ ] 思维步骤可以折叠/展开
- [ ] 短期记忆正确保存当前会话
- [ ] 中期记忆可以跨会话检索
- [ ] 长期记忆支持语义搜索
- [ ] 记忆可以手动删除
- [ ] WebSocket连接稳定

#### 性能验收

- [ ] 首次响应时间 < 3秒
- [ ] 思维链渲染流畅 (60fps)
- [ ] 向量搜索响应 < 500ms
- [ ] 内存占用稳定 < 500MB

#### 稳定性验收

- [ ] 无崩溃运行 > 24小时
- [ ] 错误正确处理和恢复
- [ ] 日志完整可追溯

---

## 附录

### A. API响应示例

```json
// POST /api/chat/send
{
  "message": "帮我写个排序算法",
  "sessionId": "abc123"
}

// 响应 (WebSocket stream)
{
  "type": "thinking:step",
  "data": {
    "id": "step-1",
    "phase": "observe",
    "content": "理解用户需求：需要生成一个排序算法",
    "status": "completed"
  }
}

{
  "type": "thinking:step", 
  "data": {
    "id": "step-2",
    "phase": "reason",
    "content": "推理步骤1: 确定排序算法类型（快速排序、归并排序等）",
    "status": "active"
  }
}

{
  "type": "chat:message",
  "data": {
    "content": "# 快速排序实现\n\n以下是Python实现的快速排序算法...",
    "thinking": {
      "steps": [...],
      "finalConfidence": 0.95
    }
  }
}
```

### B. 配置示例

```yaml
# config/development.yaml
server:
  host: 0.0.0.0
  port: 8000

memory:
  working:
    capacity: 20
  episodic:
    retention_days: 30
  semantic:
    provider: chromadb
    persist_directory: ./data/chroma

cot:
  max_iterations: 10
  enable_reflection: true
  streaming: true

llm:
  provider: deepseek
  model: deepseek-chat
  temperature: 0.7
```

---

> 文档结束
