# Deprecated Modules

此目录存放已下线的执行链路代码（原 Graph/LangGraph 风格实现）。

- `graph/`: 旧图执行框架
- `graph_handler.py`: 旧网关图调度入口

当前主执行路径统一为 `agent/loop.py`，避免双执行链路冲突。
