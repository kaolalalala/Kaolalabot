# Bus 模块 - 消息总线系统

> 消息总线是 kaolalabot 的神经系统，负责各模块间的通信和事件分发。

## 📖 目录

- [功能说明](#功能说明)
- [核心架构](#核心架构)
- [使用方法](#使用方法)
- [API 参考](#api-参考)
- [实现原理](#实现原理)
- [最佳实践](#最佳实践)

---

## 🎯 功能说明

### 核心职责

1. **消息传递**：在 Channel 和 Agent 之间传递消息
2. **事件分发**：发布/订阅模式的事件系统
3. **流量控制**：基于令牌桶的限流机制
4. **解耦模块**：减少模块间直接依赖

### 为什么需要消息总线？

#### 没有消息总线的问题

```python
# ❌ 紧耦合的设计
class FeishuChannel:
    def __init__(self):
        self.agent = AgentLoop()  # 直接依赖 Agent
    
    async def on_message(self, msg):
        response = await self.agent.process(msg)  # 直接调用
        await self.send(response)
```

**问题**：
- Channel 和 Agent 强耦合
- 难以添加新的消费者
- 无法统一处理消息
- 测试困难

#### 使用消息总线

```python
# ✅ 松耦合的设计
class FeishuChannel:
    def __init__(self, bus):
        self.bus = bus  # 只依赖总线
    
    async def on_message(self, msg):
        await self.bus.inbound.put(msg)  # 发布到总线

class AgentLoop:
    def __init__(self, bus):
        self.bus = bus
    
    async def run(self):
        msg = await self.bus.inbound.get()  # 从总线消费
        response = await self.process(msg)
        await self.bus.outbound.put(response)
```

**优势**：
- Channel 和 Agent 互不了解
- 可添加多个消费者
- 统一的消息处理
- 易于测试和 mock

---

## 🏗️ 核心架构

### 组件图

```
┌─────────────────────────────────────────────────────┐
│                   MessageBus                        │
│  ┌───────────────────────────────────────────────┐  │
│  │  Inbound Queue (入站队列)                      │  │
│  │  - Channel 发送消息到这里                      │  │
│  │  - Agent 从这里消费                           │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  Outbound Queue (出站队列)                     │  │
│  │  - Agent 发送响应到这里                        │  │
│  │  - Channel 从这里消费并发送给用户              │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  Event Manager (事件管理器)                    │  │
│  │  - 发布/订阅模式                               │  │
│  │  - 支持异步回调                                │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  Rate Limiter (限流器)                         │  │
│  │  - 令牌桶算法                                  │  │
│  │  - 防止 API 过载                               │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 数据流

```
用户消息
   ↓
Channel 接收
   ↓
bus.inbound.put(message)
   ↓
AgentLoop 消费
   ↓
处理并生成响应
   ↓
bus.outbound.put(response)
   ↓
Channel 消费并发送
   ↓
用户收到响应
```

---

## 📖 使用方法

### 初始化

```python
from kaolalabot.bus import MessageBus, EventManager, RateLimiter

# 创建消息总线
bus = MessageBus(
    max_queue_size=1000,  # 队列最大长度
    rate_limit=100,       # 每秒请求数限制
)

# 启动后台任务
async def start_bus():
    asyncio.create_task(bus.process_inbound())
    asyncio.create_task(bus.process_outbound())
```

### 发布和订阅事件

```python
from kaolalabot.bus.events import EventManager, Event

# 创建事件管理器
event_manager = EventManager()

# 定义事件处理器
async def on_message_received(event: Event):
    print(f"收到消息：{event.data}")

# 订阅事件
event_manager.subscribe("message.received", on_message_received)

# 发布事件
await event_manager.publish("message.received", {
    "content": "Hello",
    "from": "user123"
})
```

### 使用限流器

```python
from kaolalabot.bus import RateLimiter

# 创建限流器
limiter = RateLimiter(
    rate=10,    # 每秒 10 个令牌
    capacity=20  # 桶容量 20
)

# 在 API 调用前检查
async def call_api():
    await limiter.acquire()  # 等待令牌
    # 执行 API 调用
    response = await api.request()
    return response
```

---

## 📚 API 参考

### MessageBus

#### 属性

```python
class MessageBus:
    inbound: asyncio.Queue      # 入站消息队列
    outbound: asyncio.Queue     # 出站消息队列
    events: EventManager        # 事件管理器
    limiter: RateLimiter        # 限流器
```

#### 方法

```python
class MessageBus:
    async def process_inbound(self) -> None:
        """
        处理入站消息（后台任务）
        
        从 inbound 队列消费消息并发布事件
        """
    
    async def process_outbound(self) -> None:
        """
        处理出站消息（后台任务）
        
        从 outbound 队列消费消息并发送
        """
    
    async def send_to_agent(self, message: dict) -> None:
        """
        发送消息到 Agent
        
        Args:
            message: 消息字典，包含 content, session_id 等
        """
    
    async def send_to_channel(self, message: dict) -> None:
        """
        发送消息到 Channel
        
        Args:
            message: 响应字典，包含 content, channel 等
        """
```

### EventManager

```python
class EventManager:
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型，如 "message.received"
            handler: 异步回调函数
        """
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 要移除的处理器
        """
    
    async def publish(self, event_type: str, data: any) -> None:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
    
    async def publish_wait(self, event_type: str, data: any) -> list:
        """
        发布事件并等待所有处理器完成
        
        Returns:
            所有处理器的返回值列表
        """
```

### RateLimiter

```python
class RateLimiter:
    def __init__(self, rate: float = 10.0, capacity: float = 20.0):
        """
        初始化限流器
        
        Args:
            rate: 令牌生成速率（个/秒）
            capacity: 桶容量
        """
    
    async def acquire(self, tokens: float = 1.0) -> None:
        """
        获取令牌（阻塞直到有足够令牌）
        
        Args:
            tokens: 需要的令牌数
        """
    
    def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        尝试获取令牌（立即返回）
        
        Args:
            tokens: 需要的令牌数
        
        Returns:
            是否成功获取
        """
```

---

## 🔍 实现原理

### 1. 异步队列实现

```python
class MessageBus:
    def __init__(self, max_queue_size: int = 1000):
        # 使用 asyncio.Queue 实现异步 FIFO 队列
        self.inbound = asyncio.Queue(maxsize=max_queue_size)
        self.outbound = asyncio.Queue(maxsize=max_queue_size)
    
    async def process_inbound(self):
        """持续处理入站消息"""
        while True:
            # 阻塞等待新消息
            message = await self.inbound.get()
            
            try:
                # 发布事件
                await self.events.publish("message.received", message)
                
                # 转发给 Agent
                await self._forward_to_agent(message)
            finally:
                # 标记任务完成
                self.inbound.task_done()
```

**关键点**：
- `asyncio.Queue` 天然支持异步生产者 - 消费者模式
- `task_done()` 用于队列管理
- `maxsize` 防止内存溢出

### 2. 发布/订阅模式

```python
class EventManager:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, data: any):
        """异步通知所有订阅者"""
        handlers = self._subscribers.get(event_type, [])
        
        # 并发执行所有处理器
        tasks = [handler(Event(event_type, data)) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
```

**优势**：
- 解耦发布者和订阅者
- 支持多个订阅者
- 并发执行处理器

### 3. 令牌桶限流

```python
class RateLimiter:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate          # 令牌生成速率
        self.capacity = capacity  # 桶容量
        self.tokens = capacity    # 当前令牌数
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: float = 1.0):
        """获取令牌"""
        async with self._lock:
            while True:
                # 补充令牌
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                # 检查是否有足够令牌
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                # 计算等待时间
                wait_time = (tokens - self.tokens) / self.rate
                
            # 释放锁并等待（避免阻塞其他协程）
            self._lock.release()
            await asyncio.sleep(wait_time)
            await self._lock.acquire()
```

**算法说明**：
- 令牌以固定速率生成
- 桶满时丢弃多余令牌
- 请求消耗令牌，无令牌时等待

---

## 💡 最佳实践

### 1. 消息格式标准化

```python
# ✅ 推荐：统一的消息格式
message = {
    "id": "msg_123",
    "type": "text",  # text, image, file, etc.
    "content": "Hello",
    "session_id": "session_456",
    "channel": "feishu",
    "timestamp": "2026-03-04T12:00:00Z",
    "metadata": {
        "sender": "user123",
        "priority": "normal"
    }
}

# ❌ 避免：不一致的格式
message = {"text": "Hello"}  # 缺少必要字段
```

### 2. 事件命名规范

```python
# ✅ 推荐：使用动词。名词 格式
"message.received"
"message.sent"
"session.started"
"session.ended"
"tool.executed"

# ❌ 避免：模糊的命名
"new_message"
"msg"
"event1"
```

### 3. 错误处理

```python
# ✅ 推荐：完善的错误处理
async def process_message(message):
    try:
        await bus.send_to_agent(message)
    except asyncio.QueueFull:
        logger.error("队列已满，丢弃消息")
    except Exception as e:
        logger.exception(f"处理失败：{e}")
        # 发布错误事件
        await bus.events.publish("message.error", {
            "message": message,
            "error": str(e)
        })

# ❌ 避免：忽略错误
async def process_message(message):
    await bus.send_to_agent(message)  # 没有异常处理
```

### 4. 性能优化

```python
# ✅ 推荐：批量处理
async def process_batch():
    batch = []
    while not bus.inbound.empty():
        batch.append(await bus.inbound.get())
        if len(batch) >= 10:  # 批量大小
            await process_messages(batch)
            batch = []

# ❌ 避免：单个处理
async def process_one_by_one():
    while True:
        msg = await bus.inbound.get()
        await process_message(msg)  # 每个消息都处理
```

### 5. 监控和日志

```python
# ✅ 推荐：添加监控
class MonitoredMessageBus(MessageBus):
    def __init__(self):
        super().__init__()
        self.metrics = {
            "inbound_count": 0,
            "outbound_count": 0,
            "error_count": 0
        }
    
    async def process_inbound(self):
        while True:
            try:
                message = await self.inbound.get()
                self.metrics["inbound_count"] += 1
                # ... 处理逻辑
            except Exception as e:
                self.metrics["error_count"] += 1
                logger.error(f"处理入站消息失败：{e}")
```

---

## 🐛 常见问题

### Q1: 消息丢失怎么办？

**A**: 消息总线使用持久化队列（可选），关键消息可以：

```python
# 启用持久化
bus = MessageBus(persistent=True, storage_path="data/queue")

# 或使用事件溯源
await bus.events.publish("message.received", data, persist=True)
```

### Q2: 如何处理消息优先级？

**A**: 使用多个队列：

```python
class PriorityMessageBus:
    def __init__(self):
        self.high_priority = asyncio.Queue()
        self.normal_priority = asyncio.Queue()
    
    async def process(self):
        # 优先处理高优先级队列
        if not self.high_priority.empty():
            msg = await self.high_priority.get()
        else:
            msg = await self.normal_priority.get()
        await self.handle(msg)
```

### Q3: 如何调试消息流？

**A**: 启用详细日志：

```python
# config.json
{
  "bus": {
    "logging": {
      "enabled": true,
      "level": "DEBUG",
      "log_messages": true  # 记录所有消息
    }
  }
}
```

---

## 📚 相关资源

- [ asyncio 官方文档](https://docs.python.org/3/library/asyncio-queue.html)
- [发布/订阅模式](https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern)
- [令牌桶算法](https://en.wikipedia.org/wiki/Token_bucket)

---

**最后更新**: 2026-03-04

**维护者**: kaolalabot Team
