"""
分析任务定义 - prd04-02实现
@celery.task装饰的分析任务，支持异步Reddit信号分析

基于Linus设计哲学：
1. 任务职责单一 - 每个任务只做一件事
2. 统一错误处理 - 消除特殊情况的错误处理
3. 配置驱动 - 所有参数通过配置传入
4. 简单胜过聪明 - 直观的任务逻辑
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from typing import Any, Dict, Generator, List, Optional, cast
from uuid import UUID

from celery import Task
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..core.celery_app import get_celery_app
from ..core.database import get_session_sync
from ..core.task_base import BaseUnifiedTask
from ..models.analysis import Analysis
from ..models.analysis_pipeline import AnalysisReport
from ..models.report import Report
from ..models.task import Task as TaskModel, TaskStatus
from ..services.analysis_engine import AnalysisEngine

logger = logging.getLogger(__name__)


# =========================
# Pydantic响应模型 - 基于Context7最佳实践
# =========================


class AnalysisTaskResponse(BaseModel):
    """产品分析任务响应模型"""

    task_id: str
    status: str
    product_description: str
    analysis_result: Dict[str, Any]
    execution_time: float
    completed_at: str
    metadata: Dict[str, Any]


class BatchAnalysisResponse(BaseModel):
    """批量分析任务响应模型"""

    batch_id: str
    total_products: int
    submitted_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    completed_at: str


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""

    service: str
    status: str
    timestamp: str
    version: str


class DeadLetterOperationResponse(BaseModel):
    """死信队列操作响应模型"""

    operation: str
    moved_count: int
    processed_tasks: List[Dict[str, Any]]
    timestamp: str


class RetryTaskResponse(BaseModel):
    """重试任务响应模型"""

    success: bool
    task_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


class DeadLetterStatsResponse(BaseModel):
    """死信队列统计响应模型"""

    total_dead_letters: int
    by_category: Dict[str, int]
    recent_tasks: List[Dict[str, Any]]
    timestamp: str


# 获取Celery应用实例
celery_app = get_celery_app()


def _analyze_product_typed(
    self: BaseUnifiedTask,
    payload: Dict[str, Any],
    task_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    产品分析Celery任务 - Reddit信号分析的核心任务

    这是用户请求的最终执行者，负责：
    1. Reddit数据采集
    2. 信号提取和分析
    3. 结果生成和存储
    4. 状态更新

    Args:
        payload: 任务载荷数据，包含product_description等
        task_data: 任务元数据，包含task_id等信息

    Returns:
        Dict[str, Any]: 分析结果

    Raises:
        AnalysisError: 分析过程中的错误
        DatabaseError: 数据库操作错误
        RetryError: 需要重试的临时错误
    """
    # 使用合法UUID，若传入非UUID则回退为当前request.id
    import uuid

    raw_task_id = (
        (task_data.get("task_id") if task_data else self.request.id)
        if task_data
        else self.request.id
    )
    try:
        task_uuid = uuid.UUID(str(raw_task_id))
        task_id: str = str(task_uuid)
    except Exception:
        task_id = str(self.request.id)
    product_description = payload.get("product_description", "")

    # Linus修复：从TaskConfig获取配置参数
    from ..schemas.task_producer import TaskConfig

    config = TaskConfig.default_config()

    logger.info(f"开始产品分析任务: {task_id}")
    start_time = time.time()

    # 更新任务状态为进行中
    _update_task_status_sync(
        task_id,
        "processing",
        {"started_at": datetime.now(timezone.utc).isoformat()},
    )

    try:
        # 第1步：参数验证（统一验证逻辑）
        if not product_description or len(product_description.strip()) < 10:
            raise ValueError("产品描述不能为空且长度必须至少10个字符")

        # 第2步：初始化分析引擎
        # 在任务内确保分析引擎可用（构造函数内会保证配置已加载）
        analysis_engine = AnalysisEngine()

        # 第3步：执行分析（核心业务逻辑）
        import asyncio

        analysis_report = asyncio.run(
            analysis_engine.analyze(product_description=product_description.strip())
        )
        persistence_payload = _persist_analysis_report(
            task_id=task_id,
            product_description=product_description.strip(),
            report=analysis_report,
        )
        analysis_result: Dict[str, Any] = {
            "report_id": analysis_report.report_id,
            "summary": analysis_report.get_executive_summary(),
            "confidence_score": analysis_report.confidence_score,
            "total_posts": analysis_report.total_posts_analyzed,
            "communities": persistence_payload["sources"].get("communities", []),
            "market_metrics": persistence_payload["market_metrics"],
            "insights_overview": {
                "pain_points": len(
                    persistence_payload["insights"].get("pain_points", [])
                ),
                "competitors": len(
                    persistence_payload["insights"].get("competitors", [])
                ),
                "opportunities": len(
                    persistence_payload["insights"].get("opportunities", [])
                ),
            },
        }

        # 第4步：处理分析结果
        metadata_payload: Dict[str, Any] = {
            **(task_data or {}),
            **persistence_payload["metadata"],
        }
        result_data = {
            "task_id": task_id,
            "status": "completed",
            "product_description": product_description,
            "analysis_result": analysis_result,
            "execution_time": time.time() - start_time,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata_payload,
        }

        # 第5步：更新数据库状态
        _update_task_status_sync(
            task_id,
            "completed",
            {
                "result": analysis_result,
                "execution_time": result_data["execution_time"],
                "completed_at": result_data["completed_at"],
            },
        )

        logger.info(f"任务完成: {task_id}, 耗时: {result_data['execution_time']:.2f}秒")
        return result_data

    except ValueError as e:
        # 参数验证错误 - 不可重试
        error_msg = f"参数验证失败: {str(e)}"
        logger.error(f"任务 {task_id} 参数错误: {error_msg}")

        _update_task_status_sync(
            task_id,
            "failed",
            {"error": error_msg, "error_type": "validation_error"},
        )

        # 不重试参数错误
        raise ValueError(error_msg)

    except (ConnectionError, TimeoutError, OSError) as e:
        # 这些异常会被autoretry_for自动处理，无需手动重试
        error_msg = f"临时性错误，将自动重试: {str(e)}"
        logger.warning(f"任务 {task_id} 临时错误: {error_msg}")

        # 更新数据库记录重试信息
        _update_task_status_sync(
            task_id,
            "retrying",
            {
                "error": error_msg,
                "retry_count": self.request.retries,
                "error_type": "temporary_error",
            },
        )

        # 让Celery的autoretry_for处理重试逻辑
        raise  # 直接重新抛出异常，由Celery处理

    except Exception as e:
        # 其他异常不自动重试，直接失败
        error_msg = f"分析任务失败: {str(e)}"
        logger.error(f"任务 {task_id} 不可重试错误: {error_msg}")

        _update_task_status_sync(
            task_id,
            "failed",
            {
                "error": error_msg,
                "error_type": "permanent_error",
                "retry_count": self.request.retries,
            },
        )

        # 直接失败，不重试
        raise


