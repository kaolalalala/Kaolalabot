# kaolalabot 快速开始指南

> 5 分钟快速上手，开始与 AI 助手的对话！

## 🚀 快速开始（5 分钟）

### 步骤 1: 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/kaolalabot.git
cd kaolalabot
```

### 步骤 2: 安装依赖

```bash
# 确保 Python 3.11+
python --version  # 应该 >= 3.11

# 安装后端依赖
pip install -r requirements-backend.txt

# 安装项目本身
pip install -e .
```

### 步骤 3: 初始化配置

```bash
# 运行配置向导
kaolalabot onboard
```

这会创建一个 `config.json` 文件。

### 步骤 4: 配置 API 密钥

编辑 `config.json`，添加你的 LLM API 密钥：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-your-api-key-here",
      "model": "openai/gpt-3.5-turbo"
    }
  }
}
```

**获取 API 密钥**：
- [OpenRouter](https://openrouter.ai/) - 支持多种模型
- [OpenAI](https://platform.openai.com/) - GPT 系列
- [Anthropic](https://console.anthropic.com/) - Claude 系列
- 或其他 LiteLLM 支持的提供商

### 步骤 5: 启动 Agent

```bash
# 交互式聊天
kaolalabot agent

# 或直接发送消息
kaolalabot agent -m "你好，请介绍一下自己"
```

🎉 **恭喜！你已经成功运行了 kaolalabot！**

---

## 💬 基础使用

### 命令行聊天

```bash
# 启动交互式会话
kaolalabot agent

# 你会看到提示符
> 你好
你好！我是 kaolalabot，你的 AI 助手。有什么我可以帮助你的吗？

> 帮我写一个 Python 函数，计算斐波那契数列
好的，这是一个计算斐波那契数列的 Python 函数：

def fibonacci(n):
    if n <= 1:
        return n
    else:
        return fibonacci(n-1) + fibonacci(n-2)

# 使用示例
for i in range(10):
    print(fibonacci(i))
```

### 使用工具

kaolalabot 支持多种工具：

#### 1. 网络搜索

```
> 请搜索最新的 AI 新闻

正在使用 web_search 工具搜索...
[搜索结果]
1. OpenAI 发布新模型 GPT-5
2. Google DeepMind 取得重大突破
...
```

#### 2. 文件操作

```
> 请把刚才的内容保存到 workspace/notes.txt

正在写入文件...
✅ 已保存到 workspace/notes.txt

> 读取 workspace/notes.txt

[文件内容]
...
```

#### 3. 浏览器自动化

```
> 访问 https://example.com 并截图

正在使用 Playwright...
✅ 截图已保存到 workspace/screenshots/example.png
```

---

## 🔧 配置选项

### 基础配置

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-...",
      "model": "openai/gpt-3.5-turbo",
      "temperature": 0.7
    }
  },
  "logging": {
    "level": "INFO",
    "format": "detailed"
  },
  "memory": {
    "working_capacity": 20,
    "episodic_retention_days": 30
  }
}
```

### 高级配置

#### 多 Provider 配置

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-...",
      "priority": 1
    },
    "openai": {
      "apiKey": "sk-...",
      "priority": 2
    },
    "anthropic": {
      "apiKey": "sk-ant-...",
      "priority": 3
    }
  },
  "fallback": {
    "enabled": true,
    "max_retries": 3
  }
}
```

#### 通道配置

```json
{
  "channels": {
    "feishu": {
      "enabled": false,
      "appId": "cli_xxx",
      "appSecret": "xxx"
    },
    "web": {
      "enabled": true,
      "port": 8765
    }
  }
}
```

---

## 🌐 使用 Web 界面

### 启动 Web 服务

```bash
# 启动网关（包含 Web 界面）
kaolalabot gateway
```

### 访问界面

打开浏览器访问：`http://localhost:8765`

**功能**：
- 💬 实时聊天
- 🧠 查看记忆
- 🔧 工具执行日志
- 📊 系统状态监控

---

## 📚 下一步学习

### 入门教程

