"""
算法指标聚合服务（PRD‑07‑03）

职责：
- 计算 Must Gates 与 A‑Score
- 汇总单任务或任务列表的指标

依赖：通过 provider(task_id) 提供底层指标，服务只负责纯计算与装配
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List

from ..schemas.admin.analysis import (
    AnalysisMustGates,
    AnalysisMustResult,
    AnalysisSummary,
    TaskAnalysisMetrics,
)


@dataclass(frozen=True)
class ExternalAnalysisMetrics:
    coverage: float
    relevance: float
    evidence_per_insight_avg: float
    median_days: float
    dup_ratio: float
    spam_ratio: float
    diversity: float
    safety_pass: bool = True


def _compute_a_score(m: ExternalAnalysisMetrics) -> int:
    # 百分制转化
    relevance_pct = m.relevance * 100.0
    coverage_pct = m.coverage * 100.0
    evidence_strength_pct = min(2.0, m.evidence_per_insight_avg) / 2.0 * 100.0
    freshness_pct = max(0.0, 1.0 - (m.median_days / 7.0)) * 100.0
    cleanliness_pct = (1.0 - m.dup_ratio) * (1.0 - m.spam_ratio) * 100.0
    diversity_pct = m.diversity * 100.0

    score = (
        0.30 * relevance_pct
        + 0.20 * coverage_pct
        + 0.20 * evidence_strength_pct
        + 0.15 * freshness_pct
        + 0.10 * cleanliness_pct
        + 0.05 * diversity_pct
    )
    return int(round(max(0.0, min(100.0, score))))


def _compute_must(g: AnalysisMustGates, m: ExternalAnalysisMetrics) -> AnalysisMustResult:
    return AnalysisMustResult(
        coverage_ok=m.coverage >= g.evidence_coverage_min,
        freshness_ok=m.median_days <= g.fresh_median_days_max,
        relevance_ok=m.relevance >= g.relevance_pass_rate_min,
        dup_ok=m.dup_ratio <= g.dup_ratio_max,
        spam_ok=m.spam_ratio <= g.spam_ratio_max,
        safety_ok=bool(m.safety_pass),
    )


def summarize_task(task_id: str, metrics: ExternalAnalysisMetrics, gates: AnalysisMustGates | None = None) -> AnalysisSummary:
    g = gates or AnalysisMustGates()
    must = _compute_must(g, metrics)
    a_score = _compute_a_score(metrics)
    return AnalysisSummary(
        task_id=task_id,
        a_score=a_score,
        must=must,
        coverage=metrics.coverage,
        relevance=metrics.relevance,
        evidence_per_insight_avg=metrics.evidence_per_insight_avg,
        median_days=metrics.median_days,
        dup_ratio=metrics.dup_ratio,
        spam_ratio=metrics.spam_ratio,
        diversity=metrics.diversity,
    )


def summarize_many(
    task_ids: Iterable[str],
    provider: Callable[[str], ExternalAnalysisMetrics],
) -> List[AnalysisSummary]:
    out: List[AnalysisSummary] = []
    for tid in task_ids:
        out.append(summarize_task(tid, provider(tid)))
    return out
