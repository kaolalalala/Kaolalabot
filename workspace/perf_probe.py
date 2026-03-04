import time
import tracemalloc
import asyncio
from pathlib import Path

from kaolalabot.config.loader import load_config
from kaolalabot.bus.queue import MessageBus
from kaolalabot.channels.manager import ChannelManager
from kaolalabot.agent.loop import AgentLoop
from kaolalabot.agent.tools import create_default_tools
from kaolalabot.providers.provider_wrapper import create_fallback_provider
from kaolalabot.bus.events import InboundMessage

cfg = load_config()
cfg.channels.voice.enabled = False

tracemalloc.start()
t0 = time.perf_counter()
bus = MessageBus()
manager = ChannelManager(cfg, bus)
t1 = time.perf_counter()

provider = create_fallback_provider(cfg)
agent = AgentLoop(
    bus=bus,
    provider=provider,
    workspace=Path('D:/ai/kaolalabot/workspace'),
    model=cfg.agents.defaults.model,
    temperature=cfg.agents.defaults.temperature,
    max_tokens=cfg.agents.defaults.max_tokens,
    max_iterations=cfg.agents.defaults.max_tool_iterations,
    memory_window=cfg.agents.defaults.memory_window,
    reasoning_effort=cfg.agents.defaults.reasoning_effort,
    channels_config=cfg.channels,
    tool_registry=create_default_tools(workspace=Path('D:/ai/kaolalabot/workspace'), config=cfg.tools),
    tools_config=cfg.tools,
    rate_limit_config=cfg.rate_limit,
)
t2 = time.perf_counter()

async def run_once():
    return await agent._process_message(InboundMessage(channel='cli', sender_id='u', chat_id='c', content='/help'))

resp = asyncio.run(run_once())
t3 = time.perf_counter()

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

lines = [
    'baseline.channel_manager_init_ms=%.2f' % ((t1-t0)*1000),
    'baseline.agent_init_ms=%.2f' % ((t2-t1)*1000),
    'baseline.help_roundtrip_ms=%.2f' % ((t3-t2)*1000),
    'baseline.mem_peak_kb=%.2f' % (peak/1024),
    'baseline.channels=%s' % ','.join(manager.enabled_channels),
    'baseline.help_len=%d' % len(resp.content or ''),
]
print('\n'.join(lines))
Path('D:/ai/kaolalabot/workspace/perf_baseline.txt').write_text('\n'.join(lines), encoding='utf-8')
