"""
重试机制综合测试

测试覆盖：
- EnhancedRetryPolicy 重试策略
- DeadLetterHandler 死信队列管理  
- FailureAnalyzer 失败模式分析
- Manual Retry API 手动重试接口
- 端到端重试流程测试

基于Linus原则和质量门禁要求：
- 严格的数据隔离
- 边界条件测试
- 性能基准测试
- 100%类型安全验证
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.task import Task, TaskStatus, FailureCategory
from app.models.user import User
from app.core.retry_policy import (
    EnhancedRetryPolicy,
    RetryStrategy,
    RetryPolicyConfig,
    get_retry_policy,
)
from app.tasks.dead_letter_handler import (
    DeadLetterHandler,
    DeadLetterQueryFilter,
    ManualRetryRequest,
    get_dead_letter_handler,
)
from app.services.failure_analyzer import (
    FailureAnalyzer,
    FailurePattern,
    FailureSeverity,
    get_failure_analyzer,
)
from app.core.exceptions import RetryLimitExceededException, DeadLetterException


class TestEnhancedRetryPolicy:
    """重试策略测试套件"""

    @pytest.fixture
    def retry_policy(self) -> EnhancedRetryPolicy:
        """重试策略实例"""
        return EnhancedRetryPolicy()

    @pytest.fixture
    def sample_task(self, db_session: Session, test_user: User) -> Task:
        """样本任务"""
        task = Task(
            user_id=test_user.id,
            product_description="测试产品描述",
            status=TaskStatus.FAILED.value,
            retry_count=0,
            error_message="Network connection failed",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    def test_get_policy_for_network_error(self, retry_policy: EnhancedRetryPolicy):
        """测试网络错误策略匹配"""
        # 测试网络连接错误
        network_error = ConnectionError("Connection refused")
        policy, category = retry_policy.get_policy_for_exception(network_error)

        assert policy.failure_category == FailureCategory.NETWORK_ERROR
        assert category == FailureCategory.NETWORK_ERROR
        assert policy.auto_recoverable is True
        assert policy.retry_config.max_retries == 3

    def test_get_policy_for_validation_error(self, retry_policy: EnhancedRetryPolicy):
        """测试数据验证错误策略匹配"""
        validation_error = ValueError("Invalid data format")
        policy, category = retry_policy.get_policy_for_exception(validation_error)

        assert policy.failure_category == FailureCategory.DATA_VALIDATION_ERROR
        assert category == FailureCategory.DATA_VALIDATION_ERROR
        assert policy.auto_recoverable is False
        assert policy.retry_config.strategy == RetryStrategy.NO_RETRY

    def test_should_retry_within_limit(
        self, retry_policy: EnhancedRetryPolicy, sample_task: Task
    ):
        """测试在重试限制内的重试判断"""
        sample_task.retry_count = 1
        exception = ConnectionError("Connection timeout")

        should_retry, delay, category = retry_policy.should_retry(
            sample_task, exception
        )

        assert should_retry is True
        assert delay > 0
        assert category == FailureCategory.NETWORK_ERROR

    def test_should_not_retry_over_limit(
        self, retry_policy: EnhancedRetryPolicy, sample_task: Task
    ):
        """测试超过重试限制的情况"""
        sample_task.retry_count = 5  # 超过最大重试次数
        exception = ConnectionError("Connection timeout")

        should_retry, delay, category = retry_policy.should_retry(
            sample_task, exception
        )

        assert should_retry is False
        assert delay == 0
        assert category == FailureCategory.NETWORK_ERROR

    def test_calculate_exponential_backoff_delay(
        self, retry_policy: EnhancedRetryPolicy
    ):
        """测试指数退避延迟计算"""
        config = RetryPolicyConfig(
            base_delay=60,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False,  # 关闭抖动以确保可预测的结果
        )

        # 第一次重试: 60秒
        delay_0 = retry_policy._calculate_retry_delay(0, config)
        assert delay_0 == 60

        # 第二次重试: 120秒
        delay_1 = retry_policy._calculate_retry_delay(1, config)
        assert delay_1 == 120

        # 第三次重试: 240秒
        delay_2 = retry_policy._calculate_retry_delay(2, config)
        assert delay_2 == 240

    def test_calculate_linear_backoff_delay(self, retry_policy: EnhancedRetryPolicy):
        """测试线性退避延迟计算"""
        config = RetryPolicyConfig(
            base_delay=60, strategy=RetryStrategy.LINEAR_BACKOFF, jitter=False
        )

        # 线性退避: base_delay * (retry_count + 1)
        assert retry_policy._calculate_retry_delay(0, config) == 60
        assert retry_policy._calculate_retry_delay(1, config) == 120
        assert retry_policy._calculate_retry_delay(2, config) == 180

    def test_handle_task_failure_success_retry(
        self, retry_policy: EnhancedRetryPolicy, sample_task: Task, db_session: Session
    ):
        """测试成功安排重试的情况"""
        exception = ConnectionError("Network error")

        with patch.object(retry_policy, "_schedule_retry") as mock_schedule:
            result = retry_policy.handle_task_failure(
                sample_task, exception, db_session
            )

            assert result is True  # 成功安排重试
            assert sample_task.retry_count == 1
            assert sample_task.failure_category == FailureCategory.NETWORK_ERROR.value
            assert sample_task.status == TaskStatus.PENDING.value
            mock_schedule.assert_called_once()

    def test_handle_task_failure_dead_letter(
        self, retry_policy: EnhancedRetryPolicy, sample_task: Task, db_session: Session
    ):
        """测试超过重试次数进入死信队列"""
        sample_task.retry_count = 3  # 已达到重试次数
        exception = ConnectionError("Network error")

        with patch.object(
            retry_policy, "_move_to_dead_letter_queue"
        ) as mock_dead_letter:
            result = retry_policy.handle_task_failure(
                sample_task, exception, db_session
            )

            assert result is False  # 没有安排重试
            mock_dead_letter.assert_called_once_with(sample_task, exception, db_session)


class TestDeadLetterHandler:
    """死信队列处理器测试套件"""

    @pytest.fixture
    def dlq_handler(self) -> DeadLetterHandler:
        """死信队列处理器实例"""
        return DeadLetterHandler()

    @pytest.fixture
    def dead_letter_tasks(self, db_session: Session, test_user: User) -> List[Task]:
        """创建死信队列任务样本"""
        tasks = []
        categories = [FailureCategory.NETWORK_ERROR, FailureCategory.PROCESSING_ERROR]

        for i, category in enumerate(categories):
            task = Task(
                user_id=test_user.id,
                product_description=f"Dead letter task {i+1}",
                status=TaskStatus.DEAD_LETTER.value,
                retry_count=3,
                failure_category=category.value,
                error_message=f"Error {i+1}: Failed after 3 retries",
                dead_letter_at=datetime.utcnow() - timedelta(hours=i + 1),
            )
            tasks.append(task)
            db_session.add(task)

        db_session.commit()
        for task in tasks:
            db_session.refresh(task)
        return tasks

    def test_get_dead_letter_tasks_all(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试获取所有死信任务"""
        tasks, total_count = dlq_handler.get_dead_letter_tasks(db_session)

        assert total_count == 2
        assert len(tasks) == 2
        assert all(task.status == TaskStatus.DEAD_LETTER.value for task in tasks)

    def test_get_dead_letter_tasks_with_category_filter(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试按失败类型过滤死信任务"""
        filters = DeadLetterQueryFilter(
            failure_categories=[FailureCategory.NETWORK_ERROR.value]
        )

        tasks, total_count = dlq_handler.get_dead_letter_tasks(db_session, filters)

        assert total_count == 1
        assert len(tasks) == 1
        assert tasks[0].failure_category == FailureCategory.NETWORK_ERROR.value

    def test_get_dead_letter_tasks_with_age_filter(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试按存在时间过滤死信任务"""
        filters = DeadLetterQueryFilter(
            age_hours_min=1, age_hours_max=2  # 1小时前创建的  # 2小时内创建的
        )

        tasks, total_count = dlq_handler.get_dead_letter_tasks(db_session, filters)

        assert total_count == 1  # 只有一个任务在这个时间范围内

    def test_manual_retry_tasks_success(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试成功手动重试任务"""
        task_ids = [str(task.id) for task in dead_letter_tasks]
        retry_request = ManualRetryRequest(
            task_ids=task_ids, retry_immediately=False, reason="manual_test_retry"
        )

        result = dlq_handler.manual_retry_tasks(db_session, retry_request)

        assert result["total_requested"] == 2
        assert result["successful_retries"] == 2
        assert result["failed_retries"] == 0
        assert len(result["success_task_ids"]) == 2

        # 验证任务状态已重置
        for task in dead_letter_tasks:
            db_session.refresh(task)
            assert task.status == TaskStatus.PENDING.value
            assert task.retry_count == 0
            assert task.dead_letter_at is None

    def test_manual_retry_nonexistent_tasks(
        self, dlq_handler: DeadLetterHandler, db_session: Session
    ):
        """测试重试不存在的任务"""
        fake_task_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        retry_request = ManualRetryRequest(
            task_ids=fake_task_ids, reason="test_nonexistent"
        )

        with pytest.raises(Exception):  # 应该抛出ValidationException
            dlq_handler.manual_retry_tasks(db_session, retry_request)

    def test_get_dead_letter_statistics(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试获取死信队列统计信息"""
        stats = dlq_handler.get_dead_letter_statistics(db_session)

        assert stats.total_count == 2
        assert len(stats.by_category) >= 2  # 至少包含测试的两个类型
        assert FailureCategory.NETWORK_ERROR.value in stats.by_category
        assert FailureCategory.PROCESSING_ERROR.value in stats.by_category
        assert stats.avg_failure_count == 3.0  # 两个任务都重试了3次

    def test_cleanup_old_dead_letters_dry_run(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试清理旧死信任务（试运行模式）"""
        # 设置一个任务为很久以前的
        old_task = dead_letter_tasks[0]
        old_task.dead_letter_at = datetime.utcnow() - timedelta(days=31)
        db_session.commit()

        result = dlq_handler.cleanup_old_dead_letters(
            db_session, older_than_days=30, dry_run=True
        )

        assert result["total_deleted"] == 1
        assert result["dry_run"] is True

        # 验证任务未被实际删除（因为是试运行）
        db_session.refresh(old_task)
        assert old_task.status == TaskStatus.DEAD_LETTER.value

    def test_cleanup_old_dead_letters_actual(
        self,
        dlq_handler: DeadLetterHandler,
        db_session: Session,
        dead_letter_tasks: List[Task],
    ):
        """测试实际清理旧死信任务"""
        # 设置所有任务为很久以前的
        for task in dead_letter_tasks:
            task.dead_letter_at = datetime.utcnow() - timedelta(days=31)
        db_session.commit()

        result = dlq_handler.cleanup_old_dead_letters(
            db_session, older_than_days=30, dry_run=False
        )

        assert result["total_deleted"] == 2
        assert result["dry_run"] is False

        # 验证任务已被删除
        remaining_tasks = (
            db_session.query(Task)
            .filter(Task.status == TaskStatus.DEAD_LETTER.value)
            .count()
        )
        assert remaining_tasks == 0


class TestFailureAnalyzer:
    """失败分析器测试套件"""

    @pytest.fixture
    def analyzer(self) -> FailureAnalyzer:
        """失败分析器实例"""
        return FailureAnalyzer()

    def test_analyze_reddit_rate_limit_failure(self, analyzer: FailureAnalyzer):
        """测试Reddit限流错误分析"""
        error_message = "Rate limit exceeded for Reddit API"
        exception_type = "HTTPError"

        result = analyzer.analyze_failure(error_message, exception_type)

        assert result.pattern_id == "reddit_rate_limit"
        assert result.confidence > 0.5
        assert result.failure_category == FailureCategory.NETWORK_ERROR
        assert result.auto_recoverable is True
        assert "降低Reddit API调用频率" in "\n".join(result.recovery_suggestions)

    def test_analyze_memory_exhaustion_failure(self, analyzer: FailureAnalyzer):
        """测试内存耗尽错误分析"""
        error_message = "Cannot allocate memory"
        exception_type = "MemoryError"

        result = analyzer.analyze_failure(error_message, exception_type)

        assert result.pattern_id == "memory_exhaustion"
        assert result.confidence > 0.5
        assert result.failure_category == FailureCategory.SYSTEM_ERROR
        assert result.severity == FailureSeverity.CRITICAL
        assert result.auto_recoverable is False

    def test_analyze_unknown_failure(self, analyzer: FailureAnalyzer):
        """测试未知错误分析"""
        error_message = "Some random unknown error"
        exception_type = "UnknownError"

        result = analyzer.analyze_failure(error_message, exception_type)

        assert result.pattern_id is None
        assert result.pattern_name == "Unknown Pattern"
        assert result.confidence == 0.0
        assert result.auto_recoverable is False

    def test_failure_pattern_confidence_calculation(self, analyzer: FailureAnalyzer):
        """测试失败模式置信度计算"""
        # 创建包含多个匹配模式的错误
        network_pattern = next(
            p
            for p in analyzer.failure_patterns
            if p.pattern_id == "network_connectivity"
        )

        # 完全匹配的情况
        error_context = "connection refused network error"
        confidence = analyzer._calculate_pattern_confidence(
            network_pattern, error_context
        )
        assert confidence > 0.5  # 应该有较高的置信度

        # 部分匹配的情况
        error_context = "connection refused but not network related"
        confidence = analyzer._calculate_pattern_confidence(
            network_pattern, error_context
        )
        assert 0 < confidence < 1  # 应该有部分匹配

    def test_generate_recovery_suggestions(self, analyzer: FailureAnalyzer):
        """测试恢复建议生成"""
        pattern = next(
            p for p in analyzer.failure_patterns if p.pattern_id == "processing_timeout"
        )

        suggestions = analyzer._generate_recovery_suggestions(pattern, None)

        assert len(suggestions) > 0
        assert any("重试" in suggestion for suggestion in suggestions)
        assert any("调整参数" in suggestion for suggestion in suggestions)

    def test_get_failure_statistics(
        self, analyzer: FailureAnalyzer, db_session: Session
    ):
        """测试失败统计信息获取"""
        # 创建一些失败任务用于统计
        user = User(username="test_user", email="test@example.com")
        db_session.add(user)
        db_session.commit()

        for i in range(3):
            task = Task(
                user_id=user.id,
                product_description=f"Failed task {i}",
                status=TaskStatus.FAILED.value,
                failure_category=FailureCategory.NETWORK_ERROR.value,
                updated_at=datetime.utcnow(),
            )
            db_session.add(task)

        db_session.commit()

        stats = analyzer.get_failure_statistics(db_session, time_window_hours=24)

        assert "failure_by_category" in stats
        assert "total_failures" in stats
        assert stats["total_failures"] >= 3


class TestRetryAPIEndpoints:
    """重试API端点测试套件"""

    def test_get_dead_letter_queue_endpoint(
        self, client: TestClient, auth_headers: Dict[str, str], db_session: Session
    ):
        """测试死信队列查询API端点"""
        response = client.get("/api/v1/retry/dead-letter", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_count" in data
        assert "tasks" in data
        assert "has_more" in data

    def test_get_retry_statistics_endpoint(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """测试重试统计API端点"""
        response = client.get("/api/v1/retry/statistics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "user_statistics" in data
        assert "system_statistics" in data

    def test_get_failure_analysis_endpoint(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """测试失败分析API端点"""
        response = client.get(
            "/api/v1/retry/failure-analysis?time_window_hours=24", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "time_window_hours" in data
        assert "failure_by_category" in data
        assert "preventive_suggestions" in data

    def test_retry_cleanup_endpoint_success_response(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """/retry/cleanup 统一为 SuccessResponse"""
        response = client.post(
            "/api/v1/retry/cleanup?older_than_days=30&dry_run=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data.get("timestamp"), str)
        assert "data" in data

    def test_manual_retry_endpoint_invalid_task_id(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """测试手动重试API端点 - 无效任务ID"""
        retry_data = {
            "task_ids": ["invalid-task-id"],
            "retry_immediately": False,
            "reason": "test_retry",
        }

        response = client.post(
            "/api/v1/retry/manual", json=retry_data, headers=auth_headers
        )

        assert response.status_code == 400  # 应该返回错误

    def test_manual_retry_endpoint_empty_task_list(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """测试手动重试API端点 - 空任务列表"""
        retry_data = {
            "task_ids": [],
            "retry_immediately": False,
            "reason": "test_retry",
        }

        response = client.post(
            "/api/v1/retry/manual", json=retry_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


class TestRetryIntegration:
    """重试机制集成测试"""

    def test_end_to_end_retry_flow(self, db_session: Session, test_user: User):
        """端到端重试流程测试"""
        # 1. 创建一个失败的任务
        task = Task(
            user_id=test_user.id,
            product_description="Integration test task",
            status=TaskStatus.FAILED.value,
            error_message="Network connection timeout",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        # 2. 分析失败
        analyzer = get_failure_analyzer()
        analysis = analyzer.analyze_failure(
            task.error_message or "", "ConnectionError", task, db_session
        )

        assert analysis.failure_category == FailureCategory.NETWORK_ERROR

        # 3. 应用重试策略
        retry_policy = get_retry_policy()
        should_retry, delay, category = retry_policy.should_retry(
            task, ConnectionError("timeout")
        )

        assert should_retry is True
        assert delay > 0

        # 4. 模拟重试失败多次，最终进入死信队列
        for i in range(4):  # 超过最大重试次数
            task.retry_count = i + 1
            should_retry, _, _ = retry_policy.should_retry(
                task, ConnectionError("timeout")
            )
            if not should_retry:
                # 移至死信队列
                task.status = TaskStatus.DEAD_LETTER.value
                task.dead_letter_at = datetime.utcnow()
                break

        db_session.commit()
        assert task.status == TaskStatus.DEAD_LETTER.value

        # 5. 从死信队列手动重试
        dlq_handler = get_dead_letter_handler()
        retry_request = ManualRetryRequest(
            task_ids=[str(task.id)], reason="integration_test_retry"
        )

        result = dlq_handler.manual_retry_tasks(db_session, retry_request)

        assert result["successful_retries"] == 1
        db_session.refresh(task)
        assert task.status == TaskStatus.PENDING.value
        assert task.retry_count == 0

    def test_performance_bulk_operations(self, db_session: Session, test_user: User):
        """测试批量操作性能"""
        import time

        # 创建100个死信任务
        tasks = []
        for i in range(100):
            task = Task(
                user_id=test_user.id,
                product_description=f"Bulk test task {i}",
                status=TaskStatus.DEAD_LETTER.value,
                retry_count=3,
                dead_letter_at=datetime.utcnow(),
            )
            tasks.append(task)
            db_session.add(task)

        db_session.commit()

        # 测试批量查询性能
        dlq_handler = get_dead_letter_handler()
        start_time = time.time()

        result_tasks, total_count = dlq_handler.get_dead_letter_tasks(
            db_session, limit=100
        )

        query_time = time.time() - start_time
        assert query_time < 1.0  # 应该在1秒内完成
        assert total_count >= 100

        # 测试批量重试性能
        task_ids = [str(task.id) for task in tasks[:50]]  # 重试前50个
        retry_request = ManualRetryRequest(task_ids=task_ids, reason="performance_test")

        start_time = time.time()
        result = dlq_handler.manual_retry_tasks(db_session, retry_request)
        retry_time = time.time() - start_time

        assert retry_time < 5.0  # 应该在5秒内完成
        assert result["successful_retries"] == 50


@pytest.fixture
def test_user(db_session: Session) -> User:
    """创建测试用户"""
    user = User(username="retry_test_user", email="retry_test@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> Dict[str, str]:
    """认证头部"""
    # 这里应该生成真实的JWT令牌，简化处理
    return {"Authorization": f"Bearer test-token-{test_user.id}"}


# 性能基准测试
class TestRetryPerformanceBenchmarks:
    """重试机制性能基准测试"""

    @pytest.mark.performance
    def test_retry_policy_decision_performance(self):
        """测试重试策略决策性能"""
        import time

        retry_policy = get_retry_policy()

        # 测试1000次策略决策的性能
        start_time = time.time()

        for i in range(1000):
            exception = ConnectionError(f"Error {i}")
            retry_policy.get_policy_for_exception(exception)

        elapsed_time = time.time() - start_time

        # 1000次决策应该在100ms内完成
        assert elapsed_time < 0.1

        # 平均每次决策应该在0.1ms内
        avg_time_per_decision = elapsed_time / 1000
        assert avg_time_per_decision < 0.0001

    @pytest.mark.performance
    def test_failure_analysis_performance(self):
        """测试失败分析性能"""
        import time

        analyzer = get_failure_analyzer()
        error_messages = [
            "Connection timeout error",
            "Memory allocation failed",
            "Invalid data format",
            "Rate limit exceeded",
            "Permission denied access",
        ]

        start_time = time.time()

        for i in range(200):
            error_msg = error_messages[i % len(error_messages)]
            analyzer.analyze_failure(error_msg, "TestError")

        elapsed_time = time.time() - start_time

        # 200次分析应该在50ms内完成（利用缓存）
        assert elapsed_time < 0.05
