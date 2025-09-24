"""
分析引擎主控制器 - Reddit Signal Scanner
统一编排四步分析流水线，实现30秒输入→5分钟分析→结构化商业洞察

基于Linus设计原则：
- 简单的流水线控制逻辑，无复杂条件分支
- 数据驱动的步骤执行，统一接口处理
- 错误早发现早处理，保证系统稳定性
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Mapping, Optional, TypedDict, Union, cast
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from ..core.analyzer_config import (
    ConfigManager,
    ConfigValidationResult,
    get_config,
    load_default_config,
)
from ..core.step_base import AnalysisStep
from ..core.types import JsonValue, StepInfo
from ..models.analysis_pipeline import (
    AnalysisConfig,
    AnalysisReport,
    InsightsData,
    PipelineData,
    StepResultValue,
    StepStatus,
)


# -----------------------------
# 本地类型收敛助手（仅本文件使用）
# -----------------------------
def as_str(v: object) -> str:
    if isinstance(v, str):
        return v
    if v is None:
        return ""
    return str(v)


def as_int(v: object) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return int(float(v))
            except ValueError:
                return 0
    return 0


def as_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0.0
    if isinstance(v, bool):
        return float(int(v))
    return 0.0


def as_list(v: object) -> list[JsonValue]:
    if isinstance(v, list):
        return v
    return []


def as_mapping(v: object) -> Mapping[str, JsonValue]:
    if isinstance(v, Mapping):
        return v
    return {}


def as_list_of_dicts(v: object) -> list[dict[str, JsonValue]]:
    """将任意对象转为 list[dict[str, JsonValue]]（I/O 边界收敛）"""
    items = as_list(v)
    return [cast(dict[str, JsonValue], as_mapping(x)) for x in items]


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class AnalysisRequest:
    analysis_id: str
    keywords: List[str]
    min_subscribers: int
    max_communities: int
    user_id: str


@dataclass
class AnalysisResponse:
    analysis_id: str
    status: AnalysisStatus
    success: bool
    results: List[Dict[str, Union[str, float, int]]]
    execution_time: float
    timestamp: datetime


class QualityMetricsPayload(TypedDict):
    community_relevance: float
    cache_hit_rate: float
    data_freshness: float
    signal_confidence: float


class EngineStatusPayload(TypedDict):
    version: str
    steps_count: int
    steps_info: List[StepInfo]
    max_total_duration: float
    config_loaded: bool


class EngineHealthPayload(TypedDict, total=False):
    status: str
    config_valid: bool
    config_errors: List[str]
    config_warnings: List[str]
    steps_healthy: bool
    steps_count: int
    error: str


class AnalysisEngine:
    """
    分析引擎主控制器 - 编排四步流水线

    功能：
    - 管理四个分析步骤的执行顺序
    - 统一错误处理和超时控制
    - 性能监控和日志记录
    - 结果验证和置信度计算
    """

    def __init__(self) -> None:
        self.config_manager = get_config()
        # 确保配置已加载
        try:
            # 访问一个必需项，触发未加载异常时自动加载默认配置
            _ = self.config_manager.get("analysis_engine.version", None)
            if _ is None:
                load_default_config()
        except (KeyError, ValueError, RuntimeError):
            load_default_config()
        self.logger = logging.getLogger("analysis_engine")
        self.steps: List[AnalysisStep] = []
        self._initialize_steps()

    def _initialize_steps(self) -> None:
        """初始化四个分析步骤"""
        # 注意：这里使用懒加载，避免循环导入
        # 具体的步骤实现将在后续PRD中完成
        from app.services.analysis.community_discovery_step import (
            CommunityDiscoveryStep,
        )
        from app.services.analysis.data_collector import DataCollectionStep
        from app.services.analysis.result_ranker import ResultRankingStep
        from app.services.analysis.signal_extractor import (
            RedditSignalExtractor as SignalExtractionStep,
        )

        comm_cfg = self.config_manager.get_step_config("community_discovery")
        data_cfg = self.config_manager.get_step_config("data_collection")
        signal_cfg = self.config_manager.get_step_config("signal_extraction")
        rank_cfg = self.config_manager.get_step_config("result_ranking")

        # DataCollectionStep / SignalExtractionStep 构造器期望 dict 配置
        # 这些步骤构造函数接受 Mapping[str, JsonValue]，这里做宽松到窄化转换
        # 下游 DataCollectionStep/SignalExtractionStep 构造器要求 dict[str, str] | None
        def to_str_dict(m: Mapping[str, JsonValue] | None) -> dict[str, str]:
            if not m:
                return {}
            out: dict[str, str] = {}
            for k, v in m.items():
                out[str(k)] = str(v) if v is not None else ""
            return out

        data_cfg_dict = to_str_dict(
            cast(Mapping[str, JsonValue] | None, data_cfg.config_data)
        )
        # SignalExtractionStep 期望 dict[str, JsonValue] | None

        def to_json_mapping(
            m: Mapping[str, JsonValue] | None,
        ) -> dict[str, JsonValue]:
            return dict(m) if m else {}

        signal_cfg_dict_json = to_json_mapping(
            cast(Mapping[str, JsonValue] | None, signal_cfg.config_data)
        )

        self.steps = [
            CommunityDiscoveryStep(comm_cfg),
            DataCollectionStep(data_cfg_dict),
            SignalExtractionStep(signal_cfg_dict_json),
            ResultRankingStep(rank_cfg),
        ]

        self.logger.info(f"初始化完成，共 {len(self.steps)} 个分析步骤")

    async def analyze(
        self, product_description: str, **kwargs: JsonValue
    ) -> AnalysisReport:
        """
        执行完整的四步分析流水线

        Args:
            product_description: 产品描述
            **kwargs: 其他分析参数

        Returns:
            AnalysisReport: 完整分析报告

        Raises:
            ValueError: 输入参数无效
            RuntimeError: 分析执行失败
        """
        # 生成唯一的分析ID
        pipeline_id = str(uuid.uuid4())

        self.logger.info(f"开始分析 [{pipeline_id}]: {product_description[:50]}...")

        try:
            # 1. 构建分析配置
            # 显式构造配置，避免 **kwargs 带来的类型不确定
            tk_raw = kwargs.get("target_keywords", [])
            target_keywords = [as_str(x) for x in as_list(tk_raw) if as_str(x)]

            max_communities = (
                as_int(kwargs.get("max_communities"))
                if "max_communities" in kwargs
                else None
            )
            enable_cache = bool(kwargs.get("enable_cache", True))
            priority = as_str(kwargs.get("priority", "normal"))
            output_format = as_str(kwargs.get("output_format", "structured"))
            include_raw_data = bool(kwargs.get("include_raw_data", False))
            max_total_time = (
                as_float(kwargs.get("max_total_time"))
                if "max_total_time" in kwargs
                else None
            )

            analysis_config = AnalysisConfig(
                product_description=product_description,
                target_keywords=target_keywords,
                max_communities=max_communities,
                enable_cache=enable_cache,
                priority=priority,
                output_format=output_format,
                include_raw_data=include_raw_data,
                max_total_time=max_total_time,
            )

            # 2. 初始化流水线数据
            pipeline_data = self._create_pipeline_data(pipeline_id, analysis_config)

            # 3. 执行分析步骤
            await self._execute_pipeline(pipeline_data)

            # 4. 构建分析报告
            report = await self._build_analysis_report(pipeline_data)

            self.logger.info(
                f"分析完成 [{pipeline_id}]: 耗时 {report.total_duration:.2f}s, "
                f"置信度 {report.confidence_score:.2%}, "
                f"洞察数 {report.insights.total_insights}"
            )

            return report

        except (
            asyncio.TimeoutError,
            ValueError,
            RuntimeError,
            TypeError,
            KeyError,
        ) as e:
            self.logger.error(f"分析失败 [{pipeline_id}]: {str(e)}", exc_info=True)
            raise RuntimeError(f"分析执行失败: {str(e)}")

    # ===== 以下为测试兼容API（tests/algorithms/test_analysis_engine.py 依赖） =====

    async def execute_analysis(self, request: AnalysisRequest) -> AnalysisResponse:
        start_time = time.time()
        try:
            # 将简单请求映射到当前 analyze 接口
            report = await self.analyze(
                product_description=", ".join(request.keywords) or "analysis",
                max_communities=request.max_communities,
            )
            duration = time.time() - start_time
            return AnalysisResponse(
                analysis_id=request.analysis_id,
                status=AnalysisStatus.COMPLETED,
                success=True,
                results=[{"total_posts": report.total_posts_analyzed}],
                execution_time=duration,
                timestamp=datetime.utcnow(),
            )
        except (RuntimeError, ValueError):
            duration = time.time() - start_time
            return AnalysisResponse(
                analysis_id=request.analysis_id,
                status=AnalysisStatus.FAILED,
                success=False,
                results=[],
                execution_time=duration,
                timestamp=datetime.utcnow(),
            )

    def _validate_request(self, request: AnalysisRequest) -> bool:
        return bool(request.keywords) and len(request.keywords) <= 20

    def _cache_result(self, analysis_id: str, response: AnalysisResponse) -> None:
        # 最小实现：记录日志或预留hook（不引入新的依赖）
        self.logger.debug(
            f"缓存分析结果 {analysis_id}: success={response.success}, time={response.execution_time:.2f}s"
        )

    def _create_pipeline_data(
        self, pipeline_id: str, config: AnalysisConfig
    ) -> PipelineData:
        """创建流水线数据对象"""
        return PipelineData(
            product_description=config.product_description,
            target_keywords=config.target_keywords,
            analysis_config=config,
            pipeline_id=pipeline_id,
            total_steps=len(self.steps),
        )

    async def _execute_pipeline(self, data: PipelineData) -> None:
        """
        执行流水线步骤

        设计原则：
        - 顺序执行，前一步的输出是后一步的输入
        - 统一错误处理，任何步骤失败都会终止流水线
        - 性能监控，记录每步的执行时间
        """
        data.total_start_time = time.time()

        for i, step in enumerate(self.steps):
            data.current_step = i

            self.logger.info(f"执行步骤 {i+1}/{len(self.steps)}: {step.name}")

            try:
                # 执行步骤
                result = await step.process(data)

                # 保存结果（形状统一为 PipelineData 要求）
                data.step_results[result.step_name] = cast(
                    Dict[str, StepResultValue], result.data
                )
                data.step_durations.append(result.duration)

                # 检查执行结果
                if not result.success:
                    error_msg = result.error_message or f"步骤 {step.name} 执行失败"
                    data.add_error(error_msg)
                    break

                # 检查超时
                total_elapsed = time.time() - data.total_start_time
                max_total_time = as_float(
                    self.config_manager.get("analysis_engine.max_total_duration", 270)
                )

                if total_elapsed > max_total_time:
                    data.add_error(f"分析总时间超限 (>{max_total_time}s)")
                    break

            except (
                asyncio.TimeoutError,
                RuntimeError,
                ValueError,
                TypeError,
                KeyError,
            ) as e:
                error_msg = f"步骤 {step.name} 执行异常: {str(e)}"
                data.add_error(error_msg)
                self.logger.error(error_msg, exc_info=True)
                break

        # 检查流水线完整性
        if data.current_step < len(self.steps) - 1 and not data.errors:
            data.add_error("流水线未完整执行")

    async def _build_analysis_report(self, data: PipelineData) -> AnalysisReport:
        """构建最终分析报告"""

        # 提取洞察数据
        insights_result = data.get_step_result("signal_extraction") or {}
        insights_data_map = as_mapping(insights_result.get("insights", {}))

        # 兜底机制：确保5个关键字段始终存在且类型正确
        pain_points_raw = insights_data_map.get("pain_points", [])
        competitors_raw = insights_data_map.get("competitors", [])
        opportunities_raw = insights_data_map.get("opportunities", [])

        # 类型安全的字段提取，确保即使为空也返回正确的数组类型
        pain_points = as_list_of_dicts(pain_points_raw) if pain_points_raw else []
        competitors = as_list_of_dicts(competitors_raw) if competitors_raw else []
        opportunities = as_list_of_dicts(opportunities_raw) if opportunities_raw else []

        # 确保每个字段都有最小的结构，防止下游处理失败
        if not pain_points:
            pain_points = []
        if not competitors:
            competitors = []
        if not opportunities:
            opportunities = []

        insights = InsightsData(
            pain_points=pain_points,
            competitors=competitors,
            opportunities=opportunities,
            analysis_summary=as_str(insights_data_map.get("analysis_summary", "")),
            key_insights=[
                as_str(x)
                for x in as_list(insights_data_map.get("key_insights", []))
                if as_str(x)
            ],
            confidence_score=as_float(insights_data_map.get("confidence_score", 0.0)),
            data_quality_score=as_float(
                insights_data_map.get("data_quality_score", 0.0)
            ),
        )

        # 计算置信度
        confidence_score = await self._calculate_overall_confidence(data)

        # 构建数据源信息
        collection_result = data.get_step_result("data_collection") or {}
        data_sources_map = as_mapping(collection_result.get("data_sources", {}))
        data_sources: Dict[str, int] = {
            k: as_int(v) for k, v in data_sources_map.items()
        }
        total_posts = as_int(collection_result.get("total_posts", 0))

        # 提取社区信息
        communities_result = data.get_step_result("community_discovery") or {}
        communities_val = as_list(communities_result.get("communities", []))
        communities: List[str] = [
            as_str(as_mapping(c).get("subreddit_name", "")) for c in communities_val
        ]

        # 构建步骤耗时统计
        step_durations = {}
        for i, duration in enumerate(data.step_durations):
            if i < len(self.steps):
                step_durations[self.steps[i].name] = duration

        quality_metrics = await self._calculate_quality_metrics(data)
        data_quality_metrics = {
            "community_relevance": quality_metrics["community_relevance"],
            "cache_hit_rate": quality_metrics["cache_hit_rate"],
            "data_freshness": quality_metrics["data_freshness"],
            "signal_confidence": quality_metrics["signal_confidence"],
        }

        return AnalysisReport(
            report_id=data.pipeline_id,
            product_description=data.product_description,
            insights=insights,
            confidence_score=confidence_score,
            total_posts_analyzed=total_posts,
            communities_scanned=communities,
            data_sources=data_sources,
            total_duration=sum(data.step_durations),
            step_durations=step_durations,
            data_quality_metrics=data_quality_metrics,
        )

    async def _calculate_overall_confidence(self, data: PipelineData) -> float:
        """
        计算整体置信度

        基于以下因素：
        - 数据质量（缓存命中率、帖子质量）
        - 结果数量（洞察总数）
        - 执行成功率（步骤完成度）
        - 时间效率（是否在预期时间内完成）
        """
        if data.errors:
            return 0.0  # 有错误时置信度为0

        confidence_factors: List[float] = []

        # 1. 数据质量评分
        collection_result = data.get_step_result("data_collection") or {}
        cache_hit_rate = as_float(collection_result.get("cache_hit_rate", 0.0))
        data_quality = min(1.0, cache_hit_rate + 0.3)  # 缓存命中率+基础分
        confidence_factors.append(data_quality * 0.3)

        # 2. 结果数量评分
        insights_result = data.get_step_result("signal_extraction") or {}
        insights_map = as_mapping(insights_result.get("insights", {}))
        total_insights = (
            len(as_list(insights_map.get("pain_points", [])))
            + len(as_list(insights_map.get("competitors", [])))
            + len(as_list(insights_map.get("opportunities", [])))
        )
        result_score = min(1.0, total_insights / 10)  # 10个洞察为满分
        confidence_factors.append(result_score * 0.4)

        # 3. 执行成功率评分
        success_rate = (data.current_step + 1) / len(self.steps)
        confidence_factors.append(success_rate * 0.2)

        # 4. 时间效率评分
        total_duration = sum(data.step_durations)
        expected_duration = as_float(
            self.config_manager.get("analysis_engine.max_total_duration", 270)
        )
        time_efficiency = max(0.5, 1.0 - (total_duration / expected_duration))
        confidence_factors.append(time_efficiency * 0.1)

        return sum(confidence_factors)

    async def _calculate_quality_metrics(
        self, data: PipelineData
    ) -> QualityMetricsPayload:
        """计算数据质量指标"""

        communities_result = data.get_step_result("community_discovery") or {}
        communities_list = as_list(communities_result.get("communities", []))
        scores = [
            as_float(as_mapping(community).get("relevance_score", 0))
            for community in communities_list
        ]
        community_relevance = (
            sum(scores) / max(len(scores), 1) if scores else 0.0
        )

        collection_result = data.get_step_result("data_collection") or {}
        cache_hit_rate = as_float(collection_result.get("cache_hit_rate", 0.0))
        data_freshness = as_float(collection_result.get("freshness_score", 0.5))

        signal_result = data.get_step_result("signal_extraction") or {}
        insights = as_mapping(signal_result.get("insights", {}))
        signal_confidence = as_float(insights.get("confidence_score", 0.0))

        quality_metrics: QualityMetricsPayload = {
            "community_relevance": float(community_relevance),
            "cache_hit_rate": float(cache_hit_rate),
            "data_freshness": float(data_freshness),
            "signal_confidence": float(signal_confidence),
        }

        return quality_metrics

    def get_engine_status(self) -> EngineStatusPayload:
        """获取引擎状态信息"""
        steps_info: List[StepInfo] = [step.get_step_info() for step in self.steps]
        max_total_duration = as_float(
            self.config_manager.get("analysis_engine.max_total_duration", 270)
        )
        version_value = as_str(
            self.config_manager.get("analysis_engine.version", "unknown")
        )

        status_payload: EngineStatusPayload = {
            "version": version_value,
            "steps_count": len(self.steps),
            "steps_info": steps_info,
            "max_total_duration": float(max_total_duration),
            "config_loaded": bool(self.config_manager._config),
        }

        return status_payload

    async def health_check(self) -> EngineHealthPayload:
        """健康检查"""
        try:
            # 检查配置
            config_valid: ConfigValidationResult = (
                self.config_manager.validate_config()
            )

            # 检查步骤初始化
            steps_healthy = all(step is not None for step in self.steps)
            status = (
                "healthy"
                if config_valid["is_valid"] and steps_healthy
                else "unhealthy"
            )

            health_payload: EngineHealthPayload = {
                "status": status,
                "config_valid": config_valid["is_valid"],
                "config_errors": list(config_valid["errors"]),
                "config_warnings": list(config_valid["warnings"]),
                "steps_healthy": steps_healthy,
                "steps_count": len(self.steps),
            }

            return health_payload

        except (RuntimeError, ValueError) as e:
            return {
                "status": "unhealthy",
                "config_valid": False,
                "config_errors": [str(e)],
                "config_warnings": [],
                "steps_healthy": False,
                "steps_count": len(self.steps),
                "error": str(e),
            }


# 全局引擎实例
_engine_instance: Optional[AnalysisEngine] = None


def get_analysis_engine() -> AnalysisEngine:
    """获取全局分析引擎实例（单例模式）"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AnalysisEngine()
    return _engine_instance


async def quick_analyze(
    product_description: str, **kwargs: JsonValue
) -> AnalysisReport:
    """快速分析入口函数"""
    engine = get_analysis_engine()
    return await engine.analyze(product_description, **kwargs)


# 便捷导入
__all__ = ["AnalysisEngine", "get_analysis_engine", "quick_analyze"]
