"""
任务监控系统测试

测试覆盖：
1. 任务状态跟踪
2. 系统监控
3. 告警处理
4. API端点
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.task_status import UnifiedTaskStatus
from app.schemas.task_monitor import (
    AlertConditionType,
    AlertConfig,
    AlertSeverity,
    QueueMetrics,
    TaskEvent,
    TaskSnapshot,
    WorkerStatus,
)
from app.services.alert_processor import AlertProcessor
from app.services.task_monitor import SystemMonitor
from app.services.task_tracker import TaskStatusTracker


# ==================== TaskStatusTracker 测试 ====================


class TestTaskStatusTracker:
    """任务状态跟踪器测试"""

    @pytest.fixture
    def tracker(self):
        """创建测试用的跟踪器"""
        with patch("app.services.task_tracker.get_redis_client"):
            with patch("app.services.task_tracker.get_db"):
                tracker = TaskStatusTracker()
                tracker.redis_client = MagicMock()
                return tracker

    def test_process_event(self, tracker):
        """测试事件处理"""
        event = TaskEvent(
            task_id="test-123",
            event_type="status_change",
            old_status=UnifiedTaskStatus.PENDING,
            new_status=UnifiedTaskStatus.PROCESSING,
            user_id="user-1",
            worker_id="worker-1",
        )

        # Mock数据库操作
        with patch("app.services.task_tracker.get_db") as mock_db:
            mock_session = MagicMock()
            mock_task = MagicMock()
            mock_task.id = "test-123"
            mock_session.query().filter().first.return_value = mock_task
            mock_db.return_value = iter([mock_session])

            result = tracker.process_event(event)

            assert result is True
            # 验证Redis操作被调用
            assert tracker.redis_client.setex.called
            assert tracker.redis_client.lpush.called
            assert tracker.redis_client.publish.called

    def test_get_task_status_from_cache(self, tracker):
        """测试从缓存获取任务状态"""
        cache_data = {
            "task_id": "test-123",
            "status": "processing",
            "progress": "50",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "user_id": "user-1",
            "worker_id": "worker-1",
            "queue_name": "default",
        }

        tracker.redis_client.get.return_value = json.dumps(cache_data)

        snapshot = tracker.get_task_status("test-123")

        assert snapshot is not None
        assert snapshot.task_id == "test-123"
        assert snapshot.status == UnifiedTaskStatus.PROCESSING
        assert snapshot.progress == 50

    def test_get_task_status_from_db(self, tracker):
        """测试从数据库获取任务状态（缓存未命中）"""
        tracker.redis_client.get.return_value = None

        with patch("app.services.task_tracker.get_db") as mock_db:
            mock_session = MagicMock()
            mock_task = MagicMock()
            mock_task.id = "test-123"
            mock_task.status = "completed"
            mock_task.created_at = datetime.now(timezone.utc)
            mock_task.updated_at = datetime.now(timezone.utc)
            mock_task.started_at = None
            mock_task.completed_at = datetime.now(timezone.utc)
            mock_task.user_id = "user-1"
            mock_task.queue_name = "default"

            mock_session.query().filter().first.return_value = mock_task
            mock_db.return_value = iter([mock_session])

            snapshot = tracker.get_task_status("test-123")

            assert snapshot is not None
            assert snapshot.task_id == "test-123"
            assert snapshot.status == UnifiedTaskStatus.COMPLETED

    def test_batch_update_status(self, tracker):
        """测试批量更新状态"""
        task_ids = ["task-1", "task-2", "task-3"]

        with patch.object(tracker, "process_event", return_value=True) as mock_process:
            count = tracker.batch_update_status(
                task_ids, UnifiedTaskStatus.COMPLETED, "worker-1"
            )

            assert count == 3
            assert mock_process.call_count == 3


# ==================== SystemMonitor 测试 ====================


class TestSystemMonitor:
    """系统监控器测试"""

    @pytest.fixture
    def monitor(self):
        """创建测试用的监控器"""
        with patch("app.services.task_monitor.get_redis_client"):
            monitor = SystemMonitor()
            monitor.redis_client = MagicMock()
            return monitor

    def test_check_worker_health_alive(self, monitor):
        """测试健康Worker检查"""
        heartbeat_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": "test-host",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        monitor.redis_client.get.return_value = json.dumps(heartbeat_data)

        status = monitor.check_worker_health("worker-1")

        assert status.worker_id == "worker-1"
        assert status.is_alive is True
        assert status.hostname == "test-host"

    def test_check_worker_health_dead(self, monitor):
        """测试宕机Worker检查"""
        old_time = datetime.now(timezone.utc).timestamp() - 3600  # 1小时前
        heartbeat_data = {
            "timestamp": datetime.fromtimestamp(old_time, tz=timezone.utc).isoformat(),
            "hostname": "test-host",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        monitor.redis_client.get.return_value = json.dumps(heartbeat_data)

        status = monitor.check_worker_health("worker-1")

        assert status.worker_id == "worker-1"
        assert status.is_alive is False

    def test_get_queue_metrics(self, monitor):
        """测试获取队列指标"""
        with patch("app.services.task_monitor.get_db") as mock_db:
            mock_session = MagicMock()

            # Mock查询结果
            mock_session.query().filter().count.side_effect = [10, 5, 20, 2]
            mock_session.query().filter().order_by().limit().all.return_value = []
            mock_session.query().filter().order_by().first.return_value = None

            mock_db.return_value = iter([mock_session])

            metrics = monitor.get_queue_metrics("default")

            assert metrics.queue_name == "default"
            assert metrics.pending_count == 10
            assert metrics.processing_count == 5
            assert metrics.completed_count == 20
            assert metrics.failed_count == 2

    def test_system_health(self, monitor):
        """测试系统健康检查"""
        with patch.object(monitor, "get_all_workers") as mock_workers:
            with patch.object(monitor, "get_all_queues") as mock_queues:
                mock_workers.return_value = [
                    WorkerStatus(
                        worker_id="worker-1",
                        hostname="host-1",
                        is_alive=True,
                        last_heartbeat=datetime.now(timezone.utc),
                        started_at=datetime.now(timezone.utc),
                    ),
                    WorkerStatus(
                        worker_id="worker-2",
                        hostname="host-2",
                        is_alive=False,
                        last_heartbeat=datetime.now(timezone.utc),
                        started_at=datetime.now(timezone.utc),
                    ),
                ]

                mock_queues.return_value = [
                    QueueMetrics(queue_name="default", pending_count=5)
                ]

                health = monitor.get_system_health()

                assert health.total_workers == 2
                assert health.healthy_workers == 1
                assert health.system_status == "degraded"


# ==================== AlertProcessor 测试 ====================


class TestAlertProcessor:
    """告警处理器测试"""

    @pytest.fixture
    def processor(self):
        """创建测试用的处理器"""
        with patch("app.services.alert_processor.get_redis_client"):
            processor = AlertProcessor()
            processor.redis_client = MagicMock()
            return processor

    def test_check_worker_alerts(self, processor):
        """测试Worker告警检查"""
        workers = [
            WorkerStatus(
                worker_id="worker-1",
                hostname="host-1",
                is_alive=False,
                last_heartbeat=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )
        ]

        processor.redis_client.exists.return_value = 0  # 不在冷却期

        alerts = processor.check_worker_alerts(workers)

        assert len(alerts) > 0
        assert alerts[0].condition_type == AlertConditionType.WORKER_DOWN

    def test_check_queue_alerts(self, processor):
        """测试队列告警检查"""
        queues = [
            QueueMetrics(
                queue_name="default",
                pending_count=150,  # 超过默认阈值100
                processing_count=5,
                completed_count=100,
                failed_count=50,  # 失败率33%
            )
        ]

        processor.redis_client.exists.return_value = 0  # 不在冷却期

        alerts = processor.check_queue_alerts(queues)

        # 应该有队列积压告警
        assert any(a.condition_type == AlertConditionType.QUEUE_BACKLOG for a in alerts)
        # 应该有高失败率告警
        assert any(
            a.condition_type == AlertConditionType.HIGH_FAILURE_RATE for a in alerts
        )

    def test_cooldown_mechanism(self, processor):
        """测试冷却期机制"""
        config = AlertConfig(
            rule_id="test-rule",
            rule_name="测试规则",
            condition_type=AlertConditionType.QUEUE_BACKLOG,
            threshold=100,
            comparison="gt",
            cooldown_period=300,
        )

        # 第一次检查 - 不在冷却期
        processor.redis_client.exists.return_value = 0
        should_trigger = processor._should_trigger_alert(config, 150)
        assert should_trigger is True

        # 触发后设置冷却期
        processor._set_cooldown(config.rule_id, config.cooldown_period)

        # 第二次检查 - 在冷却期内
        processor.redis_client.exists.return_value = 1
        should_trigger = processor._should_trigger_alert(config, 150)
        assert should_trigger is False


# ==================== API端点测试 ====================


@pytest.mark.asyncio
class TestMonitoringAPI:
    """监控API端点测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from app.main import app

        return TestClient(app)

    async def test_get_task_status(self, client):
        """测试获取任务状态端点"""
        with patch("app.api.v1.endpoints.monitoring.get_task_tracker") as mock:
            mock_tracker = MagicMock()
            mock_tracker.get_task_status.return_value = TaskSnapshot(
                task_id="test-123",
                status=UnifiedTaskStatus.PROCESSING,
                progress=50,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            mock.return_value = mock_tracker

            response = client.get("/api/v1/monitoring/tasks/test-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-123"
            assert data["status"] == "processing"
            assert data["progress"] == 50

    async def test_process_task_event_success(self, client):
        """事件处理端点应返回 SuccessResponse 结构"""
        with patch("app.api.v1.endpoints.monitoring.get_task_tracker") as mock:
            mock_tracker = MagicMock()
            mock_tracker.process_event.return_value = True
            mock.return_value = mock_tracker

            payload = {
                "task_id": "test-123",
                "event_type": "status_change",
                "new_status": "processing",
            }
            response = client.post(
                "/api/v1/monitoring/tasks/test-123/event", json=payload
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert isinstance(data.get("timestamp"), str)
            assert data.get("data", {}).get("task_id") == "test-123"

    async def test_batch_update_tasks_success(self, client):
        """批量更新端点应返回 SuccessResponse 结构"""
        with patch("app.api.v1.endpoints.monitoring.get_task_tracker") as mock:
            mock_tracker = MagicMock()
            mock_tracker.batch_update_status.return_value = 2
            mock.return_value = mock_tracker

            response = client.post(
                "/api/v1/monitoring/tasks/batch-update",
                json={"task_ids": ["t1", "t2"], "new_status": "completed"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["total"] == 2
            assert data["data"]["success"] == 2
            assert data["data"]["failed"] == 0

    async def test_cleanup_old_data_success(self, client):
        """清理端点应返回 SuccessResponse 结构"""
        with patch("app.api.v1.endpoints.monitoring.get_task_tracker") as mock:
            mock_tracker = MagicMock()
            mock_tracker.cleanup_old_history.return_value = 5
            mock.return_value = mock_tracker

            response = client.post("/api/v1/monitoring/maintenance/cleanup?days=30")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["cleaned_history"] == 5
            assert data["data"]["retention_days"] == 30

    async def test_get_workers_response_model(self, client):
        """/workers 返回 List[WorkerStatus]"""
        with patch("app.api.v1.endpoints.monitoring.get_system_monitor") as mock:
            worker = WorkerStatus(
                worker_id="w1",
                hostname="h1",
                is_alive=True,
                last_heartbeat=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )
            monitor = MagicMock()
            monitor.get_all_workers.return_value = [worker]
            mock.return_value = monitor

            response = client.get("/api/v1/monitoring/workers")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list) and len(data) == 1
            assert data[0]["worker_id"] == "w1"

    async def test_get_queues_response_model(self, client):
        """/queues 返回 List[QueueMetrics]"""
        with patch("app.api.v1.endpoints.monitoring.get_system_monitor") as mock:
            queue = QueueMetrics(queue_name="default")
            monitor = MagicMock()
            monitor.get_all_queues.return_value = [queue]
            mock.return_value = monitor

            response = client.get("/api/v1/monitoring/queues")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list) and len(data) == 1
            assert data[0]["queue_name"] == "default"

    async def test_resolve_alert_success_response(self, client):
        """/alerts/{id}/resolve 返回 SuccessResponse"""
        with patch("app.api.v1.endpoints.monitoring.get_alert_processor") as mock:
            processor = MagicMock()
            processor.resolve_alert.return_value = True
            mock.return_value = processor

            response = client.post("/api/v1/monitoring/alerts/alert-1/resolve")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["alert_id"] == "alert-1"
            assert data["data"]["resolved"] is True

    async def test_system_health(self, client):
        """测试系统健康端点"""
        with patch(
            "app.api.v1.endpoints.monitoring.get_system_monitor"
        ) as mock_monitor:
            with patch(
                "app.api.v1.endpoints.monitoring.get_alert_processor"
            ) as mock_processor:
                mock_monitor.return_value.get_system_health.return_value = MagicMock(
                    workers=[],
                    queues=[],
                    active_alerts=[],
                    total_workers=2,
                    healthy_workers=2,
                    total_queues=1,
                    system_status="healthy",
                )
                mock_processor.return_value.get_active_alerts.return_value = []

                response = client.get("/api/v1/monitoring/health")

                assert response.status_code == 200
                data = response.json()
                assert data["system_status"] == "healthy"
                assert data["total_workers"] == 2
                assert data["healthy_workers"] == 2
