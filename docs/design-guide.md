# kaolalabot 项目设计指南

> 技术探索可以慢慢来，不必焦虑，让我们一起静静感受前沿技术的魅力。

本文档详细记录了 kaolalalabot 项目从 0 到 1 的设计思路、架构决策和实现细节。无论您是想学习 AI Agent 开发，还是想为项目贡献代码，本文档都将为您提供全面的指导。

## 📖 目录

- [设计理念](#设计理念)
- [架构演进](#架构演进)
- [核心架构图](#核心架构图)
- [技术选型](#技术选型)
- [模块设计](#模块设计)
- [开发规范](#开发规范)
- [学习路径](#学习路径)

---

## 🎯 设计理念

### 为什么创建 kaolalabot？

作为一名在读研究生，我在开发过程中发现：

1. **学习曲线陡峭**：现有 AI Agent 框架往往过于复杂，初学者难以入手
2. **文档不完善**：很多项目缺少详细的设计说明和学习资源
3. **过度工程化**：为了"炫技"而增加不必要的复杂度
4. **缺乏温度**：技术文档冷冰冰，缺少人文关怀

因此，kaolalabot 的设计遵循以下原则：

### 核心原则

#### 1. 渐进式复杂度

```
初学者 → 基础功能使用
    ↓
进阶者 → 理解模块交互
    ↓
专家 → 参与核心开发
```

- 入门简单：只需几行代码即可启动
- 扩展灵活：按需添加功能模块
- 深度足够：支持高级定制和优化

#### 2. 文档即代码

- 每个模块都有 README
- 关键代码都有注释
- 注释说明"为什么"而非"做什么"
- 提供丰富的示例代码

#### 3. 学习友好

- 清晰的错误提示
- 详细的日志输出
- 调试工具齐全
- 循序渐进的示例

#### 4. 工程规范

- 代码风格统一
- 测试覆盖核心功能
- CI/CD 自动化
- 版本管理严格

---

## 🏗️ 架构演进

### V0.1 - 原型阶段

**目标**：验证核心概念

```python
# 最简单的 Agent
class SimpleAgent:
    def __init__(self, api_key):
        self.client = OpenAI(api_key)
    
    def chat(self, message):
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message}]
        )
        return response.choices[0].message.content
```

**问题**：
- 没有模块化
- 无法扩展
- 缺少错误处理

### V0.5 - 模块化阶段

**改进**：
- 分离 LLM Provider
- 添加工具系统
- 引入消息总线

**架构**：
```
用户 → Channel → Agent → Tools
                  ↓
               Provider
```

**问题**：
- 模块耦合度高
- 测试困难
- 缺少持久化

### V1.0 - 当前版本

**核心特性**：
- 完整的模块化架构
- 多渠道支持
- 记忆系统
- 监控和日志
- 完善的测试套件

**架构**：详见 [核心架构图](#核心架构图)

### 未来规划

#### V1.5 - 增强版
- [ ] 多 Agent 协作
- [ ] 可视化调试界面
- [ ] 性能优化
- [ ] 更多渠道集成

#### V2.0 - 生态版
- [ ] 插件系统
- [ ] 技能市场
- [ ] 分布式部署
- [ ] 自动化工具链

---

## 🗺️ 核心架构图

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     用户界面层                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │ 飞书    │  │ 钉钉    │  │ Web     │  │ Voice   │     │
│  │ Channel │  │ Channel │  │ Channel │  │ Channel │     │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │
│       │           │           │           │            │
│       └───────────┴─────┬─────┴───────────┘            │
│                         │                              │
│                  ┌──────▼──────┐                       │
│                  │ ChannelMgr  │                       │
│                  └──────┬──────┘                       │
└─────────────────────────┼───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     消息总线层                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │              MessageBus (异步队列)               │    │
│  │  - inbound_queue (入站消息)                      │    │
│  │  - outbound_queue (出站消息)                     │    │
│  │  - event_system (事件分发)                       │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     Agent 核心层                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │               AgentLoop                         │    │
│  │  - 消息处理循环                                  │    │
│  │  - 上下文管理                                    │    │
│  │  - 意图识别                                    │    │
│  │  - 工具调度                                    │    │
│  └─────────────────────────────────────────────────┘    │
│         │              │              │                 │
│  ┌──────▼───┐   ┌─────▼────┐  ┌──────▼──────┐          │
│  │ Context  │   │   CoT    │  │   Tools     │          │
│  │ 管理器    │   │ 思维链   │  │ 注册表      │          │
│  └──────────┘   └──────────┘  └──────┬──────┘          │
└─────────────────────────────────────┼───────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────┐
│                     服务层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Memory   │  │ Session  │  │  RAG     │  │  User   │ │
│  │ 记忆系统 │  │ 会话管理 │  │ 知识增强 │  │  画像   │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Provider │  │  Scheduler│  │  MCP    │  │ Clawhub │ │
│  │ LLM 抽象 │  │  任务调度 │  │  桥接   │  │  技能   │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     基础设施层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Config  │  │  Logger  │  │ Monitor  │  │  Utils  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 数据流

#### 入站消息流

```
1. 用户发送消息
   ↓
2. Channel 接收并转换为统一格式
   ↓
3. ChannelManager 路由到 MessageBus.inbound
   ↓
4. AgentLoop 从队列获取消息
   ↓
5. 构建上下文 (Context)
   ↓
6. 意图识别 (Intent Classifier)
   ↓
7. 选择执行路径:
   - Native Command → 直接执行
   - Tool Call → 工具调用
   - Chat → LLM 对话
   ↓
8. 生成响应
```

#### 出站消息流

```
1. AgentLoop 生成响应
   ↓
2. 发送到 MessageBus.outbound
   ↓
3. ChannelManager 根据 channel 字段路由
   ↓
4. 对应 Channel.send() 执行发送
   ↓
5. 用户收到消息
```

---

## 🛠️ 技术选型

### 核心依赖

#### 1. Python 3.11+

**选择理由**：
- 性能提升：比 3.10 快 10-60%
- 类型系统增强：更精确的类型检查
- 异步改进：更好的 async/await 支持
- 长期支持：主流版本

**替代方案**：3.10、3.12
**不选原因**：
- 3.10：缺少新特性
- 3.12：生态尚未完全兼容

#### 2. FastAPI + Uvicorn

**选择理由**：
- 异步原生：基于 asyncio
- 自动文档：Swagger UI 自动生成
- 类型安全：基于 Pydantic
- 高性能：Starlette 底层

**替代方案**：Flask、Django
**不选原因**：
- Flask：同步模型，性能受限
- Django：过于重量级

#### 3. Pydantic v2

**选择理由**：
- 数据验证：自动类型检查和转换
- 配置管理：结构化配置
- 文档生成：JSON Schema 支持
- 性能优秀：Rust 核心

**替代方案**：attrs、dataclasses
**不选原因**：
- attrs：缺少验证
- dataclasses：功能简单

#### 4. LiteLLM

**选择理由**：
- 统一接口：支持 100+ LLM
- 降级机制：自动故障切换
- 成本追踪：使用量统计
- 本地缓存：减少 API 调用

**替代方案**：直接调用各厂商 SDK
**不选原因**：
- 代码重复：每个 provider 都要实现
- 维护困难：API 变更需更新代码

#### 5. pytest

**选择理由**：
- 简洁易用：无需样板代码
- 插件丰富：asyncio、cov 等
- 社区活跃：持续更新
- 集成友好：CI/CD 支持

**替代方案**：unittest、nose
**不选原因**：
- unittest：样板代码多
- nose：已停止维护

### 架构模式

#### 1. 消息总线 (Message Bus)

**核心思想**：解耦生产者和消费者

```python
# 简化的 MessageBus
class MessageBus:
    def __init__(self):
        self.inbound_queue = asyncio.Queue()
        self.outbound_queue = asyncio.Queue()
        self.subscribers = {}
    
    async def publish(self, event):
        """发布事件"""
        for subscriber in self.subscribers.get(event.type, []):
            await subscriber(event)
    
    def subscribe(self, event_type, handler):
        """订阅事件"""
        self.subscribers.setdefault(event_type, []).append(handler)
```

**优势**：
- 松耦合：模块间不直接依赖
- 可扩展：轻松添加新消费者
- 可测试：独立测试各组件
- 异步友好：天然支持 async

#### 2. 依赖注入 (Dependency Injection)

**核心思想**：将依赖作为参数传递

```python
# 不好的做法：硬编码依赖
class AgentLoop:
    def __init__(self):
        self.provider = OpenAIProvider()  # ❌ 硬编码
        self.memory = SQLiteMemory()      # ❌ 硬编码

# 好的做法：依赖注入
class AgentLoop:
    def __init__(self, provider, memory, tool_registry):
        self.provider = provider          # ✅ 注入
        self.memory = memory              # ✅ 注入
        self.tool_registry = tool_registry # ✅ 注入
```

**优势**：
- 可测试：轻松 mock 依赖
- 可替换：运行时切换实现
- 可配置：通过配置组装

#### 3. 策略模式 (Strategy Pattern)

**应用于**：Provider 选择、工具执行

```python
# Provider 策略
class ProviderStrategy:
    def __init__(self, providers):
        self.providers = providers
        self.current_index = 0
    
    def get_provider(self):
        """获取当前 provider，失败时自动切换"""
        provider = self.providers[self.current_index]
        if not provider.is_available():
            self.current_index = (self.current_index + 1) % len(self.providers)
            return self.get_provider()
        return provider
```

---

## 📦 模块设计

### 核心模块职责

#### 1. Agent 模块 (`kaolalabot/agent/`)

**职责**：消息处理核心逻辑

**关键类**：
- `AgentLoop`：主循环，处理消息
- `Context`：对话上下文管理
- `ToolRegistry`：工具注册和调度
- `IntentClassifier`：意图识别

**设计要点**：
```python
# AgentLoop 简化版
class AgentLoop:
    async def run(self):
        """主循环"""
        while True:
            message = await self.bus.inbound.get()
            try:
                response = await self.process(message)
                await self.bus.outbound.put(response)
            except Exception as e:
                logger.error(f"处理失败：{e}")
    
    async def process(self, message):
        """处理单条消息"""
        # 1. 构建上下文
        context = await self.context.build(message)
        
        # 2. 意图识别
        intent = await self.classify(message)
        
        # 3. 选择执行路径
        if intent == "native_command":
            return await self.execute_native(message)
        elif intent == "tool_call":
            return await self.execute_tools(context)
        else:
            return await self.chat(context)
```

#### 2. Channels 模块 (`kaolalabot/channels/`)

**职责**：外部平台集成

**设计模式**：策略模式 + 工厂模式

```python
# 统一接口
class BaseChannel(ABC):
    @abstractmethod
    async def start(self):
        """启动通道"""
    
    @abstractmethod
    async def stop(self):
        """停止通道"""
    
    @abstractmethod
    async def send(self, message):
        """发送消息"""
    
    @abstractmethod
    async def _handle_message(self, raw_message):
        """处理接收到的消息"""
```

**扩展新通道**：
```python
class WeChatChannel(BaseChannel):
    async def start(self):
        # 连接微信 API
        pass
    
    async def send(self, message):
        # 发送微信消息
        pass
```

#### 3. Memory 模块 (`kaolalabot/memory/`)

**职责**：持久化对话历史

**核心概念**：
- 情景记忆 (Episodic)：具体对话
- 语义记忆 (Semantic)：抽象知识
- 工作记忆 (Working)：当前上下文

**存储结构**：
```
memory/
├── episodic/      # 按会话存储
│   └── {session_id}.jsonl
├── semantic/      # 知识库
│   └── chroma_db/
└── working/       # 内存缓存
    └── {session_id}.json
```

#### 4. Providers 模块 (`kaolalabot/providers/`)

**职责**：LLM 抽象层

**设计要点**：
- 统一接口：所有 provider 实现相同方法
- 自动降级：失败时切换到备用 provider
- 请求限流：防止 API 过载

```python
class ProviderRegistry:
    def __init__(self, config):
        self.providers = []
        self.load_providers(config)
    
    def load_providers(self, config):
        """加载所有配置的 provider"""
        for name, cfg in config.providers.items():
            provider = self.create_provider(name, cfg)
            self.providers.append(provider)
    
    def get_available_provider(self):
        """获取可用的 provider（带降级）"""
        for provider in self.providers:
            if provider.is_available():
                return provider
        raise Exception("所有 provider 都不可用")
```

#### 5. Bus 模块 (`kaolalabot/bus/`)

**职责**：消息总线和事件系统

**核心组件**：
- `MessageBus`：消息队列
- `EventManager`：事件分发
- `RateLimiter`：请求限流

**实现要点**：
```python
class MessageBus:
    def __init__(self):
        self.inbound = asyncio.Queue()
        self.outbound = asyncio.Queue()
        self.events = EventManager()
    
    async def process_inbound(self):
        """处理入站消息"""
        while True:
            message = await self.inbound.get()
            await self.events.publish("message.received", message)
    
    async def process_outbound(self):
        """处理出站消息"""
        while True:
            message = await self.outbound.get()
            await self.events.publish("message.sent", message)
```

---

## 📝 开发规范

### 代码风格

#### 1. 命名规范

```python
# 类名：大驼峰
class MessageBus:
    pass

# 函数和变量：小写 + 下划线
def process_message(message):
    user_name = "John"

# 常量：全大写 + 下划线
MAX_RETRIES = 3
API_KEY = "sk-..."

# 私有方法：单下划线前缀
def _internal_helper():
    pass

# 魔术方法：双下划线
class MyClass:
    def __init__(self):
        pass
```

#### 2. 类型注解

```python
# 必须使用类型注解
def greet(name: str, age: int) -> str:
    return f"{name} is {age} years old"

# 复杂类型
from typing import List, Dict, Optional, Union

def process_items(
    items: List[str],
    config: Optional[Dict[str, any]] = None
) -> Union[str, List[str]]:
    pass

# 异步函数
async def fetch_data(url: str) -> dict:
    pass
```

#### 3. 文档字符串

```python
def calculate_distance(
    point_a: Tuple[float, float],
    point_b: Tuple[float, float]
) -> float:
    """
    计算两点之间的欧几里得距离
    
    Args:
        point_a: 第一个点的坐标 (x, y)
        point_b: 第二个点的坐标 (x, y)
    
    Returns:
        两点之间的距离
    
    Raises:
        ValueError: 当坐标维度不匹配时
    
    Example:
        >>> calculate_distance((0, 0), (3, 4))
        5.0
    """
    if len(point_a) != 2 or len(point_b) != 2:
        raise ValueError("坐标必须是二维的")
    
    return math.sqrt((point_a[0] - point_b[0])**2 + 
                     (point_a[1] - point_b[1])**2)
```

### 测试规范

#### 1. 测试组织

```
tests/
├── test_<module>.py       # 单元测试
├── test_<module>_integration.py  # 集成测试
└── fixtures/              # 测试夹具
```

#### 2. 测试命名

```python
def test_<功能>_<场景>_<预期结果>():
    pass

# 示例
def test_web_search_with_invalid_query_returns_empty():
    pass
```

#### 3. 测试模板

```python
import pytest
from kaolalabot.agent import AgentLoop

class TestAgentLoop:
    """测试 AgentLoop 类"""
    
    @pytest.fixture
    def agent(self, mock_provider, mock_bus):
        """创建测试用的 agent"""
        return AgentLoop(
            provider=mock_provider,
            bus=mock_bus
        )
    
    def test_initialization(self, agent):
        """测试初始化"""
        assert agent is not None
        assert agent.provider is not None
    
    @pytest.mark.asyncio
    async def test_process_message(self, agent):
        """测试消息处理"""
        message = {"content": "Hello", "session_id": "test"}
        response = await agent.process(message)
        assert response is not None
```

### Git 工作流

#### 1. 分支策略

```
main          - 主分支，随时可发布
develop       - 开发分支
feature/*     - 功能分支
fix/*         - 修复分支
hotfix/*      - 紧急修复
```

#### 2. 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建工具

**示例**：
```
feat(agent): 添加意图识别功能

- 实现基于规则的意图分类
- 支持置信度评估
- 添加单元测试

Closes #123
```

---

## 🎓 学习路径

### 初学者路径

#### 第 1 周：基础了解

**目标**：运行第一个 Agent

```bash
# 1. 克隆项目
git clone https://github.com/yourname/kaolalabot.git

# 2. 安装依赖
pip install -r requirements-backend.txt

# 3. 配置 API Key
kaolalabot onboard

# 4. 启动 Agent
kaolalabot agent
```

**阅读材料**：
- [README.md](../README.md) - 项目概述
- [quickstart.md](../docs/quickstart.md) - 快速开始

#### 第 2 周：理解架构

**目标**：理解消息流

**任务**：
1. 阅读 `kaolalabot/agent/loop.py`
2. 绘制消息流程图
3. 添加日志输出跟踪消息

**阅读材料**：
- [agent/README.md](../kaolalabot/agent/README.md)
- [bus/README.md](../kaolalabot/bus/README.md)

#### 第 3 周：添加功能

**目标**：实现一个新工具

**任务**：
1. 创建 `kaolalabot/agent/tools/weather.py`
2. 实现天气查询功能
3. 注册到 ToolRegistry
4. 编写测试

**示例**：
```python
from .base import BaseTool

class WeatherTool(BaseTool):
    async def execute(self, query: str) -> str:
        # 调用天气 API
        return f"Weather: Sunny"
```

### 进阶者路径

#### 第 1 个月：深入核心

**目标**：理解设计决策

**任务**：
1. 阅读所有核心模块源码
2. 理解消息总线设计
3. 分析性能瓶颈
4. 提出优化建议

#### 第 2 个月：贡献代码

**目标**：成为贡献者

**任务**：
1. 选择 open issue
2. 实现解决方案
3. 提交 Pull Request
4. 根据反馈修改

#### 第 3 个月：主导功能

**目标**：主导新功能开发

**任务**：
1. 提出功能设计
2. 编写设计文档
3. 实现核心逻辑
4. 指导新人

### 专家路径

**目标**：成为维护者

**职责**：
- 审查 Pull Request
- 指导社区成员
- 规划技术路线
- 解决复杂问题

---

## 🔧 调试指南

### 常用调试技巧

#### 1. 启用详细日志

```python
# config.json
{
  "logging": {
    "level": "DEBUG",
    "format": "detailed"
  }
}
```

#### 2. 使用断点

```python
import pdb

def problematic_function():
    pdb.set_trace()  # 设置断点
    # ... 代码
```

#### 3. 性能分析

```bash
# 使用 cProfile
python -m cProfile -o output.prof kaolalabot/server.py

# 查看分析结果
python -m pstats output.prof
```

### 常见问题

#### Q1: Agent 不响应

**排查步骤**：
1. 检查日志：`logs/agent.log`
2. 验证 API Key：`kaolalabot status`
3. 测试 Provider：`python scripts/check_model.py`

#### Q2: 工具调用失败

**排查步骤**：
1. 检查工具注册：`ToolRegistry.list_tools()`
2. 验证参数格式
3. 查看工具日志

#### Q3: 内存泄漏

**排查步骤**：
1. 使用 memory_profiler
2. 检查缓存清理
3. 分析对象引用

---

## 📚 推荐资源

### 书籍

- 《Python 异步编程》- 深入理解 asyncio
- 《架构整洁之道》- 软件架构原则
- 《设计模式》- 经典设计模式

### 在线课程

- [Python Asyncio](https://realpython.com/async-io-python/)
- [FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)

### 开源项目

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用框架
- [AutoGen](https://github.com/microsoft/autogen) - 多 Agent 系统

---

## 🤝 参与贡献

感谢您阅读到这里！我们欢迎各种形式的贡献：

- 💻 提交代码
- 📖 完善文档
- 🐛 报告问题
- 💡 提出建议

详见 [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**最后更新**: 2026-03-04

**维护者**: kaolalabot Team

**许可证**: MIT
