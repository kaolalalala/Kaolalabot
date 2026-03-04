# Services Module

## 功能说明
`services/` 提供与Agent主循环并行运行的系统级能力：
- `mcp.py`：Minecraft MCP双向通信服务（包解析、事件监听、指令执行）
- `scheduler.py`：可配置定时任务系统（CRUD、周期调度、执行日志）
- `heartbeat.py`：心跳与健康上报服务（资源占用、失败告警）
- `clawhub.py`：Clawhub技能同步与动态加载/卸载
- `runtime.py`：全局服务注册器

## 使用方法
在 `config.json` 中启用对应模块：
- `mcp.enabled`
- `scheduler.enabled`
- `heartbeat.enabled`
- `clawhub.enabled`

启动 `kaolalabot gateway` 或 `kaolalabot.server` 后自动运行。

## 统一接口
- MCP: `status()`, `execute_command(command)`
- Scheduler: `add_task`, `update_task`, `delete_task`, `enable_task`, `run_task_now`, `read_logs`
- Heartbeat: `status()`, `build_payload()`
- Clawhub: `sync_once()`, `list_skills()`, `invoke_skill()`, `load_skill()`, `unload_skill()`

## 示例
通过API管理任务：
- `POST /api/system/scheduler/tasks`
- `GET /api/system/scheduler/logs`

通过API调用技能：
- `POST /api/system/clawhub/skills/{name}/invoke`
