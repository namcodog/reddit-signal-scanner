"""
报告缓存服务 - Linus式简单实现

原则：应用处理逻辑，数据库存储数据
- 200行代码替换500行SQL逻辑
- 简单明了的缓存策略
"""

from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session

from ..models.report import Report, create_report
from ..models.analysis import Analysis


class ReportCacheService:
    """报告缓存服务 - 简单实现"""

    def __init__(self, db: Session):
        self.db = db

    def get_report_html(self, analysis_id: UUID) -> str:
        """获取报告HTML - 核心缓存逻辑"""

        # 查找活跃报告
        report = (
            self.db.query(Report)
            .filter(Report.analysis_id == analysis_id, Report.status == "active")
            .first()
        )

        if report:
            return report.html_content

        # 没有缓存，生成新报告
        html = self._generate_html(analysis_id)

        # 保存缓存
        report = create_report(analysis_id, html, "active")
        self.db.add(report)
        self.db.commit()

        return html

    def invalidate_cache(self, analysis_id: UUID) -> None:
        """失效缓存 - 标记为废弃"""
        self.db.query(Report).filter(
            Report.analysis_id == analysis_id, Report.status == "active"
        ).update({"status": "deprecated"})
        self.db.commit()

    def _generate_html(self, analysis_id: UUID) -> str:
        """生成HTML报告 - 业务逻辑层"""

        # 获取分析数据
        analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()

        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        # 简单HTML模板
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Reddit Analysis Report</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>Reddit Signal Analysis Report</h1>
            <div class="analysis-info">
                <p><strong>Analysis ID:</strong> {analysis.id}</p>
                <p><strong>Confidence:</strong> {analysis.confidence_score * 100:.1f}%</p>
                <p><strong>Generated:</strong> {analysis.created_at}</p>
            </div>
            
            <div class="insights">
                <h2>Key Insights</h2>
                <div class="insights-content">
                    {self._format_insights(analysis.insights)}
                </div>
            </div>
            
            <div class="sources">
                <h2>Data Sources</h2>
                <div class="sources-content">
                    {self._format_sources(analysis.sources)}
                </div>
            </div>
        </body>
        </html>
        """

        return html_content.strip()

    def _format_insights(self, insights: dict) -> str:
        """格式化洞察数据"""
        if not insights:
            return "<p>No insights available</p>"

        html_parts = []

        # 痛点
        if "pain_points" in insights and insights["pain_points"]:
            html_parts.append("<h3>Pain Points</h3><ul>")
            for pain in insights["pain_points"][:5]:  # 最多显示5个
                html_parts.append(f"<li>{pain.get('description', 'N/A')}</li>")
            html_parts.append("</ul>")

        # 竞争对手
        if "competitors" in insights and insights["competitors"]:
            html_parts.append("<h3>Competitors</h3><ul>")
            for comp in insights["competitors"][:5]:  # 最多显示5个
                html_parts.append(f"<li>{comp.get('name', 'N/A')}</li>")
            html_parts.append("</ul>")

        # 机会
        if "opportunities" in insights and insights["opportunities"]:
            html_parts.append("<h3>Opportunities</h3><ul>")
            for opp in insights["opportunities"][:5]:  # 最多显示5个
                html_parts.append(f"<li>{opp.get('title', 'N/A')}</li>")
            html_parts.append("</ul>")

        return "".join(html_parts) or "<p>No structured insights available</p>"

    def _format_sources(self, sources: dict) -> str:
        """格式化数据源信息"""
        if not sources:
            return "<p>No source information available</p>"

        html_parts = []

        # 社区信息
        if "communities" in sources and sources["communities"]:
            communities = sources["communities"][:10]  # 最多显示10个
            html_parts.append(
                f"<p><strong>Communities:</strong> {', '.join(communities)}</p>"
            )

        # 数据量
        posts_count = sources.get("posts_analyzed", 0)
        html_parts.append(f"<p><strong>Posts Analyzed:</strong> {posts_count}</p>")

        # 缓存命中率
        cache_rate = sources.get("cache_hit_rate", 0)
        html_parts.append(
            f"<p><strong>Cache Hit Rate:</strong> {cache_rate * 100:.1f}%</p>"
        )

        return "".join(html_parts)

    def cleanup_deprecated_reports(self, days_old: int = 7) -> int:
        """清理废弃的报告"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        result = (
            self.db.query(Report)
            .filter(Report.status == "deprecated", Report.created_at < cutoff_date)
            .delete()
        )

        self.db.commit()
        return result

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        total_reports = self.db.query(Report).count()
        active_reports = self.db.query(Report).filter(Report.status == "active").count()

        return {
            "total_reports": total_reports,
            "active_reports": active_reports,
            "deprecated_reports": total_reports - active_reports,
        }


# ===== 便利函数 =====


def get_report_html(db: Session, analysis_id: UUID) -> str:
    """获取报告HTML - 便利函数"""
    service = ReportCacheService(db)
    return service.get_report_html(analysis_id)


def invalidate_report_cache(db: Session, analysis_id: UUID) -> None:
    """失效报告缓存 - 便利函数"""
    service = ReportCacheService(db)
    service.invalidate_cache(analysis_id)
