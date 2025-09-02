"""
分析报告端点测试 - /api/v1/report/{task_id}

基于Linus统一架构：
- 配置驱动测试规格
- 结构化报告验证
- 性能目标<20ms
- 缓存策略验证
"""

import uuid
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, Analysis, Report
from .base import (
    BaseAPITest,
    APITestSpec,
    TestScenario,
    TestScenarioType,
    PerformanceSpec,
)
from tests.conftest import DatabaseTestFactory


class TestReportEndpoint(BaseAPITest):
    """报告端点测试类 - 统一配置驱动架构"""

    @property
    def test_spec(self) -> APITestSpec:
        """报告端点测试规格配置"""
        return APITestSpec(
            endpoint_name="report",
            base_path="/api/v1/report",
            requires_auth=True,
            requires_task_setup=True,
            scenarios=[
                # 1. 正常流程测试
                TestScenario(
                    name="获取完整分析报告",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=200,
                    expected_response_schema={
                        "required": [
                            "task_id",
                            "analysis_summary",
                            "insights",
                            "sources",
                            "generated_at",
                            "report_version",
                        ],
                        "properties": {
                            "task_id": {"type": "string"},
                            "analysis_summary": {"type": "object"},
                            "insights": {"type": "object"},
                            "sources": {"type": "object"},
                            "generated_at": {"type": "string"},
                            "report_version": {"type": "string"},
                            "confidence_score": {"type": "number"},
                            "processing_time_seconds": {"type": "number"},
                        },
                    },
                    description="获取已完成任务的完整分析报告",
                ),
                TestScenario(
                    name="获取JSON格式报告",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"format": "json"},
                    expected_status=200,
                    description="获取JSON格式的分析报告",
                ),
                TestScenario(
                    name="获取PDF格式报告",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"format": "pdf"},
                    expected_status=200,
                    description="获取PDF格式的分析报告",
                ),
                TestScenario(
                    name="获取Excel格式报告",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"format": "excel"},
                    expected_status=200,
                    description="获取Excel格式的分析报告",
                ),
                # 2. 边界条件测试
                TestScenario(
                    name="刚完成任务的报告",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=200,
                    description="获取刚完成任务的报告（测试缓存更新）",
                ),
                TestScenario(
                    name="包含详细选项的报告",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"include_raw_data": "true", "include_debug": "true"},
                    expected_status=200,
                    description="获取包含详细调试信息的报告",
                ),
                TestScenario(
                    name="大型数据集报告",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=200,
                    description="获取大型数据集分析的报告",
                ),
                TestScenario(
                    name="指定语言的报告",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"lang": "zh-CN"},
                    expected_status=200,
                    description="获取中文版本的分析报告",
                ),
                # 3. 错误场景测试
                TestScenario(
                    name="不存在任务的报告",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path=f"/api/v1/report/{uuid.uuid4()}",
                    expected_status=404,
                    expected_response_schema={
                        "required": ["detail"],
                        "properties": {"detail": {"type": "string"}},
                    },
                    description="获取不存在任务的报告应返回404",
                ),
                TestScenario(
                    name="未完成任务的报告",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=202,  # Accepted，任务进行中
                    expected_response_schema={
                        "required": ["message", "status", "progress"],
                        "properties": {
                            "message": {"type": "string"},
                            "status": {"type": "string"},
                            "progress": {"type": "number"},
                        },
                    },
                    description="获取未完成任务的报告应返回202状态",
                ),
                TestScenario(
                    name="失败任务的报告",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=422,
                    expected_response_schema={
                        "required": ["detail", "error_type"],
                        "properties": {
                            "detail": {"type": "string"},
                            "error_type": {"type": "string"},
                        },
                    },
                    description="获取失败任务的报告应返回422错误",
                ),
                TestScenario(
                    name="无效UUID的报告请求",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/report/invalid-uuid",
                    expected_status=422,
                    description="无效UUID格式应返回422错误",
                ),
                TestScenario(
                    name="不支持的格式请求",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"format": "unsupported_format"},
                    expected_status=400,
                    description="不支持的报告格式应返回400错误",
                ),
                TestScenario(
                    name="未认证的报告请求",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    headers={},  # 清空认证headers
                    expected_status=401,
                    description="未认证访问应返回401错误",
                ),
                # 4. 性能测试
                TestScenario(
                    name="报告获取性能测试",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=20.0,  # PRD要求<20ms
                        max_tolerance_ratio=1.5,
                        iterations=100,
                        warmup_iterations=10,
                    ),
                    description="验证报告获取性能<20ms（缓存命中）",
                ),
                TestScenario(
                    name="不同格式报告性能",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/report/{task_id}",
                    params={"format": "pdf"},
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=100.0,  # PDF生成稍慢
                        iterations=20,
                        warmup_iterations=3,
                    ),
                    description="验证PDF格式报告生成性能",
                ),
            ],
        )

    async def setup_test_environment(self, db_session: AsyncSession) -> None:
        """重写环境设置，创建完整的报告数据"""
        await super().setup_test_environment(db_session)

        if not self._test_user:
            return

        # 创建不同状态的任务用于测试
        completed_task = Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=self._test_user.id,
                product_description="已完成的测试任务，用于报告生成测试",
                status="completed",
            )
        )

        processing_task = Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=self._test_user.id,
                product_description="处理中的任务，用于测试报告未就绪场景",
                status="processing",
            )
        )

        failed_task = Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=self._test_user.id,
                product_description="失败的任务，用于测试报告错误场景",
                status="failed",
                error_message="分析过程中发生错误",
            )
        )

        db_session.add_all([completed_task, processing_task, failed_task])
        await db_session.commit()

        # 刷新以获取ID
        for task in [completed_task, processing_task, failed_task]:
            await db_session.refresh(task)

        # 为完成的任务创建分析和报告数据
        analysis = Analysis(
            **DatabaseTestFactory.minimal_valid_analysis(task_id=completed_task.id)
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        # 创建报告
        report = Report(
            analysis_id=analysis.id,
            format="json",
            content_json={
                "analysis_summary": {
                    "total_insights": 5,
                    "confidence_score": 0.85,
                    "processing_time_seconds": 45.6,
                },
                "insights": DatabaseTestFactory.valid_insights_data(),
                "sources": DatabaseTestFactory.valid_sources_data(),
                "generated_at": "2025-09-01T16:00:00Z",
                "report_version": "v1.0",
            },
            file_size_bytes=1024,
        )
        db_session.add(report)
        await db_session.commit()

        # 保存不同状态任务的映射
        self._task_status_map = {
            "completed": completed_task.id,
            "processing": processing_task.id,
            "failed": failed_task.id,
        }

        # 设置默认任务为已完成任务
        self._test_task = completed_task

    async def _execute_single_scenario(
        self, client: TestClient, scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写单个场景执行，处理不同任务状态路由"""

        # 根据场景选择合适的任务ID
        task_id_to_use = self._test_task.id

        if hasattr(self, "_task_status_map"):
            if "未完成任务" in scenario.name:
                task_id_to_use = self._task_status_map["processing"]
            elif "失败任务" in scenario.name:
                task_id_to_use = self._task_status_map["failed"]
            elif (
                "完整分析报告" in scenario.name
                or "格式报告" in scenario.name
                or "性能" in scenario.name
            ):
                task_id_to_use = self._task_status_map["completed"]

        # 准备请求参数
        request_kwargs = {
            "method": scenario.method,
            "url": scenario.path.format(task_id=task_id_to_use),
            "headers": {**scenario.headers, **self._auth_headers},
        }

        if scenario.params:
            request_kwargs["params"] = scenario.params

        # 特殊处理未认证场景
        if scenario.name == "未认证的报告请求":
            request_kwargs["headers"] = scenario.headers  # 不包含认证headers

        # 执行测试
        if scenario.performance_spec:
            return await self._execute_performance_test(
                client, request_kwargs, scenario
            )
        else:
            return await self._execute_functional_test(client, request_kwargs, scenario)

    async def _execute_functional_test(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写功能测试，处理不同报告格式验证"""

        # 执行标准功能测试
        result = await super()._execute_functional_test(
            client, request_kwargs, scenario
        )

        # 对于成功的报告请求，进行额外的格式验证
        if result["status_code"] == 200:
            response = client.request(**request_kwargs)

            # 验证报告格式
            format_param = request_kwargs.get("params", {}).get("format", "json")
            self._validate_report_format(response, format_param)

            # 验证报告内容结构（JSON格式）
            if format_param == "json":
                self._validate_report_content_structure(response)

        return result

    def _validate_report_format(self, response, expected_format: str) -> None:
        """验证报告格式正确性"""
        content_type = response.headers.get("content-type", "")

        if expected_format == "json":
            assert (
                "application/json" in content_type
            ), f"JSON报告Content-Type错误: {content_type}"
        elif expected_format == "pdf":
            assert (
                "application/pdf" in content_type
            ), f"PDF报告Content-Type错误: {content_type}"
        elif expected_format == "excel":
            assert (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                in content_type
                or "application/vnd.ms-excel" in content_type
            ), f"Excel报告Content-Type错误: {content_type}"

    def _validate_report_content_structure(self, response) -> None:
        """验证JSON报告内容结构"""
        try:
            report_data = response.json()
        except:
            pytest.fail("JSON报告响应格式错误")

        # 验证核心字段存在
        required_fields = ["task_id", "analysis_summary", "insights", "sources"]
        for field in required_fields:
            assert field in report_data, f"报告缺少必需字段: {field}"

        # 验证insights结构
        insights = report_data["insights"]
        assert isinstance(insights, dict), "insights应该是对象"
        assert "pain_points" in insights, "insights缺少pain_points"
        assert "opportunities" in insights, "insights缺少opportunities"

        # 验证sources结构
        sources = report_data["sources"]
        assert isinstance(sources, dict), "sources应该是对象"
        assert "posts_analyzed" in sources, "sources缺少posts_analyzed"
        assert isinstance(sources["posts_analyzed"], int), "posts_analyzed应该是整数"


# ============================================================================
# pytest测试函数
# ============================================================================


@pytest.fixture
async def report_test_instance():
    """报告测试实例fixture"""
    return TestReportEndpoint()


@pytest.mark.asyncio
async def test_report_normal_scenarios(report_test_instance, client, db_session):
    """测试报告端点正常流程场景"""
    results = await report_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.NORMAL
    )

    assert results["failed"] == 0, f"报告正常场景测试失败: {results}"
    assert results["passed"] >= 4, "应该通过所有报告格式测试"


@pytest.mark.asyncio
async def test_report_boundary_scenarios(report_test_instance, client, db_session):
    """测试报告端点边界条件场景"""
    results = await report_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.BOUNDARY
    )

    assert results["failed"] == 0, f"报告边界条件测试失败: {results}"
    assert results["passed"] >= 3, "应该通过边界条件测试"


