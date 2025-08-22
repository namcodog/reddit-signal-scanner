# PRD-06: 用户认证系统

## 1. 问题陈述

### 1.1 背景
Reddit Signal Scanner作为SaaS产品，**必须从第一天就支持多租户架构**。用户数据完全隔离，每个用户只能访问自己的分析任务和报告。同时，认证系统必须简单可靠，不能成为用户使用产品的障碍。

**关键设计约束**：
- 数据库中已有user_id字段，认证系统必须与现有架构兼容
- 支持未来的订阅和计费集成
- 无状态设计，支持水平扩展
- 30秒注册流程，降低用户门槛

### 1.2 目标
设计基于JWT的无状态认证系统：
- **即时多租户**：从第一天就支持用户数据隔离
- **简单注册**：邮箱+密码，30秒完成注册
- **无状态认证**：JWT令牌，无需session存储
- **安全设计**：密码加密，令牌过期，HTTPS强制
- **扩展预留**：为未来的OAuth和订阅系统预留接口

### 1.3 非目标
- **不支持**社交登录（初版保持简单）
- **不支持**复杂的权限系统（租户隔离足够）
- **不支持**单点登录SSO（面向个人用户）
- **不支持**多因素认证（初版专注核心功能）

## 2. 解决方案

### 2.1 核心设计：JWT无状态认证

采用行业标准的JWT认证模式，实现完全无状态的用户会话管理：

```
注册/登录 → JWT签发 → 请求验证 → 数据隔离
    ↓           ↓          ↓          ↓
  用户表        令牌        中间件      user_id过滤
```

**认证流程**：
1. 用户注册：邮箱+密码创建账户，立即签发JWT
2. 用户登录：验证密码，签发新JWT（旧token失效）
3. API请求：每个请求携带JWT，中间件验证并提取user_id
4. 数据访问：所有查询自动添加user_id过滤条件

### 2.2 数据模型

基于已有的数据架构，新增users表：

```sql
-- 用户账户表（与Task表的user_id关联）
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- 订阅相关字段（预留）
    subscription_tier VARCHAR(50) DEFAULT 'free',
    subscription_expires_at TIMESTAMP,
    
    -- 索引
    CONSTRAINT users_email_unique UNIQUE (email)
);

-- 为性能优化创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;
```

**设计决策**：
- **UUID主键**：避免用户ID可预测，增强安全性
- **邮箱唯一**：作为登录标识符，符合用户习惯
- **密码散列**：使用bcrypt，防止彩虹表攻击
- **软删除**：is_active字段，保留数据但禁用访问

### 2.3 JWT令牌设计

```python
# JWT Payload 结构
{
    "user_id": "uuid-string",
    "email": "user@example.com",
    "subscription_tier": "free",
    "iat": 1642500000,  # 签发时间
    "exp": 1642586400,  # 过期时间（24小时）
    "iss": "reddit-signal-scanner",  # 签发者
    "sub": "user-authentication"     # 主题
}
```

**安全设计**：
- **短期有效**：24小时过期，平衡安全与用户体验
- **签名验证**：HMAC-SHA256算法，防止令牌伪造
- **声明最小**：只包含必要信息，减少泄露风险

## 3. 技术规范

### 3.1 认证API设计

