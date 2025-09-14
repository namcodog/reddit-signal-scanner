"""测试框架自检测试 - 验证关键功能

这些是元测试(meta-tests)，确保测试框架本身的可靠性
只测试最关键的功能，避免过度工程化
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from tests.fixtures.base_fixtures import TestLayerMarker
from tests.fixtures.mock_services import MockServiceFactory, TestDataGenerator
from tests.utils.api_switcher import ApiSwitcher, ContractValidator


class TestFrameworkCriticalFeatures:
    """测试框架关键功能验证"""
    
    def test_mock_services_deterministic(self):
        """验证Mock服务的确定性 - 相同输入应该产生相同输出"""
        factory = MockServiceFactory()
        
        # 多次调用应该返回相同的实例（单例模式）
        client1 = factory.get_reddit_client()
        client2 = factory.get_reddit_client()
        assert client1 is client2
        
        # 相同的关键词应该生成相同的数据
        posts1 = asyncio.run(client1.search_posts(["python"], limit=5))
        posts2 = asyncio.run(client1.search_posts(["python"], limit=5))
        
        assert len(posts1) == len(posts2)
        for p1, p2 in zip(posts1, posts2):
            assert p1.id == p2.id
            assert p1.title == p2.title
            assert p1.score == p2.score
            
    def test_api_switcher_isolation(self):
        """验证API切换器的隔离性 - 不同测试之间不应相互影响"""
        # 第一个切换器
        switcher1 = ApiSwitcher()
        switcher1.switch_to_mock()
        assert switcher1.is_mock_mode
        
        # 第二个切换器应该独立
        switcher2 = ApiSwitcher()
        # 应该是原始状态，不受switcher1影响
        assert switcher2.is_mock_mode == switcher2.original_mode
        
        # 恢复后不应影响其他实例
        switcher1.restore()
        assert switcher2.is_mock_mode == switcher2.original_mode
        
    def test_performance_timer_accuracy(self):
        """验证性能计时器的准确性"""
        import time
        
        # 创建Timer实例（不使用fixture）
        class Timer:
            def __init__(self):
                self.start_time = None
                self.end_time = None
                self.duration = None
                self.checkpoints = {}
            
            def start(self):
                self.start_time = time.time()
                return self
            
            def checkpoint(self, name: str):
                self.checkpoints[name] = time.time()
                
            def stop(self):
                self.end_time = time.time()
                if self.start_time:
                    self.duration = self.end_time - self.start_time
                return self.duration
        
        timer = Timer()
        
        # 测试基本计时
        timer.start()
        time.sleep(0.1)  # 100ms
        timer.stop()
        
        # 允许20ms的误差（系统调度等因素）
        assert 0.08 <= timer.duration <= 0.12
        
        # 测试检查点功能
        timer2 = Timer()
        timer2.start()
        
        time.sleep(0.05)
        timer2.checkpoint("step1")
        
        time.sleep(0.05)
        timer2.checkpoint("step2")
        
        timer2.stop()
        
        assert "step1" in timer2.checkpoints
        assert "step2" in timer2.checkpoints
        assert timer2.checkpoints["step1"] < timer2.checkpoints["step2"]
        
    def test_contract_validator_basic(self):
        """验证契约验证器的基本功能"""
        validator = ContractValidator()
        
        # 定义简单的契约
        from pydantic import BaseModel
        
        class SimpleResponse(BaseModel):
            id: str
            status: str
            data: dict
            
        validator.register_contract("/test/endpoint", SimpleResponse)
        
        # Mock响应应该通过验证
        mock_response = {
            "id": "123",
            "status": "ok",
            "data": {"key": "value"}
        }
        
        # 不应该抛出异常
        validator.validate_response("/test/endpoint", mock_response, is_mock=True)
        
        # 无效响应应该失败
        invalid_response = {
            "id": "123",
            "status": "ok"
            # 缺少 data 字段
        }
        
        with pytest.raises(AssertionError):
            validator.validate_response("/test/endpoint", invalid_response, is_mock=True)
            
    def test_test_data_generator_edge_cases(self):
        """验证测试数据生成器的边界条件"""
        edge_cases = TestDataGenerator.generate_edge_case_keywords()
        
        # 应该包含各种边界情况
        assert len(edge_cases) > 5
        
        # 验证包含了关键的边界条件
        has_single = any(len(case) == 1 for case in edge_cases)
        has_many = any(len(case) > 10 for case in edge_cases)
        has_unicode = any(any(ord(c) > 127 for keyword in case for c in keyword) for case in edge_cases)
        has_empty = any("" in case for case in edge_cases)
        
        assert has_single, "应该包含单个关键词的情况"
        assert has_many, "应该包含大量关键词的情况"
        assert has_unicode, "应该包含Unicode字符"
        assert has_empty, "应该包含空字符串情况"
        
    def test_layer_marker_detection(self):
        """验证测试层级标记检测"""
        # 创建带标记的测试函数
        @pytest.mark.unit
        def unit_test(): pass
        
        @pytest.mark.integration
        def integration_test(): pass
        
        @pytest.mark.system
        def system_test(): pass
        
        # 验证层级检测
        assert TestLayerMarker.get_layer_from_test(unit_test) == "unit"
        assert TestLayerMarker.get_layer_from_test(integration_test) == "integration"
        assert TestLayerMarker.get_layer_from_test(system_test) == "system"
        
        # 无标记的测试
        def unmarked_test(): pass
        assert TestLayerMarker.get_layer_from_test(unmarked_test) == "unknown"
        
    @pytest.mark.asyncio
    async def test_mock_service_error_injection(self):
        """验证Mock服务的错误注入功能"""
        # 重置工厂
        MockServiceFactory.reset_all()
        
        # 获取服务并设置错误率
        reddit_client = MockServiceFactory.get_reddit_client()
        
        # 设置100%错误率
        reddit_client.error_rate = 1.0
        
        # 应该总是失败
        with pytest.raises(Exception) as exc_info:
            await reddit_client.search_posts(["test"])
            
        assert "暂时不可用" in str(exc_info.value)
        
        # 设置0%错误率
        reddit_client.error_rate = 0.0
        
        # 应该总是成功
        posts = await reddit_client.search_posts(["test"])
        assert len(posts) > 0
        
    def test_mock_service_call_tracking(self):
        """验证Mock服务的调用追踪"""
        MockServiceFactory.reset_all()
        
        # 执行一些操作
        reddit = MockServiceFactory.get_reddit_client()
        auth = MockServiceFactory.get_auth_service()
        
        asyncio.run(reddit.search_posts(["test"]))
        asyncio.run(reddit.search_posts(["test2"]))
        asyncio.run(auth.login("test@example.com", "password123"))
        
        # 获取调用统计
        stats = MockServiceFactory.get_call_stats()
        
        assert stats["reddit"] == 2
        assert stats["auth"] == 1


@pytest.mark.smoke
class TestFrameworkSmokeTests:
    """框架冒烟测试 - 快速验证基本功能"""
    
    def test_imports_work(self):
        """验证所有关键导入正常"""
        # 如果能运行到这里，说明导入没问题
        from tests.fixtures import base_fixtures, mock_services
        from tests.utils import api_switcher
        assert True
        
    def test_core_classes_instantiable(self):
        """验证核心类可以实例化"""
        # 不直接调用fixture，而是验证类的可实例化性
        switcher = ApiSwitcher()
        assert switcher is not None
        
        factory = MockServiceFactory()
        assert factory is not None
        
        validator = ContractValidator()
        assert validator is not None


# 运行自检的便捷命令
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])