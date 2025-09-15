"""
测试基础设施 - 类型安全的测试工具 v3
基于真实代码结构的测试基础类
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from app.core.analyzer_config import StepConfig
from app.models.analysis_pipeline import (
    AnalysisConfig,
    PipelineData,
    PipelineResult,
    StepStatus,
)
from app.models.signal_pattern import RedditPost, Signal, SignalPattern, SignalType


@dataclass
class TestData:
    """测试数据容器 - 类型安全"""

    pipeline_data: PipelineData
    step_config: StepConfig
    expected_result: Dict[str, Any]
    mock_data: Dict[str, Any] = field(default_factory=dict)


def create_test_pipeline_data(
    product_description: str = "Test product for analysis",
    keywords: Optional[List[str]] = None,
) -> PipelineData:
    """创建测试用PipelineData"""
    config = AnalysisConfig(
        product_description=product_description,
        target_keywords=keywords or ["test", "product"],
    )
    return PipelineData(
        product_description=product_description,
        target_keywords=keywords or ["test", "product"],
        analysis_config=config,
        pipeline_id="test_123",
    )


def create_test_step_config(
    step_name: str = "test_step", max_duration: float = 60.0
) -> StepConfig:
    """创建测试用StepConfig"""
    return StepConfig(
        step_name=step_name,
        max_duration=max_duration,
        config_data={"test_mode": True},
    )


def create_success_result(step_name: str, data: Dict[str, Any]) -> PipelineResult:
    """创建成功的PipelineResult"""
    return PipelineResult(
        step_name=step_name,
        status=StepStatus.COMPLETED,
        success=True,
        data=data,
        duration=1.0,
    )


def create_error_result(step_name: str, error: str) -> PipelineResult:
    """创建错误的PipelineResult"""
    return PipelineResult(
        step_name=step_name,
        status=StepStatus.FAILED,
        success=False,
        data={"error": error},
        duration=0.0,
        error_message=error,
    )


def create_test_reddit_posts(count: int = 5) -> List[RedditPost]:
    """创建测试用Reddit帖子"""
    posts = []
    for i in range(count):
        post = RedditPost(
            id=f"post_{i}",
            title=f"Test post title {i}",
            content=f"Test post content {i} with some keywords",
            subreddit=f"test_subreddit_{i % 3}",
            score=100 + i * 10,
            comment_count=10 + i * 2,
            created_at=datetime.utcnow(),
        )
        posts.append(post)
    return posts


def create_test_signal_patterns() -> List[SignalPattern]:
    """创建测试用信号模式"""
    return [
        SignalPattern(
            signal_type=SignalType.PAIN_POINT,
            keywords=["problem", "issue", "broken", "frustrating"],
            sentiment_threshold=-0.5,
            context_rules=["complaint"],
            confidence_weight=0.9,
        ),
        SignalPattern(
            signal_type=SignalType.COMPETITOR,
            keywords=["alternative", "vs", "better than", "compared to"],
            sentiment_threshold=0.0,
            context_rules=["comparison"],
            confidence_weight=0.8,
        ),
        SignalPattern(
            signal_type=SignalType.OPPORTUNITY,
            keywords=["wish", "need", "would be great", "missing"],
            sentiment_threshold=0.3,
            context_rules=["feature_request"],
            confidence_weight=0.85,
        ),
    ]


def create_test_signals(count: int = 3) -> List[Signal]:
    """创建测试用信号"""
    signal_types = [
        SignalType.PAIN_POINT,
        SignalType.COMPETITOR,
        SignalType.OPPORTUNITY,
    ]
    signals = []

    for i in range(count):
        signal = Signal(
            signal_type=signal_types[i % 3],
            content=f"Test signal content {i}",
            matched_keywords=[f"keyword_{i}"],
            sentiment_score=-0.5 + i * 0.5,
            confidence=0.7 + i * 0.1,
            context_metadata={"score": 100 + i * 50, "comment_count": 10 + i * 5},
            source_post_id=f"post_{i}",
            subreddit=f"test_sub_{i}",
        )
        signals.append(signal)

    return signals


class AsyncTestRunner:
    """异步测试运行器"""

    @staticmethod
    def run(coro: Any) -> Any:
        """运行异步协程"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                try:
                    # 尝试导入nest_asyncio
                    import nest_asyncio

                    nest_asyncio.apply()
                    return loop.run_until_complete(coro)
                except ImportError:
                    # 如果没有nest_asyncio，创建新任务
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, coro)
                        return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)


def create_mock_redis_client() -> Mock:
    """创建Mock Redis客户端"""
    mock_redis = Mock()
    mock_redis.get = Mock(return_value=None)
    mock_redis.set = Mock(return_value=True)
    mock_redis.delete = Mock(return_value=1)
    mock_redis.exists = Mock(return_value=False)
    return mock_redis


def assert_pipeline_result(
    result: PipelineResult, expected_status: StepStatus, expected_success: bool
) -> None:
    """验证PipelineResult"""
    assert result.status == expected_status
    assert result.success == expected_success
    assert result.data is not None
    assert isinstance(result.duration, (int, float))
    assert result.duration >= 0
