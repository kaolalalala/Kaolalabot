"""Gateway module - OpenClaw-style unified Gateway system."""

from kaolalabot.gateway.rpc_protocol import (
    GatewayRPCProtocol,
    ChatMessage,
    ChatSendRequest,
    ChatHistoryRequest,
    get_rpc_protocol,
)

from kaolalabot.gateway.auth import (
    GatewayAuth,
    AuthMode,
    AuthResult,
    get_gateway_auth,
    create_gateway_auth_from_config,
)

from kaolalabot.gateway.remote import (
    RemoteAccessManager,
    RemoteMode,
    GatewayEndpoint,
    get_remote_manager,
    configure_remote_access,
)

__all__ = [
    "GatewayRPCProtocol",
    "ChatMessage",
    "ChatSendRequest", 
    "ChatHistoryRequest",
    "get_rpc_protocol",
    "GatewayAuth",
    "AuthMode",
    "AuthResult",
    "get_gateway_auth",
    "create_gateway_auth_from_config",
    "RemoteAccessManager",
    "RemoteMode",
    "GatewayEndpoint",
    "get_remote_manager",
    "configure_remote_access",
]
