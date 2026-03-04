"""Gateway Remote Access - Support for remote connections via SSH/Tunnel."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from loguru import logger


class RemoteMode(str, Enum):
    DISABLED = "disabled"
    TAILSCALE = "tailscale"
    SSH_TUNNEL = "ssh_tunnel"
    CUSTOM = "custom"


@dataclass
class RemoteConfig:
    mode: RemoteMode = RemoteMode.DISABLED
    url: str = ""
    token: str = ""
    password: str = ""
    enabled: bool = False


@dataclass
class GatewayEndpoint:
    host: str
    port: int
    use_tls: bool = True
    path: str = "/gateway"
    
    @property
    def ws_url(self) -> str:
        protocol = "wss" if self.use_tls else "ws"
        return f"{protocol}://{self.host}:{self.port}{self.path}"
    
    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "useTls": self.use_tls,
            "path": self.path,
            "wsUrl": self.ws_url,
        }


class RemoteAccessManager:
    """
    Gateway Remote Access Manager.
    
    Supports remote connections via:
    - Tailscale: Use Tailnet IP for remote access
    - SSH Tunnel: Forward WebSocket through SSH
    - Custom: User-specified remote URL
    
    The key difference from local access:
    - Remote access requires explicit configuration
    - May need different authentication
    - Connection goes through gateway.remote.*
    """
    
    def __init__(self):
        self._config = RemoteConfig()
        self._local_endpoint = GatewayEndpoint(host="127.0.0.1", port=8000)
        self._remote_endpoint: Optional[GatewayEndpoint] = None
    
    def configure(
        self,
        mode: RemoteMode = RemoteMode.DISABLED,
        url: str = "",
        token: str = "",
        password: str = "",
    ) -> None:
        """Configure remote access."""
        self._config = RemoteConfig(
            mode=mode,
            url=url,
            token=token,
            password=password,
            enabled=mode != RemoteMode.DISABLED,
        )
        
        if mode == RemoteMode.TAILSCALE:
            self._setup_tailscale()
        elif mode == RemoteMode.CUSTOM and url:
            self._setup_custom(url)
        
        logger.info(f"Remote access configured: mode={mode}, enabled={self._config.enabled}")
    
    def _setup_tailscale(self) -> None:
        """Setup Tailscale remote access."""
        try:
            import socket
            
            hostname = socket.gethostname()
            tailnet_host = f"{hostname}.tail-scale.ts.net"
            
            self._remote_endpoint = GatewayEndpoint(
                host=tailnet_host,
                port=self._local_endpoint.port,
                use_tls=True,
            )
            
            logger.info(f"Tailscale remote endpoint: {self._remote_endpoint.ws_url}")
            
        except Exception as e:
            logger.warning(f"Failed to setup Tailscale: {e}")
            self._remote_endpoint = None
    
    def _setup_custom(self, url: str) -> None:
        """Setup custom remote URL."""
        if url.startswith("wss://") or url.startswith("ws://"):
            parsed = url.replace("wss://", "").replace("ws://", "")
            use_tls = url.startswith("wss://")
        else:
            parsed = url
            use_tls = False
        
        if ":" in parsed:
            host, port_str = parsed.split(":", 1)
            try:
                port = int(port_str.split("/")[0])
            except:
                port = 8000
        else:
            host = parsed.split("/")[0]
            port = 8000
        
        path = "/"
        if "/" in parsed:
            path = "/" + parsed.split("/", 1)[1]
        
        self._remote_endpoint = GatewayEndpoint(
            host=host,
            port=port,
            use_tls=use_tls,
            path=path,
        )
    
    @property
    def is_enabled(self) -> bool:
        return self._config.enabled
    
    @property
    def mode(self) -> RemoteMode:
        return self._config.mode
    
    def get_local_endpoint(self) -> GatewayEndpoint:
        """Get local endpoint for loopback access."""
        return self._local_endpoint
    
    def get_remote_endpoint(self) -> Optional[GatewayEndpoint]:
        """Get remote endpoint for external access."""
        if self._config.enabled:
            return self._remote_endpoint
        return None
    
    def get_effective_endpoint(self, prefer_remote: bool = False) -> GatewayEndpoint:
        """Get the effective endpoint based on client location."""
        if prefer_remote and self._remote_endpoint:
            return self._remote_endpoint
        return self._local_endpoint
    
    def resolve_host(self, request_host: str = None) -> str:
        """Resolve the appropriate host for WebSocket URL."""
        if not request_host:
            return self._local_endpoint.host
        
        if request_host in ("localhost", "127.0.0.1", "::1"):
            return self._local_endpoint.host
        
        if self._config.enabled and self._remote_endpoint:
            return self._remote_endpoint.host
        
        return request_host
    
    def get_config(self) -> dict:
        """Get remote access configuration."""
        return {
            "mode": self._config.mode.value,
            "enabled": self._config.enabled,
            "hasUrl": bool(self._config.url),
            "hasToken": bool(self._config.token),
            "hasPassword": bool(self._config.password),
            "localEndpoint": self._local_endpoint.to_dict(),
            "remoteEndpoint": self._remote_endpoint.to_dict() if self._remote_endpoint else None,
        }


_remote_manager: Optional[RemoteAccessManager] = None


def get_remote_manager() -> RemoteAccessManager:
    """Get the global remote access manager."""
    global _remote_manager
    if _remote_manager is None:
        _remote_manager = RemoteAccessManager()
    return _remote_manager


def configure_remote_access(
    mode: RemoteMode = RemoteMode.DISABLED,
    url: str = "",
    token: str = "",
    password: str = "",
) -> None:
    """Configure remote access."""
    manager = get_remote_manager()
    manager.configure(mode=mode, url=url, token=token, password=password)
