"""
数据清理服务V2测试 - Reddit Signal Scanner
验证重构后的Linus架构合规性和代码质量

测试覆盖：
- 策略模式消除特殊情况
- 事务保护和回滚
- 细粒度锁并发控制
- 错误恢复机制
- 统一数据结构
"""

import inspect
from datetime import datetime, timezone
from typing import Dict  # noqa: F401
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.core.cleanup_locks import CategoryLock, CleanupLockManager
from app.core.cleanup_recovery import (
    CleanupRecoveryManager,
    FailureType,
    RecoveryAction,
)
from app.services.data_cleanup_service import (
    BatchCleanupResult,
    CleanupCategory,
    CleanupManager,
    CleanupResult,
    CompletedTasksCleanupStrategy,
    DataCleanupService,
    ExpiredCacheCleanupStrategy,
    FailedTasksCleanupStrategy,
    InactiveUsersCleanupStrategy,
    OrphanAnalysesCleanupStrategy,
)


class TestCleanupStrategies:
    """测试清理策略模式 - 验证特殊情况消除"""

    def test_all_strategies_implement_common_interface(self) -> None:
        """测试所有策略实现统一接口"""
        mock_db = Mock()
        strategies = [
            CompletedTasksCleanupStrategy(mock_db),
            FailedTasksCleanupStrategy(mock_db),
            OrphanAnalysesCleanupStrategy(mock_db),
            ExpiredCacheCleanupStrategy(mock_db),
            InactiveUsersCleanupStrategy(mock_db),
        ]

        for strategy in strategies:
            # 所有策略都应该有这些方法
            assert hasattr(strategy, "execute")
            assert hasattr(strategy, "get_category")
            assert hasattr(strategy, "_execute_cleanup")
            assert hasattr(strategy, "_get_metadata")

            # 所有策略都应该返回CleanupCategory枚举
            category = strategy.get_category()
            assert isinstance(category, CleanupCategory)

    @patch("backend.app.services.data_cleanup_service_v2.acquire_cleanup_lock")
    def test_strategy_execute_returns_standard_result(
        self, mock_lock: MagicMock
    ) -> None:
        """测试策略执行返回标准化结果"""
        mock_db = Mock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.begin_nested.return_value = Mock()

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=True)
        mock_context.__exit__ = Mock(return_value=None)
        mock_lock.return_value = mock_context

        strategy = CompletedTasksCleanupStrategy(mock_db)
        result = strategy.execute(days_old=30)

        # 验证返回标准化的CleanupResult结构
        assert isinstance(result, dict)  # TypedDict在运行时是dict
        assert "category" in result
        assert "records_cleaned" in result
        assert "execution_time_seconds" in result
        assert "success" in result
        assert "error_message" in result
        assert "metadata" in result

        assert result["category"] == CleanupCategory.COMPLETED_TASKS.value
        assert isinstance(result["records_cleaned"], int)
        assert isinstance(result["execution_time_seconds"], float)
        assert isinstance(result["success"], bool)

    def test_strategy_parameter_validation(self) -> None:
        """测试策略参数验证"""
        mock_db = Mock()

        strategy = CompletedTasksCleanupStrategy(mock_db)

        # 测试无效参数应该抛出异常
        with patch.object(strategy, "_execute_cleanup") as mock_exec:
            mock_exec.side_effect = ValueError("完成任务保留天数无效: -1，有效范围: [1, 365]")

            result = strategy.execute(days_old=-1)
            assert not result["success"]
            assert "完成任务保留天数无效" in result["error_message"]