# 使用注册方式创建 Celery 任务，避免装饰器导致的 mypy 未类型化报错
analyze_product_task = celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.analyze_product",
    queue="analysis_queue",
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=300,
    soft_time_limit=240,
    serializer="json",
    compression="gzip",
)(_analyze_product_typed)


def _batch_analyze_products_typed(
    self: BaseUnifiedTask,
    product_list: List[str],
    batch_id: str,
    task_data: Optional[Dict[str, Any]] = None,
) -> BatchAnalysisResponse:
    """
    批量产品分析任务

    处理多个产品的批量分析请求，用于未来扩展

    Args:
        product_list: 产品描述列表
        batch_id: 批次ID
        task_data: 任务元数据

    Returns:
        Dict: 批量分析结果
    """
    logger.info(f"开始批量分析任务: {batch_id}, 产品数量: {len(product_list)}")

    results = []
    failed_count = 0

    for i, product_description in enumerate(product_list):
        try:
            # 为每个产品创建子任务
            sub_task_id = f"{batch_id}_item_{i+1}"

            # 调用单个产品分析
            result = cast(Any, analyze_product_task).delay(
                payload={"product_description": product_description},
                task_data={"task_id": sub_task_id, "batch_id": batch_id},
            )

            results.append(
                {
                    "index": i + 1,
                    "product": product_description[:50] + "...",
                    "sub_task_id": sub_task_id,
                    "status": "submitted",
                }
            )

        except Exception as e:
            failed_count += 1
            logger.error(f"批量任务 {batch_id} 第{i+1}项提交失败: {e}")

            results.append(
                {
                    "index": i + 1,
                    "product": product_description[:50] + "...",
                    "status": "failed",
                    "error": str(e),
                }
            )

    return BatchAnalysisResponse(
        batch_id=batch_id,
        total_products=len(product_list),
        submitted_count=len(product_list) - failed_count,
        failed_count=failed_count,
        results=results,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


batch_analyze_products = celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.batch_analyze",
    queue="analysis_queue",
    max_retries=2,
    time_limit=900,  # 15分钟
    soft_time_limit=800,
)(_batch_analyze_products_typed)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Convert arbitrary JSON values to timezone-aware datetimes when possible."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            logger.warning("无法解析日期时间字符串: %s", value)
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None

    return None


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _sanitize_string_list(values: Any, limit: Optional[int] = None) -> list[str]:
    if not isinstance(values, list):
        return []
    sanitized = [
        str(item).strip() for item in values if isinstance(item, (str, int, float))
    ]
    sanitized = [item for item in sanitized if item]
    if limit is not None:
        return sanitized[:limit]
    return sanitized


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _sanitize_communities(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return ["r/unknown"]
    sanitized: list[str] = []
    for item in raw:
        community = str(item).strip()
        if not community:
            continue
        community = community.lstrip("/")
        if not community.startswith("r/"):
            community = f"r/{community}"
        sanitized.append(community[:80])
    return sanitized or ["r/unknown"]


def _sanitize_pain_points(raw_items: Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return sanitized
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("title") or "").strip()
        if not description:
            continue
        frequency = _coerce_int(item.get("frequency"))
        if frequency is None:
            frequency = _coerce_int(item.get("mention_count"))
        if frequency is None:
            frequency = _coerce_int(item.get("mentions"))
        frequency = max(frequency or 0, 0)
        sentiment = _coerce_float(item.get("sentiment_score"))
        if sentiment is None:
            sentiment = _coerce_float(item.get("sentiment"))
        sentiment = _clamp(sentiment if sentiment is not None else 0.0, -1.0, 1.0)
        evidence = item.get("evidence_posts") or item.get("example_posts") or []
        example_posts = _sanitize_string_list(evidence, limit=10)
        categories = _sanitize_string_list(item.get("categories"), limit=10)
        enriched = dict(item)
        enriched["description"] = description
        enriched["frequency"] = frequency
        enriched["sentiment_score"] = sentiment
        enriched["example_posts"] = example_posts
        enriched["evidence_posts"] = example_posts
        enriched["categories"] = categories
        sanitized.append(enriched)
    return sanitized


def _sanitize_competitors(raw_items: Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return sanitized
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        mentions = _coerce_int(item.get("mention_count"))
        if mentions is None:
            mentions = _coerce_int(item.get("mentions"))
        mentions = max(mentions or 0, 0)
        sentiment = _coerce_float(item.get("sentiment_score"))
        if sentiment is None:
            sentiment = _coerce_float(item.get("sentiment"))
        sentiment = _clamp(sentiment if sentiment is not None else 0.0, -1.0, 1.0)
        strengths = _sanitize_string_list(item.get("strengths"), limit=10)
        weaknesses = _sanitize_string_list(item.get("weaknesses"), limit=10)
        price_mentions = _sanitize_string_list(item.get("price_mentions"), limit=10)
        enriched = dict(item)
        enriched["name"] = name
        enriched["mentions"] = mentions
        enriched["mention_count"] = mentions
        enriched["sentiment"] = sentiment
        enriched["sentiment_score"] = sentiment
        enriched["strengths"] = strengths
        enriched["weaknesses"] = weaknesses
        enriched["price_mentions"] = price_mentions
        sanitized.append(enriched)
    return sanitized


def _sanitize_opportunities(raw_items: Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return sanitized
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("title") or "").strip()
        if not description:
            continue
        relevance = _coerce_float(item.get("relevance_score"))
        if relevance is None:
            relevance = _coerce_float(item.get("urgency_score"))
        relevance = _clamp(relevance if relevance is not None else 0.0, 0.0, 1.0)
        potential = _coerce_int(item.get("potential_users"))
        if potential is None:
            potential = _coerce_int(item.get("estimated_demand"))
        potential = max(potential or 0, 0)
        feasibility = _coerce_float(item.get("feasibility_score"))
        feasibility = _clamp(feasibility if feasibility is not None else 0.0, 0.0, 1.0)
        target_communities = _sanitize_string_list(
            item.get("target_communities"), limit=10
        )
        related_keywords = _sanitize_string_list(item.get("related_keywords"), limit=10)
        enriched = dict(item)
        enriched.setdefault("title", description[:120])
        enriched["description"] = description
        enriched["relevance_score"] = relevance
        enriched["urgency_score"] = _clamp(
            _coerce_float(enriched.get("urgency_score")) or relevance, 0.0, 1.0
        )
        enriched["feasibility_score"] = feasibility
        enriched["potential_users"] = potential
        enriched["estimated_demand"] = potential
        enriched["target_communities"] = target_communities
        enriched["related_keywords"] = related_keywords
        sanitized.append(enriched)
    return sanitized


def _derive_sentiment_summary(pain_points: list[dict[str, Any]]) -> dict[str, float]:
    if not pain_points:
        return {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    buckets = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    total = 0.0
    for pain in pain_points:
        sentiment = _coerce_float(pain.get("sentiment_score")) or 0.0
        weight = float(_coerce_int(pain.get("frequency")) or 1)
        total += weight
        if sentiment >= 0.6:
            buckets["positive"] += weight
        elif sentiment <= 0.4:
            buckets["negative"] += weight
        else:
            buckets["neutral"] += weight
    if total <= 0:
        return {"positive": 0.33, "neutral": 0.34, "negative": 0.33}
    return {key: round(value / total, 2) for key, value in buckets.items()}


def _derive_trending_topics(
    pain_points: list[dict[str, Any]], opportunities: list[dict[str, Any]]
) -> list[str]:
    topics: list[str] = []
    for pain in pain_points:
        topics.extend(_sanitize_string_list(pain.get("categories")))
    for opportunity in opportunities:
        topics.extend(_sanitize_string_list(opportunity.get("related_keywords")))
    ordered: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        normalized = topic.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if len(ordered) >= 10:
            break
    return ordered


def _build_market_metrics(
    report: AnalysisReport,
    sentiment_summary: dict[str, float],
    communities: list[str],
    trending_topics: list[str],
) -> dict[str, Any]:
    # 兜底机制：确保数值字段类型正确且有合理默认值
    total_posts = max(int(report.total_posts_analyzed or 0), 0)
    sentiment_score = round(
        sentiment_summary.get("positive", 0.0) - sentiment_summary.get("negative", 0.0),
        2,
    )
    engagement_rate = _clamp(
        _coerce_float(report.data_quality_metrics.get("community_relevance")) or 0.0,
        0.0,
        1.0,
    )

    # 兜底机制：确保数组字段始终为列表类型
    safe_communities = communities if isinstance(communities, list) else []
    safe_trending_topics = trending_topics if isinstance(trending_topics, list) else []

    # 确保market_metrics字段结构完整，符合API契约
    market_metrics = {
        "total_mentions": total_posts,
        "sentiment_score": sentiment_score,
        "top_communities": safe_communities[:5],
        "trending_keywords": safe_trending_topics[:10],
        "engagement_rate": round(engagement_rate, 2),
        "sample_size": total_posts,
    }
    return market_metrics


def _build_insights_payload(
    report: AnalysisReport, product_description: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    # 兜底机制：确保5个关键字段始终存在且类型正确
    pain_points = _sanitize_pain_points(report.insights.pain_points or [])
    competitors = _sanitize_competitors(report.insights.competitors or [])
    opportunities = _sanitize_opportunities(report.insights.opportunities or [])

    # 确保即使原始数据为空，也返回正确的数组结构
    pain_points = pain_points if isinstance(pain_points, list) else []
    competitors = competitors if isinstance(competitors, list) else []
    opportunities = opportunities if isinstance(opportunities, list) else []

    sentiment_summary = _derive_sentiment_summary(pain_points)
    trending_topics = _derive_trending_topics(pain_points, opportunities)
    communities = _sanitize_communities(report.communities_scanned)
    analysis_summary = (
        report.insights.analysis_summary
        if report.insights.analysis_summary
        else report.get_executive_summary()
    )
    key_insights = report.insights.key_insights or [
        insight.get("title", "") for insight in pain_points[:3]
    ]
    summary_points = [str(point) for point in key_insights[:3] if str(point).strip()]
    top_opportunity = None
    if opportunities:
        top_opportunity = (
            str(
                opportunities[0].get("title")
                or opportunities[0].get("description")
                or ""
            ).strip()
            or None
        )

    # 兜底机制：确保executive_summary字段结构完整
    executive_summary_payload = {
        "headline": str(key_insights[0]).strip() if key_insights else None,
        "total_communities": len(communities),
        "key_insights": len(key_insights),
        "top_opportunity": top_opportunity,
        "confidence_score": float(report.confidence_score),
        "summary_points": summary_points,
    }
    metadata = {
        "report_id": report.report_id,
        "generated_at": report.generated_at.isoformat(),
        "total_duration": report.total_duration,
        "step_durations": report.step_durations,
        "data_sources": report.data_sources,
        "data_quality_metrics": report.data_quality_metrics,
        "product_description": product_description,
    }
    insights_payload: dict[str, Any] = {
        "pain_points": pain_points,
        "competitors": competitors,
        "opportunities": opportunities,
        "analysis_summary": analysis_summary,
        "key_insights": key_insights,
        "sentiment_summary": sentiment_summary,
        "trending_topics": trending_topics,
        "user_personas": [],
        "executive_summary": executive_summary_payload,
        "confidence_score": float(report.confidence_score),
        "metadata": metadata,
    }
    market_metrics = _build_market_metrics(
        report,
        sentiment_summary,
        communities,
        trending_topics,
    )
    return insights_payload, market_metrics, metadata


def _build_sources_payload(
    report: AnalysisReport, communities: list[str]
) -> dict[str, Any]:
    posts_analyzed = max(int(report.total_posts_analyzed or 0), 1)
    comments_analyzed = _coerce_int(report.data_sources.get("comments_analyzed")) or 0
    time_range_days = _coerce_int(report.data_sources.get("time_range_days")) or 30
    if time_range_days <= 0:
        time_range_days = 30
    cache_hit_rate = _clamp(
        _coerce_float(report.data_quality_metrics.get("cache_hit_rate")) or 0.0,
        0.0,
        1.0,
    )
    analysis_duration = max(float(report.total_duration or 0.0), 0.0)
    reddit_api_calls = (
        _coerce_int(
            report.data_sources.get("api_calls")
            or report.data_sources.get("api")
            or report.data_sources.get("reddit_api_calls")
        )
        or 0
    )
    data_quality_score = _clamp(
        _coerce_float(report.data_quality_metrics.get("signal_confidence")) or 0.0,
        0.0,
        1.0,
    )
    filtered_spam = _coerce_int(report.data_sources.get("filtered_spam_posts")) or 0
    language_distribution = report.data_sources.get("language_distribution")
    if not isinstance(language_distribution, dict):
        language_distribution = {}
    algorithm_version = str(report.data_sources.get("algorithm_version") or "v1")
    processing_parameters = {
        "data_sources": report.data_sources,
        "step_durations": report.step_durations,
    }
    return {
        "communities": communities,
        "posts_analyzed": posts_analyzed,
        "comments_analyzed": max(int(comments_analyzed), 0),
        "time_range_days": time_range_days,
        "cache_hit_rate": cache_hit_rate,
        "analysis_duration_seconds": analysis_duration,
        "reddit_api_calls": max(int(reddit_api_calls), 0),
        "data_quality_score": data_quality_score,
        "filtered_spam_posts": max(int(filtered_spam), 0),
        "language_distribution": language_distribution,
        "algorithm_version": algorithm_version,
        "processing_parameters": processing_parameters,
    }


def _render_report_html(
    task_id: str,
    product_description: str,
    insights: dict[str, Any],
    market_metrics: dict[str, Any],
) -> str:
    pain_items = [
        f"<li><strong>{escape(pain.get('description', ''))}</strong>"
        f" — 频次 {pain.get('frequency', 0)}, 情感 {pain.get('sentiment_score', 0.0):.2f}</li>"
        for pain in insights.get("pain_points", [])[:5]
    ]
    competitor_items = [
        f"<li><strong>{escape(comp.get('name', ''))}</strong>"
        f" — 提及 {comp.get('mentions', 0)}, 情感 {comp.get('sentiment', 0.0):.2f}</li>"
        for comp in insights.get("competitors", [])[:5]
    ]
    opportunity_items = [
        f"<li><strong>{escape(opp.get('title', ''))}</strong>"
        f" — 相关度 {opp.get('relevance_score', 0.0):.2f}, 潜在用户 {opp.get('potential_users', 0)}</li>"
        for opp in insights.get("opportunities", [])[:5]
    ]
    if not pain_items:
        pain_items.append("<li>暂无数据</li>")
    if not competitor_items:
        competitor_items.append("<li>暂无数据</li>")
    if not opportunity_items:
        opportunity_items.append("<li>暂无数据</li>")

    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
        "<title>Reddit Signal Analysis Report</title></head><body>",
        f"<h1>分析任务 {escape(task_id)}</h1>",
        f"<p><strong>产品描述:</strong> {escape(product_description[:512])}</p>",
        "<section><h2>市场指标</h2><ul>",
        f"<li>总提及量: {market_metrics.get('total_mentions', 0)}</li>",
        f"<li>情感得分: {market_metrics.get('sentiment_score', 0.0):.2f}</li>",
        f"<li>互动率: {market_metrics.get('engagement_rate', 0.0):.2f}</li>",
        f"<li>核心社区: {', '.join(map(escape, market_metrics.get('top_communities', [])[:5]))}</li>",
        "</ul></section>",
        "<section><h2>用户痛点</h2><ol>" + "".join(pain_items) + "</ol></section>",
        "<section><h2>竞争对手</h2><ol>" + "".join(competitor_items) + "</ol></section>",
        "<section><h2>市场机会</h2><ol>" + "".join(opportunity_items) + "</ol></section>",
        "</body></html>",
    ]
    return "".join(parts)


def _persist_analysis_report(
    task_id: str,
    product_description: str,
    report: AnalysisReport,
) -> dict[str, Any]:
    insights_payload, market_metrics, metadata = _build_insights_payload(
        report, product_description
    )
    communities = _sanitize_communities(report.communities_scanned)
    sources_payload = _build_sources_payload(report, communities)
    html_content = _render_report_html(
        task_id, product_description, insights_payload, market_metrics
    )

    metadata = dict(metadata)
    metadata.update(
        {
            "communities": communities,
            "html_length": len(html_content),
        }
    )

    try:
        task_uuid = UUID(task_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"非法任务ID，无法落库: {task_id}") from exc

    with _get_sync_session() as db:
        analysis = (
            db.query(Analysis).filter(Analysis.task_id == task_uuid).one_or_none()
        )
        confidence_decimal = Decimal(str(round(report.confidence_score, 4)))
        if analysis is None:
            analysis = Analysis(
                task_id=task_uuid,
                insights=insights_payload,
                sources=sources_payload,
                confidence_score=confidence_decimal,
            )
            db.add(analysis)
            db.flush()
        else:
            analysis.insights = insights_payload
            analysis.sources = sources_payload
            analysis.confidence_score = confidence_decimal
            analysis.analysis_version = (analysis.analysis_version or 0) + 1
            db.add(analysis)
            db.flush()

        metadata["analysis_id"] = str(analysis.id)

        report_record = (
            db.query(Report)
            .filter(Report.analysis_id == analysis.id, Report.status == "active")
            .one_or_none()
        )
        if report_record is None:
            report_record = Report(
                analysis_id=analysis.id,
                html_content=html_content,
                status="active",
            )
            db.add(report_record)
        else:
            report_record.html_content = html_content
        db.flush()

    return {
        "insights": insights_payload,
        "market_metrics": market_metrics,
        "metadata": metadata,
        "sources": sources_payload,
        "html_content": html_content,
    }


def _update_task_status_sync(
    task_id: str, status: str, additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """统一的任务状态更新函数 - 确保数据库记录与任务执行状态保持一致。"""
    try:
        from sqlalchemy import update
        from uuid import UUID as UUIDType

        with _get_sync_session() as db:
            try:
                task_uuid = UUIDType(task_id) if isinstance(task_id, str) else task_id
            except (ValueError, TypeError):
                logger.warning("非法任务ID，跳过状态更新: %s", task_id)
                return

            additional_data = additional_data or {}
            normalized_status = (status or "").strip().lower()
            status_aliases = {
                "retrying": TaskStatus.PENDING,
                "queued": TaskStatus.PENDING,
            }

            if normalized_status in status_aliases:
                task_status = status_aliases[normalized_status]
            else:
                try:
                    task_status = TaskStatus(normalized_status)
                except ValueError:
                    logger.warning("不支持的任务状态 %s，跳过状态字段更新", status)
                    task_status = None

            update_values: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
            if task_status is not None:
                update_values["status"] = task_status.value

            started_at = _parse_iso_datetime(additional_data.get("started_at"))
            if started_at is not None:
                update_values["started_at"] = started_at

            completed_at = _parse_iso_datetime(additional_data.get("completed_at"))

            if task_status is TaskStatus.COMPLETED:
                update_values["completed_at"] = completed_at or datetime.now(
                    timezone.utc
                )
                update_values["error_message"] = None
            elif task_status is TaskStatus.FAILED:
                update_values["completed_at"] = None
            elif task_status in {TaskStatus.PROCESSING, TaskStatus.PENDING}:
                if completed_at is not None:
                    update_values["completed_at"] = completed_at
                else:
                    update_values.setdefault("completed_at", None)

            if "error" in additional_data or "error_message" in additional_data:
                error_text = str(
                    additional_data.get("error_message")
                    or additional_data.get("error")
                    or ""
                ).strip()
                if error_text:
                    update_values["error_message"] = error_text

            retry_count = _coerce_int(additional_data.get("retry_count"))
            if retry_count is not None:
                update_values["retry_count"] = retry_count

            stmt = (
                update(TaskModel)
                .where(TaskModel.id == task_uuid)
                .values(**update_values)
            )

            result = db.execute(stmt)

            if result.rowcount == 0:
                logger.warning("任务不存在，无法更新状态: %s", task_id)
            else:
                unused_keys = set(additional_data.keys()) - {
                    "started_at",
                    "completed_at",
                    "error",
                    "error_message",
                    "retry_count",
                    "result",
                    "execution_time",
                    "error_type",
                }
                if unused_keys:
                    logger.debug("额外状态字段未写入数据库，仅记录: %s", sorted(unused_keys))
                logger.debug("任务状态已更新: %s -> %s", task_id, update_values.get("status"))

    except SQLAlchemyError as exc:
        logger.error("更新任务状态失败 %s: %s", task_id, exc, exc_info=True)
        # 数据库更新失败不影响任务执行，只记录日志


@contextmanager
def _get_sync_session() -> Generator[Session, None, None]:
    """同步数据库会话上下文管理器 - 基于Context7最佳实践"""
    session = get_session_sync()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        session.close()


# 任务健康检查（注册方式）
def _analysis_health_check_typed() -> HealthCheckResponse:
    """
    分析任务健康检查

    用于监控系统检查分析任务的健康状态

    Returns:
        Dict: 健康状态报告
    """
    # 为保证Celery JSON序列化兼容，返回Pydantic模型的可序列化字典
    model = HealthCheckResponse(
        service="analysis_tasks",
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )
    return model


analysis_health_check = celery_app.task(
    name="analysis_tasks.health_check", queue="monitoring_queue"
)(_analysis_health_check_typed)

# 兼容导出：测试导入 analyze_product
analyze_product = analyze_product_task


# ========== prd04-05: 简化的死信队列和恢复机制 ==========


def _move_failed_tasks_to_dead_letter_typed() -> DeadLetterOperationResponse:
    """
    将重试失败的任务移至死信队列

    这个任务定期运行，查找状态为failed且retry_count达到最大值的任务，
    将其移至DEAD_LETTER状态。简化版实现，基于Celery最佳实践。

    Returns:
        处理结果统计
    """
    # get_db_session 已在模块级别修复
    from ..models.task import FailureCategory, TaskStatus

    logger.info("开始检查需要移至死信队列的任务")

    moved_count = 0
    processed_tasks = []

    try:
        with _get_sync_session() as db:
            # 查找状态为failed且重试次数已满的任务
            from sqlalchemy.sql.elements import ColumnElement

            failed_tasks = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.FAILED.value)
                .filter(TaskModel.retry_count >= 3)
                .limit(100)
                .all()
            )  # 批量处理，避免过载

            for task in failed_tasks:
                try:
                    # 移至死信队列
                    setattr(task, "status", TaskStatus.DEAD_LETTER.value)
                    setattr(task, "dead_letter_at", datetime.now(timezone.utc))

                    # 分析失败原因（简化版）
                    error_msg = task.error_message or "未知错误"
                    if (
                        "网络" in error_msg
                        or "连接" in error_msg
                        or "timeout" in error_msg.lower()
                    ):
                        setattr(
                            task,
                            "failure_category",
                            FailureCategory.NETWORK_ERROR.value,
                        )
                    elif "验证" in error_msg or "validation" in error_msg.lower():
                        setattr(
                            task,
                            "failure_category",
                            FailureCategory.DATA_VALIDATION_ERROR.value,
                        )
                    else:
                        setattr(
                            task, "failure_category", FailureCategory.SYSTEM_ERROR.value
                        )

                    processed_tasks.append(
                        {
                            "task_id": str(task.id),
                            "failure_category": task.failure_category,
                            "retry_count": task.retry_count,
                        }
                    )

                    moved_count += 1

                except Exception as e:
                    logger.error(f"移动任务到死信队列失败 {task.id}: {e}")

            # 提交所有更改
            if moved_count > 0:
                db.commit()
                logger.info(f"成功移动 {moved_count} 个任务到死信队列")

    except Exception as e:
        logger.error(f"死信队列处理异常: {e}")

    return DeadLetterOperationResponse(
        operation="move_to_dead_letter",
        moved_count=moved_count,
        processed_tasks=processed_tasks,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


move_failed_tasks_to_dead_letter = celery_app.task(
    name="analysis_tasks.move_to_dead_letter",
    queue="maintenance_queue",
    max_retries=1,
)(_move_failed_tasks_to_dead_letter_typed)


def _retry_dead_letter_task_typed(task_id: str) -> RetryTaskResponse:
    """
    手动重试死信队列中的任务

    简化实现：重置任务状态，让其重新进入正常处理流程。
    基于Context7最佳实践的最小可行实现。

    Args:
        task_id: 要重试的任务ID

    Returns:
        重试结果
    """
    logger.info(f"开始重试死信队列任务: {task_id}")

    from ..models.task import TaskStatus

    try:
        from uuid import UUID as UUIDType

        # 确保task_id是UUID类型
        task_uuid = UUIDType(task_id) if isinstance(task_id, str) else task_id

        with _get_sync_session() as db:
            # 查找死信队列中的任务
            from sqlalchemy.sql.elements import ColumnElement

            task = (
                db.query(TaskModel)
                .filter(
                    TaskModel.id == task_uuid,
                    TaskModel.status == TaskStatus.DEAD_LETTER.value,
                )
                .first()
            )

            if not task:
                return RetryTaskResponse(
                    success=False,
                    error=f"任务不存在或不在死信队列: {task_id}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            # 重置任务状态，给其新的机会
            setattr(task, "status", TaskStatus.PENDING.value)
            setattr(task, "retry_count", 0)  # 重置重试计数
            setattr(task, "error_message", None)
            setattr(task, "dead_letter_at", None)
            setattr(task, "last_retry_at", datetime.now(timezone.utc))

            db.commit()

            # 重新提交任务到队列
            cast(Any, analyze_product_task).delay(
                payload={"product_description": task.product_description},
                task_data={"task_id": str(task.id)},
            )

            logger.info(f"成功重试死信队列任务: {task_id}")

            return RetryTaskResponse(
                success=True,
                task_id=task_id,
                message="任务已重新提交处理",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    except Exception as e:
        logger.error(f"重试死信队列任务失败 {task_id}: {e}")
        return RetryTaskResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


retry_dead_letter_task = celery_app.task(
    name="analysis_tasks.retry_dead_letter",
    queue="maintenance_queue",
    max_retries=2,
)(_retry_dead_letter_task_typed)


def _get_dead_letter_statistics_typed() -> DeadLetterStatsResponse:
    """
    获取死信队列统计信息

    简化的监控功能，提供死信队列的基本统计数据。

    Returns:
        统计信息
    """
    from ..models.task import TaskStatus

    try:
        with _get_sync_session() as db:
            # 总数统计
            from sqlalchemy.sql.elements import ColumnElement

            total_dead_letters = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                .count()
            )

            # 按失败类型统计（如果有）
            category_stats = {}
            if total_dead_letters > 0:
                from sqlalchemy import func

                results = (
                    db.query(cast(Any, TaskModel.failure_category), func.count())
                    .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                    .group_by(TaskModel.failure_category)
                    .all()
                )

                category_stats = {
                    category or "unknown": count for category, count in results
                }

            # 最近的死信任务
            from sqlalchemy import desc

            recent_dead_letters = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                .filter(cast(Any, TaskModel.dead_letter_at).is_not(None))
                .order_by(cast(Any, TaskModel.dead_letter_at).desc())
                .limit(5)
                .all()
            )

            recent_tasks = [
                {
                    "task_id": str(task.id),
                    "failure_category": task.failure_category,
                    "dead_letter_at": (
                        task.dead_letter_at.isoformat() if task.dead_letter_at else None
                    ),
                    "retry_count": task.retry_count,
                }
                for task in recent_dead_letters
            ]

            return DeadLetterStatsResponse(
                total_dead_letters=total_dead_letters,
                by_category=category_stats,
                recent_tasks=recent_tasks,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    except Exception as e:
        logger.error(f"获取死信队列统计失败: {e}")
        return DeadLetterStatsResponse(
            total_dead_letters=0,
            by_category={},
            recent_tasks=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


get_dead_letter_statistics = celery_app.task(
    name="analysis_tasks.get_dead_letter_stats", queue="monitoring_queue"
)(_get_dead_letter_statistics_typed)
