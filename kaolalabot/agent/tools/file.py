"""Agent tools - File operations tools."""

import os
from pathlib import Path
from typing import Any

from kaolalabot.agent.tools.base import Tool


class WriteFileTool(Tool):
    """Tool for writing content to a file."""

    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path("./workspace")

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file in the workspace. Creates the file if it doesn't exist, or overwrites if it does."

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The filename (relative to workspace) to write to",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file",
                        },
                        "append": {
                            "type": "boolean",
                            "description": "Whether to append to existing file (default false - overwrite)",
                            "default": False,
                        },
                    },
                    "required": ["filename", "content"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "filename" not in params:
            errors.append("filename is required")
        if "content" not in params:
            errors.append("content is required")
        return errors

    async def execute(self, filename: str, content: str, append: bool = False) -> str:
        """Write content to file."""
        try:
            file_path = self.workspace / filename
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = "a" if append else "w"
            encoding = "utf-8"
            
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            
            abs_path = str(file_path.resolve())
            action = "Appended to" if append else "Written to"
            return f"✅ {action} file: {abs_path}\nSize: {len(content)} characters"
            
        except PermissionError:
            return f"Error: Permission denied writing to {filename}"
        except Exception as e:
            return f"Error writing to {filename}: {str(e)}"


class ReadFileTool(Tool):
    """Tool for reading a file."""

    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path("./workspace")

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read content from a file in the workspace."

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The filename (relative to workspace) to read from",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Maximum number of characters to read (default 10000)",
                            "default": 10000,
                        },
                    },
                    "required": ["filename"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "filename" not in params:
            errors.append("filename is required")
        return errors

    async def execute(self, filename: str, max_chars: int = 10000) -> str:
        """Read file content."""
        try:
            file_path = self.workspace / filename
            
            if not file_path.exists():
                return f"Error: File not found: {filename}"
            
            if not file_path.is_file():
                return f"Error: Not a file: {filename}"
            
            content = file_path.read_text(encoding="utf-8")
            
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n... (truncated, total {len(content)} chars)"
            
            return f"Content of {filename}:\n\n{content}"
            
        except PermissionError:
            return f"Error: Permission denied reading {filename}"
        except Exception as e:
            return f"Error reading {filename}: {str(e)}"


class ListFilesTool(Tool):
    """Tool for listing files in workspace."""

    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path("./workspace")

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files in the workspace directory."

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to list (relative to workspace, default root)",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "File pattern to filter (e.g., *.txt, *.md)",
                        },
                    },
                },
            },
        }

    async def execute(self, directory: str = "", pattern: str = None) -> str:
        """List files in directory."""
        try:
            dir_path = self.workspace / directory if directory else self.workspace
            
            if not dir_path.exists():
                return f"Error: Directory not found: {directory or 'workspace'}"
            
            if not dir_path.is_dir():
                return f"Error: Not a directory: {directory}"
            
            if pattern:
                files = list(dir_path.glob(pattern))
            else:
                files = [f for f in dir_path.iterdir() if f.is_file()]
            
            if not files:
                return f"No files found in {directory or 'workspace'}"
            
            output = []
            for f in sorted(files):
                size = f.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                output.append(f"  {f.name} ({size_str})")
            
            return "Files:\n" + "\n".join(output)
            
        except Exception as e:
            return f"Error listing files: {str(e)}"
