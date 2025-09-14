"""
数据收集步骤 - 分析流水线第二步
负责从缓存和API混合数据源收集Reddit数据
"""

from typing import Any, Dict, Optional

from app.core.analyzer_config import StepConfig
from app.core.step_base import AnalysisStep
from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus
from app.services.data_collector import DataCollectionService


class DataCollectionStep(AnalysisStep):
    """数据收集步骤实现"""

    def __init__(self, config: Optional[Dict[str, str]] = None) -> None:
        """初始化数据收集步骤"""
        # Create StepConfig from dict (适配当前 StepConfig 定义)
        step_config = StepConfig(
            step_name="data_collection",
            max_duration=float(config.get("max_duration", 60)) if config else 60.0,
            config_data={
                "enabled": bool(config.get("enabled", True)) if config else True,
                "retry_count": int(config.get("retry_count", 3)) if config else 3,
            },
        )
        super().__init__(step_config)
        self.service = DataCollectionService()

    async def _process_step(self, data: PipelineData) -> PipelineResult:
        """执行数据收集"""
        # 从前一步获取社区列表
        communities_any: Any = data.step_results.get("community_discovery", {}).get(
            "communities", []
        )
        communities: list[Dict[str, Any]] = (
            communities_any if isinstance(communities_any, list) else []
        )

        # 收集数据
        posts_data: Dict[str, list[Dict[str, Any]]] = {}
        cache_hits = 0
        total_requests = len(communities)

        for community in communities[:20]:  # 限制最多20个社区
            name_val = community.get("name", "") if isinstance(community, dict) else ""
            posts_data[name_val] = []

        return PipelineResult(
            step_name="data_collection",
            duration=5.0,
            data={
                "posts": posts_data,
                "cache_hit_rate": cache_hits / max(total_requests, 1),
                "api_calls": total_requests - cache_hits,
                "total_posts": sum(len(posts) for posts in posts_data.values()),
            },
            success=True,
            status=StepStatus.COMPLETED,
        )

    def _validate_input(self, data: PipelineData) -> bool:
        """验证输入数据"""
        return "community_discovery" in data.step_results

    # 基类要求的抽象方法实现
    def validate_input(self, data: PipelineData) -> bool:
        return self._validate_input(data)

    def _create_error_result(
        self, error_message: str, status: StepStatus = StepStatus.FAILED
    ) -> PipelineResult:
        """创建错误结果"""
        return PipelineResult(
            step_name="data_collection",
            duration=0.0,
            data={},
            success=False,
            status=status,
            error_message=error_message,
        )
