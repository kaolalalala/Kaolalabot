# Channels Module

## 功能说明
- 通道层负责外部平台与 `MessageBus` 之间的双向转换。
- `manager.py` 统一管理通道生命周期与出站消息分发。
- 支持通道：`feishu`、`web`、`voice`、`dingtalk`。

## 使用方法
- 在 `config.json` 的 `channels` 下启用通道。
- 启动 `kaolalabot gateway` 后由 `ChannelManager` 自动加载启用通道。
- 钉钉启用后会启动内置回调服务，默认地址 `http://0.0.0.0:18791/api/channels/dingtalk/callback`。

## 接口定义
- `BaseChannel.start()`
- `BaseChannel.stop()`
- `BaseChannel.send(msg: OutboundMessage)`
- `BaseChannel._handle_message(...)`（内部入站分发）

## 示例代码
```python
manager = ChannelManager(config, bus)
await manager.start_all()
```

## 钉钉配置示例
```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "callbackPath": "/api/channels/dingtalk/callback",
      "callbackHost": "0.0.0.0",
      "callbackPort": 18791,
      "webhookAccessToken": "YOUR_TOKEN",
      "webhookSecret": "YOUR_SECRET"
    }
  }
}
```
