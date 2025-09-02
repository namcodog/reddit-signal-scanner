"""
分析流水线数据模型 - Reddit Signal Scanner
定义流水线处理过程中的核心数据结构

基于Linus设计原则：
- 数据结构决定复杂度，简洁的模型减少处理逻辑
- 统一的接口消除特殊情况
- 强类型保证数据安全
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import time


class StepStatus(Enum):
    """步骤执行状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    TIMEOUT = "timeout"  # 执行超时


@dataclass
class AnalysisConfig:
    """分析配置 - 用户输入的分析参数"""

    # 基础参数
    product_description: str
    target_keywords: List[str] = field(default_factory=list)

    # 高级配置
    max_communities: Optional[int] = None  # 覆盖默认社区数量
    enable_cache: bool = True  # 是否使用缓存
    priority: str = "normal"  # 分析优先级: low, normal, high

    # 输出配置
    output_format: str = "structured"  # structured, summary, detailed
    include_raw_data: bool = False  # 是否包含原始数据

    # 时间限制
    max_total_time: Optional[float] = None  # 覆盖默认总时长

    def __post_init__(self):
        """后处理验证"""
        if not self.product_description.strip():
            raise ValueError("产品描述不能为空")

        if self.max_communities is not None and self.max_communities < 1:
            raise ValueError("社区数量必须大于0")


@dataclass
class PipelineData:
    """
    流水线数据载体 - 在各步骤间传递的统一数据结构

    设计原则：
    - 单一数据载体，避免参数传递复杂化
    - 包含完整的执行上下文和状态
    - 支持步骤间的数据共享
    """

    # 输入数据
    product_description: str
    target_keywords: List[str] = field(default_factory=list)
    analysis_config: AnalysisConfig = field(default_factory=lambda: AnalysisConfig(""))

    # 流水线状态
    current_step: int = 0
    total_steps: int = 4
    step_results: Dict[str, Any] = field(default_factory=dict)

    # 性能追踪
    step_durations: List[float] = field(default_factory=list)
    total_start_time: float = field(default_factory=time.time)

    # 错误处理
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # 元数据
    pipeline_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None

    def get_step_result(self, step_name: str, default: Any = None) -> Any:
        """安全获取步骤结果"""
        return self.step_results.get(step_name, default)

    def add_error(self, error: str, step_name: Optional[str] = None) -> None:
        """添加错误信息"""
        if step_name:
            error = f"[{step_name}] {error}"
        self.errors.append(error)

    def add_warning(self, warning: str, step_name: Optional[str] = None) -> None:
        """添加警告信息"""
        if step_name:
            warning = f"[{step_name}] {warning}"
        self.warnings.append(warning)

    def get_total_duration(self) -> float:
        """获取总执行时间"""
        if not self.step_durations:
            return 0.0
        return sum(self.step_durations)

    def is_healthy(self) -> bool:
        """检查流水线状态是否健康"""
        return len(self.errors) == 0 and self.current_step <= self.total_steps


@dataclass
class PipelineResult:
    """单步骤执行结果"""

    step_name: str
    duration: float
    data: Dict[str, Any]
    success: bool
    status: StepStatus = StepStatus.COMPLETED

    # 可选的详细信息
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """设置状态"""
        if not self.success:
            self.status = StepStatus.FAILED


@dataclass
class CommunityInfo:
    """社区信息数据结构"""

    subreddit_name: str
    member_count: int
    relevance_score: float
    activity_level: str  # high, medium, low
    last_post_time: Optional[datetime] = None

    # 匹配信息
    matched_keywords: List[str] = field(default_factory=list)
    keyword_density: float = 0.0


@dataclass
class PostData:
    """帖子数据结构"""

    post_id: str
    title: str
    content: str
    subreddit: str
    author: str

    # 时间信息
    created_utc: datetime

    # 互动数据
    score: int = 0
    num_comments: int = 0
    upvote_ratio: float = 0.0

    # 分析结果
    sentiment_score: Optional[float] = None
    pain_point_score: Optional[float] = None
    opportunity_score: Optional[float] = None

    # 元数据
    source: str = "api"  # api, cache
    processed_at: Optional[datetime] = None


@dataclass
class InsightsData:
    """洞察数据结构 - Step3的输出"""

    # 三类核心洞察
    pain_points: List[Dict[str, Any]] = field(default_factory=list)
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    opportunities: List[Dict[str, Any]] = field(default_factory=list)

    # 分析摘要
    analysis_summary: str = ""
    key_insights: List[str] = field(default_factory=list)

    # 置信度评分
    confidence_score: float = 0.0
    data_quality_score: float = 0.0

    @property
    def total_insights(self) -> int:
        """总洞察数量"""
        return len(self.pain_points) + len(self.competitors) + len(self.opportunities)

    def get_top_insights(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取top洞察"""
        all_insights = []

        # 合并所有洞察并按分数排序
        for pain_point in self.pain_points:
            all_insights.append({**pain_point, "type": "pain_point"})

        for competitor in self.competitors:
            all_insights.append({**competitor, "type": "competitor"})

        for opportunity in self.opportunities:
            all_insights.append({**opportunity, "type": "opportunity"})

        # 按score降序排序
        sorted_insights = sorted(
            all_insights, key=lambda x: x.get("score", 0), reverse=True
        )

        return sorted_insights[:limit]


@dataclass
class AnalysisReport:
    """最终分析报告 - Step4的输出"""

    # 报告元数据
    report_id: str
    product_description: str
    generated_at: datetime = field(default_factory=datetime.now)

    # 核心结果
    insights: InsightsData = field(default_factory=InsightsData)
    confidence_score: float = 0.0

    # 数据源信息
    total_posts_analyzed: int = 0
    communities_scanned: List[str] = field(default_factory=list)
    data_sources: Dict[str, int] = field(
        default_factory=dict
    )  # {"cache": 450, "api": 50}

    # 执行统计
    total_duration: float = 0.0
    step_durations: Dict[str, float] = field(default_factory=dict)

    # 质量指标
    data_quality_metrics: Dict[str, float] = field(default_factory=dict)

    def get_executive_summary(self) -> Dict[str, Any]:
        """生成执行摘要"""
        return {
            "总洞察数": self.insights.total_insights,
            "置信度": f"{self.confidence_score:.1%}",
            "分析时长": f"{self.total_duration:.1f}秒",
            "数据来源": self.data_sources,
            "关键发现": self.insights.key_insights[:3],  # 前3个关键发现
        }

    def is_actionable(self) -> bool:
        """判断报告是否可执行"""
        return (
            self.confidence_score >= 0.5
            and self.insights.total_insights >= 3
            and self.total_duration <= 300  # 5分钟内完成
        )


# 便捷的类型别名
AnalysisStepData = Dict[str, Any]  # 步骤间传递的数据
AnalysisMetrics = Dict[str, float]  # 性能指标数据
