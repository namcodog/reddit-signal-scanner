"""
pytest配置和共享夹具
基于Linus原则和质量门禁Agent要求：

- 严格的数据库隔离：每个测试独立数据库会话
- 高性能测试夹具：会话级别的连接池复用
- 统计学严格的性能测试基础设施
- 完整的边界条件测试数据工厂
"""

import asyncio
import logging
import os
import uuid
from typing import Dict, Any, List, AsyncGenerator, Generator
from decimal import Decimal
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import User, Task, Analysis, Report, CommunityCache
from app.core.config import get_settings


# ============================================================================
# 1. 测试配置和环境设置
# ============================================================================

# 测试日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试数据库URL - 隔离的测试数据库
settings = get_settings()
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        settings.database_url.replace("reddit_scanner", "reddit_scanner_test")
        if hasattr(settings, "database_url")
        else "postgresql+asyncpg://test_user:test_pass@localhost:5432/reddit_scanner_test"
    ),
)

# 同步版本用于setup/teardown
TEST_DATABASE_URL_SYNC = TEST_DATABASE_URL.replace("+asyncpg", "")


# ============================================================================
# 2. 数据库夹具 - 严格隔离和性能优化
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """提供事件循环给整个测试会话"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """异步数据库引擎 - 会话级别复用"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,  # 测试时不输出SQL
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

        # 创建JSON Schema验证函数
        await conn.execute(
            text(
                """
        CREATE OR REPLACE FUNCTION validate_insights_schema(data jsonb)
        RETURNS boolean AS $$
        BEGIN
            -- 必须是对象类型
            IF jsonb_typeof(data) != 'object' THEN
                RETURN false;
            END IF;
            
            -- 必须包含三个核心字段
            IF NOT (data ? 'pain_points' AND data ? 'competitors' AND data ? 'opportunities') THEN
                RETURN false;
            END IF;
            
            -- 每个字段必须是数组
            IF jsonb_typeof(data->'pain_points') != 'array' OR
               jsonb_typeof(data->'competitors') != 'array' OR 
               jsonb_typeof(data->'opportunities') != 'array' THEN
                RETURN false;
            END IF;
            
            -- 验证pain_points结构
            IF EXISTS (
                SELECT 1 FROM jsonb_array_elements(data->'pain_points') AS item
                WHERE NOT (item ? 'description' AND item ? 'frequency' AND item ? 'sentiment_score')
            ) THEN
                RETURN false;
            END IF;
            
            RETURN true;
        END;
        $$ LANGUAGE plpgsql;
        """
            )
        )

        await conn.execute(
            text(
                """
        CREATE OR REPLACE FUNCTION validate_sources_schema(data jsonb)
        RETURNS boolean AS $$
        BEGIN
            IF jsonb_typeof(data) != 'object' THEN
                RETURN false;
            END IF;
            
            -- 必须包含核心溯源字段
            IF NOT (data ? 'communities' AND data ? 'posts_analyzed' AND data ? 'cache_hit_rate') THEN
                RETURN false;
            END IF;
            
            -- communities必须是数组
            IF jsonb_typeof(data->'communities') != 'array' THEN
                RETURN false;
            END IF;
            
            -- posts_analyzed必须是数字且为正数
            IF jsonb_typeof(data->'posts_analyzed') != 'number' OR 
               (data->>'posts_analyzed')::int <= 0 THEN
                RETURN false;
            END IF;
            
            -- cache_hit_rate必须是0-1之间的数字
            IF jsonb_typeof(data->'cache_hit_rate') != 'number' OR
               (data->>'cache_hit_rate')::float < 0 OR
               (data->>'cache_hit_rate')::float > 1 THEN
                RETURN false;
            END IF;
            
            RETURN true;
        END;
        $$ LANGUAGE plpgsql;
        """
            )
        )

        # 创建枚举类型
        await conn.execute(
            text(
                """
        DO $$ BEGIN
            CREATE TYPE task_status AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
            )
        )

    yield engine

    # 清理
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine):
    """数据库会话 - 函数级别隔离

    每个测试函数都有独立的数据库会话和事务
    测试结束后自动回滚，确保数据隔离
    """
    async with async_engine.begin() as conn:
        session_factory = sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False
        )

        async with session_factory() as session:
            yield session
            await session.rollback()  # 确保测试后清理


@pytest.fixture(scope="function")
def sync_db_session():
    """同步数据库会话 - 用于需要同步操作的测试"""
    engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        yield session
        session.rollback()


# ============================================================================
# 3. 性能测试基础设施 - 统计学严格
# ============================================================================


@pytest.fixture
def performance_timer():
    """性能计时器 - 支持统计学分析的多次测量"""
    import time
    import statistics

    class PerformanceTimer:
        def __init__(self):
            self.measurements: List[float] = []

        def measure_operation(self, operation, iterations=100):
            """测量操作多次执行的统计数据"""
            # 预热：消除JIT和缓存影响
            for _ in range(10):
                operation()

            # 实际测量
            for _ in range(iterations):
                start = time.perf_counter()
                operation()
                end = time.perf_counter()
                self.measurements.append((end - start) * 1000)  # 转换为毫秒

        def get_stats(self) -> Dict[str, float]:
            """获取统计数据"""
            if not self.measurements:
                return {}

            return {
                "mean": statistics.mean(self.measurements),
                "median": statistics.median(self.measurements),
                "stdev": (
                    statistics.stdev(self.measurements)
                    if len(self.measurements) > 1
                    else 0
                ),
                "min": min(self.measurements),
                "max": max(self.measurements),
                "p95": (
                    statistics.quantiles(self.measurements, n=20)[18]
                    if len(self.measurements) >= 20
                    else max(self.measurements)
                ),
                "p99": (
                    statistics.quantiles(self.measurements, n=100)[98]
                    if len(self.measurements) >= 100
                    else max(self.measurements)
                ),
                "count": len(self.measurements),
            }

        def assert_performance(self, target_ms: float, tolerance: float = 0.1):
            """断言性能目标达成"""
            stats = self.get_stats()
            mean_ms = stats.get("mean", float("inf"))
            p95_ms = stats.get("p95", float("inf"))

            assert mean_ms <= target_ms, (
                f"平均延迟{mean_ms:.2f}ms超过目标{target_ms}ms。" f"统计: {stats}"
            )
            assert p95_ms <= target_ms * (1 + tolerance), (
                f"P95延迟{p95_ms:.2f}ms超过容忍阈值{target_ms * (1 + tolerance):.2f}ms。"
                f"统计: {stats}"
            )

    return PerformanceTimer()


# ============================================================================
# 4. 测试数据工厂 - 边界条件优先
# ============================================================================


class DatabaseTestFactory:
    """数据库测试数据工厂

    基于Linus原则：消除特殊情况的数据工厂设计
    提供系统化的边界条件测试数据
    """

    @staticmethod
    def minimal_valid_user(**overrides) -> Dict[str, Any]:
        """最小有效用户 - 边界条件基准"""
        data = {
            "tenant_id": uuid.uuid4(),
            "email": "test@example.com",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",  # 'password'的BCrypt哈希
            "email_verified": False,
            "is_active": True,
        }
        data.update(overrides)
        return data

    @staticmethod
    def user_with_constraint_edge_cases() -> List[Dict[str, Any]]:
        """约束边界情况用户数据"""
        return [
            # 邮箱长度边界：320字符（RFC 5321限制）
            DatabaseTestFactory.minimal_valid_user(
                email="x" * 64 + "@" + "y" * 251 + ".com"  # 320字符
            ),
            # 最短有效邮箱
            DatabaseTestFactory.minimal_valid_user(email="a@b.co"),  # 5字符
            # 包含特殊字符的有效邮箱
            DatabaseTestFactory.minimal_valid_user(
                email="test.email+tag@sub.domain.com"
            ),
        ]

    @staticmethod
    def invalid_users_systematic() -> List[tuple[Dict[str, Any], str]]:
        """系统化无效用户数据 - 每种约束违反"""
        return [
            # 邮箱格式违反
            (
                {"email": "invalid-email", **DatabaseTestFactory.minimal_valid_user()},
                "ck_users_email_format",
            ),
            (
                {"email": "@domain.com", **DatabaseTestFactory.minimal_valid_user()},
                "ck_users_email_format",
            ),
            (
                {"email": "user@", **DatabaseTestFactory.minimal_valid_user()},
                "ck_users_email_format",
            ),
            (
                {"email": "user@domain", **DatabaseTestFactory.minimal_valid_user()},
                "ck_users_email_format",
            ),
            # 密码哈希格式违反
            (
                {
                    "password_hash": "plain-text",
                    **DatabaseTestFactory.minimal_valid_user(),
                },
                "ck_users_password_bcrypt",
            ),
            (
                {
                    "password_hash": "$2a$10$invalid",
                    **DatabaseTestFactory.minimal_valid_user(),
                },
                "ck_users_password_bcrypt",
            ),
            # NULL约束违反
            (
                {"tenant_id": None, **DatabaseTestFactory.minimal_valid_user()},
                "not-null",
            ),
            ({"email": None, **DatabaseTestFactory.minimal_valid_user()}, "not-null"),
        ]

    @staticmethod
    def minimal_valid_task(user_id: uuid.UUID, **overrides) -> Dict[str, Any]:
        """最小有效任务"""
        data = {
            "user_id": user_id,
            "product_description": "这是一个测试产品描述，长度符合要求",  # 刚好10字符以上
            "status": "pending",
            "error_message": None,
            "completed_at": None,
        }
        data.update(overrides)
        return data

    @staticmethod
    def task_description_edge_cases(user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """任务描述边界条件"""
        return [
            # 最短有效描述：10字符
            DatabaseTestFactory.minimal_valid_task(
                user_id, product_description="1234567890"
            ),
            # 最长有效描述：2000字符
            DatabaseTestFactory.minimal_valid_task(
                user_id, product_description="x" * 2000
            ),
            # 包含特殊字符
            DatabaseTestFactory.minimal_valid_task(
                user_id,
                product_description="测试产品包含特殊字符：@#$%^&*()_+-={}[]|\\:\";'<>?,./",
            ),
        ]

    @staticmethod
    def invalid_tasks_systematic(
        user_id: uuid.UUID,
    ) -> List[tuple[Dict[str, Any], str]]:
        """系统化无效任务数据"""
        return [
            # 描述长度违反
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, product_description="too_short"
                ),
                "ck_tasks_description_length",
            ),
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, product_description="x" * 2001
                ),
                "ck_tasks_description_length",
            ),
            # 状态一致性违反
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, status="failed", error_message=None
                ),
                "ck_tasks_error_message_when_failed",
            ),
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, status="pending", error_message="Some error"
                ),
                "ck_tasks_error_message_when_failed",
            ),
            # 完成时间一致性违反
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, status="pending", completed_at=datetime.now()
                ),
                "ck_tasks_completed_at_consistency",
            ),
            (
                DatabaseTestFactory.minimal_valid_task(
                    user_id, status="completed", completed_at=None
                ),
                "ck_tasks_completed_at_consistency",
            ),
        ]

    @staticmethod
    def valid_insights_data() -> Dict[str, Any]:
        """有效的洞察数据"""
        return {
            "pain_points": [
                {
                    "description": "找不到好用的Reddit营销工具",
                    "sentiment_score": 0.75,
                    "frequency": 23,
                    "evidence_posts": ["post_123"],
                    "categories": ["工具缺失"],
                }
            ],
            "competitors": [
                {
                    "name": "Hootsuite",
                    "mention_count": 45,
                    "sentiment_score": 0.65,
                    "strengths": ["功能全面"],
                    "weaknesses": ["价格昂贵"],
                    "price_mentions": ["$99/month"],
                    "market_position": "leader",
                }
            ],
            "opportunities": [
                {
                    "title": "Reddit自动化工具",
                    "description": "自动化Reddit内容发布管理",
                    "market_size_indicator": "large",
                    "urgency_score": 0.85,
                    "feasibility_score": 0.70,
                    "target_communities": ["r/entrepreneur"],
                    "related_keywords": ["automation"],
                    "estimated_demand": 2500,
                }
            ],
            "analysis_summary": {"total_mentions": 100},
            "key_insights": ["主要需求是自动化"],
        }

    @staticmethod
    def valid_sources_data() -> Dict[str, Any]:
        """有效的数据来源"""
        return {
            "communities": ["r/entrepreneur", "r/marketing"],
            "posts_analyzed": 1250,
            "comments_analyzed": 8450,
            "time_range_days": 30,
            "cache_hit_rate": 0.75,
            "analysis_duration_seconds": 45.6,
            "reddit_api_calls": 125,
            "data_quality_score": 0.92,
            "filtered_spam_posts": 23,
            "language_distribution": {"en": 1200, "es": 50},
            "algorithm_version": "v2.1.0",
            "processing_parameters": {
                "min_score_threshold": 5,
                "sentiment_model": "vader",
            },
        }

    @staticmethod
    def minimal_valid_analysis(task_id: uuid.UUID, **overrides) -> Dict[str, Any]:
        """最小有效分析数据"""
        data = {
            "task_id": task_id,
            "insights": DatabaseTestFactory.valid_insights_data(),
            "sources": DatabaseTestFactory.valid_sources_data(),
            "confidence_score": Decimal("0.85"),
            "analysis_version": 1,
        }
        data.update(overrides)
        return data


@pytest.fixture
def test_data_factory():
    """测试数据工厂夹具"""
    return DatabaseTestFactory


# ============================================================================
# 5. 多租户测试支持
# ============================================================================


@pytest_asyncio.fixture
async def multi_tenant_setup(db_session):
    """多租户测试环境设置"""
    # 创建两个不同租户的用户
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    user_a = User(
        **DatabaseTestFactory.minimal_valid_user(
            tenant_id=tenant_a_id, email="user_a@tenant_a.com"
        )
    )
    user_b = User(
        **DatabaseTestFactory.minimal_valid_user(
            tenant_id=tenant_b_id, email="user_b@tenant_b.com"
        )
    )

    db_session.add_all([user_a, user_b])
    await db_session.commit()

    return {
        "tenant_a": {"user": user_a, "tenant_id": tenant_a_id},
        "tenant_b": {"user": user_b, "tenant_id": tenant_b_id},
    }


# ============================================================================
# 6. 测试工具函数
# ============================================================================


def assert_constraint_violation(exception, constraint_name: str):
    """断言特定约束违反"""
    error_msg = str(exception.value)
    assert (
        constraint_name in error_msg
    ), f"期望约束违反 '{constraint_name}'，实际错误: {error_msg}"


def assert_performance_target(
    stats: Dict[str, float], target_ms: float, operation_name: str
):
    """断言性能目标达成 - 统计学严格"""
    mean_ms = stats.get("mean", float("inf"))
    p95_ms = stats.get("p95", float("inf"))
    p99_ms = stats.get("p99", float("inf"))

    # 平均延迟必须达标
    assert mean_ms <= target_ms, (
        f"{operation_name} 平均延迟{mean_ms:.2f}ms超过目标{target_ms}ms。"
        f"统计数据: {stats}"
    )

    # P95延迟不超过目标的120%
    assert p95_ms <= target_ms * 1.2, (
        f"{operation_name} P95延迟{p95_ms:.2f}ms超过容忍阈值{target_ms * 1.2:.2f}ms。"
        f"统计数据: {stats}"
    )

    # P99延迟不超过目标的150%
    assert p99_ms <= target_ms * 1.5, (
        f"{operation_name} P99延迟{p99_ms:.2f}ms超过最大阈值{target_ms * 1.5:.2f}ms。"
        f"统计数据: {stats}"
    )


# ============================================================================
# 7. FastAPI TestClient配置 - API集成测试
# ============================================================================


@pytest.fixture
def client():
    """FastAPI测试客户端 - API集成测试专用

    配置测试环境的FastAPI应用实例
    包含所有中间件和路由配置
    """
    from fastapi.testclient import TestClient
    from app.main import app

    # 使用测试配置覆盖生产设置
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def api_client():
    """异步HTTP客户端 - 用于SSE等异步API测试"""
    import httpx

    async with httpx.AsyncClient(
        base_url="http://testserver", timeout=30.0, follow_redirects=True
    ) as async_client:
        yield async_client


# 导出给测试使用
__all__ = [
    "db_session",
    "sync_db_session",
    "async_engine",
    "client",
    "api_client",
    "performance_timer",
    "test_data_factory",
    "multi_tenant_setup",
    "DatabaseTestFactory",
    "assert_constraint_violation",
    "assert_performance_target",
]
