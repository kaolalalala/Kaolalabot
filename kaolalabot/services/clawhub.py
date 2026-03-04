"""Clawhub skill integration with dynamic load/unload support."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@dataclass
class SkillMeta:
    """Skill metadata."""

    name: str
    version: str
    file: str
    entrypoint: str = "run"


class ClawhubClient:
    """Simple HTTP client for Clawhub API."""

    def __init__(self, base_url: str, api_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token

    async def fetch_skills(self) -> list[dict[str, Any]]:
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for Clawhub sync")
        if not self.base_url:
            return []
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        url = f"{self.base_url}/skills"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"clawhub fetch failed: status={resp.status}, body={text[:200]}")
                data = await resp.json()
                if isinstance(data, dict):
                    skills = data.get("skills") or []
                else:
                    skills = data
                if not isinstance(skills, list):
                    return []
                return skills


class ClawhubSkillService:
    """Skill manager with dynamic loader and periodic sync."""

    def __init__(
        self,
        skills_dir: Path,
        metadata_file: Path,
        client: ClawhubClient | None = None,
        sync_interval_seconds: int = 300,
    ):
        self.skills_dir = Path(skills_dir)
        self.metadata_file = Path(metadata_file)
        self.client = client
        self.sync_interval_seconds = max(30, int(sync_interval_seconds))

        self._running = False
        self._sync_task: asyncio.Task | None = None
        self._metas: dict[str, SkillMeta] = {}
        self._modules: dict[str, ModuleType] = {}
        self._lock = asyncio.Lock()

        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_metadata()

    async def start(self) -> None:
        self._running = True
        self._reload_all_local_skills()
        if self.client:
            self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task

    async def sync_once(self) -> dict[str, Any]:
        if not self.client:
            return {"ok": False, "error": "clawhub client not configured"}
        try:
            remote_skills = await self.client.fetch_skills()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        updated = 0
        for item in remote_skills:
            try:
                name = str(item["name"])
                version = str(item.get("version", "0.0.0"))
                code = str(item.get("code", ""))
                entrypoint = str(item.get("entrypoint", "run"))
                if not code.strip():
                    continue
                current = self._metas.get(name)
                if current and current.version == version:
                    continue
                file_path = self.skills_dir / f"{name}.py"
                file_path.write_text(code, encoding="utf-8")
                self._metas[name] = SkillMeta(
                    name=name,
                    version=version,
                    file=str(file_path),
                    entrypoint=entrypoint,
                )
                self._load_skill_module(name)
                updated += 1
            except Exception as exc:
                logger.warning("Clawhub skill sync item failed: {}", exc)
        self._save_metadata()
        return {"ok": True, "updated": updated, "total_remote": len(remote_skills)}

    async def invoke_skill(self, name: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
        mod = self._modules.get(name)
        if mod is None:
            raise RuntimeError(f"skill not loaded: {name}")
        meta = self._metas.get(name)
        if meta is None:
            raise RuntimeError(f"skill metadata missing: {name}")
        fn = getattr(mod, meta.entrypoint, None)
        if not callable(fn):
            raise RuntimeError(f"skill entrypoint not callable: {meta.entrypoint}")
        result = fn(payload, context or {})
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "name": meta.name,
                "version": meta.version,
                "entrypoint": meta.entrypoint,
                "loaded": meta.name in self._modules,
                "file": meta.file,
            }
            for meta in self._metas.values()
        ]

    def unload_skill(self, name: str) -> bool:
        if name not in self._modules and name not in self._metas:
            return False
        self._modules.pop(name, None)
        return True

    def load_skill(self, name: str, file_path: Path, version: str = "local", entrypoint: str = "run") -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": "skill file not found"}
        self._metas[name] = SkillMeta(name=name, version=version, file=str(path), entrypoint=entrypoint)
        try:
            self._load_skill_module(name)
            self._save_metadata()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "skill_count": len(self._metas),
            "loaded_count": len(self._modules),
            "sync_enabled": self.client is not None,
        }

    async def _sync_loop(self) -> None:
        while self._running:
            result = await self.sync_once()
            if not result.get("ok"):
                logger.warning("Clawhub sync failed: {}", result.get("error"))
            await asyncio.sleep(self.sync_interval_seconds)

    def _reload_all_local_skills(self) -> None:
        for py in self.skills_dir.glob("*.py"):
            name = py.stem
            if name not in self._metas:
                self._metas[name] = SkillMeta(name=name, version="local", file=str(py), entrypoint="run")
        for name in list(self._metas.keys()):
            with contextlib.suppress(Exception):
                self._load_skill_module(name)

    def _load_skill_module(self, name: str) -> None:
        meta = self._metas[name]
        file_path = Path(meta.file)
        if not file_path.exists():
            raise FileNotFoundError(meta.file)
        spec = importlib.util.spec_from_file_location(f"kaolalabot_clawhub_{name}", file_path)
        if not spec or not spec.loader:
            raise RuntimeError(f"unable to build module spec: {name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._modules[name] = module

    def _load_metadata(self) -> None:
        if not self.metadata_file.exists():
            return
        try:
            rows = json.loads(self.metadata_file.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                return
            self._metas = {
                row["name"]: SkillMeta(**row)
                for row in rows
                if isinstance(row, dict) and row.get("name")
            }
        except Exception as exc:
            logger.warning("Clawhub metadata load failed: {}", exc)

    def _save_metadata(self) -> None:
        rows = [
            {
                "name": meta.name,
                "version": meta.version,
                "file": meta.file,
                "entrypoint": meta.entrypoint,
            }
            for meta in self._metas.values()
        ]
        self.metadata_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


import contextlib

