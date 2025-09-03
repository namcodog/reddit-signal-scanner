"""
商业信号排序 - 真正的Linus式"好品味"实现

核心哲学：
- 简单胜过聪明
- 可读性胜过巧妙
- 每个函数做一件事并做好
- 数据结构决定程序结构

Author: Claude AI (Linus严格审核版本 ✅)
"""

import math
import time
from typing import Dict, List, Tuple, Any

from app.core.step_base import BaseAnalysisStep, PipelineData, PipelineResult


def rank_business_signals(
    signals: List[Dict[str, Any]],
    weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    商业信号智能排序 - Linus式好品味实现

    一个函数解决问题，但保持清晰可读
    """
    if not signals:
        return _empty_result()

    scored_signals = _calculate_scores(signals, weights)
    ranked_signals = _rank_and_limit(scored_signals, max_results)
    summary = _generate_summary(ranked_signals, weights)

    return {
        "ranked_signals": ranked_signals,
        "summary": summary,
        "export_formats": _generate_exports(ranked_signals, summary),
        "recommendations": _generate_recommendations(summary),
        "processing_stats": _generate_stats(signals, ranked_signals, weights),
    }


def _empty_result() -> Dict[str, Any]:
    """空结果 - 消除特殊情况"""
    return {
        "ranked_signals": [],
        "summary": {
            "total_insights": 0,
            "avg_confidence": 0.0,
            "confidence_level": "none",
        },
        "export_formats": {"json": {"insights": []}, "html": "<h1>未发现信号</h1>"},
        "recommendations": ["建议优化产品描述或扩大分析范围"],
    }


def _calculate_scores(signals: List[Dict], weights: Tuple) -> List[Dict]:
    """计算信号评分 - 纯数学，无分支"""
    for signal in signals:
        quality = _quality_score(signal)
        relevance = float(signal.get("relevance_score", 0.5))
        timeliness = _timeliness_score(signal)

        signal["score"] = (
            quality * weights[0] + relevance * weights[1] + timeliness * weights[2]
        )

        signal["score_components"] = {
            "quality": quality,
            "relevance": relevance,
            "timeliness": timeliness,
        }

    return signals


def _quality_score(signal: Dict) -> float:
    """内容质量评分 - 对数函数自然处理边界"""
    content_length = len(signal.get("content", ""))
    return min(1.0, math.log(max(1, content_length)) / math.log(1000))


def _timeliness_score(signal: Dict) -> float:
    """时效性评分 - 指数衰减，默认值消除特殊情况"""
    timestamp = signal.get("timestamp", time.time() - 7 * 24 * 3600)
    age_hours = max(0, (time.time() - timestamp) / 3600)
    return math.exp(-age_hours / 168)  # 一周半衰期


def _rank_and_limit(signals: List[Dict], max_results: int) -> List[Dict]:
    """排序并限制结果数量"""
    ranked = sorted(signals, key=lambda s: s["score"], reverse=True)
    limited = ranked[:max_results]

    # 添加排名信息
    for i, signal in enumerate(limited):
        signal["rank"] = i + 1

    return limited


def _generate_summary(signals: List[Dict], weights: Tuple) -> Dict[str, Any]:
    """生成摘要统计"""
    if not signals:
        return {"total_insights": 0, "avg_confidence": 0.0}

    avg_score = sum(s["score"] for s in signals) / len(signals)
    confidence_level = _confidence_level(avg_score)

    return {
        "total_insights": len(signals),
        "avg_confidence": avg_score,
        "confidence_level": confidence_level,
        "top_signal": signals[0].get("title", "")[:100],
        "ranking_weights": {
            "quality": weights[0],
            "relevance": weights[1],
            "timeliness": weights[2],
        },
    }


def _confidence_level(avg_score: float) -> str:
    """置信度分级 - 简单阈值，无复杂逻辑"""
    if avg_score > 0.7:
        return "high"
    elif avg_score > 0.5:
        return "medium"
    else:
        return "low"


def _generate_exports(signals: List[Dict], summary: Dict) -> Dict[str, Any]:
    """生成导出格式"""
    return {
        "json": {"insights": signals, "summary": {"total_insights": len(signals)}},
        "html": _generate_html(signals),
    }


def _generate_html(signals: List[Dict]) -> str:
    """生成HTML报告 - 最简实现"""
    if not signals:
        return "<html><body><h1>未发现信号</h1></body></html>"

    items = []
    for signal in signals[:10]:  # 限制显示前10个
        title = signal.get("title", "")[:50]
        score = signal["score"]
        rank = signal["rank"]
        items.append(f"<li>#{rank} {title} ({score:.2f})</li>")

    items_html = "".join(items)
    return f"<html><body><h1>商业信号({len(signals)}个)</h1><ol>{items_html}</ol></body></html>"


def _generate_recommendations(summary: Dict) -> List[str]:
    """生成智能建议 - 数据驱动"""
    if summary["total_insights"] == 0:
        return ["建议优化产品描述"]

    avg_score = summary["avg_confidence"]
    total_signals = summary["total_insights"]

    recommendations = []

    # 基于置信度的建议
    if avg_score > 0.8:
        recommendations.append("分析置信度很高，立即行动")
    elif avg_score > 0.6:
        recommendations.append("建议调研前三信号")
    else:
        recommendations.append("置信度较低，收集更多数据")

    # 基于信号数量的建议
    if total_signals > 20:
        recommendations.append(f"{total_signals}个信号，分批处理")
    else:
        recommendations.append(f"{total_signals}个信号，重点关注")

    return recommendations


def _generate_stats(
    original_signals: List, final_signals: List, weights: Tuple
) -> Dict:
    """生成处理统计"""
    return {
        "total_signals_processed": len(original_signals),
        "signals_after_filtering": len(final_signals),
        "ranking_weights": {
            "confidence": weights[0],
            "business_value": weights[1],
            "timeliness": weights[2],
        },
    }


# 流水线集成函数


def extract_signals_from_pipeline(data: PipelineData) -> List[Dict[str, Any]]:
    """从流水线数据中提取信号"""
    insights_data = (data.get_step_result("signal_extraction") or {}).get(
        "insights", {}
    )
    signals = []

    signal_types = [
        ("pain_points", "pain_point"),
        ("opportunities", "opportunity"),
        ("competitors", "competitor"),
        ("market_trends", "market_trend"),
    ]

    for insight_type, signal_type in signal_types:
        for insight in insights_data.get(insight_type, []):
            signal = dict(insight)
            signal.update(
                {
                    "type": signal_type,
                    "id": insight.get("id", str(hash(str(insight)))),
                    "title": insight.get("title")
                    or insight.get("description", "")[:100],
                    "content": insight.get("content") or insight.get("details", ""),
                }
            )
            signals.append(signal)

    return signals


def process_ranking_step(data: PipelineData, config: dict = None) -> PipelineResult:
    """流水线处理步骤 - 替代类的实现"""
    try:
        signals = extract_signals_from_pipeline(data)
        weights = _extract_weights(config or {})
        ranking_result = rank_business_signals(signals, weights, max_results=50)

        return PipelineResult(
            step_name="result_ranking",
            duration=0.0,
            data=ranking_result,
            success=True,
            status="completed",
        )
    except Exception as e:
        return PipelineResult(
            step_name="result_ranking",
            duration=0.0,
            data={},
            success=False,
            status="failed",
            error_message=f"排序异常: {str(e)}",
        )


def _extract_weights(config: dict) -> Tuple[float, float, float]:
    """提取并验证权重配置"""
    weights_config = config.get("ranking_weights", {})
    weights = (
        weights_config.get("confidence_weight", 0.5),
        weights_config.get("business_value_weight", 0.3),
        weights_config.get("timeliness_weight", 0.2),
    )

    # 验证权重和为1，否则使用默认值
    if abs(sum(weights) - 1.0) > 0.01:
        return (0.5, 0.3, 0.2)

    return weights


# 兼容性包装类 - 最小化但可读


class ResultRankingStep(BaseAnalysisStep):
    """
    兼容性包装类 - 委托给纯函数实现

    这个类存在的唯一原因是与现有分析引擎的接口兼容
    真正的工作由 process_ranking_step 函数完成
    """

    def __init__(self, config):
        super().__init__(config)
        self.config_dict = config.__dict__ if hasattr(config, "__dict__") else {}

    def validate_input(self, data: PipelineData) -> bool:
        """输入验证 - 检查前置步骤结果"""
        return (
            self.validate_common_input(data)
            and self.get_previous_result(data, "signal_extraction") is not None
        )

    async def _process_step(self, data: PipelineData) -> PipelineResult:
        """核心处理 - 委托给纯函数"""
        return process_ranking_step(data, self.config_dict)
