"""
Reddit Signal Scanner - 报告格式化服务

Linus原则："数据结构决定一切"
- 统一的报告响应格式
- 消除特殊情况处理
- 清晰的数据转换逻辑
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Type, TypeVar, cast
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.analysis import Analysis
from ..models.report import Report
from ..models.task import Task
from pydantic import BaseModel, ValidationError

from ..schemas.contracts.report_contract import (
    CompetitorInsight,
    ExecutiveSummary,
    InsightItem,
    MarketMetrics,
    OpportunityInsight,
    PainPointInsight,
    ReportData,
    ReportFormat,
)


class ReportFormatterService:
    """报告格式化服务 - 统一数据处理"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_complete_report(self, task_id: str) -> dict[str, Any]:
        """
        获取完整的分析报告

        Args:
            task_id: 任务ID字符串

        Returns:
            Dict: 标准化的报告数据结构

        Raises:
            ValueError: 参数验证失败
            RuntimeError: 数据库查询失败
        """
        # 参数验证
        try:
            task_uuid = UUID(task_id)
        except ValueError as e:
            raise ValueError(f"无效的任务ID格式: {task_id}") from e

        try:
            # 执行联表查询 - 一次性获取所有数据
            result = (
                self.db.query(Analysis, Report, Task)
                .join(Report, Analysis.id == Report.analysis_id)
                .join(Task, Analysis.task_id == Task.id)
                .filter(Task.id == task_uuid, Report.status == "active")
                .first()
            )

            if not result:
                return self._create_empty_response(task_id, "未找到分析结果")

            analysis, report, task = result

            # 格式化完整报告
            return self._format_complete_report(analysis, report, task)

        except SQLAlchemyError as e:
            raise RuntimeError(f"数据库查询失败: {str(e)}") from e

    def get_summary_report(self, task_id: str) -> dict[str, Any]:
        """获取摘要版报告"""
        complete_report: dict[str, Any] = self.get_complete_report(task_id)

        # 只保留核心摘要信息
        if complete_report.get("success"):
            data: dict[str, Any] = cast(dict[str, Any], complete_report["data"])
            data["key_insights"] = data["key_insights"][:1]  # 只保留第一个洞察
            data["user_personas"] = []  # 移除用户画像
            complete_report["message"] = "摘要报告获取成功"

        return complete_report

    def get_insights_only(self, task_id: str) -> dict[str, Any]:
        """仅获取关键洞察"""
        complete_report: dict[str, Any] = self.get_complete_report(task_id)

        if complete_report.get("success"):
            data: dict[str, Any] = cast(dict[str, Any], complete_report["data"])
            # 只保留洞察相关字段
            insights_data = {
                "task_id": data["task_id"],
                "query": data["query"],
                "key_insights": data["key_insights"],
                "generated_at": data["generated_at"],
                "confidence_score": data.get("confidence_score", 0.0),
            }
            complete_report["data"] = insights_data
            complete_report["message"] = "关键洞察获取成功"

        return complete_report

    def _format_complete_report(
        self, analysis: Analysis, report: Report, task: Task
    ) -> dict[str, Any]:
        """格式化完整报告数据"""

        # 提取JSONB数据并显式类型化，避免 Column/Any 混用
        insights_data: dict[str, Any] = cast(dict[str, Any], analysis.insights or {})
        sources_data: dict[str, Any] = cast(dict[str, Any], analysis.sources or {})

        # 构建标准化响应
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        key_insights = self._format_insights(insights_data)
        sentiment_summary = self._format_sentiment(
            cast(Mapping[str, Any], insights_data)
        )
        trending_topics = self._format_topics(cast(Mapping[str, Any], insights_data))
        user_personas = self._format_personas(cast(Mapping[str, Any], insights_data))

        # 兜底机制：确保5个关键字段始终存在且类型正确
        pain_points_raw = insights_data.get("pain_points", [])
        competitors_raw = insights_data.get("competitors", [])
        opportunities_raw = insights_data.get("opportunities", [])

        pain_points = self._enrich_pain_points(
            self._normalize_list_of_dicts(pain_points_raw)
        )
        competitors = self._enrich_competitors(
            self._normalize_list_of_dicts(competitors_raw)
        )
        opportunities = self._enrich_opportunities(
            self._normalize_list_of_dicts(opportunities_raw)
        )

        # 确保即使enrichment失败，也返回空数组而不是None
        pain_points = pain_points if isinstance(pain_points, list) else []
        competitors = competitors if isinstance(competitors, list) else []
        opportunities = opportunities if isinstance(opportunities, list) else []

        # 兜底机制：确保executive_summary字段结构完整
        executive_summary_raw = insights_data.get("executive_summary")
        executive_summary = self._normalize_mapping(executive_summary_raw)

        top_opportunity_title: Optional[str] = None
        if opportunities:
            first_opportunity = opportunities[0]
            top_opportunity_title = cast(
                Optional[str],
                first_opportunity.get("title") or first_opportunity.get("description"),
            )

        community_names = self._extract_community_names(sources_data.get("communities"))

        # 兜底机制：无论executive_summary是否存在，都确保字段完整性
        if not executive_summary or not isinstance(executive_summary, dict):
            summary_points = [
                str(insight.get("title"))
                for insight in key_insights
                if insight.get("title")
            ][:3]
            executive_summary = {
                "headline": None,
                "total_communities": len(community_names),
                "key_insights": len(key_insights),
                "top_opportunity": top_opportunity_title,
                "confidence_score": float(analysis.confidence_score),
                "summary_points": summary_points,
            }
        else:
            # 确保所有必需字段都存在
            executive_summary.setdefault("headline", None)
            executive_summary.setdefault("total_communities", len(community_names))
            executive_summary.setdefault("key_insights", len(key_insights))
            executive_summary.setdefault("top_opportunity", top_opportunity_title)
            executive_summary.setdefault(
                "confidence_score", float(analysis.confidence_score)
            )
            executive_summary.setdefault("summary_points", [])

            # 更新动态字段
            if top_opportunity_title and not executive_summary.get("top_opportunity"):
                executive_summary["top_opportunity"] = top_opportunity_title
            if executive_summary.get("confidence_score") is None:
                executive_summary["confidence_score"] = float(analysis.confidence_score)
            if not isinstance(executive_summary.get("summary_points"), list):
                executive_summary["summary_points"] = []

        total_posts = int(sources_data.get("posts_analyzed", 0) or 0)
        total_comments = int(
            sources_data.get("comments_count", sources_data.get("comments_analyzed", 0))
            or 0
        )

        # 兜底机制：确保market_metrics字段结构完整且类型正确
        safe_community_names = (
            community_names if isinstance(community_names, list) else []
        )
        safe_trending_topics = (
            trending_topics if isinstance(trending_topics, list) else []
        )

        market_metrics: dict[str, Any] = {
            "total_mentions": total_posts + total_comments,
            "sentiment_score": self._clamp(
                float(sentiment_summary.get("positive", 0.0))
                - float(sentiment_summary.get("negative", 0.0)),
                -1.0,
                1.0,
            ),
            "top_communities": safe_community_names,
            "trending_keywords": safe_trending_topics,
            # 确保必需字段存在
            "engagement_rate": 0.0,
            "sample_size": total_posts,
        }

        # 可选字段的安全设置
        if sources_data.get("engagement_rate") is not None:
            try:
                market_metrics["engagement_rate"] = float(
                    sources_data["engagement_rate"]
                )
            except (ValueError, TypeError):
                market_metrics["engagement_rate"] = 0.0

        report_data = {
            "task_id": str(task.id),
            "query": self._get_effective_query(task),
            "total_posts": total_posts,
            "total_comments": total_comments,
            "analysis_duration": self._calculate_duration(
                task.created_at, cast(datetime, analysis.created_at)
            ),
            "confidence_score": float(analysis.confidence_score),
            # 核心洞察
            "key_insights": key_insights,
            # 情感分析摘要
            "sentiment_summary": sentiment_summary,
            # 热门话题
            "trending_topics": trending_topics,
            # 用户画像
            "user_personas": user_personas,
            # 结构化洞察
            "executive_summary": executive_summary,
            "market_metrics": market_metrics,
            "pain_points": pain_points,
            "competitors": competitors,
            "opportunities": opportunities,
            # 元数据
            "generated_at": current_time,
            "data_freshness": self._calculate_freshness(
                cast(datetime, analysis.created_at)
            ),
            "html_content": report.html_content,
            "data_coverage": {
                "communities": len(sources_data.get("communities", [])),
                "cache_hit_rate": sources_data.get("cache_hit_rate", 0.0),
                "analysis_version": analysis.analysis_version,
            },
        }

        return {
            "success": True,
            "message": "分析报告获取成功",
            "timestamp": current_time,
            "data": report_data,
        }

    @staticmethod
    def _normalize_mapping(value: Any) -> dict[str, Any]:
        """尽力将对象转换为字典。"""

        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)

        dump_method = getattr(value, "model_dump", None)
        if callable(dump_method):
            dumped = dump_method()
            if isinstance(dumped, Mapping):
                return dict(dumped)

        return {}

    @staticmethod
    def _normalize_list_of_dicts(value: Any) -> list[dict[str, Any]]:
        """确保洞察结构始终以字典列表返回。"""

        if value is None:
            return []
        if isinstance(value, list):
            normalized: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, Mapping):
                    normalized.append(dict(item))
                    continue

                dump_method = getattr(item, "model_dump", None)
                if callable(dump_method):
                    dumped = dump_method()
                    if isinstance(dumped, Mapping):
                        normalized.append(dict(dumped))
            return normalized

        if isinstance(value, Mapping):
            return [dict(value)]

        dump_method = getattr(value, "model_dump", None)
        if callable(dump_method):
            dumped = dump_method()
            if isinstance(dumped, Mapping):
                return [dict(dumped)]

        return []

    def _enrich_pain_points(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """补全痛点洞察的缺失字段。"""

        enriched: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            description = str(
                item.get("description") or item.get("title") or ""
            ).strip()
            if not description:
                continue

            sentiment = self._safe_float(item.get("sentiment_score"))
            frequency = self._safe_int(item.get("frequency"))

            item["description"] = description
            item["sentiment_score"] = sentiment
            item["frequency"] = frequency
            item.setdefault(
                "confidence", self._clamp(abs(sentiment) * 0.5 + 0.55, 0.0, 1.0)
            )
            item.setdefault(
                "severity",
                self._infer_pain_point_severity(sentiment, frequency),
            )

            example_posts = item.get("example_posts")
            needs_conversion = False
            if not isinstance(example_posts, list) or not example_posts:
                needs_conversion = True
            else:
                for raw_example in example_posts:
                    if not isinstance(raw_example, Mapping):
                        needs_conversion = True
                        break
            if needs_conversion:
                examples = self._convert_evidence_posts(
                    item.get("evidence_posts") or example_posts, index
                )
                item["example_posts"] = examples if examples else []

            if "tags" not in item:
                tags = item.get("tags") or item.get("categories") or []
                item["tags"] = [str(tag) for tag in tags][:5]

            enriched.append(item)

        return enriched

    def _convert_evidence_posts(
        self, evidence: Any, offset: int
    ) -> list[dict[str, Any]]:
        """将证据帖子转换为 PainPointExample 兼容格式。"""

        if not isinstance(evidence, list):
            return []

        examples: list[dict[str, Any]] = []
        for idx, raw in enumerate(evidence, start=1):
            if isinstance(raw, Mapping):
                post_id = str(
                    raw.get("post_id") or raw.get("id") or f"ref-{offset+1}-{idx}"
                )
                snippet = raw.get("content_snippet") or raw.get("content")
                snippet = snippet or raw.get("title")

                example: dict[str, Any] = {"post_id": post_id}
                community = raw.get("community") or raw.get("subreddit")
                if isinstance(community, str):
                    example["community"] = community
                permalink = raw.get("permalink")
                if isinstance(permalink, str):
                    example["permalink"] = permalink
                if isinstance(snippet, str):
                    example["content_snippet"] = snippet[:140]
                upvotes = self._safe_int(raw.get("upvotes"))
                if upvotes > 0:
                    example["upvotes"] = upvotes
                examples.append(example)
                continue

            if isinstance(raw, str):
                examples.append(
                    {
                        "post_id": f"ref-{offset+1}-{idx}",
                        "content_snippet": raw[:140],
                    }
                )

        return examples[:5]

    @staticmethod
    def _infer_pain_point_severity(sentiment: float, frequency: int) -> str:
        if frequency >= 50 or sentiment <= -0.6:
            return "high"
        if frequency >= 20 or sentiment <= -0.3:
            return "medium"
        return "low"

    def _enrich_competitors(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """补全竞品洞察，确保声量和总结信息。"""

        total_mentions = sum(
            max(self._safe_int(item.get("mention_count")), 0) for item in items
        )

        enriched: list[dict[str, Any]] = []
        for item in items:
            name = str(item.get("name") or "未知竞品")
            mention_count = max(self._safe_int(item.get("mention_count")), 0)
            sentiment = self._safe_float(item.get("sentiment_score"))

            item["name"] = name
            item["mention_count"] = mention_count
            item["sentiment_score"] = sentiment
            item.setdefault("market_position", item.get("market_position", "unknown"))
            item.setdefault(
                "strengths", [str(s) for s in item.get("strengths", [])][:5]
            )
            item.setdefault(
                "weaknesses", [str(w) for w in item.get("weaknesses", [])][:5]
            )
            item.setdefault(
                "price_mentions",
                [str(p) for p in item.get("price_mentions", [])][:5],
            )

            if total_mentions > 0 and "share_of_voice" not in item:
                item["share_of_voice"] = round(mention_count / total_mentions, 4)

            if "summary" not in item:
                item["summary"] = self._build_competitor_summary(
                    name,
                    sentiment,
                    item.get("strengths", []),
                    item.get("weaknesses", []),
                    item.get("market_position", "unknown"),
                )

            enriched.append(item)

        return enriched

    @staticmethod
    def _build_competitor_summary(
        name: str,
        sentiment: float,
        strengths: list[str],
        weaknesses: list[str],
        position: str,
    ) -> str:
        sentiment_label = (
            "正面" if sentiment > 0.2 else "负面" if sentiment < -0.2 else "褒贬不一"
        )
        strength_text = ", ".join(strengths[:2]) or "优势待确认"
        weakness_text = ", ".join(weaknesses[:1]) or "弱项待确认"
        return (
            f"{name} 被视为{sentiment_label}，定位 {position}，"
            f"优势包括 {strength_text}，需关注 {weakness_text}"
        )

    def _enrich_opportunities(
        self, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """补全机会洞察的默认字段。"""

        enriched: list[dict[str, Any]] = []
        for item in items:
            title = str(item.get("title") or item.get("description") or "")
            description = str(item.get("description") or title)
            urgency = self._clamp(self._safe_float(item.get("urgency_score")), 0.0, 1.0)
            feasibility = self._clamp(
                self._safe_float(item.get("feasibility_score")), 0.0, 1.0
            )

            item["title"] = title or "待评估机会"
            item["description"] = description
            item.setdefault("market_size_indicator", "unknown")
            item["urgency_score"] = urgency
            item["feasibility_score"] = feasibility
            item.setdefault(
                "target_communities",
                [str(c) for c in item.get("target_communities", [])][:6],
            )
            item.setdefault(
                "related_keywords",
                [str(k) for k in item.get("related_keywords", [])][:10],
            )
            if "potential_score" not in item:
                potential = urgency * 0.6 + feasibility * 0.4
                item["potential_score"] = round(self._clamp(potential, 0.0, 1.0), 2)

            enriched.append(item)

        return enriched

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _extract_community_names(self, raw: Any) -> list[str]:
        """从任意结构中提取社区名称列表。"""

        if raw is None:
            return []
        if isinstance(raw, list):
            names: list[str] = []
            for entry in raw:
                if isinstance(entry, str):
                    names.append(entry)
                elif isinstance(entry, Mapping):
                    candidate = entry.get("name") or entry.get("subreddit_name")
                    if isinstance(candidate, str):
                        names.append(candidate)
            return names[:10]
        if isinstance(raw, Mapping):
            candidate = raw.get("name") or raw.get("subreddit_name")
            if isinstance(candidate, str):
                return [candidate]
        return []

    def _format_insights(
        self, insights_data: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """格式化关键洞察"""
        formatted_insights: list[dict[str, Any]] = []

        # 痛点洞察
        pain_points = insights_data.get("pain_points", [])
        if pain_points:
            top_pain = pain_points[0] if isinstance(pain_points, list) else pain_points
            formatted_insights.append(
                {
                    "title": "核心用户痛点",
                    "content": top_pain.get("description", "用户痛点分析中..."),
                    "confidence": top_pain.get("confidence", 0.7),
                    "source_count": top_pain.get("mentions", 0),
                    "tags": ["痛点分析", "用户需求"],
                }
            )

        # 竞品洞察
        competitors = insights_data.get("competitors", [])
        if competitors:
            top_competitor = (
                competitors[0] if isinstance(competitors, list) else competitors
            )
            formatted_insights.append(
                {
                    "title": "竞品分析洞察",
                    "content": f"主要竞品: {top_competitor.get('name', '未知')}, 用户评价关注点在功能和价格方面。",
                    "confidence": 0.8,
                    "source_count": top_competitor.get("mentions", 0),
                    "tags": ["竞品分析", "市场对比"],
                }
            )

        # 机会洞察
        opportunities = insights_data.get("opportunities", [])
        if opportunities:
            top_opportunity = (
                opportunities[0] if isinstance(opportunities, list) else opportunities
            )
            formatted_insights.append(
                {
                    "title": "市场机会识别",
                    "content": top_opportunity.get("description", "市场机会分析中..."),
                    "confidence": top_opportunity.get("relevance_score", 0.6),
                    "source_count": top_opportunity.get("potential_users", 0),
                    "tags": ["市场机会", "商业价值"],
                }
            )

        return formatted_insights

    def _format_sentiment(self, insights_data: Mapping[str, Any]) -> dict[str, float]:
        """格式化情感分析"""
        sentiment = cast(Mapping[str, Any], insights_data.get("sentiment_summary", {}))

        # 提供默认值确保数据一致性
        return {
            "positive": sentiment.get("positive", 0.5),
            "neutral": sentiment.get("neutral", 0.3),
            "negative": sentiment.get("negative", 0.2),
        }

    def _format_topics(self, insights_data: Mapping[str, Any]) -> List[str]:
        """格式化热门话题"""
        topics_any = insights_data.get("trending_topics", [])
        if not topics_any:
            return ["用户体验讨论", "功能需求反馈", "价格对比分析", "替代方案探讨"]
        topics_list = list(map(str, cast(List[Any], topics_any)))
        return topics_list[:5]  # 最多返回5个话题

    def _format_personas(
        self, insights_data: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """格式化用户画像"""
        personas_any = insights_data.get("user_personas", [])

        if not personas_any:
            # 提供默认用户画像
            return [
                {
                    "name": "技术决策者",
                    "percentage": 40,
                    "characteristics": ["关注功能特性", "比较多个方案", "影响购买决策"],
                },
                {
                    "name": "终端用户",
                    "percentage": 60,
                    "characteristics": ["重视用户体验", "价格敏感", "依赖社区推荐"],
                },
            ]

        # 尽力转换为字典列表
        personas_list = cast(List[dict[str, Any]], personas_any)
        return personas_list

    def _calculate_duration(self, start_time: datetime, end_time: datetime) -> float:
        """计算分析耗时（秒）"""
        if not start_time or not end_time:
            return 0.0

        delta = end_time - start_time
        return round(delta.total_seconds(), 2)

    def _calculate_freshness(self, analysis_time: datetime) -> str:
        """计算数据新鲜度"""
        if not analysis_time:
            return "未知"

        now = datetime.now(timezone.utc)
        # 确保 analysis_time 有时区信息
        if analysis_time.tzinfo is None:
            analysis_time = analysis_time.replace(tzinfo=timezone.utc)

        delta = now - analysis_time
        hours = delta.total_seconds() / 3600

        if hours < 1:
            return "1小时内"
        elif hours < 24:
            return f"{int(hours)}小时内"
        else:
            return f"{int(hours/24)}天内"

    def _get_effective_query(self, task: Task) -> str:
        """
        获取有效的查询描述

        Args:
            task: 任务模型实例

        Returns:
            str: 适合显示的查询描述（最大100字符）
        """
        if not task.product_description:
            return "未指定查询"

        # 取前100个字符作为查询摘要
        desc = str(task.product_description)
        if len(desc) <= 100:
            return desc
        else:
            return desc[:97] + "..."

    def _create_empty_response(self, task_id: str, message: str) -> dict[str, Any]:
        """创建空响应"""
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            "success": False,
            "message": message,
            "timestamp": current_time,
            "data": {
                "task_id": task_id,
                "query": "",
                "total_posts": 0,
                "total_comments": 0,
                "analysis_duration": 0.0,
                "confidence_score": 0.0,
                "key_insights": [],
                "sentiment_summary": {"positive": 0.0, "neutral": 0.0, "negative": 0.0},
                "trending_topics": [],
                "user_personas": [],
                "executive_summary": {
                    "headline": None,
                    "total_communities": 0,
                    "key_insights": 0,
                    "top_opportunity": None,
                    "confidence_score": 0.0,
                    "summary_points": [],
                },
                "market_metrics": {
                    "total_mentions": 0,
                    "sentiment_score": 0.0,
                    "top_communities": [],
                    "trending_keywords": [],
                },
                "pain_points": [],
                "competitors": [],
                "opportunities": [],
                "generated_at": current_time,
                "data_freshness": "无数据",
            },
        }


# ===== 便利函数 =====


def get_formatted_report(
    db: Session, task_id: str, format_type: str = "full"
) -> ReportData:
    """
    获取格式化报告的便利函数

    Args:
        db: 数据库会话
        task_id: 任务ID
        format_type: 格式类型 (full/summary/insights)

    Returns:
        ReportData: 结构化的报告数据
    """
    service = ReportFormatterService(db)

    raw: dict[str, Any]
    if format_type == ReportFormat.SUMMARY.value:
        raw = service.get_summary_report(task_id)
    elif format_type == ReportFormat.INSIGHTS.value:
        raw = service.get_insights_only(task_id)
    else:
        raw = service.get_complete_report(task_id)

    # 容错：失败则抛出 404，由上层捕获
    if not raw.get("success"):
        raise LookupError(raw.get("message", "未找到分析报告"))
    data: dict[str, Any] = cast(dict[str, Any], raw.get("data", {}))

    insights: List[InsightItem] = []
    for it in data.get("key_insights") or []:
        try:
            insights.append(
                InsightItem(
                    title=str(it.get("title", "")),
                    content=str(it.get("content", "")),
                    confidence=float(it.get("confidence", 0.0)),
                    source_count=int(it.get("source_count", 0)),
                    tags=list(it.get("tags", []) or []),
                )
            )
        except (TypeError, ValueError, KeyError):
            continue

    executive_summary = _coerce_executive_summary(data.get("executive_summary"))
    market_metrics = _coerce_market_metrics(data.get("market_metrics"))
    pain_points = _coerce_pain_points(data.get("pain_points"))
    competitors = _coerce_competitors(data.get("competitors"))
    opportunities = _coerce_opportunities(data.get("opportunities"))

    return ReportData(
        task_id=str(data.get("task_id", task_id)),
        query=str(data.get("query", "")),
        total_posts=int(data.get("total_posts", 0)),
        total_comments=int(data.get("total_comments", 0)),
        analysis_duration=float(data.get("analysis_duration", 0.0)),
        confidence_score=float(data.get("confidence_score", 0.0)),
        key_insights=insights,
        sentiment_summary=dict(data.get("sentiment_summary", {})),
        trending_topics=list(data.get("trending_topics", []) or []),
        user_personas=list(data.get("user_personas", []) or []),
        generated_at=str(data.get("generated_at", raw.get("timestamp", ""))),
        data_freshness=str(data.get("data_freshness", "unknown")),
        html_content=data.get("html_content"),
        market_metrics=market_metrics,
        pain_points=pain_points,
        competitors=competitors,
        opportunities=opportunities,
        data_coverage=data.get("data_coverage"),
    )


def _coerce_executive_summary(raw: Any) -> ExecutiveSummary:
    """兜底机制：确保executive_summary字段结构正确"""
    if isinstance(raw, ExecutiveSummary):
        return raw
    try:
        return ExecutiveSummary.model_validate(raw or {})
    except ValidationError:
        return ExecutiveSummary()


def _coerce_market_metrics(raw: Any) -> MarketMetrics:
    """兜底机制：确保market_metrics字段结构正确"""
    if isinstance(raw, MarketMetrics):
        return raw
    try:
        return MarketMetrics.model_validate(raw or {})
    except ValidationError:
        return MarketMetrics()


def _coerce_pain_points(raw: Any) -> list[PainPointInsight]:
    """兜底机制：确保pain_points字段为列表类型"""
    return _coerce_list(raw, PainPointInsight)


def _coerce_competitors(raw: Any) -> list[CompetitorInsight]:
    """兜底机制：确保competitors字段为列表类型"""
    return _coerce_list(raw, CompetitorInsight)


def _coerce_opportunities(raw: Any) -> list[OpportunityInsight]:
    """兜底机制：确保opportunities字段为列表类型"""
    return _coerce_list(raw, OpportunityInsight)


TModel = TypeVar("TModel", bound=BaseModel)


def _coerce_list(raw: Any, model: Type[TModel]) -> list[TModel]:
    if isinstance(raw, list):
        result: list[TModel] = []
        for item in raw:
            if isinstance(item, model):
                result.append(item)
                continue
            try:
                result.append(model.model_validate(item))
            except ValidationError:
                continue
        return result
    if isinstance(raw, model):
        return [raw]
    if raw is None:
        return []
    try:
        validated = model.model_validate(raw)
        return [validated]
    except ValidationError:
        return []
