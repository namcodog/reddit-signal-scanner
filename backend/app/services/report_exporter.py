"""报告导出服务 - 生成可下载的报告文件。"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List

from app.schemas.contracts.report_contract import InsightItem, ReportData


@dataclass(slots=True)
class ExportPayload:
    """报告导出结果载体"""

    filename: str
    content_type: str
    content: bytes
    format: str


class ReportExportService:
    """报告导出服务"""

    @staticmethod
    def generate(report: ReportData, export_format: str) -> ExportPayload:
        format_lower = export_format.lower()

        if format_lower == "json":
            return ReportExportService._generate_json(report)
        if format_lower == "csv":
            return ReportExportService._generate_csv(report)
        if format_lower == "pdf":
            return ReportExportService._generate_pdf(report)

        raise ValueError(f"不支持的导出格式: {export_format}")

    @staticmethod
    def _generate_json(report: ReportData) -> ExportPayload:
        payload = report.model_dump(mode="json")
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = f"report_{report.task_id}.json"
        return ExportPayload(
            filename=filename,
            content_type="application/json",
            content=content,
            format="json",
        )

    @staticmethod
    def _generate_csv(report: ReportData) -> ExportPayload:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(["Field", "Value"])
        writer.writerow(["Task ID", report.task_id])
        writer.writerow(["Query", report.query])
        writer.writerow(["Total Posts", report.total_posts])
        writer.writerow(["Total Comments", report.total_comments])
        writer.writerow(["Analysis Duration (s)", f"{report.analysis_duration:.2f}"])
        writer.writerow(["Generated At", report.generated_at])
        writer.writerow(["Data Freshness", report.data_freshness])

        sentiment = report.sentiment_summary or {}
        if sentiment:
            writer.writerow([])
            writer.writerow(["Sentiment", "Score"])
            for name, value in sentiment.items():
                writer.writerow([name, value])

        writer.writerow([])
        writer.writerow(["Insights", "Description"])
        for idx, insight in enumerate(report.key_insights or [], start=1):
            ReportExportService._write_insight(writer, idx, insight)

        csv_content = buffer.getvalue().encode("utf-8")
        filename = f"report_{report.task_id}.csv"
        return ExportPayload(
            filename=filename,
            content_type="text/csv; charset=utf-8",
            content=csv_content,
            format="csv",
        )

    @staticmethod
    def _write_insight(writer: Any, idx: int, insight: InsightItem) -> None:
        writer.writerow([f"Insight {idx} Title", insight.title])
        writer.writerow([f"Insight {idx} Content", insight.content])
        writer.writerow([f"Insight {idx} Confidence", f"{insight.confidence:.2f}"])
        writer.writerow([f"Insight {idx} Source Count", insight.source_count])
        if insight.tags:
            writer.writerow([f"Insight {idx} Tags", ", ".join(insight.tags)])
        writer.writerow([])

    @staticmethod
    def _generate_pdf(report: ReportData) -> ExportPayload:
        lines: List[str] = [
            f"Reddit Signal Scanner Report",
            f"Task ID: {report.task_id}",
            f"Query: {report.query}",
            f"Total Posts: {report.total_posts}",
            f"Total Comments: {report.total_comments}",
            f"Generated At: {report.generated_at}",
            f"Data Freshness: {report.data_freshness}",
            "",
            "Key Insights:",
        ]

        if report.key_insights:
            for idx, insight in enumerate(report.key_insights, start=1):
                lines.append(f"{idx}. {insight.title} - {insight.content}")
        else:
            lines.append("暂无关键洞察")

        pdf_bytes = ReportExportService._build_simple_pdf(lines)
        filename = f"report_{report.task_id}.pdf"
        return ExportPayload(
            filename=filename,
            content_type="application/pdf",
            content=pdf_bytes,
            format="pdf",
        )

    @staticmethod
    def _build_simple_pdf(lines: List[str]) -> bytes:
        sanitized_lines = [ReportExportService._sanitize_pdf_text(line) for line in lines]

        stream_lines = ["BT", "/F1 12 Tf", "72 750 Td"]
        for line in sanitized_lines:
            stream_lines.append(f"({line}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")

        stream_content = "\n".join(stream_lines) + "\n"
        stream_bytes = stream_content.encode("latin-1")

        buffer = io.BytesIO()
        buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets: List[int] = [0]

        def _write_obj(obj: str) -> None:
            offsets.append(buffer.tell())
            buffer.write(obj.encode("latin-1"))
            buffer.write(b"\n")

        _write_obj("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
        _write_obj("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
        _write_obj(
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj"
        )
        _write_obj(
            f"4 0 obj << /Length {len(stream_bytes)} >>\nstream\n{stream_content}endstream\nendobj"
        )
        _write_obj("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")

        xref_start = buffer.tell()
        buffer.write(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
        buffer.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))

        buffer.write(
            (
                "trailer << /Size {size} /Root 1 0 R >>\n"
                "startxref\n{xref}\n%%EOF"
            ).format(size=len(offsets), xref=xref_start).encode("latin-1")
        )

        return buffer.getvalue()

    @staticmethod
    def _sanitize_pdf_text(value: str) -> str:
        cleaned = "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in value)
        return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


__all__ = ["ReportExportService", "ExportPayload"]
