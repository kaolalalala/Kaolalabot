"""Agent tools - Shell execution tools for local command execution."""

import asyncio
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

from kaolalabot.agent.tools.base import Tool

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class ExecTool(Tool):
    """Tool for executing local shell commands (PowerShell/cmd)."""

    DEFAULT_TIMEOUT = 60

    FORBIDDEN_COMMANDS = [
        "rm -rf /",
        "rmdir /s /q",
        "format",
        "del /s /q",
        "Invoke-Expression",
        "iex",
        "curl.*\\|.*bash",
        "wget.*\\|.*bash",
        "powershell.*-enc",
        "New-Object.*Net\\.WebClient",
        "DownloadFile",
        "DownloadString",
    ]

    ALLOWED_COMMANDS = {
        "dir", "ls", "cd", "pwd", "echo", "type", "cat", "copy", "move",
        "mkdir", "rmdir", "del", "find", "grep", "head", "tail", "wc",
        "cp", "rm",
        "python", "pip", "git", "node", "npm", "yarn", "cargo", "rustc",
        "go", "java", "javac", "docker", "docker-compose", "kubectl",
        "curl", "wget", "ping", "ipconfig", "ip", "hostname", "whoami",
        "tasklist", "netstat", "systeminfo", "ver", "date", "time",
        "cls", "clear", "exit", "help", "set", "where", "which",
        "choco", "winget", "scoop", "timeout", "start", "powershell",
        "notepad", "calc", "explorer", "cmd", "chrome", "msedge",
        "get-service", "start-service", "stop-service",
        "get-process", "stop-process",
        "get-netipaddress", "test-netconnection",
        "get-itemproperty", "set-itemproperty",
    }

    GUI_LAUNCH_TOKENS = {
        "notepad", "notepad.exe",
        "powershell", "powershell.exe", "pwsh", "pwsh.exe",
        "cmd", "cmd.exe",
        "explorer", "explorer.exe",
        "calc", "calc.exe",
        "chrome", "chrome.exe",
        "msedge", "msedge.exe",
    }

    _POWERSHELL_CMDLET_PREFIXES = (
        "get-",
        "set-",
        "start-",
        "stop-",
        "test-",
        "new-",
        "remove-",
    )

    def __init__(
        self,
        workspace: Path = None,
        timeout: int = 60,
        restrict_to_workspace: bool = False,
        allowed_commands: list[str] = None,
        deny_commands: list[str] | None = None,
        backend: str = "native",
        openclaw_gateway_url: str = "http://127.0.0.1:18789",
        openclaw_token: str = "",
        openclaw_session_key: str = "main",
        openclaw_host: str = "sandbox",
        openclaw_security: str = "allowlist",
        openclaw_ask: str = "on-miss",
        openclaw_node: str = "",
        openclaw_elevated: bool = False,
    ):
        self.workspace = workspace or Path("./workspace")
        self.timeout = timeout
        self.restrict_to_workspace = restrict_to_workspace
        self.allowed_commands = set(allowed_commands) if allowed_commands else self.ALLOWED_COMMANDS
        self.deny_commands = [item.strip().lower() for item in (deny_commands or []) if item and item.strip()]
        self.backend = backend
        self.openclaw_gateway_url = openclaw_gateway_url.rstrip("/")
        self.openclaw_token = openclaw_token
        self.openclaw_session_key = openclaw_session_key
        self.openclaw_host = openclaw_host
        self.openclaw_security = openclaw_security
        self.openclaw_ask = openclaw_ask
        self.openclaw_node = openclaw_node
        self.openclaw_elevated = openclaw_elevated

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return (
            "Execute a local shell command or launch applications on Windows/Unix. "
            "USE THIS TOOL whenever user asks to run commands, open programs, launch applications, "
            "execute shell commands, run scripts, or start processes. "
            "For opening apps like PowerShell/Notepad/browser, use 'start <appname>' on Windows. "
            "This is the PRIMARY tool for executing user requests that involve running commands or launching software."
        )

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute (e.g., 'dir', 'ls', 'python script.py')",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default 60, max 300)",
                            "default": 60,
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory for the command (default: workspace path)",
                        },
                    },
                    "required": ["command"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "command" not in params or not params["command"]:
            errors.append("command is required")
        return errors

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if command is allowed to execute."""
        cmd_lower = command.lower().strip()

        for denied in self.deny_commands:
            if denied in cmd_lower:
                return False, f"Command blocked by policy: {denied}"

        for forbidden in self.FORBIDDEN_COMMANDS:
            if re.search(forbidden, cmd_lower, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {forbidden}"

        first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
        if first_word:
            if first_word not in self.allowed_commands and not self._is_local_executable_token(first_word):
                return False, f"Command '{first_word}' not in allowed list"

        if self.restrict_to_workspace:
            cmd_parts = cmd_lower.split()
            for part in cmd_parts:
                if part.startswith("/") or (len(part) > 2 and part[1] == ":"):
                    try:
                        resolved = Path(part).resolve()
                        if not str(resolved).startswith(str(self.workspace.resolve())):
                            return False, f"Path outside workspace not allowed: {part}"
                    except Exception:
                        pass

        return True, ""

    async def execute(self, command: str, timeout: int = None, cwd: str = None) -> str:
        """Execute a shell command and return output."""
        command = self._normalize_command(command)
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            return f"Error: Command not allowed - {reason}"

        exec_timeout = min(timeout or self.timeout, 300)
        if exec_timeout <= 0:
            exec_timeout = self.DEFAULT_TIMEOUT

        work_dir = cwd or str(self.workspace)

        try:
            if self.backend == "openclaw":
                return await self._run_command_openclaw(command, exec_timeout, work_dir)
            if os.name == "nt" and self._looks_like_powershell_cmdlet(command):
                return await self._run_powershell_command(command, exec_timeout)
            result = await self._run_command(command, exec_timeout, work_dir)
            return result
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {exec_timeout} seconds"
        except PermissionError:
            return "Error: Permission denied executing command"
        except FileNotFoundError:
            return f"Error: Command not found in PATH"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    async def _run_command_openclaw(self, command: str, timeout: int, cwd: str) -> str:
        """Run command through OpenClaw gateway tools/invoke API."""
        if not AIOHTTP_AVAILABLE:
            return "Error: aiohttp is required for OpenClaw backend"

        endpoint = f"{self.openclaw_gateway_url}/tools/invoke"
        headers = {"Content-Type": "application/json"}
        if self.openclaw_token:
            headers["Authorization"] = f"Bearer {self.openclaw_token}"

        args: dict[str, Any] = {
            "command": command,
            "timeout": timeout,
            "workdir": cwd,
            "host": self.openclaw_host,
            "security": self.openclaw_security,
            "ask": self.openclaw_ask,
            "elevated": self.openclaw_elevated,
        }
        if self.openclaw_node:
            args["node"] = self.openclaw_node

        payload = {
            "tool": "exec",
            "args": args,
            "sessionKey": self.openclaw_session_key,
        }

        try:
            client_timeout = aiohttp.ClientTimeout(total=max(5, timeout + 5))
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(endpoint, headers=headers, json=payload) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status != 200:
                        return f"Error: OpenClaw invoke failed (HTTP {resp.status}): {data}"
                    if not isinstance(data, dict):
                        return f"Error: OpenClaw returned invalid response: {data}"
                    if data.get("ok") is False:
                        err = data.get("error") or {}
                        if isinstance(err, dict):
                            return f"Error: OpenClaw tool error: {err.get('message') or err}"
                        return f"Error: OpenClaw tool error: {err}"
                    result = data.get("result")
                    if isinstance(result, str):
                        return result
                    return str(result) if result is not None else "Command completed."
        except Exception as exc:
            return f"Error: OpenClaw backend request failed: {exc}"

    async def _run_command(self, command: str, timeout: int, cwd: str) -> str:
        """Run command using asyncio subprocess."""
        is_windows = os.name == "nt"

        if is_windows:
            return await self._run_command_windows(command, timeout, cwd)
        else:
            return await self._run_command_unix(command, timeout, cwd)

    async def _run_command_windows(self, command: str, timeout: int, cwd: str) -> str:
        """Run command on Windows with support for GUI apps."""
        launch_cmd = self._to_windows_launch_command(command)

        try:
            if launch_cmd:
                launch_parts = self._resolve_windows_launch_parts(launch_cmd)
                if launch_parts:
                    proc = await asyncio.create_subprocess_exec(
                        *launch_parts,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        env=os.environ.copy(),
                    )
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=min(timeout, 3))
                    except asyncio.TimeoutError:
                        pass
                    if proc.returncode not in (None, 0):
                        return f"Error (code {proc.returncode}): failed to launch application"
                    return "Application launch command executed."

                # Fallback to cmd start for unknown launch command forms.
                proc = await asyncio.create_subprocess_exec(
                    "cmd.exe",
                    "/c",
                    launch_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=os.environ.copy(),
                )
                try:
                    await asyncio.wait_for(proc.wait(), timeout=min(timeout, 5))
                except asyncio.TimeoutError:
                    pass
                if proc.returncode not in (None, 0):
                    return f"Error (code {proc.returncode}): failed to launch application"
                return "Application launch command executed."

            proc = await asyncio.create_subprocess_exec(
                "cmd.exe",
                "/c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=self._get_safe_env(),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise

            out = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
            err = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

            if proc.returncode != 0 and err:
                return f"Error (code {proc.returncode}): {err}"

            return out if out else "Command completed."

        except Exception as e:
            return f"Error: {str(e)}"

    def _to_windows_launch_command(self, command: str) -> str | None:
        """Normalize app-launch commands for Windows."""
        normalized = command.strip()
        if not normalized:
            return None

        lowered = normalized.lower()
        if lowered.startswith("start "):
            return normalized

        tokens = shlex.split(normalized, posix=False)
        first = tokens[0].lower() if tokens else ""
        if first in self.GUI_LAUNCH_TOKENS:
            # powershell/cmd with arguments should execute command, not launch an empty shell window
            if first in {"powershell", "powershell.exe", "pwsh", "pwsh.exe", "cmd", "cmd.exe"} and len(tokens) > 1:
                return None
            return f'start "" {normalized}'

        return None

    def _normalize_command(self, command: str) -> str:
        """Normalize cross-platform aliases and PowerShell cmdlet invocations."""
        normalized = (command or "").strip()
        if not normalized:
            return normalized
        if os.name != "nt":
            return normalized

        normalized = (
            normalized.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        normalized = self._normalize_windows_start_command(normalized)

        parts = normalized.split(maxsplit=1)
        first = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if first == "cp":
            return f"copy {rest}".strip()
        if first == "rm":
            return f"del {rest}".strip()

        return normalized

    def _normalize_windows_start_command(self, command: str) -> str:
        """Fix common Windows `start` quoting mistakes from user/model text."""
        if not command.lower().startswith("start "):
            return command

        text = command.strip()

        # start "" powershell  -> start powershell
        m = re.match(r'(?i)^start\s+""\s+(.+)$', text)
        if m:
            rest = m.group(1).strip()
            if rest:
                return f"start {rest}"

        # start "powershell"  -> start powershell (quoted arg interpreted as title otherwise)
        m = re.match(r'(?i)^start\s+"([^"]+)"\s*$', text)
        if m:
            quoted = m.group(1).strip()
            if quoted:
                return f"start {quoted}"

        return text

    def _looks_like_powershell_cmdlet(self, command: str) -> bool:
        token = (command or "").strip().split(maxsplit=1)
        first = token[0].lower() if token else ""
        return first.startswith(self._POWERSHELL_CMDLET_PREFIXES)

    def _is_local_executable_token(self, token: str) -> bool:
        """Allow local executable invocation such as ./program.exe or C:\\tools\\app.bat."""
        cleaned = token.strip().strip('"').strip("'")
        if not cleaned:
            return False
        lowered = cleaned.lower()
        return lowered.endswith((".exe", ".bat", ".cmd", ".ps1"))

    def _resolve_windows_launch_parts(self, launch_cmd: str) -> list[str] | None:
        """Convert launch command into direct executable call when possible."""
        try:
            tokens = shlex.split(launch_cmd, posix=False)
        except Exception:
            return None
        if not tokens:
            return None

        target_tokens = tokens
        if tokens[0].lower() == "start":
            idx = 1
            if idx < len(tokens) and tokens[idx] in ('""', "''"):
                idx += 1
            elif idx < len(tokens) and tokens[idx].startswith('"') and tokens[idx].endswith('"'):
                idx += 1
            if idx >= len(tokens):
                return None
            target_tokens = tokens[idx:]

            # Keep terminal launches in `cmd /c start` fallback path so a new console window is created.
            if target_tokens:
                maybe_terminal = target_tokens[0].strip('"').strip("'").lower()
                if maybe_terminal in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
                    return None

        exe = target_tokens[0].strip('"').strip("'")
        args = [item.strip('"').strip("'") for item in target_tokens[1:]]

        exe_lower = exe.lower()
        if exe_lower in self.GUI_LAUNCH_TOKENS:
            resolved = self._resolve_windows_executable(exe)
            if resolved:
                return [resolved, *args]
            if exe_lower in {"chrome", "chrome.exe"}:
                # Fallback when Chrome is not installed or not in PATH.
                edge = self._resolve_windows_executable("msedge")
                if edge:
                    return [edge, *args]
            if "." not in Path(exe).name:
                exe = f"{exe}.exe"
            return [exe, *args]
        return None

    def _resolve_windows_executable(self, exe: str) -> str | None:
        """Resolve executable path with PATH lookup and common install dirs."""
        name = exe if "." in Path(exe).name else f"{exe}.exe"
        found = shutil.which(name)
        if found:
            return found

        candidates = [
            Path("C:/Windows/System32") / name,
            Path("C:/Windows") / name,
            Path("C:/Program Files") / "Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files (x86)") / "Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files (x86)") / "Microsoft/Edge/Application/msedge.exe",
            Path("C:/Program Files") / "Microsoft/Edge/Application/msedge.exe",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        return None

    async def _run_command_unix(self, command: str, timeout: int, cwd: str) -> str:
        """Run command on Unix/Linux."""
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=self._get_safe_env(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        output_parts = []

        if stdout:
            try:
                stdout_text = stdout.decode("utf-8", errors="replace").strip()
                if stdout_text:
                    output_parts.append(stdout_text)
            except Exception:
                pass

        if stderr:
            try:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"[stderr]\n{stderr_text}")
            except Exception:
                pass

        if proc.returncode != 0 and not output_parts:
            return f"Command exited with code {proc.returncode}"

        return "\n".join(output_parts) if output_parts else "Command completed successfully (no output)"

    async def _run_powershell_command(self, command: str, timeout: int) -> str:
        """Execute PowerShell command directly on Windows."""
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._get_safe_env(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Error: Command timed out after {timeout} seconds"

        out = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
        err = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
        if proc.returncode != 0 and err:
            return f"Error (code {proc.returncode}): {err}"
        return out if out else "Command completed."

    def _get_safe_env(self) -> dict[str, str]:
        """Get sanitized environment variables."""
        if os.name == "nt":
            # Windows command/powershell compatibility is sensitive to missing system env vars.
            return os.environ.copy()
        safe_vars = [
            "PATH", "TEMP", "TMP", "HOME", "USER", "USERNAME",
            "LANG", "LC_ALL", "PYTHONPATH", "NODE_PATH",
        ]
        env = {}
        for var in safe_vars:
            if val := os.environ.get(var):
                env[var] = val
        return env


class PowerShellTool(Tool):
    """Tool specifically for PowerShell execution on Windows."""

    FORBIDDEN_PATTERNS = [
        r"Remove-Item.*-Recurse.*-Force",
        r"Format-Volume",
        r"Clear-Disk",
        r"Stop-Computer",
        r"Restart-Computer",
        r"New-PSSession",
        r"Invoke-Command.*-ComputerName",
        r"Download\w+String",
        r"Download\w+File",
        r"WebClient",
        r"Start-Process.*-Verb.*RunAs",
    ]

    def __init__(
        self,
        workspace: Path = None,
        timeout: int = 60,
    ):
        self.workspace = workspace or Path("./workspace")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "powershell"

    @property
    def description(self) -> str:
        return (
            "Execute PowerShell commands on Windows. Use for Windows-specific tasks "
            "like system management, registry access, Windows services, etc. "
            "Returns stdout and stderr output."
        )

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "PowerShell command to execute",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default 60)",
                            "default": 60,
                        },
                    },
                    "required": ["command"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "command" not in params or not params["command"]:
            errors.append("command is required")
        return errors

    def _is_command_safe(self, command: str) -> tuple[bool, str]:
        """Check if PowerShell command is safe."""
        cmd_upper = command.upper()
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, cmd_upper, re.IGNORECASE):
                return False, f"Forbidden pattern: {pattern}"
        return True, ""

    async def execute(self, command: str, timeout: int = None) -> str:
        """Execute a PowerShell command."""
        if os.name != "nt":
            return "Error: PowerShell is only available on Windows"

        safe, reason = self._is_command_safe(command)
        if not safe:
            return f"Error: Command blocked - {reason}"

        exec_timeout = min(timeout or self.timeout, 300)

        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=exec_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"Error: Command timed out after {exec_timeout} seconds"

            output = []
            if stdout:
                output.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                err_text = stderr.decode("utf-8", errors="replace")
                if err_text.strip():
                    output.append(f"[stderr]\n{err_text}")

            if not output:
                return "Command completed (no output)"

            return "\n".join(output)

        except FileNotFoundError:
            return "Error: PowerShell not found"
        except Exception as e:
            return f"Error: {str(e)}"

