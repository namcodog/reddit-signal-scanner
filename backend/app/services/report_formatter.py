"""
Reddit Signal Scanner - 报告格式化服务

Linus原则："数据结构决定一切"
- 统一的报告响应格式
- 消除特殊情况处理
- 清晰的数据转换逻辑
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.analysis import Analysis
from ..models.report import Report
from ..models.task import Task


class ReportFormatterService:
    """报告格式化服务 - 统一数据处理"""

    def __init__(self, db: Session):
        self.db = db

    def get_complete_report(self, task_id: str) -> Dict[str, Any]:
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

    def get_summary_report(self, task_id: str) -> Dict[str, Any]:
        """获取摘要版报告"""
        complete_report = self.get_complete_report(task_id)

        # 只保留核心摘要信息
        if complete_report.get("success"):
            data = complete_report["data"]
            data["key_insights"] = data["key_insights"][:1]  # 只保留第一个洞察
            data["user_personas"] = []  # 移除用户画像
            complete_report["message"] = "摘要报告获取成功"

        return complete_report

    def get_insights_only(self, task_id: str) -> Dict[str, Any]:
        """仅获取关键洞察"""
        complete_report = self.get_complete_report(task_id)

        if complete_report.get("success"):
            data = complete_report["data"]
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
    ) -> Dict[str, Any]:
        """格式化完整报告数据"""

        # 提取JSONB数据
        insights_data = analysis.insights or {}
        sources_data = analysis.sources or {}

        # 构建标准化响应
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        report_data = {
            "task_id": str(task.id),
            "query": self._get_effective_query(task),
            "total_posts": sources_data.get("posts_analyzed", 0),
            "total_comments": sources_data.get("comments_count", 0),
            "analysis_duration": self._calculate_duration(
                task.created_at, analysis.created_at
            ),
            "confidence_score": float(analysis.confidence_score),
            # 核心洞察
            "key_insights": self._format_insights(insights_data),
            # 情感分析摘要
            "sentiment_summary": self._format_sentiment(insights_data),
            # 热门话题
            "trending_topics": self._format_topics(insights_data),
            # 用户画像
            "user_personas": self._format_personas(insights_data),
            # 元数据
            "generated_at": current_time,
            "data_freshness": self._calculate_freshness(analysis.created_at),
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

    def _format_insights(self, insights_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化关键洞察"""
        formatted_insights = []

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

    def _format_sentiment(self, insights_data: Dict[str, Any]) -> Dict[str, float]:
        """格式化情感分析"""
        sentiment = insights_data.get("sentiment_summary", {})

        # 提供默认值确保数据一致性
        return {
            "positive": sentiment.get("positive", 0.5),
            "neutral": sentiment.get("neutral", 0.3),
            "negative": sentiment.get("negative", 0.2),
        }

    def _format_topics(self, insights_data: Dict[str, Any]) -> List[str]:
        """格式化热门话题"""
        topics = insights_data.get("trending_topics", [])

        if not topics:
            return ["用户体验讨论", "功能需求反馈", "价格对比分析", "替代方案探讨"]

        return topics[:5]  # 最多返回5个话题

    def _format_personas(self, insights_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化用户画像"""
        personas = insights_data.get("user_personas", [])

        if not personas:
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

        return personas

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
        if len(task.product_description) <= 100:
            return task.product_description
        else:
            return task.product_description[:97] + "..."

    def _create_empty_response(self, task_id: str, message: str) -> Dict[str, Any]:
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
                "generated_at": current_time,
                "data_freshness": "无数据",
            },
        }


# ===== 便利函数 =====


def get_formatted_report(
    db: Session, task_id: str, format_type: str = "full"
) -> Dict[str, Any]:
    """
    获取格式化报告的便利函数

    Args:
        db: 数据库会话
        task_id: 任务ID
        format_type: 格式类型 (full/summary/insights)

    Returns:
        Dict: 格式化的报告数据
    """
    service = ReportFormatterService(db)

    if format_type == "summary":
        return service.get_summary_report(task_id)
    elif format_type == "insights":
        return service.get_insights_only(task_id)
    else:
        return service.get_complete_report(task_id)
