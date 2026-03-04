# Agent Module

## 功能说明
- `AgentLoop` 负责从消息总线消费消息、构建上下文、调用模型、执行工具并回传结果。
- `native_commands.py` 提供确定性本地命令路由（如打开 PowerShell/记事本）。

## 使用方法
- 初始化 `AgentLoop` 时传入 `MessageBus`、`LLMProvider`、`ToolRegistry`。
- 通过 `run()` 持续处理消息，或 `process_direct()` 处理单条请求。

## 接口定义
- `AgentLoop.run() -> None`
- `AgentLoop.process_direct(content: str, session_key: str = ..., channel: str = ..., chat_id: str = ...) -> str`

## 示例代码
```python
agent = AgentLoop(bus=bus, provider=provider, workspace=workspace, tool_registry=tools)
response = await agent.process_direct("打开记事本")
```
