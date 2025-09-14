"""
SQLite兼容的数据库模型单元测试

基于SQLAlchemy最佳实践，专门为SQLite测试环境设计
避免SQLite不支持的特性（正则表达式、UUID类型等）
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
import pytest
import pytest_asyncio
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import StaticPool

from tests.fixtures.base_fixtures import TestIsolation

# 创建SQLite专用的Base类
SQLiteBase = declarative_base()


class SQLiteUser(SQLiteBase):
    """SQLite兼容的用户模型"""
    
    __tablename__ = "test_users"
    
    # 使用String类型替代UUID
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), nullable=False)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)


class SQLiteTask(SQLiteBase):
    """SQLite兼容的任务模型"""
    
    __tablename__ = "test_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    product_description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)


class SQLiteAnalysis(SQLiteBase):
    """SQLite兼容的分析模型"""
    
    __tablename__ = "test_analyses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), nullable=False)
    # 在SQLite中使用Text存储JSON，避免JSONB复杂性
    insights = Column(Text, nullable=False)  # JSON as string
    sources = Column(Text, nullable=False)   # JSON as string
    confidence_score = Column(Numeric(3, 2), nullable=False)
    analysis_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


# SQLite测试专用的fixtures
@pytest_asyncio.fixture(scope="function")
async def sqlite_engine():
    """创建SQLite内存数据库引擎"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(SQLiteBase.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def sqlite_session(sqlite_engine):
    """创建SQLite测试会话"""
    async_session_factory = sessionmaker(
        bind=sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        yield session


class TestSQLiteUserModel:
    """SQLite用户模型测试"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_user_creation(self, sqlite_session: AsyncSession):
        """测试用户创建"""
        user = SQLiteUser(
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        # 验证基本字段
        assert user.id is not None
        assert user.tenant_id is not None
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.email_verified is False
        assert isinstance(user.created_at, datetime)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_user_field_types(self, sqlite_session: AsyncSession):
        """测试字段类型"""
        user = SQLiteUser(
            email="types@example.com",
            password_hash="test_hash"
        )
        
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        # 验证字段类型
        assert isinstance(user.id, str)
        assert isinstance(user.tenant_id, str)
        assert isinstance(user.email, str)
        assert isinstance(user.email_verified, bool)
        assert isinstance(user.is_active, bool)
        assert isinstance(user.created_at, datetime)


class TestSQLiteTaskModel:
    """SQLite任务模型测试"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_creation(self, sqlite_session: AsyncSession):
        """测试任务创建"""
        # 先创建用户
        user = SQLiteUser(
            email="task_test@example.com",
            password_hash="test_hash"
        )
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        # 创建任务
        task = SQLiteTask(
            product_description="Test product",
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        
        sqlite_session.add(task)
        await sqlite_session.commit()
        await sqlite_session.refresh(task)
        
        # 验证任务
        assert task.id is not None
        assert task.user_id == user.id
        assert task.tenant_id == user.tenant_id
        assert task.product_description == "Test product"
        assert task.status == "pending"
        assert task.retry_count == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_status_update(self, sqlite_session: AsyncSession):
        """测试任务状态更新"""
        user = SQLiteUser(
            email="status_test@example.com",
            password_hash="test_hash"
        )
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        task = SQLiteTask(
            product_description="Status test",
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        sqlite_session.add(task)
        await sqlite_session.commit()
        
        # 更新状态
        task.status = "completed"
        task.completed_at = datetime.now()
        await sqlite_session.commit()
        
        assert task.status == "completed"
        assert task.completed_at is not None


class TestSQLiteAnalysisModel:
    """SQLite分析模型测试"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analysis_creation(self, sqlite_session: AsyncSession):
        """测试分析创建"""
        # 创建用户和任务
        user = SQLiteUser(
            email="analysis_test@example.com",
            password_hash="test_hash"
        )
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        task = SQLiteTask(
            product_description="Analysis test",
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        sqlite_session.add(task)
        await sqlite_session.commit()
        await sqlite_session.refresh(task)
        
        # 创建分析（JSON存储为字符串）
        import json
        insights_data = {
            "pain_points": [{"title": "Test point", "confidence": 0.8}],
            "competitors": [],
            "opportunities": []
        }
        sources_data = {
            "subreddits": ["r/test"],
            "total_posts": 10
        }
        
        analysis = SQLiteAnalysis(
            task_id=task.id,
            insights=json.dumps(insights_data),
            sources=json.dumps(sources_data),
            confidence_score=Decimal("0.85")
        )
        
        sqlite_session.add(analysis)
        await sqlite_session.commit()
        await sqlite_session.refresh(analysis)
        
        # 验证分析
        assert analysis.id is not None
        assert analysis.task_id == task.id
        assert analysis.confidence_score == Decimal("0.85")
        assert analysis.analysis_version == 1
        
        # 验证JSON数据
        parsed_insights = json.loads(analysis.insights)
        assert len(parsed_insights["pain_points"]) == 1
        assert parsed_insights["pain_points"][0]["title"] == "Test point"


class TestSQLiteModelRelationships:
    """SQLite模型关系测试"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_user_task_relationship(self, sqlite_session: AsyncSession):
        """测试用户任务关系"""
        # 创建用户
        user = SQLiteUser(
            email="relationship@example.com",
            password_hash="test_hash"
        )
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        # 创建多个任务
        tasks = []
        for i in range(3):
            task = SQLiteTask(
                product_description=f"Task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id
            )
            tasks.append(task)
        
        sqlite_session.add_all(tasks)
        await sqlite_session.commit()
        
        # 查询用户的任务
        from sqlalchemy import select
        result = await sqlite_session.execute(
            select(SQLiteTask).where(SQLiteTask.user_id == user.id)
        )
        user_tasks = result.scalars().all()
        
        assert len(user_tasks) == 3
        for task in user_tasks:
            assert task.user_id == user.id
            assert task.tenant_id == user.tenant_id
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_analysis_relationship(self, sqlite_session: AsyncSession):
        """测试任务分析关系"""
        import json
        
        # 创建用户、任务、分析
        user = SQLiteUser(
            email="task_analysis@example.com",
            password_hash="test_hash"
        )
        sqlite_session.add(user)
        await sqlite_session.commit()
        await sqlite_session.refresh(user)
        
        task = SQLiteTask(
            product_description="Relationship test",
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        sqlite_session.add(task)
        await sqlite_session.commit()
        await sqlite_session.refresh(task)
        
        analysis = SQLiteAnalysis(
            task_id=task.id,
            insights=json.dumps({"test": "data"}),
            sources=json.dumps({"test": "source"}),
            confidence_score=Decimal("0.90")
        )
        sqlite_session.add(analysis)
        await sqlite_session.commit()
        
        # 验证关系
        from sqlalchemy import select
        result = await sqlite_session.execute(
            select(SQLiteAnalysis).where(SQLiteAnalysis.task_id == task.id)
        )
        task_analysis = result.scalar_one_or_none()
        
        assert task_analysis is not None
        assert task_analysis.task_id == task.id
        assert task_analysis.confidence_score == Decimal("0.90")
