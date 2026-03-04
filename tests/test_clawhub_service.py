from pathlib import Path

import pytest

from kaolalabot.services.clawhub import ClawhubSkillService


@pytest.mark.asyncio
async def test_clawhub_load_invoke_unload(tmp_path: Path):
    skills_dir = tmp_path / 'skills'
    index = tmp_path / 'index.json'
    svc = ClawhubSkillService(skills_dir=skills_dir, metadata_file=index, client=None)

    skill_file = skills_dir / 'hello.py'
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        'def run(payload, context):\n    return {"echo": payload.get("name", "")}',
        encoding='utf-8',
    )

    loaded = svc.load_skill('hello', skill_file)
    assert loaded['ok'] is True

    out = await svc.invoke_skill('hello', {'name': 'kaola'}, {})
    assert out['echo'] == 'kaola'

    assert svc.unload_skill('hello') is True
