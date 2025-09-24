"""Demo分析模拟器

用于在缺少后台任务处理器的环境下，模拟分析任务的进度与报告结果，确保
前端演示流程可用。
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field
from html import escape
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Type, TypeVar, cast

from pydantic import BaseModel, ValidationError

from ..core.config import get_settings
from ..core.types import JsonValue
from ..schemas.contracts.report_contract import (
    CompetitorInsight,
    ExecutiveSummary,
    InsightItem,
    MarketMetrics,
    OpportunityInsight,
    PainPointInsight,
    ReportData,
)
from ..schemas.task import TaskInfo, TaskStatus

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _DemoTaskState:
    task_id: str
    description: str
    created_at: datetime = field(default_factory=_utc_now)
    duration_seconds: float = 10.0
    report_id: str = field(init=False)
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        # 使用任务ID生成稳定的report_id，避免随机数导致的非确定行为
        digest = hashlib.sha1(self.task_id.encode("utf-8")).hexdigest()
        self.report_id = f"demo-{digest[:12]}"

    def progress(self, now: datetime) -> int:
        if self.completed_at is not None:
            return 100

        elapsed = (now - self.created_at).total_seconds()
        if elapsed <= 0:
            return 5

        ratio = min(elapsed / self.duration_seconds, 1.0)
        return max(5, min(100, int(ratio * 100)))

    def status(self, now: datetime) -> TaskStatus:
        if self.completed_at is not None:
            return TaskStatus.COMPLETED
        elapsed = (now - self.created_at).total_seconds()
        if elapsed >= self.duration_seconds:
            # 将完成时间固定在创建时间 + duration，避免多次调用写入不同时间
            self.completed_at = self.created_at + timedelta(
                seconds=self.duration_seconds
            )
            return TaskStatus.COMPLETED

        running_threshold = max(0.5, min(2.0, self.duration_seconds * 0.2))
        if elapsed >= running_threshold:
            return TaskStatus.RUNNING

        return TaskStatus.PENDING


def _build_demo_html_content(
    task_id: str,
    product_description: str,
    market_metrics: dict[str, JsonValue],
    pain_points: list[dict[str, JsonValue]],
    competitors: list[dict[str, JsonValue]],
    opportunities: list[dict[str, JsonValue]],
) -> str:
    pain_items = [
        f"<li><strong>{escape(item.get('description', ''))}</strong>"
        f" — 频次 {item.get('frequency', 0)}, 情感 {item.get('sentiment_score', 0.0)}</li>"
        for item in pain_points[:5]
    ] or ["<li>暂无数据</li>"]
    competitor_items = [
        f"<li><strong>{escape(item.get('name', ''))}</strong>"
        f" — 提及 {item.get('mention_count', 0)}, 情感 {item.get('sentiment_score', 0.0)}</li>"
        for item in competitors[:5]
    ] or ["<li>暂无数据</li>"]
    opportunity_items = [
        f"<li><strong>{escape(item.get('title', ''))}</strong>"
        f" — 相关度 {item.get('relevance_score', 0.0)}, 潜在用户 {item.get('estimated_demand', 0)}</li>"
        for item in opportunities[:5]
    ] or ["<li>暂无数据</li>"]

    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
        "<title>Reddit Signal Analysis Report (Demo)</title></head><body>",
        f"<h1>Demo 分析任务 {escape(task_id)}</h1>",
        f"<p><strong>产品描述:</strong> {escape(product_description[:512])}</p>",
        "<section><h2>市场指标</h2><ul>",
        f"<li>总提及量: {market_metrics.get('total_mentions', 0)}</li>",
        f"<li>情感得分: {market_metrics.get('sentiment_score', 0.0)}</li>",
        f"<li>互动率: {market_metrics.get('engagement_rate', 0.0)}</li>",
        f"<li>核心社区: {', '.join(map(escape, market_metrics.get('top_communities', [])[:5]))}</li>",
        "</ul></section>",
        "<section><h2>用户痛点</h2><ol>" + "".join(pain_items) + "</ol></section>",
        "<section><h2>竞争对手</h2><ol>" + "".join(competitor_items) + "</ol></section>",
        "<section><h2>市场机会</h2><ol>" + "".join(opportunity_items) + "</ol></section>",
        "</body></html>",
    ]
    return "".join(parts)


class DemoAnalysisSimulator:
    """内存级模拟器，保证演示流程在无Worker时也能跑通。"""

    def __init__(self) -> None:
        settings = get_settings()
        # 允许从Settings与环境变量双路径读取，环境变量覆盖配置
        enabled_cfg = settings.enable_demo_analysis_simulator
        force_only_cfg = settings.demo_simulator_force_only

        env_enabled = os.getenv("ENABLE_DEMO_ANALYSIS_SIMULATOR")
        env_force = os.getenv("DEMO_SIMULATOR_FORCE_ONLY")

        self._enabled = (
            (env_enabled.lower() != "false")
            if isinstance(env_enabled, str)
            else enabled_cfg
        )
        self._force_only = (
            (env_force.lower() == "true")
            if isinstance(env_force, str)
            else force_only_cfg
        )
        if self._force_only:
            self._enabled = True
        self._lock = threading.Lock()
        self._tasks: Dict[str, _DemoTaskState] = {}

        # 允许通过环境变量配置单个任务的模拟耗时（单位：秒），默认10秒
        # 使用保守解析，确保错误值不会影响运行
        duration_env = os.getenv("DEMO_SIMULATOR_DURATION_SECONDS")
        try:
            self._task_duration_seconds: float = (
                float(duration_env) if duration_env is not None else 10.0
            )
            if self._task_duration_seconds <= 0:
                self._task_duration_seconds = 10.0
        except (TypeError, ValueError):
            self._task_duration_seconds = 10.0

        logger.info(
            "DemoAnalysisSimulator 启动: enabled=%s, force_only=%s",
            self._enabled,
            self._force_only,
        )
        if self._force_only:
            logger.warning("纯模拟器模式已启用（DEMO_SIMULATOR_FORCE_ONLY=true），所有数据库操作将被绕过")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def force_only(self) -> bool:
        return self._enabled and self._force_only

    def register_task(self, task_id: str, description: str) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._tasks[task_id] = _DemoTaskState(
                task_id=task_id,
                description=description.strip(),
                duration_seconds=self._task_duration_seconds,
            )
        logger.info("[demo] 已注册任务: %s | 当前总数=%d", task_id, len(self._tasks))

    def enrich_task_info(
        self, task_id: str, base: Optional[TaskInfo]
    ) -> Optional[TaskInfo]:
        if not self._enabled:
            return base
        with self._lock:
            state = self._tasks.get(task_id)
        if state is None:
            logger.info("[demo] 未找到任务状态: %s (可能尚未注册)", task_id)
            return base

        now = _utc_now()

        if base and base.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            # 数据库已有终态，直接返回
            return base

        status = state.status(now)
        progress = state.progress(now)
        created_at = (
            base.created_at
            if base is not None
            else state.created_at.strftime(ISO_FORMAT)
        )
        estimated_completion: Optional[str]
        if status == TaskStatus.COMPLETED:
            completed_at = state.completed_at or now
            estimated_completion = completed_at.strftime(ISO_FORMAT)
        else:
            eta = state.created_at + timedelta(seconds=state.duration_seconds)
            estimated_completion = eta.strftime(ISO_FORMAT)
            completed_at = None

        started_at: Optional[str]
        if status == TaskStatus.PENDING:
            started_at = None
        else:
            started_at = state.created_at.strftime(ISO_FORMAT)
        completed_at_str = completed_at.strftime(ISO_FORMAT) if completed_at else None

        updated_info = TaskInfo(
            task_id=task_id,
            status=status,
            progress=progress,
            created_at=created_at,
            updated_at=now.strftime(ISO_FORMAT),
            started_at=started_at,
            completed_at=completed_at_str,
            estimated_completion=estimated_completion,
            error_message=None,
            report_id=state.report_id if status == TaskStatus.COMPLETED else None,
        )

        # 若数据库已有信息，保持更高的进度/状态
        if base:
            if base.progress > updated_info.progress:
                updated_info.progress = base.progress
            if base.status == TaskStatus.RUNNING and status == TaskStatus.PENDING:
                updated_info.status = base.status
            if base.error_message:
                updated_info.error_message = base.error_message
            if base.estimated_completion:
                updated_info.estimated_completion = base.estimated_completion
            if base.report_id:
                updated_info.report_id = base.report_id
            if base.started_at:
                updated_info.started_at = base.started_at
            if base.completed_at:
                updated_info.completed_at = base.completed_at
        logger.info(
            "[demo] 生成任务状态: %s | status=%s progress=%d",
            task_id,
            updated_info.status.value,
            updated_info.progress,
        )
        return updated_info

    def get_report(self, task_id: str) -> Optional[ReportData]:
        if not self._enabled:
            return None
        with self._lock:
            state = self._tasks.get(task_id)
        if state is None:
            return None

        now = _utc_now()
        if state.status(now) != TaskStatus.COMPLETED:
            return None

        seed = int(hashlib.sha1(task_id.encode("utf-8")).hexdigest(), 16)
        topic_keywords = ["社区运营", "产品反馈", "增长策略", "留存改进", "目标用户"]
        trending = [topic_keywords[(seed + i) % len(topic_keywords)] for i in range(3)]
        top_communities: list[dict[str, JsonValue]] = [
            {
                "name": "r/startups",
                "members": 1_200_000,
                "relevance": 0.89,
            },
            {
                "name": "r/entrepreneur",
                "members": 980_000,
                "relevance": 0.76,
            },
            {
                "name": "r/SaaS",
                "members": 450_000,
                "relevance": 0.82,
            },
        ]
        personas: list[Dict[str, JsonValue]] = [
            {
                "name": "早期采用者",
                "goals": cast(JsonValue, ["寻找创新工具", "效率提升"]),
                "pain_points": cast(JsonValue, ["缺少整合视图", "难以追踪趋势"]),
            },
            {
                "name": "市场经理",
                "goals": cast(JsonValue, ["获取竞品动态", "洞察用户反馈"]),
                "pain_points": cast(JsonValue, ["数据来源分散", "缺乏量化指标"]),
            },
        ]

        insights = [
            InsightItem(
                title="用户痛点集中在上手成本",
                content="大量Reddit讨论集中在产品初始设置复杂、缺乏引导，需要提供预设模板和步骤化流程。",
                confidence=0.78,
                source_count=42,
                tags=["onboarding", "ux"],
            ),
            InsightItem(
                title="自定义自动化需求强烈",
                content="高频出现对自动监控与关键词报警的需求，建议提供工作流编辑器，用于跟踪竞争对手动态。",
                confidence=0.72,
                source_count=31,
                tags=["automation", "alerts"],
            ),
            InsightItem(
                title="与Slack/Notion集成可提升留存",
                content="团队协作型用户希望结果能同步到Slack与Notion，便于跨部门共享，建议提供一键集成。",
                confidence=0.69,
                source_count=27,
                tags=["integration", "retention"],
            ),
        ]

        total_posts = 180 + seed % 40
        total_comments = 420 + seed % 80
        total_mentions = total_posts + total_comments

        pain_points_data: list[dict[str, JsonValue]] = [
            {
                "description": "初始设置步骤冗长且缺乏可视化引导，导致团队上手缓慢",
                "sentiment_score": -0.62,
                "frequency": 48,
                "confidence": 0.82,
                "severity": "high",
                "categories": ["onboarding", "usability"],
                "example_posts": [
                    {
                        "post_id": "demo-pp-1",
                        "community": "r/startups",
                        "content_snippet": "Setting up the dashboard took us an entire afternoon...",
                        "upvotes": 156,
                    }
                ],
                "tags": ["setup", "guidance"],
            },
            {
                "description": "缺少跨社区的统一监控面板，团队需要在多个工具之间切换",
                "sentiment_score": -0.44,
                "frequency": 31,
                "confidence": 0.76,
                "severity": "medium",
                "categories": ["monitoring", "workflow"],
                "example_posts": [
                    {
                        "post_id": "demo-pp-2",
                        "community": "r/marketing",
                        "content_snippet": "We still have to keep a spreadsheet to track mentions...",
                    }
                ],
                "tags": ["dashboard", "tracking"],
            },
        ]

        competitors_data: list[dict[str, JsonValue]] = [
            {
                "name": "Product Hunt",
                "mention_count": 124,
                "sentiment_score": 0.32,
                "strengths": ["社区热度高", "上新速度快"],
                "weaknesses": ["缺乏深度分析", "自动化能力有限"],
                "market_position": "leader",
                "summary": "侧重发现与讨论，但对持续跟踪支持不足",
                "price_mentions": ["免费为主"],
                "share_of_voice": 0.44,
                "website": "https://www.producthunt.com",
            },
            {
                "name": "Crayon",
                "mention_count": 86,
                "sentiment_score": 0.18,
                "strengths": ["竞品监控能力强", "企业方案成熟"],
                "weaknesses": ["价格昂贵", "学习曲线陡峭"],
                "market_position": "challenger",
                "summary": "B2B 覆盖扎实，但无法快速响应新兴社区动态",
                "price_mentions": ["$99+/month"],
                "share_of_voice": 0.30,
                "website": "https://www.crayon.co",
            },
        ]

        opportunities_data: list[dict[str, JsonValue]] = [
            {
                "title": "自动化信号监控与提醒中心",
                "description": "构建跨社区的实时监控中枢，提供关键词报警和竞品信号联动分析。",
                "market_size_indicator": "large",
                "urgency_score": 0.82,
                "feasibility_score": 0.64,
                "target_communities": ["r/startups", "r/marketing", "r/saas"],
                "related_keywords": ["automation", "alert", "dashboard"],
                "estimated_demand": 2100,
                "potential_score": 0.78,
                "timeframe": "3-6 months",
            },
            {
                "title": "Slack / Notion 深度集成",
                "description": "提供原生的协作集成能力，让分析结果直接流入团队常用工具。",
                "market_size_indicator": "medium",
                "urgency_score": 0.68,
                "feasibility_score": 0.74,
                "target_communities": ["r/productivity", "r/notion"],
                "related_keywords": ["integration", "collaboration"],
                "estimated_demand": 1450,
                "potential_score": 0.72,
                "timeframe": "6-9 months",
            },
        ]

        market_metrics_data: dict[str, JsonValue] = {
            "total_mentions": total_mentions,
            "sentiment_score": 0.23,
            "top_communities": [c["name"] for c in top_communities],
            "trending_keywords": trending,
            "engagement_rate": 0.67,
            "sample_size": total_posts,
        }

        html_content = _build_demo_html_content(
            task_id,
            state.description,
            market_metrics_data,
            pain_points_data,
            competitors_data,
            opportunities_data,
        )

        executive_summary_data: dict[str, JsonValue] = {
            "headline": "Reddit 用户聚焦启动效率与自动化能力",
            "total_communities": len(top_communities),
            "key_insights": len(insights),
            "top_opportunity": opportunities_data[0]["title"],
            "confidence_score": 0.74,
            "summary_points": [
                "上手成本是用户最直接的痛点，需要模板化 onboarding",
                "竞品在多渠道整合上具有优势，但缺乏自动化能力",
                "自动化提醒与协作集成是短期内最具价值的方向",
            ],
        }

        pain_points = _validate_list(pain_points_data, PainPointInsight)
        competitors = _validate_list(competitors_data, CompetitorInsight)
        opportunities = _validate_list(opportunities_data, OpportunityInsight)

        try:
            market_metrics = MarketMetrics.model_validate(market_metrics_data)
        except ValidationError:
            market_metrics = MarketMetrics()

        try:
            executive_summary = ExecutiveSummary.model_validate(executive_summary_data)
        except ValidationError:
            executive_summary = ExecutiveSummary()

        report = ReportData(
            task_id=task_id,
            query=state.description[:160],
            total_posts=total_posts,
            total_comments=total_comments,
            analysis_duration=state.duration_seconds,
            key_insights=insights,
            sentiment_summary={"positive": 0.46, "neutral": 0.31, "negative": 0.23},
            trending_topics=trending,
            user_personas=personas,
            generated_at=now.strftime(ISO_FORMAT),
            data_freshness="实时生成",
            executive_summary=executive_summary,
            market_metrics=market_metrics,
            pain_points=pain_points,
            competitors=competitors,
            opportunities=opportunities,
            html_content=html_content,
        )
        return report


# 单例实例
_demo_simulator = DemoAnalysisSimulator()


def demo_analysis_simulator() -> DemoAnalysisSimulator:
    return _demo_simulator


TModel = TypeVar("TModel", bound=BaseModel)


def _validate_list(
    values: list[dict[str, JsonValue]], model: Type[TModel]
) -> list[TModel]:
    validated: list[TModel] = []
    for item in values:
        try:
            validated.append(model.model_validate(item))
        except ValidationError:
            continue
    return validated