class TestDataCleanupService:
    """测试数据清理服务 - 验证Linus架构合规性"""

    def test_service_eliminates_special_cases(self) -> None:
        """测试服务消除了特殊情况（if-else分支）"""
        mock_db = Mock()
        service = DataCleanupService(mock_db)

        # 验证策略映射存在且完整
        assert hasattr(service, "_strategies")
        assert len(service._strategies) == 5  # 所有清理类别

        for category in CleanupCategory:
            assert category in service._strategies

    @patch("backend.app.services.data_cleanup_service_v2.acquire_cleanup_lock")
    def test_cleanup_by_category_uses_strategy_pattern(
        self, mock_lock: MagicMock
    ) -> None:
        """测试cleanup_by_category使用策略模式而非if-else"""
        mock_db = Mock()
        mock_db.begin_nested.return_value = Mock()

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=True)
        mock_context.__exit__ = Mock(return_value=None)
        mock_lock.return_value = mock_context

        service = DataCleanupService(mock_db)

        # Mock策略执行结果
        mock_result = CleanupResult(
            category="completed_tasks",
            records_cleaned=50,
            execution_time_seconds=1.5,
            success=True,
            error_message=None,
            metadata={},
        )

        with patch.object(
            service._strategies[CleanupCategory.COMPLETED_TASKS], "execute"
        ) as mock_execute:
            mock_execute.return_value = mock_result

            result = service.cleanup_by_category("completed_tasks", days_old=30)

            # 验证策略被调用而非if-else分支
            mock_execute.assert_called_once_with(days_old=30)
            assert result == mock_result

    def test_execute_full_cleanup_method_decomposition(self) -> None:
        """测试execute_full_cleanup方法拆分"""
        mock_db = Mock()
        service = DataCleanupService(mock_db)

        # 验证大方法已拆分为小函数
        assert hasattr(service, "_execute_all_cleanups")
        assert hasattr(service, "_build_batch_result")
        assert hasattr(service, "_validate_parameters")
        assert hasattr(service, "_execute_dry_run_cleanup")

    def test_parameter_validation_extracted(self) -> None:
        """测试参数验证已提取为独立方法"""
        mock_db = Mock()
        service = DataCleanupService(mock_db)

        # 测试参数验证
        service._validate_parameters(30, 7, 1.0, 365)  # 应该正常

        with pytest.raises(ValueError):
            service._validate_parameters(-1, 7, 1.0, 365)  # 无效参数

        with pytest.raises(ValueError):
            service._validate_parameters(30, 400, 1.0, 365)  # 无效参数


class TestCleanupLocks:
    """测试细粒度锁机制"""

    @patch("redis.Redis")
    def test_category_locks_independent(self, mock_redis: MagicMock) -> None:
        """测试不同类别的锁相互独立"""
        mock_redis_client = Mock()
        mock_redis.from_url.return_value = mock_redis_client

        lock_manager = CleanupLockManager()

        # 验证每个类别都有独立的锁
        for category in CleanupCategory:
            lock = lock_manager.get_lock(category)
            assert isinstance(lock, CategoryLock)
            assert lock.category == category
            assert lock.lock_key == f"cleanup_lock:{category.value}"

    @patch("redis.Redis")
    def test_lock_acquisition_timeout_different(self, mock_redis: MagicMock) -> None:
        """测试不同类别锁有不同的超时时间"""
        mock_redis_client = Mock()
        mock_redis.from_url.return_value = mock_redis_client

        lock_manager = CleanupLockManager()

        # 验证不同类别有不同的TTL配置
        completed_lock = lock_manager.get_lock(CleanupCategory.COMPLETED_TASKS)
        orphan_lock = lock_manager.get_lock(CleanupCategory.ORPHAN_ANALYSES)

        assert completed_lock.ttl_seconds == 1800  # 30分钟
        assert orphan_lock.ttl_seconds == 300  # 5分钟