```python
# api/v1/endpoints/auth.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
import bcrypt
import jwt
from datetime import datetime, timedelta

router = APIRouter()
security = HTTPBearer()

@router.post("/register")
async def register_user(request: RegisterRequest):
    """用户注册"""
    # 验证邮箱格式
    if not is_valid_email(request.email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    
    # 验证密码强度
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要8个字符")
    
    # 检查邮箱是否已存在
    with get_db() as db:
        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?", (request.email,)
        ).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        
        # 创建新用户
        password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt())
        user_id = str(uuid.uuid4())
        
        db.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, request.email, password_hash)
        )
    
    # 立即签发JWT
    token = create_jwt_token(user_id, request.email)
    
    return {
        "message": "注册成功",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": request.email
        }
    }

@router.post("/login")
async def login_user(request: LoginRequest):
    """用户登录"""
    with get_db() as db:
        user = db.execute(
            "SELECT id, email, password_hash, is_active FROM users WHERE email = ?",
            (request.email,)
        ).fetchone()
        
        if not user or not user["is_active"]:
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        
        # 验证密码
        if not bcrypt.checkpw(request.password.encode(), user["password_hash"]):
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        
        # 更新最后登录时间
        db.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],)
        )
    
    # 签发新JWT
    token = create_jwt_token(user["id"], user["email"])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"]
        }
    }

def create_jwt_token(user_id: str, email: str) -> str:
    """创建JWT令牌"""
    payload = {
        "user_id": user_id,
        "email": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iss": "reddit-signal-scanner",
        "sub": "user-authentication"
    }
    
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
```

### 3.2 认证中间件

```python
# middleware/auth.py
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
import jwt

class JWTAuthMiddleware:
    """JWT认证中间件，自动验证并注入用户信息"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request):
        # 排除不需要认证的路径
        if request.url.path in ["/api/auth/register", "/api/auth/login", "/health"]:
            return
        
        # 提取JWT令牌
        token = await self.security(request)
        if not token:
            raise HTTPException(status_code=401, detail="认证令牌缺失")
        
        try:
            # 验证并解析JWT
            payload = jwt.decode(
                token.credentials,
                JWT_SECRET_KEY,
                algorithms=["HS256"],
                issuer="reddit-signal-scanner"
            )
            
            # 验证用户是否仍然活跃
            with get_db() as db:
                user = db.execute(
                    "SELECT is_active FROM users WHERE id = ?",
                    (payload["user_id"],)
                ).fetchone()
                
                if not user or not user["is_active"]:
                    raise HTTPException(status_code=401, detail="用户账户已禁用")
            
            # 将用户信息注入请求上下文
            request.state.current_user = {
                "id": payload["user_id"],
                "email": payload["email"]
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="认证令牌已过期")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="认证令牌无效")

# 依赖注入函数，用于获取当前用户
def get_current_user(request: Request):
    """获取当前认证用户信息"""
    if not hasattr(request.state, 'current_user'):
        raise HTTPException(status_code=401, detail="用户未认证")
    return request.state.current_user
```

### 3.3 多租户数据隔离

```python
# services/tenant_filter.py
class TenantFilterMixin:
    """多租户数据隔离混入类"""
    
    def get_user_tasks(self, user_id: str):
        """获取用户的所有任务"""
        with get_db() as db:
            return db.execute(
                "SELECT * FROM task WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
    
    def get_user_analysis(self, user_id: str, task_id: str):
        """获取用户的特定分析结果"""
        with get_db() as db:
            return db.execute(
                """
                SELECT a.* FROM analysis a
                JOIN task t ON a.task_id = t.id
                WHERE t.user_id = ? AND a.task_id = ?
                """,
                (user_id, task_id)
            ).fetchone()
    
    def verify_task_ownership(self, user_id: str, task_id: str) -> bool:
        """验证任务是否属于当前用户"""
        with get_db() as db:
            task = db.execute(
                "SELECT user_id FROM task WHERE id = ?",
                (task_id,)
            ).fetchone()
            
            return task and task["user_id"] == user_id

# 更新API端点以使用租户过滤
@router.get("/status/{task_id}")
async def get_task_status(task_id: str, current_user = Depends(get_current_user)):
    """查询任务状态（多租户安全）"""
    tenant_filter = TenantFilterMixin()
    
    # 验证任务所有权
    if not tenant_filter.verify_task_ownership(current_user["id"], task_id):
        raise HTTPException(status_code=404, detail="任务未找到")
    
    # 获取任务状态
    with get_db() as db:
        task = db.execute(
            "SELECT status, created_at, started_at, completed_at FROM task WHERE id = ? AND user_id = ?",
            (task_id, current_user["id"])
        ).fetchone()
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "created_at": task["created_at"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"]
    }
```

