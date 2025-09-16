"""
数据库模型单元测试配置

提供数据库测试所需的fixtures和工具类
遵循项目的类型安全和简洁性原则
"""

import os
import asyncio
import functools
from typing import AsyncGenerator, Awaitable, Callable, Generator, ParamSpec, TypeVar
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.models.analysis import Analysis

# 测试数据库配置
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SYNC_DATABASE_URL = "sqlite:///test.db"


P = ParamSpec("P")
R = TypeVar("R")


@pytest_asyncio.fixture(scope="function")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """创建异步数据库引擎 - 内存SQLite"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """创建异步数据库会话"""
    async_session_factory = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session


@pytest.fixture(scope="function")
def sync_engine() -> Generator[Engine, None, None]:
    """创建同步数据库引擎 - 用于同步测试"""
    engine = create_engine(
        TEST_SYNC_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    yield engine

    # 清理
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture
def sample_user_data() -> dict:
    """生成示例用户数据"""
    return {
        "email": "test@example.com",
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # BCrypt格式
        "email_verified": False,
        "is_active": True,
    }


@pytest.fixture
def sample_task_data() -> dict:
    """生成示例任务数据"""
    return {
        "product_description": "An AI-powered task management app",
        "status": TaskStatus.PENDING,
        "created_at": datetime.now(),
    }


@pytest.fixture
def sample_analysis_data() -> dict:
    """生成示例分析数据"""
    return {
        "insights": {
            "pain_points": [
                {
                    "title": "Complex setup process",
                    "description": "Users find the initial setup confusing",
                    "confidence": 0.85,
                    "source_count": 15
                }
            ],
            "competitors": [
                {
                    "name": "Competitor A",
                    "strengths": ["Easy to use", "Good pricing"],
                    "weaknesses": ["Limited features", "Poor support"],
                    "confidence": 0.78
                }
            ],
            "opportunities": [
                {
                    "title": "Mobile-first experience",
                    "description": "Strong demand for mobile apps",
                    "market_size": "large",
                    "confidence": 0.92
                }
            ]
        },
        "sources": {
            "subreddits": ["r/productivity", "r/apps"],
            "total_posts": 150,
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-12-31"
            }
        }
    }


class ModelTestHelpers:
    """模型测试辅助工具类"""

    @staticmethod
    def create_test_user(session: AsyncSession, **kwargs) -> User:
        """创建测试用户实例（不保存到数据库）"""
        default_data = {
            "email": f"user_{uuid.uuid4().hex[:8]}@test.com",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            "email_verified": False,
            "is_active": True,
        }
        default_data.update(kwargs)
        return User(**default_data)

    @staticmethod
    def create_test_task(user: User, **kwargs) -> Task:
        """创建测试任务实例（不保存到数据库）"""
        default_data = {
            "product_description": "Test product description",
            "status": TaskStatus.PENDING,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
        }
        default_data.update(kwargs)
        return Task(**default_data)

    @staticmethod
    def assert_user_valid(user: User) -> None:
        """断言用户对象有效"""
        assert user.id is not None
        assert user.tenant_id is not None
        assert user.email is not None
        assert "@" in user.email
        assert user.password_hash is not None
        assert len(user.password_hash) > 50  # BCrypt哈希长度检查
        assert user.created_at is not None
        assert user.updated_at is not None

    @staticmethod
    def assert_task_valid(task: Task) -> None:
        """断言任务对象有效"""
        assert task.id is not None
        assert task.user_id is not None
        assert task.tenant_id is not None
        assert task.product_description is not None
        assert len(task.product_description.strip()) > 0
        assert task.status in TaskStatus
        assert task.created_at is not None


@pytest.fixture
def model_helpers() -> ModelTestHelpers:
    """提供模型测试辅助工具"""
    return ModelTestHelpers()


# 性能测试装饰器
def performance_test(max_duration: float) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """性能测试装饰器"""
    def decorator(test_func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(test_func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            import time

            start_time = time.time()
            try:
                return await test_func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                assert duration <= max_duration, (
                    f"测试性能不达标: {duration:.3f}s > {max_duration}s"
                )

        return wrapper

    return decorator
