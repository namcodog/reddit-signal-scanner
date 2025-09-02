"""
Reddit Signal Scanner - Reddit数据模型

PRD-03 统一数据结构定义
基于Linus设计原则：简洁、类型安全、无歧义

核心数据模型：
- RedditPost: 统一的帖子数据结构
- DataCollectionResult: 数据采集结果
- 所有字段完整类型注解，避免运行时类型错误
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
from dataclasses import dataclass
from pydantic import BaseModel, Field, validator


class RedditPost(BaseModel):
    """Reddit帖子统一数据模型

    基于PRD-03要求：
    - 统一缓存和API数据的格式差异
    - 包含信号提取所需的全部字段
    - 严格的数据验证和类型安全
    """

    # 核心标识
    id: str = Field(..., description="Reddit帖子唯一ID")
    community: str = Field(..., description="所属社区（含r/前缀）")

    # 内容字段
    title: str = Field(..., min_length=1, description="帖子标题")
    content: str = Field(default="", description="帖子正文（self posts）")
    author: str = Field(..., description="作者用户名")

    # 时间字段
    created_utc: int = Field(..., description="创建时间（UTC时间戳）")

    # 统计字段
    score: int = Field(default=0, description="得分（upvotes - downvotes）")
    num_comments: int = Field(default=0, ge=0, description="评论数量")
    upvote_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="赞同率")

    # 链接字段
    url: Optional[str] = Field(default=None, description="帖子链接URL")
    permalink: str = Field(default="", description="Reddit永久链接")
    domain: str = Field(default="", description="链接域名")

    # 元数据字段
    flair_text: Optional[str] = Field(default=None, description="帖子标签")
    distinguished: Optional[str] = Field(
        default=None, description="特殊标识（mod/admin）"
    )
    stickied: bool = Field(default=False, description="是否置顶")
    is_self: bool = Field(default=False, description="是否为自发帖")

    # 状态字段
    is_deleted: bool = Field(default=False, description="是否已删除")
    is_removed: bool = Field(default=False, description="是否被移除")

    # 富文本字段
    selftext_html: Optional[str] = Field(default=None, description="HTML格式正文")

    @validator("community")
    def validate_community_format(cls, v):
        """验证社区名称格式"""
        if not v.startswith("r/"):
            return f"r/{v}"
        return v

    @validator("created_utc")
    def validate_created_utc(cls, v):
        """验证创建时间的合理性"""
        if v < 0:
            raise ValueError("创建时间不能为负数")
        # Reddit创建时间：2005年6月23日
        reddit_launch_timestamp = 1119484800
        if v < reddit_launch_timestamp:
            raise ValueError("创建时间早于Reddit成立时间")
        return v

    @property
    def created_datetime(self) -> datetime:
        """将UTC时间戳转换为datetime对象"""
        return datetime.fromtimestamp(self.created_utc)

    @property
    def full_url(self) -> str:
        """完整的Reddit URL"""
        if self.permalink:
            return f"https://www.reddit.com{self.permalink}"
        return f"https://www.reddit.com/r/{self.community.replace('r/', '')}/comments/{self.id}"

    @property
    def content_length(self) -> int:
        """内容总长度（标题+正文）"""
        return len(self.title) + len(self.content or "")

    @property
    def engagement_score(self) -> float:
        """参与度评分（评论数/得分比例）"""
        if self.score <= 0:
            return 0.0
        return min(1.0, self.num_comments / max(1, self.score))

    class Config:
        """Pydantic配置"""

        validate_assignment = True
        use_enum_values = True
        arbitrary_types_allowed = True


class DataCollectionResult(BaseModel):
    """数据采集结果模型

    PRD-03缓存优先架构的统一输出格式
    """

    # 采集结果
    posts: List[RedditPost] = Field(default_factory=list, description="采集的帖子列表")

    # 统计信息
    total_communities: int = Field(default=0, ge=0, description="目标社区总数")
    successful_communities: int = Field(default=0, ge=0, description="成功采集的社区数")

    # 缓存和API统计
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="缓存命中率")
    api_calls_made: int = Field(default=0, ge=0, description="API调用次数")

    # 执行信息
    execution_time_seconds: float = Field(
        default=0.0, ge=0.0, description="执行耗时（秒）"
    )
    errors: Optional[List[str]] = Field(default=None, description="错误信息列表")
    error_message: Optional[str] = Field(default=None, description="主要错误信息")

    # 质量指标
    data_quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="数据质量评分"
    )

    @validator("successful_communities")
    def validate_successful_communities(cls, v, values):
        """验证成功社区数不超过总数"""
        total = values.get("total_communities", 0)
        if v > total:
            raise ValueError("成功社区数不能超过总社区数")
        return v

    @property
    def success_rate(self) -> float:
        """成功率计算"""
        if self.total_communities == 0:
            return 0.0
        return self.successful_communities / self.total_communities

    @property
    def average_posts_per_community(self) -> float:
        """每个社区平均帖子数"""
        if self.successful_communities == 0:
            return 0.0
        return len(self.posts) / self.successful_communities

    @property
    def is_successful(self) -> bool:
        """采集是否成功（成功率>50%且有帖子）"""
        return self.success_rate > 0.5 and len(self.posts) > 0

    def get_summary(self) -> Dict[str, Any]:
        """获取采集结果摘要"""
        return {
            "total_posts": len(self.posts),
            "communities_coverage": f"{self.successful_communities}/{self.total_communities}",
            "success_rate": f"{self.success_rate:.1%}",
            "cache_hit_rate": f"{self.cache_hit_rate:.1%}",
            "api_calls_made": self.api_calls_made,
            "execution_time": f"{self.execution_time_seconds:.2f}s",
            "avg_posts_per_community": f"{self.average_posts_per_community:.1f}",
            "data_quality": (
                f"{self.data_quality_score or 0:.2f}"
                if self.data_quality_score
                else "未评估"
            ),
            "has_errors": bool(self.errors),
            "is_successful": self.is_successful,
        }

    class Config:
        """Pydantic配置"""

        validate_assignment = True
        use_enum_values = True


class CacheStatus(BaseModel):
    """缓存状态模型"""

    community: str = Field(..., description="社区名称")
    is_cached: bool = Field(default=False, description="是否有缓存")
    is_fresh: bool = Field(default=False, description="缓存是否新鲜")
    posts_count: int = Field(default=0, ge=0, description="缓存帖子数量")
    last_updated: Optional[datetime] = Field(default=None, description="最后更新时间")
    quality_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="缓存质量评分"
    )
    hit_count: int = Field(default=0, ge=0, description="命中次数")

    @property
    def cache_age_hours(self) -> Optional[float]:
        """缓存年龄（小时）"""
        if not self.last_updated:
            return None
        return (datetime.utcnow() - self.last_updated).total_seconds() / 3600

    @property
    def freshness_score(self) -> float:
        """新鲜度评分（0-1，基于时间衰减）"""
        if not self.is_cached or not self.last_updated:
            return 0.0

        age_hours = self.cache_age_hours
        if age_hours is None:
            return 0.0

        # 24小时内线性衰减
        return max(0.0, 1.0 - (age_hours / 24))


# 批量操作模型
class BatchCollectionRequest(BaseModel):
    """批量采集请求模型"""

    communities: List[str] = Field(
        ..., min_items=1, max_items=50, description="社区列表"
    )
    max_posts_per_community: int = Field(
        default=100, ge=1, le=500, description="每社区最大帖子数"
    )
    cache_freshness_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="缓存新鲜度阈值"
    )
    max_api_calls: int = Field(default=15, ge=0, le=30, description="最大API调用数")
    timeout_seconds: int = Field(default=300, ge=30, le=600, description="超时时间")

    @validator("communities")
    def validate_communities(cls, v):
        """验证社区名称列表"""
        clean_communities = []
        for community in v:
            clean_name = community.strip()
            if not clean_name:
                continue
            if not clean_name.startswith("r/"):
                clean_name = f"r/{clean_name}"
            clean_communities.append(clean_name)

        if not clean_communities:
            raise ValueError("社区列表不能为空")

        # 去重
        return list(set(clean_communities))


# 响应模型
class CollectionResponse(BaseModel):
    """采集API响应模型"""

    success: bool = Field(..., description="采集是否成功")
    data: Optional[DataCollectionResult] = Field(default=None, description="采集数据")
    message: str = Field(default="", description="响应消息")
    request_id: Optional[str] = Field(default=None, description="请求ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间")

    @property
    def response_summary(self) -> Dict[str, Any]:
        """响应摘要"""
        summary = {
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.data:
            summary.update(self.data.get_summary())

        return summary
