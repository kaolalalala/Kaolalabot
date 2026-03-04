# kaolalabot 🐨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

<div align="center">
  
```
  🐨 考拉小助手 (kaolalabot)
  
     ╭◜◝ ͡ ◜◝ ͡ ◜◝╮
     (  ˃̶͈◡˂ ̶͈ )  技术探索可以慢慢来
      ╰◟◞ ͜ ◟◞ ͜ ◟◞╯   不必焦虑～
       ╰━━━━━━━━━╯
```

> **考拉小助手** 的命名理念源于我们倡导的学习态度：技术探索可以慢慢来，不必焦虑，让我们一起静静感受前沿技术的魅力，共同探索未来的无限可能。
</div>

功能强大的 AI Agent 框架，支持多渠道集成与高级 AI 能力。这是我作为一名在读研究生利用闲暇时间开发的项目，未来会持续迭代改进。如果您有任何建议或发现问题，非常欢迎提出宝贵意见，让我们一起把这个项目做得更好。

## 功能特性

### 核心功能
- **消息总线架构**：使用异步队列实现通道与 Agent 的解耦通信
- **记忆系统**：持久化对话历史，支持上下文检索
- **多提供商支持**：基于 LiteLLM 的 LLM 提供商抽象，支持多种模型
- **会话管理**：持久化对话历史
- **可扩展设计**：易于添加新的通道和工具
- **稳定执行模式**：统一使用 AgentLoop 执行，减少多执行路径冲突

### 工具能力
- **网络工具**：内置 web_search、web_fetch 工具，支持网络搜索和网页抓取
- **文件操作工具**：内置 write_file、read_file、list_files 工具，支持文件读写
- **并行执行**：支持多个工具并行执行，提升效率

### 高级功能
- **Provider降级**：多Provider自动切换，系统可用性达99%
- **请求限流**：基于令牌桶算法的限流保护，防止系统过载
- **意图分类**：智能意图识别，支持置信度评估
- **会话追踪**：会话上下文管理与状态追踪
- **用户画像**：用户特征数据收集与个性化服务
- **资源监控**：CPU/内存/磁盘IO监控与限制
- **RAG知识增强**：检索增强生成，提升知识类响应准确率
- **主动建议**：基于用户行为的智能推荐
- **全链路监控**：指标监控、日志分析、异常检测与告警
- **MCP桥接**：支持与Minecraft服务器进行双向协议通信
- **定时任务系统**：支持每日/每周/间隔任务和执行日志
- **Cron调度**：支持标准5段Cron表达式（如 `*/5 * * * *`）
- **心跳服务**：周期健康上报与异常阈值告警
- **Playwright自动化**：支持页面访问、点击、填表、截图、内容提取
- **Clawhub技能系统**：支持技能同步、动态加载/卸载与统一调用

### 多渠道支持
- **飞书**：WebSocket 长连接集成
- **钉钉**：回调接收 + Webhook 发送
- **统一通道框架**：支持快速接入微信、企业微信、Telegram、Discord等新渠道

## 🚀 快速开始

**只需 5 分钟即可开始使用！**

```bash
# 1. 安装
git clone https://github.com/YOUR_USERNAME/kaolalabot.git
cd kaolalabot
pip install -r requirements-backend.txt
pip install -e .

# 2. 配置
kaolalabot onboard
# 编辑 config.json 添加 API 密钥

# 3. 启动
kaolalabot agent
```

📖 **详细教程**: 查看 [快速开始指南](QUICKSTART.md)

## 📦 安装

### 1. 初始化配置
```bash
kaolalabot onboard
```

### 2. 配置 API 密钥

编辑 `D:\ai\kaolalabot\config.json` 并添加您的 LLM API 密钥：
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "您的API密钥"
    }
  }
}
```

### 3. 启动服务

```bash
kaolalabot gateway
```

## Agent 工具

Agent 现在支持以下工具：

### 网络工具
| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `web_search` | 使用 DuckDuckGo 搜索网络 | `query`, `max_results` |
| `web_fetch` | 获取网页内容 | `url` |

### 文件工具
| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `write_file` | 写入文件到 workspace | `filename`, `content`, `append` |
| `read_file` | 读取 workspace 文件 | `filename`, `max_chars` |
| `list_files` | 列出 workspace 文件 | `directory`, `pattern` |

### 浏览器自动化工具
| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `playwright` | 浏览器自动化（访问/点击/填表/截图） | `url`, `actions`, `script`, `timeout`, `headless` |

示例 actions：
```json
[
  {"action":"navigate","url":"https://example.com"},
  {"action":"click","selector":"text=Login"},
  {"action":"fill","selector":"input[name='username']","text":"demo"},
  {"action":"fill","selector":"input[name='password']","text":"123456"},
  {"action":"press","selector":"input[name='password']","key":"Enter"},
  {"action":"wait","selector":"#dashboard"},
  {"action":"screenshot","path":"dashboard.png","full_page":true}
]
```

## Cron 与心跳协同

- `scheduler` 任务支持 `schedule_type = cron` 与 `cron_expression`
- 内置 runner：
  - `agent_message`：定时发送消息给 Agent
  - `playwright_script`：定时执行浏览器自动化脚本
  - `heartbeat_once`：定时触发一次心跳上报
- Scheduler 执行日志默认写入 `workspace/system/task_logs.jsonl`

### 使用示例

告诉 agent：
```
请搜索最新的AI新闻，然后保存到workspace/news.txt文件里
```

## 执行模式

当前版本统一使用 AgentLoop 单路径执行，不再提供 `/deep` 系列命令。

## 飞书配置

飞书记忆已预配置：
- App ID: `cli_a92f8dba86a3dcca`
- App Secret: `<YOUR_FEISHU_APP_SECRET>`

### 飞书设置步骤

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建新应用或使用已有应用
3. 启用机器人功能
4. 配置事件订阅 `im.message.receive_v1`
5. 使用 WebSocket 长连接（无需公网 IP）

## CLI 命令

```bash
# 初始化配置
kaolalabot onboard

