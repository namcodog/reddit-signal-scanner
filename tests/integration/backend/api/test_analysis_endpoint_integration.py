"""集成测试示例 - 分析API端点

展示集成测试的最佳实践：
1. 测试组件间交互
2. 可以使用Mock或Real API
3. 验证接口契约
4. 测试错误处理链
"""

import asyncio
from typing import Any, AsyncIterator, Awaitable, Dict, List

import pytest
from httpx import AsyncClient, Response

from tests.fixtures.base_fixtures import TestIsolation, AssertHelpers
from tests.fixtures.mock_services import MockServiceFactory
from tests.utils.api_switcher import (
    ApiSwitcher,
    ContractValidator,
    api_switcher,
    contract_validator,
)


@TestIsolation.integration_test
class TestAnalysisEndpointIntegration:
    """分析端点集成测试"""
    
    @pytest.fixture
    async def authenticated_client(
        self, api_switcher: ApiSwitcher
    ) -> AsyncIterator[AsyncClient]:
        """获取认证的客户端"""
        # 根据当前模式创建客户端
        base_url = (
            "http://localhost:8000"
            if not api_switcher.is_mock_mode
            else "http://mock-api"
        )

        async with AsyncClient(base_url=base_url) as client:
            # 登录获取token
            if api_switcher.is_mock_mode:
                auth_service = MockServiceFactory.get_auth_service()
                auth_data = await auth_service.login("test@example.com", "password123")
                token = auth_data["access_token"]
            else:
                response = await client.post("/api/auth/login", json={
                    "email": "test@example.com",
                    "password": "password123"
                })
                token = response.json()["access_token"]
                
            # 设置认证头
            client.headers["Authorization"] = f"Bearer {token}"
            yield client
            
    async def test_create_analysis_task_success(
        self,
        authenticated_client: AsyncClient,
        contract_validator: ContractValidator,
        api_switcher: ApiSwitcher,
    ) -> None:
        """测试创建分析任务 - 成功场景"""
        # 准备请求数据
        request_data = {
            "keywords": ["python", "fastapi", "react"],
            "limit": 50,
            "subreddits": ["entrepreneur", "startups"]
        }
        
        # 发送请求
        response = await authenticated_client.post(
            "/api/v1/discovery/analyze",
            json=request_data
        )
        
        # 验证响应
        AssertHelpers.assert_api_response_ok(response, 201)
        data = response.json()
        
        # 验证响应结构
        required_fields = ["task_id", "status", "created_at", "estimated_completion"]
        AssertHelpers.assert_data_integrity(data, required_fields)
        
        # 验证响应符合契约
        contract_validator.register_contract("/api/v1/discovery/analyze", {
            "task_id": str,
            "status": str,
            "created_at": str,
            "estimated_completion": str
        })
        contract_validator.validate_response(
            "/api/v1/discovery/analyze",
            data,
            is_mock=api_switcher.is_mock_mode,
        )
        
        # 验证具体值
        assert data["status"] in ["pending", "running"]
        assert len(data["task_id"]) == 36  # UUID格式
        
    async def test_create_analysis_task_validation_errors(
        self, authenticated_client: AsyncClient
    ) -> None:
        """测试创建分析任务 - 输入验证错误"""
        # 测试各种无效输入
        invalid_inputs: List[Dict[str, Any]] = [
            # 空关键词
            {"keywords": [], "limit": 50},
            # 缺少必需字段
            {"limit": 50},
            # 无效限制
            {"keywords": ["test"], "limit": 0},
            {"keywords": ["test"], "limit": 1001},
            # 无效关键词类型
            {"keywords": "not a list", "limit": 50},
            # 空字符串关键词
            {"keywords": ["", "valid", ""], "limit": 50},
        ]
        
        for invalid_input in invalid_inputs:
            response = await authenticated_client.post(
                "/api/v1/discovery/analyze",
                json=invalid_input
            )
            
            # 应该返回400错误
            assert response.status_code == 400
            error_data = response.json()
            assert "error" in error_data
            assert "message" in error_data["error"]
            
    async def test_unauthorized_access(self) -> None:
        """测试未授权访问"""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            # 不带token的请求
            response = await client.post(
                "/api/v1/discovery/analyze",
                json={"keywords": ["test"], "limit": 50}
            )
            
            assert response.status_code == 401
            AssertHelpers.assert_error_response(response, "UNAUTHORIZED")
            
    async def test_rate_limiting(self, authenticated_client: AsyncClient) -> None:
        """测试速率限制"""
        # 快速发送多个请求
        tasks: List[Awaitable[Response]] = []
        for i in range(15):  # 假设限制是10请求/分钟
            task = authenticated_client.post(
                "/api/v1/discovery/analyze",
                json={"keywords": [f"test{i}"], "limit": 10}
            )
            tasks.append(task)
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败的请求
        success_count = sum(
            1
            for response in responses
            if isinstance(response, Response) and response.status_code < 400
        )
        rate_limited_count = sum(
            1
            for response in responses
            if isinstance(response, Response) and response.status_code == 429
        )
        
        # 应该有一些请求被限流
        assert rate_limited_count > 0
        assert success_count < len(tasks)
        
    async def test_concurrent_task_creation(
        self, authenticated_client: AsyncClient
    ) -> None:
        """测试并发任务创建 - 多租户隔离"""
        # 创建多个并发任务
        tasks: List[Awaitable[Response]] = []
        for i in range(5):
            task = authenticated_client.post(
                "/api/v1/discovery/analyze",
                json={
                    "keywords": [f"concurrent_test_{i}"],
                    "limit": 20
                }
            )
            tasks.append(task)
            
        # 并发执行
        responses = await asyncio.gather(*tasks)

        # 验证所有请求都成功
        task_ids: List[str] = []
        for response in responses:
            AssertHelpers.assert_api_response_ok(response, 201)
            data = response.json()
            task_ids.append(data["task_id"])
            
        # 验证任务ID都是唯一的
        assert len(set(task_ids)) == len(task_ids)
        
    async def test_mock_specific_behavior(
        self,
        authenticated_client: AsyncClient,
        api_switcher: ApiSwitcher,
    ) -> None:
        """测试Mock特定行为 - 错误注入"""
        if not api_switcher.is_mock_mode:
            api_switcher.switch_to_mock()
        # 配置Mock服务的错误率
        if hasattr(authenticated_client, "_base_url") and "mock" in str(authenticated_client._base_url):
            MockServiceFactory.configure_error_rates(0.5)  # 50%错误率
            
        # 发送多个请求，验证错误处理
        error_count = 0
        for _ in range(10):
            response = await authenticated_client.post(
                "/api/v1/discovery/analyze",
                json={"keywords": ["error_test"], "limit": 10}
            )
            
            if response.status_code >= 500:
                error_count += 1
                
        # 应该有一些请求失败
        assert error_count > 0
        
        # 重置错误率
        MockServiceFactory.configure_error_rates(0.0)
        
    async def test_task_status_check_flow(
        self, authenticated_client: AsyncClient
    ) -> None:
        """测试任务状态检查流程 - 完整工作流"""
        # 1. 创建任务
        create_response = await authenticated_client.post(
            "/api/v1/discovery/analyze",
            json={"keywords": ["workflow_test"], "limit": 30}
        )
        AssertHelpers.assert_api_response_ok(create_response, 201)
        task_id = create_response.json()["task_id"]
        
        # 2. 检查任务状态（轮询）
        max_attempts = 10
        for attempt in range(max_attempts):
            status_response = await authenticated_client.get(
                f"/api/v1/status/{task_id}"
            )
            AssertHelpers.assert_api_response_ok(status_response)
            
            status_data = status_response.json()
            assert "status" in status_data
            assert "progress" in status_data
            
            if status_data["status"] == "completed":
                # 3. 获取结果
                result_response = await authenticated_client.get(
                    f"/api/v1/report/{task_id}"
                )
                AssertHelpers.assert_api_response_ok(result_response)
                
                result_data = result_response.json()
                assert "insights" in result_data
                assert "sources" in result_data
                break
                
            # 等待后重试
            await asyncio.sleep(1)
        else:
            pytest.fail(f"任务在{max_attempts}次尝试后未完成")
            
    async def test_database_transaction_rollback(
        self,
        authenticated_client: AsyncClient,
        api_switcher: ApiSwitcher,
    ) -> None:
        """测试数据库事务回滚 - 错误情况下的数据完整性"""
        if api_switcher.is_mock_mode:
            pytest.skip("Mock模式不测试数据库事务")
            
        # 准备会导致部分失败的数据
        request_data = {
            "keywords": ["test"] * 100,  # 大量重复关键词，可能触发某些约束
            "limit": 5000,  # 超大限制，可能导致资源问题
            "force_error": True  # 特殊标记，触发错误
        }
        
        # 记录请求前的状态
        # TODO: 查询数据库获取当前任务数
        
        # 发送请求
        response = await authenticated_client.post(
            "/api/v1/discovery/analyze",
            json=request_data
        )
        
        # 即使请求失败，数据库也不应该有部分数据
        # TODO: 验证数据库状态未改变


@pytest.mark.parametrize("api_mode", ["mock", "real"])
async def test_contract_consistency(
    api_mode: str,
    contract_validator: ContractValidator,
    api_switcher: ApiSwitcher,
) -> None:
    """测试Mock和Real API的契约一致性"""
    # 这个测试会在两种模式下运行，确保返回的数据结构一致
    
    switcher = api_switcher
    if api_mode == "mock":
        switcher.switch_to_mock()
    else:
        try:
            switcher.switch_to_real()
        except pytest.skip.Exception:
            return  # Real API不可用，跳过

    # 执行相同的请求
    async with AsyncClient() as client:
        # ... 执行测试并记录响应 ...
        _ = client

    # 测试结束后比较两种模式的响应
    contract_validator.compare_responses("/api/v1/discovery/analyze")