### 3.4 前端认证集成

```jsx
// src/services/auth.js
class AuthService {
    constructor() {
        this.token = localStorage.getItem('access_token');
        this.user = JSON.parse(localStorage.getItem('user') || 'null');
    }
    
    async register(email, password) {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            this.setAuthData(data);
            return data;
        } else {
            const error = await response.json();
            throw new Error(error.detail);
        }
    }
    
    async login(email, password) {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            this.setAuthData(data);
            return data;
        } else {
            const error = await response.json();
            throw new Error(error.detail);
        }
    }
    
    setAuthData(data) {
        this.token = data.access_token;
        this.user = data.user;
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
    }
    
    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
    }
    
    isAuthenticated() {
        return !!this.token;
    }
    
    getAuthHeader() {
        return this.token ? { Authorization: `Bearer ${this.token}` } : {};
    }
}

export const authService = new AuthService();
```

## 4. 验收标准

### 4.1 功能要求

**用户注册**：
- ✅ 邮箱格式验证（支持常见邮箱格式）
- ✅ 密码强度验证（至少8个字符）
- ✅ 重复邮箱检查（返回清晰错误信息）
- ✅ 注册成功后立即签发JWT
- ✅ 用户数据写入users表，user_id为UUID

**用户登录**：
- ✅ 邮箱和密码验证
- ✅ 密码错误返回通用错误（防止邮箱枚举）
- ✅ 登录成功签发新JWT，更新last_login_at
- ✅ 禁用用户无法登录

**JWT认证**：
- ✅ 每个API请求验证JWT有效性
- ✅ 过期令牌自动拒绝，返回401状态码
- ✅ 伪造令牌自动拒绝
- ✅ 用户信息正确注入请求上下文

**多租户隔离**：
- ✅ 用户只能访问自己的任务和报告
- ✅ 跨租户访问返回404（而不是403）
- ✅ 所有查询自动添加user_id过滤
- ✅ 任务创建时正确关联user_id

### 4.2 安全指标

| 安全项 | 要求 | 验证方法 |
|--------|------|----------|
| 密码存储 | bcrypt散列，cost≥12 | 代码审查 |
| JWT密钥 | 至少256位随机密钥 | 配置检查 |
| 令牌过期 | 24小时自动过期 | 时间戳验证 |
| HTTPS强制 | 生产环境必须HTTPS | 部署检查 |
| 数据隔离 | 用户无法访问他人数据 | 渗透测试 |

### 4.3 测试用例

```python
# tests/test_auth.py
def test_user_registration():
    """测试用户注册流程"""
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "securepassword123"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"
    
    # 验证数据库中用户已创建
    with get_db() as db:
        user = db.execute(
            "SELECT email FROM users WHERE email = ?",
            ("test@example.com",)
        ).fetchone()
        assert user is not None

def test_duplicate_email_registration():
    """测试重复邮箱注册"""
    # 先注册一个用户
    client.post("/api/auth/register", json={
        "email": "duplicate@example.com",
        "password": "password123"
    })
    
    # 尝试用相同邮箱再次注册
    response = client.post("/api/auth/register", json={
        "email": "duplicate@example.com",
        "password": "anotherpassword"
    })
    
    assert response.status_code == 400
    assert "邮箱已被注册" in response.json()["detail"]

def test_jwt_authentication():
    """测试JWT认证功能"""
    # 注册用户并获取JWT
    response = client.post("/api/auth/register", json={
        "email": "jwt@example.com",
        "password": "password123"
    })
    token = response.json()["access_token"]
    
    # 使用JWT访问受保护的端点
    response = client.post("/api/analyze", 
        json={"product_description": "测试产品"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert "task_id" in response.json()

def test_tenant_isolation():
    """测试多租户数据隔离"""
    # 创建两个用户和各自的任务
    user1_token = register_and_get_token("user1@example.com")
    user2_token = register_and_get_token("user2@example.com")
    
    # 用户1创建任务
    response = client.post("/api/analyze", 
        json={"product_description": "用户1的产品"},
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    task_id = response.json()["task_id"]
    
    # 用户2尝试访问用户1的任务
    response = client.get(f"/api/status/{task_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    
    # 应该返回404，而不是403（避免信息泄露）
    assert response.status_code == 404
```