# 启动网关服务
kaolalabot gateway

# 交互式聊天
kaolalabot agent

# 发送单条消息
kaolalabot agent -m "你好"

# 查看状态
kaolalabot status

# 查看通道状态
kaolalabot channels status
```

## 项目架构

```
kaolalabot/
├── 📁 agent/           # Agent 核心 (loop, context, tools)
│   ├── 📁 tools/      # 工具实现 (web, file, parallel)
│   ├── 📁 cot/        # 思维链引擎
│   └── intent_classifier.py  # 意图分类器
├── 📁 bus/            # 消息总线 (events, queue, rate_limit)
├── 📁 channels/       # 通道集成
│   ├── base.py        # BaseChannel 抽象类
│   ├── manager.py     # ChannelManager
│   ├── feishu.py      # 飞书通道
│   └── unified.py     # 统一通道框架
├── 📁 cli/            # CLI 命令
├── 📁 config/         # 配置 schema 和加载器
├── 📁 gateway/        # 网关系统 (RPC, 认证, 远程接入)
├── 📁 memory/         # 记忆系统
├── 📁 providers/      # LLM 提供商抽象
│   ├── base.py        # Provider 基类
│   ├── litellm_provider.py  # LiteLLM 实现
│   ├── fallback.py     # Provider 降级机制
│   └── provider_wrapper.py  # Provider 包装器
├── 📁 session/        # 会话管理
│   ├── manager.py     # 会话管理器
│   └── state_tracker.py  # 会话状态追踪
├── 📁 user/           # 用户画像
│   └── profile.py    # 用户画像管理
├── 📁 rag/            # RAG 知识增强
│   └── engine.py     # RAG 引擎
├── 📁 monitoring/     # 监控系统
│   └── dashboard.py  # 监控仪表盘
├── 📁 utils/          # 工具函数
│   └── resource_monitor.py  # 资源监控
└── 📁 templates/     # 工作流模板
```

## 消息流程

```
通道事件 → ChannelAdapter → MessageBus.inbound
                                      ↓
                              AgentLoop (处理消息)
                                      ↓
                              MessageBus.outbound
                                      ↓
                           ChannelManager → Channel.send()
```

## 📚 文档导航

### 入门指南
- [🚀 快速开始](QUICKSTART.md) - 5 分钟快速上手
- [📖 设计指南](docs/design-guide.md) - 从 0 了解项目架构
- [📝 贡献指南](CONTRIBUTING.md) - 如何参与贡献

### 模块文档
- [🤖 Agent 模块](kaolalabot/agent/README.md) - Agent 核心逻辑
- [🚌 消息总线](kaolalabot/bus/README.md) - 消息传递系统
- [🧠 记忆系统](kaolalabot/memory/README.md) - 三层记忆架构
- [🔌 通道集成](kaolalabot/channels/README.md) - 多渠道支持
- [🛠️ 工具系统](kaolalabot/agent/tools/README.md) - 工具扩展

### 开发资源
- [🧪 测试指南](tests/README.md) - 测试套件使用
- [🔧 脚本工具](scripts/README.md) - 辅助脚本说明
- [📊 优化报告](ARCHITECTURE_OPTIMIZATION_REPORT.md) - 架构优化详情

### 社区资源
- [🐨 吉祥物](docs/MASCOT.md) - 考拉小助手吉祥物
- [🤝 行为准则](CODE_OF_CONDUCT.md) - 社区规范
- [🔒 安全政策](SECURITY.md) - 安全问题处理
- [📄 许可证](LICENSE) - MIT License

## 🤝 参与贡献

我们欢迎各种形式的贡献！详见 [贡献指南](CONTRIBUTING.md)

### 贡献方式
- 💻 提交代码
- 📖 完善文档
- 🐛 报告问题
- 💡 提出建议
- 🎓 分享经验

### 开发环境搭建

```bash
# Fork 项目
git clone https://github.com/YOUR_USERNAME/kaolalabot.git

# 创建分支
git checkout -b feature/your-feature

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 提交代码
git commit -m "feat: add your feature"
```

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者们！

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) - 详见许可证文件
