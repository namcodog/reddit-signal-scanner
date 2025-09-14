"""
Reddit Signal Scanner - 社区缓存模型

Linus设计原则: "缓存优先架构 + 性能可预测"
- 缓存即数据源，避免"缓存穿透"的特殊处理逻辑
- 索引策略基于实际缓存访问模式，确保性能可预测
- LRU + TTL + Priority 三重策略，覆盖所有缓存场景
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    CheckConstraint,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP as PostgreSQL_TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CommunityCache(Base):
    """社区缓存模型 - Reddit社区数据缓存管理核心

    Linus原则应用:
    1. 数据结构决定一切 - community_name自然主键，符合查询模式
    2. 消除特殊情况 - last_crawled_at允许NULL，统一处理逻辑
    3. 性能内置设计 - 5个索引覆盖所有查询场景
    4. 约束在数据库层 - 格式验证、范围检查都在数据库实现
    """

    __tablename__ = "community_cache"

    # 主键：Reddit社区名称（自然主键，避免无意义的数字ID）
    community_name: Mapped[str] = mapped_column(
        String(100), primary_key=True, comment="Reddit社区名称，如r/startups"
    )

    # ====================================================================
    # 缓存生命周期管理字段
    # ====================================================================

    # 最后抓取时间：NULL表示从未抓取（避免特殊值处理）
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
        PostgreSQL_TIMESTAMP(timezone=True),
        nullable=True,  # 允许NULL，统一"首次抓取"逻辑
        comment="最后抓取时间，NULL表示从未抓取",
    )

    # 缓存TTL：每个社区可以有不同的缓存策略
    ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("3600"),  # 默认1小时
        comment="缓存生存时间（秒）",
    )

    # 缓存容量：帖子数量，用于容量管理
    posts_cached: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="当前缓存的帖子数量"
    )

    # ====================================================================
    # 缓存质量评估系统
    # ====================================================================

    # 质量评分：基于数据完整性、新鲜度、用户反馈的综合评分
    quality_score: Mapped[Decimal] = mapped_column(
        DECIMAL(3, 2),  # 0.00 - 1.00 精确到小数点后2位
        nullable=False,
        server_default=text("0.50"),  # 默认中等质量
        comment="缓存质量评分(0.00-1.00)",
    )

    # ====================================================================
    # LRU缓存策略支持
    # ====================================================================

    # 命中计数：LRU清理策略的核心指标
    hit_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="缓存命中次数"
    )

    # 最后访问时间：LRU算法的时间维度
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(
        PostgreSQL_TIMESTAMP(timezone=True), nullable=True, comment="最后访问时间"
    )

    # ====================================================================
    # 爬虫调度系统
    # ====================================================================

    # 爬虫优先级：1(最高优先级) - 100(最低优先级)
    crawl_priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("50"),  # 默认中等优先级
        comment="爬虫优先级(1-100)，1为最高",
    )

    # ====================================================================
    # 审计字段：自动维护
    # ====================================================================

    created_at: Mapped[datetime] = mapped_column(
        PostgreSQL_TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="缓存条目创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        PostgreSQL_TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="缓存元数据最后更新时间",
    )

    # ====================================================================
    # 数据库约束和索引：性能优化的核心
    # ====================================================================

    __table_args__ = (
        # 1. 爬虫调度索引：获取需要更新的社区
        Index(
            "ix_community_cache_crawl_schedule",
            "crawl_priority",
            "last_crawled_at",
            postgresql_where=text(
                "last_crawled_at IS NULL OR "
                "(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_crawled_at)) > ttl_seconds)"
            ),
        ),
        # 2. 缓存热度索引：LRU清理策略
        Index(
            "ix_community_cache_hotness",
            text("hit_count DESC"),
            text("last_hit_at DESC"),
        ),
        # 3. 缓存质量索引：高质量缓存优先
        Index(
            "ix_community_cache_quality",
            text("quality_score DESC"),
            postgresql_where=text("quality_score >= 0.70"),
        ),
        # 4. 缓存新鲜度索引：时间范围查询
        Index(
            "ix_community_cache_freshness",
            text("last_crawled_at DESC"),
            postgresql_where=text("last_crawled_at IS NOT NULL"),
        ),
        # 5. 缓存大小索引：容量管理
        Index(
            "ix_community_cache_size",
            text("posts_cached DESC"),
            postgresql_where=text("posts_cached > 0"),
        ),
        # ====================================================================
        # 数据完整性约束
        # ====================================================================
        # Reddit社区名称格式约束
        CheckConstraint(
            "community_name ~ '^r/[a-zA-Z0-9_]+$'",
            name="ck_community_cache_name_format",
        ),
        # 质量评分范围约束
        CheckConstraint(
            "quality_score >= 0.00 AND quality_score <= 1.00",
            name="ck_community_cache_quality_range",
        ),
        # 爬虫优先级范围约束
        CheckConstraint(
            "crawl_priority >= 1 AND crawl_priority <= 100",
            name="ck_community_cache_priority_range",
        ),
        # 缓存容量非负约束
        CheckConstraint(
            "posts_cached >= 0", name="ck_community_cache_posts_non_negative"
        ),
        # TTL正数约束
        CheckConstraint("ttl_seconds > 0", name="ck_community_cache_ttl_positive"),
        # 命中次数非负约束
        CheckConstraint(
            "hit_count >= 0", name="ck_community_cache_hit_count_non_negative"
        ),
        # 表注释
        {"comment": ("社区缓存元数据表 - Reddit社区数据的缓存状态管理，" "支持LRU + TTL + Priority三重缓存策略")},
    )

    # ====================================================================
    # 业务逻辑方法：封装常用缓存操作
    # ====================================================================

    def is_expired(self) -> bool:
        """检查缓存是否已过期

        Returns:
            bool: True如果缓存已过期或从未抓取过
        """
        if self.last_crawled_at is None:
            return True  # 从未抓取，视为过期

        # mypy: self.ttl_seconds 是 ORM 字段，这里显式转换为 int
        expiry_time = self.last_crawled_at + timedelta(seconds=int(self.ttl_seconds))
        return datetime.utcnow() > expiry_time

    def increment_hit_count(self) -> None:
        """增加缓存命中计数

        注意：这只是增加Python对象的计数，需要调用session.commit()才能持久化
        数据库触发器会自动更新last_hit_at字段
        """
        self.hit_count += 1

    def update_cache_stats(
        self, posts_count: int, quality: Optional[float] = None
    ) -> None:
        """更新缓存统计信息

        Args:
            posts_count: 新缓存的帖子数量
            quality: 可选的质量评分更新
        """
        self.posts_cached = posts_count
        self.last_crawled_at = datetime.utcnow()

        if quality is not None:
            self.quality_score = Decimal(str(min(1.0, max(0.0, quality))))

    def get_priority_score(self) -> float:
        """计算综合优先级评分，用于调度决策

        综合考虑：爬虫优先级、缓存过期程度、访问热度

        Returns:
            float: 优先级评分，分数越高越应该优先抓取
        """
        # 基础优先级（1-100 转换为 100-1，数值越高越优先）
        base_score = 101 - int(self.crawl_priority)

        # 过期程度加权（过期时间越长，优先级越高）
        expiry_weight: float = 0.0
        if self.last_crawled_at:
            last_update = self.last_crawled_at
            hours_since_update = (
                datetime.utcnow() - last_update
            ).total_seconds() / 3600
            ttl_hours = float(int(self.ttl_seconds)) / 3600.0
            if hours_since_update > ttl_hours:
                expiry_weight = min(50.0, (hours_since_update - ttl_hours) * 2.0)
        else:
            expiry_weight = 100.0  # 从未抓取，最高加权

        # 访问热度加权（热度越高，优先级越高）
        heat_weight = min(20.0, float(int(self.hit_count)) * 0.1)

        return float(base_score) + expiry_weight + heat_weight

    def __repr__(self) -> str:
        """调试友好的字符串表示"""
        expiry_status = "过期" if self.is_expired() else "有效"
        return (
            f"<CommunityCache(name={self.community_name}, "
            f"posts={self.posts_cached}, quality={self.quality_score}, "
            f"hits={self.hit_count}, status={expiry_status})>"
        )

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        last_update = (
            "从未"
            if self.last_crawled_at is None
            else self.last_crawled_at.strftime("%m-%d %H:%M")
        )
        return (
            f"{self.community_name} (质量:{self.quality_score}, "
            f"帖子:{self.posts_cached}, 更新:{last_update})"
        )
