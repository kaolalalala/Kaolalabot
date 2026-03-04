"""Voice module tests."""

from tests.voice.fixtures import (
    AudioTestData,
    TestMetrics,
    MockProvider,
    MockAgentLoop,
    MockMessageBus,
)

from tests.voice.test_functional import (
    TestVAD,
    TestAudioIn,
    TestAudioOut,
    TestSessionFSM,
    TestTurnManager,
    TestChunkStrategy,
    TestASR,
    TestTTS,
    TestVoiceGatewayIntegration,
)

from tests.voice.test_integration import (
    TestGatewayProtocol,
    TestMessageBus,
    TestVoiceGatewayIntegration,
    TestDataFormat,
    TestErrorPropagation,
)

from tests.voice.test_performance import (
    TestPerformance,
    TestStability,
    TestResourceUsage,
    TestLoadScenarios,
    TestLatencyBreakdown,
)

from tests.voice.test_exceptions import (
    TestNetworkErrors,
    TestComponentFailures,
    TestMessageBusErrors,
    TestRecovery,
    TestGracefulDegradation,
    TestResourceExhaustion,
)

from tests.voice.test_e2e import (
    TestVoiceEndToEnd,
    TestVoiceGatewayE2E,
    TestLatencyE2E,
    TestDataIntegrity,
    TestErrorRecoveryE2E,
    TestFullPipeline,
)

__all__ = [
    "AudioTestData",
    "TestMetrics",
    "MockProvider",
    "MockAgentLoop",
    "MockMessageBus",
    "TestVAD",
    "TestAudioIn",
    "TestAudioOut",
    "TestSessionFSM",
    "TestTurnManager",
    "TestChunkStrategy",
    "TestASR",
    "TestTTS",
    "TestVoiceGatewayIntegration",
    "TestGatewayProtocol",
    "TestMessageBus",
    "TestDataFormat",
    "TestErrorPropagation",
    "TestPerformance",
    "TestStability",
    "TestResourceUsage",
    "TestLoadScenarios",
    "TestLatencyBreakdown",
    "TestNetworkErrors",
    "TestComponentFailures",
    "TestMessageBusErrors",
    "TestRecovery",
    "TestGracefulDegradation",
    "TestResourceExhaustion",
    "TestVoiceEndToEnd",
    "TestVoiceGatewayE2E",
    "TestLatencyE2E",
    "TestDataIntegrity",
    "TestErrorRecoveryE2E",
    "TestFullPipeline",
]