## 5. 风险管理

### 5.1 安全风险

**风险1：JWT密钥泄露**
- **影响**：攻击者可以伪造任意用户令牌
- **缓解**：密钥存储在环境变量，定期轮换
- **应急方案**：立即轮换密钥，所有用户需重新登录

**风险2：密码数据库泄露**
- **影响**：用户密码hash可能被破解
- **缓解**：使用bcrypt+高cost因子，密码复杂度要求
- **应急方案**：强制所有用户重置密码

**风险3：会话劫持**
- **影响**：攻击者获得用户JWT，冒充用户操作
- **缓解**：HTTPS传输，令牌短期有效，异常登录检测
- **应急方案**：用户可以通过重新登录使旧令牌失效

### 5.2 依赖项

**数据库支持**：
- PostgreSQL 12+ (UUID支持)
- users表已创建并建立索引
- 外键约束已配置

**密码学库**：
- bcrypt 4.0+ (Python)
- PyJWT 2.0+ (JWT处理)
- cryptography库 (加密原语)

**环境配置**：
- JWT_SECRET_KEY环境变量（256位）
- 数据库连接字符串
- HTTPS证书（生产环境）

### 5.3 降级方案

**完全降级：维护模式**
```python
# 紧急维护期间的正确处理方式
@app.middleware("http")
async def maintenance_mode_check(request: Request, call_next):
    if MAINTENANCE_MODE:
        # 诚实地告诉用户系统在维护，而不是绕过安全
        return JSONResponse(
            status_code=503,
            content={
                "detail": "系统维护中，预计恢复时间：30分钟",
                "maintenance_window": "2025-01-21 02:00-04:00 UTC"
            },
            headers={"Retry-After": "1800"}  # 30分钟后重试
        )
    return await call_next(request)
```

**部分降级：只读模式**
```python
# 当发现安全问题时，限制写操作
@app.middleware("http") 
async def security_readonly_check(request: Request, call_next):
    if SECURITY_READONLY_MODE and request.method in ["POST", "PUT", "DELETE"]:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "安全维护中，暂时只支持查看功能",
                "affected_operations": ["创建任务", "用户注册", "数据修改"]
            }
        )
    return await call_next(request)
```

**用户通知降级**
```python
# 当认证服务不稳定时
def auth_service_degraded_notice():
    return {
        "notice": "认证服务当前不稳定，登录可能需要多次尝试。我们正在修复中。",
        "alternative": "您可以使用邮箱联系我们获取临时访问权限。"
    }
```

---

## 总结

这个认证系统设计**严格遵循了"从第一天就支持多租户"的要求**：

1. **架构正确**：JWT无状态设计，支持水平扩展，与现有数据模型完美集成
2. **安全充分**：密码安全存储，令牌防伪造，完整的多租户隔离
3. **体验简单**：30秒注册，一键登录，前端无缝集成
4. **扩展预留**：为未来的订阅、OAuth、SSO预留了接口

**最关键的是，我们诚实地处理了多租户的复杂性。**每个数据访问都经过严格的租户检查，跨租户访问返回404而不是403，避免了信息泄露。我们不依赖"安全通过默默无闻"，而是建立了深度防御的安全体系。

这不是最"花哨"的认证系统，但它是最"可靠"和最"诚实"的认证系统。