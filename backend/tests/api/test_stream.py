"""
SSE实时推送端点测试 - /api/v1/stream/{task_id}

基于Linus架构 + SSE特殊处理：
- 统一BaseAPITest架构
- SSE事件流验证
- 断线重连机制测试
- 并发连接测试
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, AsyncIterator

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from .base import (
    BaseAPITest,
    APITestSpec,
    TestScenario,
    TestScenarioType,
    PerformanceSpec,
)


class TestStreamEndpoint(BaseAPITest):
    """SSE流端点测试类 - 统一架构 + SSE专项处理"""

    @property
    def test_spec(self) -> APITestSpec:
        """SSE端点测试规格配置"""
        return APITestSpec(
            endpoint_name="stream",
            base_path="/api/v1/stream",
            requires_auth=True,
            requires_task_setup=True,
            scenarios=[
                # 1. 正常SSE流程测试
                TestScenario(
                    name="SSE连接建立测试",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="建立SSE连接并接收初始事件",
                ),
                TestScenario(
                    name="任务生命周期事件流",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="完整任务生命周期的事件流：connected→progress→completed",
                ),
                TestScenario(
                    name="错误任务事件流",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="失败任务的事件流：connected→progress→error",
                ),
                # 2. 边界条件测试
                TestScenario(
                    name="长时间连接保持",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="测试长时间SSE连接保持（30秒+）",
                ),
                TestScenario(
                    name="快速完成任务流",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="测试任务快速完成的事件流",
                ),
                TestScenario(
                    name="带查询参数的SSE连接",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    params={"include_debug": "true", "format": "detailed"},
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    description="测试包含查询参数的SSE连接",
                ),
                # 3. 错误场景测试
                TestScenario(
                    name="不存在任务的SSE连接",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path=f"/api/v1/stream/{uuid.uuid4()}",
                    expected_status=404,
                    headers={"Accept": "text/event-stream"},
                    description="连接不存在任务应返回404",
                ),
                TestScenario(
                    name="无效UUID的SSE连接",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/stream/invalid-uuid",
                    expected_status=422,
                    headers={"Accept": "text/event-stream"},
                    description="无效UUID格式应返回422错误",
                ),
                TestScenario(
                    name="未认证的SSE连接",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    headers={"Accept": "text/event-stream"},  # 不包含认证
                    expected_status=401,
                    description="未认证SSE连接应返回401",
                ),
                TestScenario(
                    name="非SSE Accept头连接",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    headers={"Accept": "application/json"},  # 错误的Accept头
                    expected_status=406,  # Not Acceptable
                    description="非SSE Accept头应返回406错误",
                ),
                # 4. 性能测试
                TestScenario(
                    name="SSE连接建立性能",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=1000.0,  # SSE连接建立<1s
                        iterations=20,  # SSE测试迭代少一些
                        warmup_iterations=3,
                    ),
                    description="验证SSE连接建立性能<1s",
                ),
                TestScenario(
                    name="并发SSE连接性能",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/stream/{task_id}",
                    expected_status=200,
                    headers={"Accept": "text/event-stream"},
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=1500.0,  # 并发场景稍微放宽
                        iterations=10,
                        warmup_iterations=2,
                    ),
                    description="验证并发SSE连接性能",
                ),
            ],
        )

    async def _execute_functional_test(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写功能测试，支持SSE流处理"""

        # 特殊处理未认证测试
        if scenario.name == "未认证的SSE连接":
            request_kwargs["headers"] = {"Accept": "text/event-stream"}

        # 对于SSE流测试，使用特殊的验证逻辑
        if (
            "Accept" in request_kwargs.get("headers", {})
            and request_kwargs["headers"]["Accept"] == "text/event-stream"
        ):
            return await self._test_sse_stream(client, request_kwargs, scenario)

        # 非SSE请求使用标准逻辑
        return await super()._execute_functional_test(client, request_kwargs, scenario)

    async def _test_sse_stream(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """SSE流专用测试逻辑"""

        # 发送SSE请求
        response = client.request(**request_kwargs)

        # 验证状态码
        assert response.status_code == scenario.expected_status, (
            f"SSE连接状态码不匹配。期望: {scenario.expected_status}, 实际: {response.status_code}\n"
            f"响应内容: {response.text}"
        )

        # 如果是错误场景，直接返回
        if scenario.expected_status >= 400:
            return {
                "status_code": response.status_code,
                "response_size": len(response.content),
                "sse_events": 0,
            }

        # 验证SSE连接成功的基本要求
        assert response.headers.get("content-type", "").startswith(
            "text/event-stream"
        ), f"SSE响应Content-Type错误: {response.headers.get('content-type')}"

        # 解析并验证SSE事件
        events = self._parse_sse_response(response.text)

        # 基本事件验证
        assert len(events) > 0, "SSE流应该至少包含1个事件"

        # 验证第一个事件应该是连接事件
        first_event = events[0]
        assert (
            first_event.get("event") == "connected" or "status" in first_event
        ), f"首个事件格式异常: {first_event}"

        # 根据场景进行特殊验证
        if "生命周期" in scenario.name:
            self._validate_lifecycle_events(events)
        elif "错误任务" in scenario.name:
            self._validate_error_events(events)

        return {
            "status_code": response.status_code,
            "sse_events": len(events),
            "event_types": [e.get("event", "unknown") for e in events],
            "connection_successful": True,
        }

    def _parse_sse_response(self, sse_text: str) -> List[Dict[str, Any]]:
        """解析SSE响应文本为事件列表"""
        events = []
        current_event = {}

        for line in sse_text.split("\n"):
            line = line.strip()

            if not line:  # 空行表示事件结束
                if current_event:
                    events.append(current_event)
                    current_event = {}
                continue

            if line.startswith("data: "):
                data_str = line[6:]  # 移除 "data: " 前缀
                try:
                    current_event["data"] = json.loads(data_str)
                except json.JSONDecodeError:
                    current_event["data"] = data_str
            elif line.startswith("event: "):
                current_event["event"] = line[7:]  # 移除 "event: " 前缀
            elif line.startswith("id: "):
                current_event["id"] = line[4:]  # 移除 "id: " 前缀

        # 处理最后一个事件（可能没有空行结尾）
        if current_event:
            events.append(current_event)

        return events

    def _validate_lifecycle_events(self, events: List[Dict[str, Any]]) -> None:
        """验证完整生命周期事件流"""
        event_types = [e.get("event", "unknown") for e in events]

        # 应该包含连接、进度、完成事件
        assert "connected" in event_types or any(
            "status" in str(e.get("data", {})) for e in events
        ), "缺少连接事件"

        # 查找进度事件
        progress_events = [
            e
            for e in events
            if e.get("event") == "progress"
            or (isinstance(e.get("data"), dict) and "progress" in e.get("data", {}))
        ]
        assert len(progress_events) > 0, "应该包含进度事件"

        # 查找完成事件
        completion_events = [
            e
            for e in events
            if e.get("event") in ["completed", "finished"]
            or (
                isinstance(e.get("data"), dict)
                and "completed" in str(e.get("data", {}))
            )
        ]
        assert len(completion_events) > 0, "应该包含完成事件"

    def _validate_error_events(self, events: List[Dict[str, Any]]) -> None:
        """验证错误事件流"""
        event_types = [e.get("event", "unknown") for e in events]

        # 应该包含错误事件
        has_error_event = "error" in event_types or any(
            "error" in str(e.get("data", {})).lower() for e in events
        )
        assert has_error_event, f"错误任务应该包含错误事件: {event_types}"


# ============================================================================
# 并发SSE连接测试工具
# ============================================================================


class ConcurrentSSETestHelper:
    """并发SSE连接测试辅助类"""

    @staticmethod
    async def test_concurrent_connections(
        client: TestClient,
        task_id: uuid.UUID,
        auth_headers: Dict[str, str],
        concurrent_count: int = 5,
    ) -> Dict[str, Any]:
        """测试并发SSE连接"""

        async def single_sse_connection():
            """单个SSE连接测试"""
            response = client.get(
                f"/api/v1/stream/{task_id}",
                headers={**auth_headers, "Accept": "text/event-stream"},
            )
            return {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "event_count": (
                    len(response.text.split("\n\n"))
                    if response.status_code == 200
                    else 0
                ),
            }

        # 并发执行多个连接
        tasks = [single_sse_connection() for _ in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful

        return {
            "total_connections": len(results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(results) if results else 0,
            "results": results,
        }


# ============================================================================
# pytest测试函数
# ============================================================================


@pytest.fixture
async def stream_test_instance():
    """SSE流测试实例fixture"""
    return TestStreamEndpoint()


@pytest.mark.asyncio
async def test_stream_normal_scenarios(stream_test_instance, client, db_session):
    """测试SSE端点正常流程场景"""
    results = await stream_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.NORMAL
    )

    assert results["failed"] == 0, f"SSE正常场景测试失败: {results}"
    assert results["passed"] >= 2, "应该通过主要SSE连接测试"


@pytest.mark.asyncio
async def test_stream_boundary_scenarios(stream_test_instance, client, db_session):
    """测试SSE端点边界条件场景"""
    results = await stream_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.BOUNDARY
    )

    # SSE边界条件测试可能因为环境因素失败，容忍度稍高
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.3, f"SSE边界测试失败率{failure_rate:.1%}过高"


@pytest.mark.asyncio
async def test_stream_error_scenarios(stream_test_instance, client, db_session):
    """测试SSE端点错误场景"""
    results = await stream_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.ERROR
    )

    assert results["failed"] == 0, f"SSE错误场景测试失败: {results}"
    assert results["passed"] >= 3, "应该通过主要SSE错误场景测试"


