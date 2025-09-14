"""Mock服务工厂 - 提供一致的Mock服务实现

基于契约测试原则：Mock必须与真实API保持一致
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ==================== Mock数据模型 ====================
class MockRedditPost(BaseModel):
    """Mock Reddit帖子"""
    id: str
    title: str
    content: str
    subreddit: str
    author: str
    score: int
    num_comments: int
    created_utc: datetime
    upvote_ratio: float = 0.95
    
    @classmethod
    def from_keyword(cls, keyword: str, index: int = 0) -> "MockRedditPost":
        """基于关键词生成确定性的Mock数据"""
        # 使用关键词的hash生成确定性但看起来随机的数据
        seed = hash(f"{keyword}_{index}") % 10000
        
        return cls(
            id=f"mock_post_{seed}",
            title=f"Discussion about {keyword} - Post {index + 1}",
            content=f"This is a detailed discussion about {keyword}. "
                   f"Many users find {keyword} very useful for their business. "
                   f"The community has been asking for better {keyword} solutions.",
            subreddit=random.choice(["entrepreneur", "startups", "business", "technology"]),
            author=f"mock_user_{seed % 100}",
            score=seed % 1000,
            num_comments=seed % 200,
            created_utc=datetime.now() - timedelta(days=seed % 30),
            upvote_ratio=0.7 + (seed % 30) / 100
        )


class MockAnalysisResult(BaseModel):
    """Mock分析结果"""
    task_id: str
    status: str
    progress: int
    insights: Dict[str, Any]
    sources: Dict[str, Any]
    confidence_score: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    

# ==================== Mock服务基类 ====================
class MockServiceBase:
    """Mock服务基类 - 提供通用功能"""
    
    def __init__(self):
        self.call_count = 0
        self.delay_enabled = True
        self.error_rate = 0.0  # 模拟错误的概率
        
    async def simulate_delay(self, min_ms: int = 10, max_ms: int = 50):
        """模拟网络延迟"""
        if self.delay_enabled:
            delay = random.randint(min_ms, max_ms) / 1000
            await asyncio.sleep(delay)
            
    def should_fail(self) -> bool:
        """根据错误率决定是否失败"""
        return random.random() < self.error_rate
        
    def increment_call_count(self):
        """增加调用计数"""
        self.call_count += 1


# ==================== Reddit Mock服务 ====================
class MockRedditClient(MockServiceBase):
    """Mock Reddit客户端"""
    
    def __init__(self):
        super().__init__()
        self.posts_cache: Dict[str, List[MockRedditPost]] = {}
        
    async def search_posts(
        self, 
        keywords: List[str], 
        limit: int = 50,
        subreddits: Optional[List[str]] = None
    ) -> List[MockRedditPost]:
        """搜索Reddit帖子"""
        self.increment_call_count()
        await self.simulate_delay(50, 200)
        
        if self.should_fail():
            raise Exception("Reddit API暂时不可用")
            
        # 为每个关键词生成帖子
        posts = []
        for keyword in keywords:
            if keyword not in self.posts_cache:
                # 生成确定性的帖子数据
                keyword_posts = [
                    MockRedditPost.from_keyword(keyword, i) 
                    for i in range(min(10, limit // len(keywords)))
                ]
                self.posts_cache[keyword] = keyword_posts
            
            posts.extend(self.posts_cache[keyword])
            
        # 如果指定了subreddit，进行过滤
        if subreddits:
            posts = [p for p in posts if p.subreddit in subreddits]
            
        # 按分数排序并限制数量
        posts.sort(key=lambda p: p.score, reverse=True)
        return posts[:limit]
    
    async def get_post_details(self, post_id: str) -> Optional[MockRedditPost]:
        """获取帖子详情"""
        self.increment_call_count()
        await self.simulate_delay(30, 100)
        
        # 从缓存中查找
        for posts in self.posts_cache.values():
            for post in posts:
                if post.id == post_id:
                    return post
        return None


# ==================== 分析服务Mock ====================
class MockAnalysisService(MockServiceBase):
    """Mock分析服务"""
    
    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, MockAnalysisResult] = {}
        
    async def create_analysis_task(
        self, 
        keywords: List[str],
        user_id: str
    ) -> MockAnalysisResult:
        """创建分析任务"""
        self.increment_call_count()
        await self.simulate_delay(10, 50)
        
        if self.should_fail():
            raise Exception("无法创建分析任务")
            
        task_id = str(uuid.uuid4())
        result = MockAnalysisResult(
            task_id=task_id,
            status="pending",
            progress=0,
            insights=self._generate_mock_insights(keywords),
            sources=self._generate_mock_sources(keywords),
            confidence_score=0.85 + random.random() * 0.1,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = result
        return result
    
    async def get_task_status(self, task_id: str) -> Optional[MockAnalysisResult]:
        """获取任务状态"""
        self.increment_call_count()
        await self.simulate_delay(5, 20)
        
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        
        # 模拟任务进度
        if task.status == "pending":
            task.status = "running"
            task.progress = 30
        elif task.status == "running":
            task.progress = min(100, task.progress + 30)
            if task.progress >= 100:
                task.status = "completed"
                task.completed_at = datetime.now()
                
        return task
    
    def _generate_mock_insights(self, keywords: List[str]) -> Dict[str, Any]:
        """生成Mock洞察数据"""
        return {
            "pain_points": [
                {
                    "description": f"用户需要更好的{keyword}解决方案",
                    "sentiment_score": 0.75,
                    "frequency": random.randint(10, 50),
                    "evidence_posts": [f"post_{i}" for i in range(3)]
                }
                for keyword in keywords[:3]
            ],
            "opportunities": [
                {
                    "title": f"{keyword}自动化工具",
                    "description": f"开发{keyword}相关的自动化工具",
                    "market_size_indicator": "large",
                    "urgency_score": 0.8,
                    "feasibility_score": 0.7
                }
                for keyword in keywords[:2]
            ]
        }
    
    def _generate_mock_sources(self, keywords: List[str]) -> Dict[str, Any]:
        """生成Mock数据源信息"""
        return {
            "communities": ["r/entrepreneur", "r/startups"],
            "posts_analyzed": random.randint(100, 500),
            "comments_analyzed": random.randint(500, 2000),
            "time_range_days": 30,
            "algorithm_version": "v2.1.0"
        }


# ==================== 认证服务Mock ====================
class MockAuthService(MockServiceBase):
    """Mock认证服务"""
    
    def __init__(self):
        super().__init__()
        self.users: Dict[str, Dict[str, Any]] = {
            "test@example.com": {
                "id": str(uuid.uuid4()),
                "email": "test@example.com",
                "password": "password123",  # 明文仅用于测试
                "is_active": True
            }
        }
        self.tokens: Dict[str, str] = {}  # token -> user_id
        
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        self.increment_call_count()
        await self.simulate_delay(20, 100)
        
        if self.should_fail():
            raise Exception("认证服务暂时不可用")
            
        user = self.users.get(email)
        if not user or user["password"] != password:
            raise ValueError("用户名或密码错误")
            
        # 生成token
        token = f"mock_token_{uuid.uuid4()}"
        self.tokens[token] = user["id"]
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["id"]
        }
    
    async def verify_token(self, token: str) -> Optional[str]:
        """验证token"""
        self.increment_call_count()
        await self.simulate_delay(5, 20)
        
        return self.tokens.get(token)


# ==================== Mock服务工厂 ====================
class MockServiceFactory:
    """Mock服务工厂 - 统一管理所有Mock服务"""
    
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def get_reddit_client(cls) -> MockRedditClient:
        """获取Reddit客户端实例"""
        if "reddit" not in cls._instances:
            cls._instances["reddit"] = MockRedditClient()
        return cls._instances["reddit"]
    
    @classmethod
    def get_analysis_service(cls) -> MockAnalysisService:
        """获取分析服务实例"""
        if "analysis" not in cls._instances:
            cls._instances["analysis"] = MockAnalysisService()
        return cls._instances["analysis"]
    
    @classmethod
    def get_auth_service(cls) -> MockAuthService:
        """获取认证服务实例"""
        if "auth" not in cls._instances:
            cls._instances["auth"] = MockAuthService()
        return cls._instances["auth"]
    
    @classmethod
    def reset_all(cls):
        """重置所有Mock服务"""
        cls._instances.clear()
    
    @classmethod
    def configure_error_rates(cls, error_rate: float = 0.0):
        """配置所有服务的错误率"""
        for service in cls._instances.values():
            if hasattr(service, 'error_rate'):
                service.error_rate = error_rate
    
    @classmethod
    def get_call_stats(cls) -> Dict[str, int]:
        """获取所有服务的调用统计"""
        stats = {}
        for name, service in cls._instances.items():
            if hasattr(service, 'call_count'):
                stats[name] = service.call_count
        return stats


# ==================== 测试数据生成器 ====================
class TestDataGenerator:
    """测试数据生成器 - 生成各种边界条件的测试数据"""
    
    @staticmethod
    def generate_edge_case_keywords() -> List[List[str]]:
        """生成边界条件的关键词组合"""
        return [
            # 正常情况
            ["python", "fastapi", "react"],
            # 单个关键词
            ["entrepreneur"],
            # 大量关键词
            ["keyword" + str(i) for i in range(20)],
            # 特殊字符
            ["test@example", "keyword#tag", "search?query"],
            # Unicode字符
            ["测试", "テスト", "тест"],
            # 空字符串（应该被过滤）
            ["", "valid", ""],
            # 超长关键词
            ["a" * 100],
        ]
    
    @staticmethod
    def generate_invalid_inputs() -> List[Any]:
        """生成无效输入用于测试"""
        return [
            None,
            [],
            {},
            "",
            " ",
            [""],
            [" " * 10],
            [None],
            123,
            True,
        ]


# ==================== 导出 ====================
__all__ = [
    # Mock服务
    "MockRedditClient",
    "MockAnalysisService", 
    "MockAuthService",
    "MockServiceFactory",
    
    # 数据模型
    "MockRedditPost",
    "MockAnalysisResult",
    
    # 工具类
    "TestDataGenerator",
]