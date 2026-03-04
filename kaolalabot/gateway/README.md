# Gateway Module

## 功能说明
- 提供 RPC 协议、鉴权与远程接入能力。
- 通过 `/api/gateway/*` 暴露会话、聊天、状态接口。

## 使用方法
- 启动服务后访问 `/api/gateway/rpc` 或 `/api/gateway/sessions`。

## 接口定义
- `GatewayRPCProtocol.handle_request(method: str, data: dict) -> dict`
- `get_gateway_auth()`
- `configure_remote_access(...)`

## 示例代码
```python
rpc = get_rpc_protocol()
result = await rpc.handle_request("sessions.list", {})
```
