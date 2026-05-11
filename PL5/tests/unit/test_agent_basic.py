"""
智能体框架基础测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.agents.base_agent import BaseAgent, AgentTask, AgentResult


class TestAgentTask:
    """代理任务测试"""

    def test_agent_task_creation(self):
        """测试创建代理任务"""
        task = AgentTask(
            task_id="test_task_001",
            task_type="test_type",
            params={"key": "value"},
            priority=1,
        )

        assert task.task_id == "test_task_001"
        assert task.task_type == "test_type"
        assert task.params == {"key": "value"}
        assert task.priority == 1
        assert task.created_at is not None

    def test_agent_task_to_dict(self):
        """测试任务转换为字典"""
        task = AgentTask(
            task_id="test_task_002",
            task_type="test_type",
            params={"key": "value"},
        )

        task_dict = task.to_dict()

        assert task_dict["task_id"] == "test_task_002"
        assert task_dict["task_type"] == "test_type"
        assert task_dict["params"] == {"key": "value"}
        assert "created_at" in task_dict


class TestAgentResult:
    """代理结果测试"""

    def test_agent_result_success(self):
        """测试成功结果"""
        result = AgentResult.success(
            task_id="test_task_001",
            data={"result": "success"},
            execution_time=1.5,
        )

        assert result.success is True
        assert result.task_id == "test_task_001"
        assert result.data == {"result": "success"}
        assert result.execution_time == 1.5
        assert result.error is None

    def test_agent_result_failure(self):
        """测试失败结果"""
        result = AgentResult.failure(
            task_id="test_task_002",
            error="Test error",
            execution_time=0.5,
        )

        assert result.success is False
        assert result.task_id == "test_task_002"
        assert result.error == "Test error"
        assert result.execution_time == 0.5
        assert result.data is None


class TestBaseAgent:
    """基础代理测试"""

    @pytest.fixture
    def base_agent(self):
        """创建基础代理实例"""
        return BaseAgent(name="TestAgent", max_workers=2)

    def test_base_agent_init(self, base_agent):
        """测试基础代理初始化"""
        assert base_agent.name == "TestAgent"
        assert base_agent.max_workers == 2
        assert base_agent.is_running is False
        assert base_agent.tasks_completed == 0
        assert base_agent.tasks_failed == 0

    def test_base_agent_validate(self, base_agent):
        """测试代理验证方法"""
        valid_task = AgentTask(
            task_id="test_task",
            task_type="test_type",
            params={},
        )

        assert base_agent.validate(valid_task) is True

        # 无效任务应该返回False
        invalid_task = Mock()
        invalid_task.task_id = None

        assert base_agent.validate(invalid_task) is False

    def test_base_agent_get_capabilities(self, base_agent):
        """测试获取代理能力"""
        capabilities = base_agent.get_capabilities()

        assert capabilities["name"] == "TestAgent"
        assert "supported_tasks" in capabilities
        assert "max_workers" in capabilities

    @pytest.mark.asyncio
    async def test_base_agent_execute_not_implemented(self, base_agent):
        """测试未实现的执行方法"""
        task = AgentTask(
            task_id="test_task",
            task_type="test_type",
            params={},
        )

        with pytest.raises(NotImplementedError):
            await base_agent.execute(task)


class MockAgent(BaseAgent):
    """模拟代理用于测试"""

    def __init__(self, name="MockAgent", max_workers=1):
        super().__init__(name, max_workers)
        self.mock_execute = AsyncMock()

    async def execute(self, task: AgentTask) -> AgentResult:
        return await self.mock_execute(task)


class TestMockAgent:
    """模拟代理测试"""

    @pytest.mark.asyncio
    async def test_mock_agent_execute(self):
        """测试模拟代理执行"""
        agent = MockAgent()
        task = AgentTask(task_id="test_task", task_type="test_type")

        # 设置模拟返回值
        expected_result = AgentResult.success(
            task_id="test_task",
            data={"mock": "data"},
        )
        agent.mock_execute.return_value = expected_result

        # 执行任务
        result = await agent.execute(task)

        # 验证结果
        assert result == expected_result
        agent.mock_execute.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_mock_agent_run_task(self):
        """测试模拟代理运行任务"""
        agent = MockAgent()
        task = AgentTask(task_id="test_task", task_type="test_type")

        # 设置模拟返回值
        expected_result = AgentResult.success(task_id="test_task")
        agent.mock_execute.return_value = expected_result

        # 运行任务
        result = await agent.run_task(task)

        # 验证结果
        assert result == expected_result
        assert agent.tasks_completed == 1
        assert agent.tasks_failed == 0

    @pytest.mark.asyncio
    async def test_mock_agent_run_task_failure(self):
        """测试模拟代理任务失败"""
        agent = MockAgent()
        task = AgentTask(task_id="test_task", task_type="test_type")

        # 设置模拟抛出异常
        agent.mock_execute.side_effect = Exception("Test error")

        # 运行任务
        result = await agent.run_task(task)

        # 验证结果
        assert result.success is False
        assert "Test error" in result.error
        assert agent.tasks_completed == 0
        assert agent.tasks_failed == 1


class TestAsyncAgentOperations:
    """异步代理操作测试"""

    @pytest.mark.asyncio
    async def test_agent_shutdown(self):
        """测试代理关闭"""
        agent = MockAgent()

        # 代理应该可以正常关闭
        await agent.shutdown()

        # 多次关闭不应该出错
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_agent_success_rate(self):
        """测试代理成功率计算"""
        agent = MockAgent()

        # 初始状态
        assert agent.success_rate == 1.0  # 默认值

        # 完成任务
        task = AgentTask(task_id="test_task", task_type="test_type")
        success_result = AgentResult.success(task_id="test_task")
        agent.mock_execute.return_value = success_result

        await agent.run_task(task)
        assert agent.success_rate == 1.0  # 1/1 = 100%

        # 失败任务
        agent.mock_execute.side_effect = Exception("Error")

        await agent.run_task(task)
        assert agent.success_rate == 0.5  # 1/2 = 50%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
