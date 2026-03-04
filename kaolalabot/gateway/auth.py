"""Gateway Authentication - Token/Password authentication mechanism."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from loguru import logger


class AuthMode(str, Enum):
    NONE = "none"
    TOKEN = "token"
    PASSWORD = "password"
    TOKEN_OR_PASSWORD = "token_or_password"


@dataclass
class AuthResult:
    success: bool
    error: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self):
        return {
            "success": self.success,
            "error": self.error,
            "user_id": self.user_id,
        }


class GatewayAuth:
    """
    Gateway Authentication Manager.
    
    Supports multiple authentication modes:
    - none: No authentication
    - token: Token-based authentication
    - password: Password-based authentication
    - token_or_password: Either token or password acceptable
    """
    
    def __init__(
        self,
        mode: AuthMode = AuthMode.TOKEN,
        token: str = "",
        password: str = "",
        token_hash: str = "",
        password_hash: str = "",
    ):
        self._mode = mode
        self._token_salt = secrets.token_hex(16)
        self._password_salt = secrets.token_hex(16)

        self._token = token or token_hash
        self._password = password or password_hash
        self._token_hash = self._hash_token(token) if token else token_hash
        self._password_hash = self._hash_password(password) if password else password_hash

        self._valid_tokens: dict[str, datetime] = {}
        self._failed_attempts: dict[str, int] = {}
        self._max_failed_attempts = 5
    
    @property
    def mode(self) -> AuthMode:
        return self._mode
    
    @property
    def is_enabled(self) -> bool:
        return self._mode != AuthMode.NONE
    
    def _hash_token(self, token: str) -> str:
        """Hash token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            self._password_salt.encode(),
            100000,
        ).hex()
    
    def _verify_token(self, token: str) -> bool:
        """Verify token."""
        if not self._token and not self._token_hash:
            return True
        
        provided_hash = self._hash_token(token)
        return hmac.compare_digest(provided_hash, self._token_hash)
    
    def _verify_password(self, password: str) -> bool:
        """Verify password."""
        if not self._password and not self._password_hash:
            return True
        
        provided_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            self._password_salt.encode(),
            100000,
        ).hex()
        return hmac.compare_digest(provided_hash, self._password_hash)
    
    def _get_client_key(self, remote_addr: str = None) -> str:
        """Get client identifier for rate limiting."""
        return remote_addr or "default"
    
    def _is_rate_limited(self, client_key: str) -> bool:
        """Check if client is rate limited."""
        attempts = self._failed_attempts.get(client_key, 0)
        return attempts >= self._max_failed_attempts
    
    def authenticate(
        self,
        token: str = None,
        password: str = None,
        remote_addr: str = None,
    ) -> AuthResult:
        """Authenticate a request."""
        if self._mode == AuthMode.NONE:
            return AuthResult(success=True, user_id="anonymous")
        
        client_key = self._get_client_key(remote_addr)
        
        if self._is_rate_limited(client_key):
            return AuthResult(
                success=False,
                error="Too many failed attempts. Please try again later.",
            )
        
        success = False
        user_id = None
        
        if self._mode in (AuthMode.TOKEN, AuthMode.TOKEN_OR_PASSWORD):
            if token and self._verify_token(token):
                success = True
                user_id = "token_user"
        
        if not success and self._mode in (AuthMode.PASSWORD, AuthMode.TOKEN_OR_PASSWORD):
            if password and self._verify_password(password):
                success = True
                user_id = "password_user"
        
        if not success:
            attempts = self._failed_attempts.get(client_key, 0) + 1
            self._failed_attempts[client_key] = attempts
            logger.warning(f"Authentication failed for {client_key}, attempts: {attempts}")
            
            if self._mode == AuthMode.TOKEN:
                return AuthResult(success=False, error="Invalid token")
            elif self._mode == AuthMode.PASSWORD:
                return AuthResult(success=False, error="Invalid password")
            else:
                return AuthResult(success=False, error="Invalid token or password")
        
        self._failed_attempts.pop(client_key, None)
        return AuthResult(success=True, user_id=user_id)
    
    def authenticate_websocket(
        self,
        token: str = None,
        password: str = None,
        headers: dict = None,
        remote_addr: str = None,
    ) -> AuthResult:
        """Authenticate a WebSocket connection."""
        ws_token = token
        ws_password = password
        
        if headers:
            auth_header = headers.get("authorization") or headers.get("Authorization")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    ws_token = auth_header[7:]
                elif auth_header.startswith("Basic "):
                    import base64
                    try:
                        decoded = base64.b64decode(auth_header[6:]).decode()
                        if ":" in decoded:
                            ws_password = decoded.split(":", 1)[1]
                    except:
                        pass
        
        return self.authenticate(token=ws_token, password=ws_password, remote_addr=remote_addr)
    
    def set_token(self, token: str) -> None:
        """Set authentication token."""
        self._token = token
        self._token_hash = self._hash_token(token)
    
    def set_password(self, password: str) -> None:
        """Set authentication password."""
        self._password = password
        self._password_hash = self._hash_password(password)
    
    def set_mode(self, mode: AuthMode) -> None:
        """Set authentication mode."""
        self._mode = mode
    
    def generate_token(self) -> str:
        """Generate a new authentication token."""
        token = secrets.token_urlsafe(32)
        self.set_token(token)
        return token
    
    def get_config(self) -> dict:
        """Get sanitized configuration (without secrets)."""
        return {
            "mode": self._mode.value,
            "is_enabled": self.is_enabled,
            "has_token": bool(self._token or self._token_hash),
            "has_password": bool(self._password or self._password_hash),
        }


_auth: Optional[GatewayAuth] = None


def get_gateway_auth(
    mode: AuthMode = AuthMode.TOKEN,
    token: str = "",
    password: str = "",
) -> GatewayAuth:
    """Get or create the global authentication instance."""
    global _auth
    if _auth is None:
        _auth = GatewayAuth(mode=mode, token=token, password=password)
    return _auth


def create_gateway_auth_from_config(config: dict) -> GatewayAuth:
    """Create authentication from configuration."""
    mode = AuthMode(config.get("mode", "token"))
    token = config.get("token", "")
    password = config.get("password", "")
    
    return GatewayAuth(mode=mode, token=token, password=password)
