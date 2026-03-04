#!/usr/bin/env python
"""语音模式独立启动脚本

用法:
    python run_voice.py
    
或指定配置文件:
    python run_voice.py --config path/to/config.yaml
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

from loguru import logger


def setup_logging(verbose: bool = False):
    """设置日志"""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
    )


async def main():
    parser = argparse.ArgumentParser(description="kaolalabot 语音模式")
    parser.add_argument(
        "--config", 
        type=str, 
        default="kaolalabot/voice/config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--verbose", 
        "-v",
        action="store_true",
        help="显示详细日志"
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    logger.info("=" * 50)
    logger.info("kaolalabot 语音模式")
    logger.info("=" * 50)

    # 导入必要的模块
    from kaolalabot.voice import VoiceConfig, VoiceShell
    from kaolalabot.agent.loop import AgentLoop
    from kaolalabot.bus.queue import MessageBus
    from kaolalabot.config.loader import load_config
    from kaolalabot.providers.litellm_provider import LiteLLMProvider
    from pathlib import Path

    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        import yaml
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            voice_cfg = data.get("voice", {})
            vad_cfg = data.get("vad", {})
            asr_cfg = data.get("asr", {})
            tts_cfg = data.get("tts", {})
            
            config = VoiceConfig(
                sample_rate=voice_cfg.get("sample_rate", 16000),
                frame_duration_ms=voice_cfg.get("frame_duration_ms", 20),
                channels=voice_cfg.get("channels", 1),
                vad_aggressiveness=vad_cfg.get("aggressiveness", 1),
                vad_enabled=vad_cfg.get("enabled", True),
                vad_min_speech_duration_ms=vad_cfg.get("min_speech_duration_ms", 250),
                vad_min_silence_duration_ms=vad_cfg.get("min_silence_duration_ms", 5000),
                vad_speech_timeout_ms=vad_cfg.get("speech_timeout_ms", 3000),
                vad_energy_threshold=vad_cfg.get("energy_threshold", 500.0),
                asr_model_size=asr_cfg.get("model_size", "tiny"),
                asr_language=asr_cfg.get("language", "auto"),
                asr_device=asr_cfg.get("device", "auto"),
                asr_window_interval_ms=asr_cfg.get("window_interval_ms", 500),
                asr_final_silence_ms=asr_cfg.get("final_silence_ms", 1000),
                tts_voice=tts_cfg.get("voice", "zh-CN-XiaoxiaoNeural"),
                tts_rate=tts_cfg.get("rate", "+0%"),
                tts_max_chars_per_chunk=tts_cfg.get("max_chars_per_chunk", 50),
                tts_chunk_interval_ms=tts_cfg.get("chunk_interval_ms", 800),
                turn_manager_enabled=True,
                turn_manager_barge_in=True,
            )
            print(f"DEBUG: vad_aggressiveness = {config.vad_aggressiveness}")
            logger.info(f"已加载配置: {config_path}")
    else:
        config = VoiceConfig()
        logger.info("使用默认配置")

    # 创建VoiceShell
    # 注意：需要先创建AgentLoop并连接
    
    print("正在初始化Agent...")
    
    # 加载配置
    config_loader = None
    try:
        config_loader = load_config()
    except Exception as e:
        print(f"警告: 无法加载配置文件: {e}")
        print("将使用基本配置...")
        config_loader = None
    
    # 创建LLM Provider
    provider = None
    if config_loader:
        try:
            provider = LiteLLMProvider(
                api_key=config_loader.get_api_key(),
                api_base=config_loader.get_api_base(),
                default_model="deepseek/deepseek-coder",
            )
        except Exception as e:
            print(f"警告: 无法创建LLM Provider: {e}")
    
    # 创建AgentLoop
    if provider:
        workspace = Path("workspace")
        agent_loop = AgentLoop(
            bus=MessageBus(),
            provider=provider,
            workspace=workspace,
        )
        print("✓ Agent已创建")
        
        # 创建VoiceShell并连接Agent
        shell = VoiceShell(config=config, agent_loop=agent_loop)
    else:
        print("⚠ 没有LLM Provider，语音将只识别文字但无法获得AI回复")
        shell = VoiceShell(config=config, agent_loop=None)
    
    # 设置信号处理
    loop = asyncio.get_event_loop()
    running = True
    
    def signal_handler(sig):
        nonlocal running
        logger.info(f"收到信号 {sig}，正在关闭...")
        running = False
        asyncio.create_task(shutdown())
    
    async def shutdown():
        logger.info("正在停止语音服务...")
        await shell.stop()
        logger.info("语音服务已停止")
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: signal_handler(sig))
        except NotImplementedError:
            pass

    logger.info("启动语音服务...")
    
    try:
        await shell.initialize()
        await shell.start()
        
        logger.info("=" * 50)
        logger.info("语音服务已启动!")
        logger.info("请对着麦克风说话...")
        logger.info("按 Ctrl+C 退出")
        logger.info("=" * 50)
        
        # 保持运行
        while running:
            await asyncio.sleep(0.5)
            
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"错误: {e}")
    finally:
        await shell.stop()
        logger.info("程序结束")


if __name__ == "__main__":
    asyncio.run(main())