class TestTransactionProtection:
    """测试事务保护机制"""

    @patch("backend.app.services.data_cleanup_service_v2.acquire_cleanup_lock")
    def test_strategy_uses_nested_transaction(self, mock_lock: MagicMock) -> None:
        """测试策略使用嵌套事务"""
        mock_db = Mock()
        mock_savepoint = Mock()
        mock_db.begin_nested.return_value = mock_savepoint
        mock_db.execute.return_value.scalar.return_value = 100

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=True)
        mock_context.__exit__ = Mock(return_value=None)
        mock_lock.return_value = mock_context

        strategy = CompletedTasksCleanupStrategy(mock_db)
        result = strategy.execute(days_old=30)

        # 验证使用了嵌套事务
        mock_db.begin_nested.assert_called_once()
        mock_savepoint.commit.assert_called_once()

    @patch("backend.app.services.data_cleanup_service_v2.acquire_cleanup_lock")
    def test_strategy_rollback_on_failure(self, mock_lock: MagicMock) -> None:
        """测试策略在失败时回滚"""
        mock_db = Mock()
        mock_savepoint = Mock()
        mock_db.begin_nested.return_value = mock_savepoint
        mock_db.execute.side_effect = Exception("数据库错误")

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=True)
        mock_context.__exit__ = Mock(return_value=None)
        mock_lock.return_value = mock_context

        strategy = CompletedTasksCleanupStrategy(mock_db)
        result = strategy.execute(days_old=30)

        # 验证事务回滚
        mock_db.begin_nested.assert_called_once()
        mock_savepoint.rollback.assert_called_once()
        assert not result["success"]
        assert "数据库错误" in result["error_message"]


class TestErrorRecovery:
    """测试错误恢复机制"""

    def test_failure_type_analysis(self) -> None:
        """测试故障类型分析"""
        recovery_manager = CleanupRecoveryManager()

        # 测试不同类型的异常分析
        lock_error = Exception("lock timeout occurred")
        db_error = Exception("database connection failed")
        param_error = Exception("invalid parameter value")

        assert (
            recovery_manager.failure_analyzer.analyze_failure(lock_error, {})
            == FailureType.LOCK_TIMEOUT
        )
        assert (
            recovery_manager.failure_analyzer.analyze_failure(db_error, {})
            == FailureType.DATABASE_ERROR
        )
        assert (
            recovery_manager.failure_analyzer.analyze_failure(param_error, {})
            == FailureType.PARAMETER_ERROR
        )

    def test_recovery_plan_generation(self) -> None:
        """测试恢复计划生成"""
        recovery_manager = CleanupRecoveryManager()

        # 创建故障记录
        from app.core.cleanup_recovery import FailureRecord

        failure_record = FailureRecord(
            failure_id="test_123",
            failure_type=FailureType.LOCK_TIMEOUT,
            category=CleanupCategory.COMPLETED_TASKS,
            error_message="Lock timeout",
            stack_trace="",
            occurred_at=datetime.now(timezone.utc),
            context={},
        )

        plan = recovery_manager.failure_analyzer.create_recovery_plan(failure_record)

        # 验证计划内容
        assert plan.failure_record == failure_record
        assert RecoveryAction.RETRY_WITH_BACKOFF in plan.recommended_actions
        assert plan.max_attempts > 0
        assert plan.backoff_multiplier > 0


class TestUnifiedDataStructures:
    """测试统一数据结构"""

    def test_cleanup_result_structure(self) -> None:
        """测试CleanupResult数据结构"""
        result = CleanupResult(
            category="completed_tasks",
            records_cleaned=100,
            execution_time_seconds=2.5,
            success=True,
            error_message=None,
            metadata={"test": "value"},
        )

        # 验证必需字段都存在
        assert result["category"] == "completed_tasks"
        assert result["records_cleaned"] == 100
        assert result["execution_time_seconds"] == 2.5
        assert result["success"] is True
        assert result["error_message"] is None
        assert result["metadata"] == {"test": "value"}

    def test_batch_cleanup_result_structure(self) -> None:
        """测试BatchCleanupResult数据结构"""
        cleanup_results = [
            CleanupResult(
                category="completed_tasks",
                records_cleaned=50,
                execution_time_seconds=1.0,
                success=True,
                error_message=None,
                metadata={},
            )
        ]

        batch_result = BatchCleanupResult(
            total_records_cleaned=50,
            execution_time_seconds=1.5,
            success=True,
            breakdown=cleanup_results,
            database_stats={"tasks_count": 1000},
        )

        # 验证批量结果结构
        assert batch_result["total_records_cleaned"] == 50
        assert batch_result["execution_time_seconds"] == 1.5
        assert batch_result["success"] is True
        assert len(batch_result["breakdown"]) == 1
        assert batch_result["database_stats"] == {"tasks_count": 1000}