1. [项目架构说明](docs/design-guide.md) - 了解整体设计
2. [Agent 模块文档](kaolalabot/agent/README.md) - 学习 Agent 核心
3. [记忆系统文档](kaolalabot/memory/README.md) - 理解记忆管理

### 实践项目

#### 项目 1: 创建自定义工具

```python
# 在 kaolalabot/agent/tools/ 创建 weather.py
from .base import BaseTool

class WeatherTool(BaseTool):
    async def execute(self, city: str) -> str:
        # 调用天气 API
        return f"{city} 的天气：晴朗，25°C"

# 注册工具
# 在 kaolalabot/agent/tools/__init__.py 添加
from .weather import WeatherTool
```

#### 项目 2: 添加新通道

```python
# 在 kaolalabot/channels/ 创建 wechat.py
from .base import BaseChannel

class WeChatChannel(BaseChannel):
    async def start(self):
        # 连接微信 API
        pass
    
    async def send(self, message):
        # 发送微信消息
        pass
```

#### 项目 3: 定时任务

```python
# 配置定时任务
{
  "scheduler": {
    "tasks": [
      {
        "name": "每日新闻",
        "schedule_type": "cron",
        "cron_expression": "0 8 * * *",  # 每天早上 8 点
        "runner": "agent_message",
        "params": {
          "message": "请发送最新的 AI 新闻"
        }
      }
    ]
  }
}
```

---

## 🐛 常见问题

### Q1: 启动时提示 "ModuleNotFoundError"

**解决方案**：
```bash
# 确保已安装所有依赖
pip install -r requirements-backend.txt
pip install -e .

# 或重新安装
pip install -e . --force-reinstall
```

### Q2: API 密钥错误

**解决方案**：
1. 检查 `config.json` 中的密钥是否正确
2. 确认账户有足够余额
3. 测试 API 连接：

```bash
python scripts/check_model.py
```

### Q3: 工具执行失败

**解决方案**：
```bash
# 查看详细日志
kaolalabot gateway --log-level DEBUG

# 检查工具注册
python -c "from kaolalabot.agent import ToolRegistry; print(ToolRegistry().list_tools())"
```

### Q4: 内存不足

**解决方案**：
```bash
# 清理记忆缓存
python -c "from pathlib import Path; import shutil; shutil.rmtree(Path('workspace/memory'))"

# 调整配置
# config.json
{
  "memory": {
    "working_capacity": 10,  # 减小容量
    "episodic_retention_days": 7  # 缩短保留期
  }
}
```

---

## 🤝 获取帮助

### 资源

- 📖 [完整文档](docs/design-guide.md)
- 💬 [GitHub Issues](https://github.com/YOUR_USERNAME/kaolalabot/issues)
- 📧 Email: kaolalabot@example.com

### 社区

- 提问前先搜索是否有类似问题
- 提供详细的错误信息和日志
- 说明你的环境和复现步骤

---

## 🎯 学习路径建议

### 第 1 周：熟悉基础

- ✅ 运行第一个 Agent
- ✅ 尝试各种工具
- ✅ 阅读主 README

### 第 2 周：理解架构

- ✅ 阅读设计指南
- ✅ 学习消息总线
- ✅ 理解记忆系统

### 第 3 周：动手实践

- ✅ 创建自定义工具
- ✅ 添加新功能
- ✅ 编写测试

### 第 4 周：深入优化

- ✅ 性能分析
- ✅ 代码重构
- ✅ 贡献代码

---

## 📝 示例代码

### 最简单的 Agent

```python
from kaolalabot import AgentLoop, MessageBus, ProviderRegistry

# 创建组件
bus = MessageBus()
providers = ProviderRegistry(config)
agent = AgentLoop(bus=bus, providers=providers)

# 运行
import asyncio
asyncio.run(agent.run())
```

### 自定义命令

```python
from kaolalabot.cli import commands

@commands.app.command("hello")
def hello():
    """打招呼命令"""
    print("Hello, World!")

# 运行
# kaolalabot hello
```

---

**祝你使用愉快！** 🎉

如有任何问题，欢迎随时提问。技术探索可以慢慢来，不必焦虑，让我们一起感受技术的魅力！
