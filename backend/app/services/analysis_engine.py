"""
分析引擎主控制器 - Reddit Signal Scanner
统一编排四步分析流水线，实现30秒输入→5分钟分析→结构化商业洞察

基于Linus设计原则：
- 简单的流水线控制逻辑，无复杂条件分支
- 数据驱动的步骤执行，统一接口处理
- 错误早发现早处理，保证系统稳定性
"""

import asyncio
import time
import uuid
from typing import List, Optional, Dict, Any
import logging

from app.models.analysis_pipeline import (
    PipelineData,
    AnalysisConfig,
    AnalysisReport,
    InsightsData,
    StepStatus,
)
from app.core.analyzer_config import ConfigManager, get_config
from app.core.step_base import AnalysisStep


class AnalysisEngine:
    """
    分析引擎主控制器 - 编排四步流水线

    功能：
    - 管理四个分析步骤的执行顺序
    - 统一错误处理和超时控制
    - 性能监控和日志记录
    - 结果验证和置信度计算
    """

    def __init__(self):
        self.config_manager = get_config()
        self.logger = logging.getLogger("analysis_engine")
        self.steps: List[AnalysisStep] = []
        self._initialize_steps()

    def _initialize_steps(self) -> None:
        """初始化四个分析步骤"""
        # 注意：这里使用懒加载，避免循环导入
        # 具体的步骤实现将在后续PRD中完成
        from app.services.analysis.community_discovery import CommunityDiscoveryStep
        from app.services.analysis.data_collector import DataCollectionStep
        from app.services.analysis.signal_extractor import SignalExtractionStep
        from app.services.analysis.result_ranker import ResultRankingStep

        self.steps = [
            CommunityDiscoveryStep(
                self.config_manager.get_step_config("community_discovery")
            ),
            DataCollectionStep(self.config_manager.get_step_config("data_collection")),
            SignalExtractionStep(
                self.config_manager.get_step_config("signal_extraction")
            ),
            ResultRankingStep(self.config_manager.get_step_config("result_ranking")),
        ]

        self.logger.info(f"初始化完成，共 {len(self.steps)} 个分析步骤")

    async def analyze(self, product_description: str, **kwargs) -> AnalysisReport:
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
            analysis_config = AnalysisConfig(
                product_description=product_description, **kwargs
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

        except Exception as e:
            self.logger.error(f"分析失败 [{pipeline_id}]: {str(e)}", exc_info=True)
            raise RuntimeError(f"分析执行失败: {str(e)}")

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

                # 保存结果
                data.step_results[result.step_name] = result.data
                data.step_durations.append(result.duration)

                # 检查执行结果
                if not result.success:
                    error_msg = result.error_message or f"步骤 {step.name} 执行失败"
                    data.add_error(error_msg)
                    break

                # 检查超时
                total_elapsed = time.time() - data.total_start_time
                max_total_time = self.config_manager.get(
                    "analysis_engine.max_total_duration", 270
                )

                if total_elapsed > max_total_time:
                    data.add_error(f"分析总时间超限 (>{max_total_time}s)")
                    break

            except Exception as e:
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
        insights_data = data.get_step_result("signal_extraction", {}).get(
            "insights", {}
        )
        insights = InsightsData(**insights_data) if insights_data else InsightsData()

        # 计算置信度
        confidence_score = await self._calculate_overall_confidence(data)

        # 构建数据源信息
        collection_result = data.get_step_result("data_collection", {})
        data_sources = collection_result.get("data_sources", {"cache": 0, "api": 0})
        total_posts = collection_result.get("total_posts", 0)

        # 提取社区信息
        communities_result = data.get_step_result("community_discovery", {})
        communities = [
            c.get("subreddit_name", "")
            for c in communities_result.get("communities", [])
        ]

        # 构建步骤耗时统计
        step_durations = {}
        for i, duration in enumerate(data.step_durations):
            if i < len(self.steps):
                step_durations[self.steps[i].name] = duration

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
            data_quality_metrics=await self._calculate_quality_metrics(data),
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

        confidence_factors = []

        # 1. 数据质量评分
        collection_result = data.get_step_result("data_collection", {})
        cache_hit_rate = collection_result.get("cache_hit_rate", 0.0)
        data_quality = min(1.0, cache_hit_rate + 0.3)  # 缓存命中率+基础分
        confidence_factors.append(data_quality * 0.3)

        # 2. 结果数量评分
        insights_result = data.get_step_result("signal_extraction", {})
        insights_data = insights_result.get("insights", {})
        total_insights = (
            len(insights_data.get("pain_points", []))
            + len(insights_data.get("competitors", []))
            + len(insights_data.get("opportunities", []))
        )
        result_score = min(1.0, total_insights / 10)  # 10个洞察为满分
        confidence_factors.append(result_score * 0.4)

        # 3. 执行成功率评分
        success_rate = (data.current_step + 1) / len(self.steps)
        confidence_factors.append(success_rate * 0.2)

        # 4. 时间效率评分
        total_duration = sum(data.step_durations)
        expected_duration = self.config_manager.get(
            "analysis_engine.max_total_duration", 270
        )
        time_efficiency = max(0.5, 1.0 - (total_duration / expected_duration))
        confidence_factors.append(time_efficiency * 0.1)

        return sum(confidence_factors)

    async def _calculate_quality_metrics(self, data: PipelineData) -> Dict[str, float]:
        """计算数据质量指标"""
        metrics = {}

        # 社区发现质量
        communities_result = data.get_step_result("community_discovery", {})
        communities = communities_result.get("communities", [])
        metrics["community_relevance"] = sum(
            c.get("relevance_score", 0) for c in communities
        ) / max(len(communities), 1)

        # 数据收集质量
        collection_result = data.get_step_result("data_collection", {})
        metrics["cache_hit_rate"] = collection_result.get("cache_hit_rate", 0.0)
        metrics["data_freshness"] = collection_result.get("freshness_score", 0.5)

        # 信号提取质量
        signal_result = data.get_step_result("signal_extraction", {})
        insights = signal_result.get("insights", {})
        metrics["signal_confidence"] = insights.get("confidence_score", 0.0)

        return metrics

    def get_engine_status(self) -> Dict[str, Any]:
        """获取引擎状态信息"""
        return {
            "version": self.config_manager.get("analysis_engine.version", "unknown"),
            "steps_count": len(self.steps),
            "steps_info": [step.get_step_info() for step in self.steps],
            "max_total_duration": self.config_manager.get(
                "analysis_engine.max_total_duration", 270
            ),
            "config_loaded": bool(self.config_manager._config),
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查配置
            config_valid = self.config_manager.validate_config()

            # 检查步骤初始化
            steps_healthy = all(step is not None for step in self.steps)

            return {
                "status": (
                    "healthy"
                    if config_valid["is_valid"] and steps_healthy
                    else "unhealthy"
                ),
                "config_valid": config_valid["is_valid"],
                "config_errors": config_valid.get("errors", []),
                "steps_healthy": steps_healthy,
                "steps_count": len(self.steps),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# 全局引擎实例
_engine_instance: Optional[AnalysisEngine] = None


def get_analysis_engine() -> AnalysisEngine:
    """获取全局分析引擎实例（单例模式）"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AnalysisEngine()
    return _engine_instance


async def quick_analyze(product_description: str, **kwargs) -> AnalysisReport:
    """快速分析入口函数"""
    engine = get_analysis_engine()
    return await engine.analyze(product_description, **kwargs)


# 便捷导入
__all__ = ["AnalysisEngine", "get_analysis_engine", "quick_analyze"]