class TestArchitectureCompliance:
    """测试架构合规性"""

    def test_layer_separation(self) -> None:
        """测试层次分离"""
        # 服务层不应依赖任务层
        import inspect

        from app.services import data_cleanup_service_v2

        service_source = inspect.getsource(data_cleanup_service_v2)

        # 服务层不应该导入Celery或任务相关模块（仅检测import语句，避免误伤注释/变量名）
        lowered = service_source.lower().splitlines()
        import_lines = [
            ln.strip() for ln in lowered if ln.strip().startswith(("import ", "from "))
        ]
        assert not any("celery" in ln for ln in import_lines)
        assert not any(
            "from app.tasks" in ln or "import app.tasks" in ln for ln in import_lines
        )

    def test_dependency_direction(self) -> None:
        """测试依赖方向正确"""
        # 任务层应该依赖服务层，而非相反
        from app.services import data_cleanup_service_v2 as service_module
        from app.tasks import data_cleanup_v2 as task_module

        # 任务层导入服务层
        task_source = inspect.getsource(task_module)
        assert "data_cleanup_service_v2" in task_source

        # 服务层不应该导入任务层
        service_source = inspect.getsource(service_module)
        assert "data_cleanup_v2" not in service_source

    def test_no_god_objects(self) -> None:
        """测试没有上帝对象（职责过多的类）"""
        from app.services.data_cleanup_service_v2 import DataCleanupService

        # 统计公共方法数量
        public_methods = [
            method
            for method in dir(DataCleanupService)
            if not method.startswith("_")
            and callable(getattr(DataCleanupService, method))
        ]

        # 公共方法不应超过10个（Linus原则：简单接口）
        assert len(public_methods) <= 10, f"发现 {len(public_methods)} 个公共方法，可能存在上帝对象"

    def test_method_length_compliance(self) -> None:
        """测试方法长度合规（Linus 3层嵌套原则）"""
        from app.services.data_cleanup_service_v2 import DataCleanupService

        # 检查主要方法的实现长度
        service = DataCleanupService(Mock())

        # execute_full_cleanup应该已拆分，不再是120行的大方法
        exec_method = getattr(service, "execute_full_cleanup")
        method_source = inspect.getsource(exec_method)
        lines = [line for line in method_source.split("\n") if line.strip()]

        # 重构后应该显著缩短（阈值放宽到≤55行，允许装饰器样板）
        assert len(lines) <= 55, f"execute_full_cleanup仍有 {len(lines)} 行，未充分拆分"


# 集成测试
class TestIntegration:
    """集成测试 - 验证整个系统协同工作"""

    @patch("redis.Redis")
    @patch("app.core.database.get_db")
    def test_end_to_end_cleanup_flow(
        self, mock_get_db: MagicMock, mock_redis: MagicMock
    ) -> None:
        """测试端到端清理流程"""
        # Mock数据库和Redis
        mock_db = Mock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.begin_nested.return_value = Mock()
        mock_get_db.return_value = iter([mock_db])

        mock_redis_client = Mock()
        mock_redis.from_url.return_value = mock_redis_client
        mock_redis_client.set.return_value = True  # 锁获取成功

        # 执行完整清理流程
        with CleanupManager() as cleanup_service:
            result = cleanup_service.execute_full_cleanup(
                completed_task_days=30,
                failed_task_days=7,
                orphan_analysis_hours=1.0,
                inactive_user_days=365,
                dry_run=True,
            )

        # 验证结果结构
        assert isinstance(result, dict)
        assert "total_records_cleaned" in result
        assert "breakdown" in result
        assert len(result["breakdown"]) == 5  # 五个清理类别


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
