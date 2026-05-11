"""
分布式智能体系统测试
"""

import pytest
import asyncio
from src.agents.distributed import (
    AgentCommunicationProtocol,
    AgentCapability,
    PredictionAgent,
    AnalysisAgent,
    OrchestratorAgent,
    AgentTask,
    MessageType,
)


@pytest.mark.asyncio
async def test_protocol_initialization():
    """测试协议初始化"""
    protocol = AgentCommunicationProtocol()
    await protocol.start()

    assert protocol._running is True
    assert protocol.registry is not None

    await protocol.stop()
    assert protocol._running is False


@pytest.mark.asyncio
async def test_agent_registration():
    """测试智能体注册"""
    protocol = AgentCommunicationProtocol()
    await protocol.start()

    capability = AgentCapability(
        name="test_capability",
        description="Test capability",
        input_schema={},
        output_schema={},
    )

    agent = PredictionAgent("wan", protocol)
    agent.agent_id = "test_agent_1"
    await agent.start()

    registered_agent = await protocol.registry.get_agent("test_agent_1")
    assert registered_agent is not None
    assert registered_agent.name == "PredictionAgent_wan"

    await agent.stop()
    await protocol.stop()


@pytest.mark.asyncio
async def test_message_sending():
    """测试消息发送"""
    protocol = AgentCommunicationProtocol()
    await protocol.start()

    received_messages = []

    async def handle_request(msg):
        received_messages.append(msg)

    protocol.register_handler(MessageType.REQUEST, handle_request)

    agent1 = PredictionAgent("wan", protocol)
    agent1.agent_id = "agent_1"

    agent2 = AnalysisAgent(protocol)
    agent2.agent_id = "agent_2"

    msg_id = await agent1.send_to("agent_2", {"test": "data"})

    await asyncio.sleep(0.5)

    assert len(received_messages) == 1
    assert received_messages[0].content["test"] == "data"

    await protocol.stop()


@pytest.mark.asyncio
async def test_prediction_agent():
    """测试预测智能体"""
    protocol = AgentCommunicationProtocol()
    await protocol.start()

    agent = PredictionAgent("wan", protocol)
    agent.agent_id = "predictor_1"
    await agent.start()

    test_data = list(range(100))
    result = await agent.predict(test_data)

    assert "prediction" in result
    assert "confidence" in result
    assert len(result["prediction"]) > 0

    await agent.stop()
    await protocol.stop()


@pytest.mark.asyncio
async def test_analysis_agent():
    """测试分析智能体"""
    protocol = AgentCommunicationProtocol()
    await protocol.start()

    agent = AnalysisAgent(protocol)
    agent.agent_id = "analyzer_1"
    await agent.start()

    test_data = [
        {"wan": 1, "qian": 2, "bai": 3},
        {"wan": 2, "qian": 3, "bai": 4},
        {"wan": 1, "qian": 2, "bai": 3},
    ]

    result = await agent.analyze_patterns(test_data)

    assert "patterns" in result
    assert result["total_records"] == 3
    assert len(result["patterns"]) > 0

    await agent.stop()
    await protocol.stop()


@pytest.mark.asyncio
async def test_orchestrator():
    """测试编排智能体"""
    orchestrator = OrchestratorAgent()

    await orchestrator.initialize_team()

    assert len(orchestrator.prediction_agents) == 5
    assert orchestrator.analysis_agent is not None
    assert orchestrator.data_agent is not None
    assert orchestrator.evaluation_agent is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
