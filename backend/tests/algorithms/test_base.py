"""
算法测试辅助 - 兼容引用桥接
提供 create_test_pipeline_data / create_test_step_config / assert_pipeline_result
"""

from datetime import datetime
from typing import Any, Dict

from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus
from app.core.analyzer_config import StepConfig


def create_test_pipeline_data(product_description: str = "test product") -> PipelineData:
    return PipelineData(
        product_description=product_description,
    )


def create_test_step_config(step_name: str) -> StepConfig:
    return StepConfig(step_name=step_name, max_duration=60.0, config_data={})


def assert_pipeline_result(
    result: PipelineResult, status: StepStatus, success: bool
) -> None:
    assert result.status == status
    assert result.success is success


def create_mock_redis_client() -> Any:
    class _Mock:
        def __init__(self) -> None:
            self._store: Dict[str, bytes] = {}

        def set(self, key: str, value: bytes | str, ex: int | None = None) -> None:
            self._store[key] = (
                value if isinstance(value, bytes) else str(value).encode()
            )

        def get(self, key: str) -> bytes | None:
            return self._store.get(key)

    return _Mock()
