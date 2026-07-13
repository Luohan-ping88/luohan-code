import unittest
import asyncio
import time
from src.ai.orchestrator import WorkflowEngine, Workflow
from src.ai.types import WorkflowStep, WorkflowStatus
from src.ai.security import get_validator, get_permission_manager, get_secrets_manager, get_scanner
from src.ai.performance import get_cache, get_performance_monitor, get_load_balancer, get_auto_scaler
from src.ai.api import app
from fastapi.testclient import TestClient


class TestCoreFunctionality(unittest.TestCase):
    """测试核心功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.client = TestClient(app)
        self.workflow_engine = WorkflowEngine()
        self.validator = get_validator()
        self.permission_manager = get_permission_manager()
        self.secrets_manager = get_secrets_manager()
        self.cache_manager = get_cache()
        self.performance_monitor = get_performance_monitor()
        self.load_balancer = get_load_balancer()
        self.auto_scaler = get_auto_scaler()
        self.scanner = get_scanner()
    
    def test_workflow_engine(self):
        """测试工作流引擎"""
        # 创建工作流
        steps = [
            WorkflowStep(
                name="step1",
                tool_name="echo",
                parameters={"message": "Hello"}
            ),
            WorkflowStep(
                name="step2",
                tool_name="echo",
                parameters={"message": "Hello"},
                condition_expr="{{step1.output}} == 'Hello'"
            )
        ]
        
        workflow = Workflow(name="test-workflow", description="Test workflow", steps=steps)
        
        # 执行工作流
        result = asyncio.run(self.workflow_engine.run_workflow(workflow))
        self.assertEqual(result["status"], WorkflowStatus.SUCCESS.value)
    
    def test_security_validator(self):
        """测试安全验证器"""
        # 测试有效的输入
        valid_input = {"name": "test", "age": 25}
        result = self.validator.validate_dict(valid_input)
        self.assertTrue(result)
        
        # 测试字符串验证
        valid_string = "test"
        result = self.validator.validate_string(valid_string)
        self.assertTrue(result)
    
    def test_permission_manager(self):
        """测试权限管理器"""
        # 测试权限检查
        user = {"id": "user1", "role": "user"}
        result = self.permission_manager.has_permission(user["role"], "calculator")
        self.assertTrue(result)
        
        # 测试角色权限
        admin_user = {"id": "admin1", "role": "admin"}
        result = self.permission_manager.has_permission(admin_user["role"], "any_tool")
        self.assertTrue(result)
    
    def test_secrets_manager(self):
        """测试密钥管理器"""
        # 测试存储和获取密钥
        secret_name = "test-secret"
        secret_value = "test-value"
        self.secrets_manager.set_secret(secret_name, secret_value)
        retrieved_value = self.secrets_manager.get_secret(secret_name)
        self.assertEqual(secret_value, retrieved_value)
        
        # 测试删除密钥
        result = self.secrets_manager.delete_secret(secret_name)
        self.assertTrue(result)
        retrieved_value = self.secrets_manager.get_secret(secret_name)
        self.assertIsNone(retrieved_value)
    
    def test_cache_manager(self):
        """测试缓存管理器"""
        # 测试缓存设置和获取
        key = "test-key"
        value = "test-value"
        self.cache_manager.set(key, value, ttl=60)
        cached_value = self.cache_manager.get(key)
        self.assertEqual(value, cached_value)
        
        # 测试缓存过期
        time.sleep(1)  # 等待1秒
        cached_value = self.cache_manager.get(key)
        self.assertEqual(value, cached_value)
    
    def test_performance_monitor(self):
        """测试性能监控"""
        from src.ai.performance import monitored
        
        # 测试性能监控
        @monitored()
        def test_function():
            time.sleep(0.1)
            return "test"
        
        result = test_function()
        self.assertEqual(result, "test")
        
        # 检查性能统计
        stats = self.performance_monitor.get_metrics("test_function")
        self.assertIn("count", stats)
        self.assertIn("total_time", stats)
    
    def test_load_balancer(self):
        """测试负载均衡器"""
        # 注册服务
        self.load_balancer.register_service("service1", "http://localhost:8000")
        services = self.load_balancer.list_services()
        self.assertIn("service1", services)
        
        # 获取服务
        service_url = self.load_balancer.get_service()
        self.assertEqual(service_url, "http://localhost:8000")
        
        # 注销服务
        self.load_balancer.unregister_service("service1")
        services = self.load_balancer.list_services()
        self.assertNotIn("service1", services)
    
    def test_auto_scaler(self):
        """测试自动扩展器"""
        # 测试扩展
        decision = self.auto_scaler.scale(0.8, 0.9)  # 高负载
        self.assertEqual(decision["action"], "scale_up")
        
        # 测试实例列表
        instances = self.auto_scaler.list_instances()
        self.assertIsInstance(instances, dict)
        self.assertGreater(len(instances), 0)
        
        # 测试无变化（最小实例数为1，无法进一步缩容）
        decision = self.auto_scaler.scale(0.1, 0.1)  # 低负载
        self.assertEqual(decision["action"], "no_change")
    
    def test_vulnerability_scanner(self):
        """测试漏洞扫描器"""
        # 测试输入验证扫描
        input_data = {"name": "test", "age": "not-a-number"}
        vulnerabilities = self.scanner.scan_input_validation(input_data)
        self.assertIsInstance(vulnerabilities, list)
        
        # 测试配置扫描
        config = {"debug": True}
        vulnerabilities = self.scanner.scan_config(config)
        self.assertIsInstance(vulnerabilities, list)
    
    def test_api_auth(self):
        """测试API认证"""
        # 测试登录
        response = self.client.post("/api/auth/login", params={"username": "admin", "password": "admin123"})
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        self.assertIsNotNone(token)
    
    def test_api_health(self):
        """测试API健康检查"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