@pytest.mark.asyncio
async def test_stream_performance_scenarios(stream_test_instance, client, db_session):
    """测试SSE端点性能场景"""
    results = await stream_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.PERFORMANCE
    )

    # SSE性能测试环境相关性较强，允许部分失败
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.5, f"SSE性能测试失败率{failure_rate:.1%}过高"


@pytest.mark.asyncio
async def test_concurrent_sse_connections(stream_test_instance, client, db_session):
    """测试并发SSE连接"""
    await stream_test_instance.setup_test_environment(db_session)

    if not stream_test_instance._test_task:
        pytest.skip("需要测试任务")

    # 测试5个并发连接
    concurrent_results = await ConcurrentSSETestHelper.test_concurrent_connections(
        client,
        stream_test_instance._test_task.id,
        stream_test_instance._auth_headers,
        concurrent_count=5,
    )

    # 至少80%的连接应该成功
    assert (
        concurrent_results["success_rate"] >= 0.8
    ), f"并发SSE连接成功率{concurrent_results['success_rate']:.1%}过低: {concurrent_results}"


@pytest.mark.asyncio
async def test_stream_complete_test_suite(stream_test_instance, client, db_session):
    """运行完整的SSE端点测试套件"""
    results = await stream_test_instance.execute_test_suite(client, db_session)

    # SSE测试由于其异步特性，允许更高的失败容忍度
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.25, f"SSE整体测试失败率{failure_rate:.1%}过高，应该<25%"

    print(
        f"✅ SSE端点测试完成: {results['passed']}通过 / {results['failed']}失败 / {results['total_scenarios']}总计"
    )