@pytest.mark.asyncio
async def test_report_error_scenarios(report_test_instance, client, db_session):
    """测试报告端点错误场景"""
    results = await report_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.ERROR
    )

    assert results["failed"] == 0, f"报告错误场景测试失败: {results}"
    assert results["passed"] >= 5, "应该通过主要错误场景测试"


@pytest.mark.asyncio
async def test_report_performance_scenarios(report_test_instance, client, db_session):
    """测试报告端点性能场景"""
    results = await report_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.PERFORMANCE
    )

    assert results["failed"] == 0, f"报告性能测试失败: {results}"

    # 验证性能结果
    for result in results["results"]:
        if result["status"] == "PASSED" and "性能测试" in result["scenario"]:
            perf_result = result["result"]
            assert perf_result["passed"], f"报告性能未达标: {perf_result}"


@pytest.mark.asyncio
async def test_report_complete_test_suite(report_test_instance, client, db_session):
    """运行完整的报告端点测试套件"""
    results = await report_test_instance.execute_test_suite(client, db_session)

    # 验证总体结果
    total_expected = len(report_test_instance.test_spec.scenarios)
    assert results["total_scenarios"] == total_expected

    # 报告功能是核心，要求高成功率
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.1, f"报告测试失败率{failure_rate:.1%}过高，应该<10%"

    print(
        f"✅ 报告端点测试完成: {results['passed']}通过 / {results['failed']}失败 / {results['total_scenarios']}总计"
    )
