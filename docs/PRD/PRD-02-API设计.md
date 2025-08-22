# PRD-02: API设计规范

## 1. 问题陈述

### 1.1 背景
Reddit Signal Scanner需要一个极简而可靠的API系统，支撑前端的"30秒输入，5分钟分析"用户体验。**基于Linus的严厉批评**，系统必须摒弃"300次无用HTTP请求"的轮询设计，改用Server-Sent Events实现真正的简单高效。同时必须提供完整的错误恢复机制，而非"祈祷式"错误处理。

### 1.2 目标
设计四个核心API端点的完整规范：
- 提供清晰、一致的RESTful接口设计
- **Server-Sent Events (SSE)实时进度推送**（替代轮询方式）
- 支持异步任务处理模式
- **完整的错误恢复策略**（检测→恢复→降级）
- 确保API响应时间 < 200ms（任务创建）

### 1.3 非目标
- **不支持**全双工WebSocket（SSE单向推送足够）
- **不支持**批量任务操作（专注单一任务流程）
- **不支持**复杂的GraphQL查询（保持REST简洁性）
- **不支持**任务修改和删除（只读和创建）

## 2. 解决方案

### 2.1 核心设计：四端点架构（SSE + Fallback）

基于Linus的"简单胜过聪明"原则，设计四个专用端点：

```
POST /api/analyze                    # 创建分析任务
GET /api/analyze/stream/{task_id}    # SSE实时进度推送（主要方式）
GET /api/status/{task_id}            # 轮询状态查询（fallback）
GET /api/report/{task_id}            # 获取分析报告
```

**设计哲学**：
- **单一职责**：每个端点只做一件事
- **SSE优先**：主要使用SSE实时推送，轮询作为fallback
- **无状态设计**：所有信息通过URL和请求体传递
- **优雅降级**：每个错误都有明确的恢复方案
- **快速失败**：输入验证在接收时立即执行

### 2.2 API流程（SSE优先）

**主要流程（SSE方式）**：
```
用户提交产品描述
  ↓ POST /api/analyze
响应task_id (< 200ms)
  ↓ 立即建立SSE连接 GET /api/analyze/stream/{task_id}
实时接收进度更新（pending→processing→completed）
  ↓ 收到completed事件
  ↓ GET /api/report/{task_id}
返回完整分析报告
```

**Fallback流程（轮询方式）**：
```
SSE不可用或连接失败
  ↓ 自动切换至轮询模式
  ↓ 定时查询 GET /api/status/{task_id}
返回状态更新
```

### 2.3 关键决策

#### 决策1: 为什么选择RESTful而非GraphQL？
**理由**: 遵循Linus的"实用主义"原则。四个简单端点比一个复杂的GraphQL查询系统更容易理解和维护。

#### 决策2: 为什么使用SSE而非WebSocket？
**理由**: SSE更简单且完美适合单向推送场景。与WebSocket相比，SSE自动支持断线重连、更容易穿过代理和防火墙。对于只需要服务器推送进度的场景，SSE是最佳选择。

#### 决策3: 为什么任务不支持修改？
**理由**: 避免复杂的状态管理。用户如需修改，重新提交新任务即可。这消除了大量边界条件。

## 3. 技术规范

### 3.1 API端点详细定义（增加SSE端点）

#### POST /api/analyze - 创建分析任务

**功能**: 接收用户产品描述，创建异步分析任务

**请求规范**:
```http
POST /api/analyze
Content-Type: application/json
Authorization: Bearer {jwt_token}

{
  "product_description": "AI笔记应用，帮助研究者自动组织和连接想法的智能工具"
}
```

**响应规范**:
```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /api/analyze/stream/123e4567-e89b-12d3-a456-426614174000

{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "created_at": "2025-01-21T10:30:00Z",
  "estimated_completion": "2025-01-21T10:35:00Z",
  "sse_endpoint": "/api/analyze/stream/123e4567-e89b-12d3-a456-426614174000"
}
```

**输入验证**:
- product_description: 必填，10-2000字符
- 内容不能全为空格或特殊字符
- 必须包含实际的产品描述信息

#### GET /api/analyze/stream/{task_id} - SSE实时进度推送（主要方式）

**功能**: 通过SSE实时推送任务进度和状态更新

**请求规范**:
```http
GET /api/analyze/stream/123e4567-e89b-12d3-a456-426614174000
Accept: text/event-stream
Cache-Control: no-cache
Authorization: Bearer {jwt_token}
```

**SSE事件流规范**:
```
# 初始连接
data: {"event": "connected", "task_id": "123e4567-e89b-12d3-a456-426614174000"}

# 进度更新事件
data: {"event": "progress", "status": "processing", "current_step": "community_discovery", "percentage": 25, "estimated_remaining": 180}

data: {"event": "progress", "status": "processing", "current_step": "data_collection", "percentage": 50, "estimated_remaining": 120}

data: {"event": "progress", "status": "processing", "current_step": "analysis", "percentage": 75, "estimated_remaining": 60}

# 完成事件
event: completed
data: {"event": "completed", "task_id": "123e4567-e89b-12d3-a456-426614174000", "report_available": true, "processing_time": 267}

# 错误事件
event: error  
data: {"event": "error", "error": {"code": "REDDIT_API_LIMIT", "recovery": {...}}}

# 连接关闭
event: close
data: {"event": "connection_closed"}
```

**客户端处理示例**:
```javascript
const eventSource = new EventSource(`/api/analyze/stream/${taskId}`);

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.event) {
        case 'connected':
            console.log('SSE连接成功');
            break;
        case 'progress':
            updateProgressBar(data.percentage);
            updateCurrentStep(data.current_step);
            break;
        case 'completed':
            eventSource.close();
            loadReport(data.task_id);
            break;
    }
};

eventSource.onerror = function(event) {
    console.warn('SSE连接错误，切换至轮询模式');
    eventSource.close();
    startPolling(taskId);  // 自动降级至轮询
};
```

#### GET /api/status/{task_id} - 查询任务状态（Fallback轮询）

**功能**: 查询指定任务的当前状态和处理进度（作为SSE的fallback）

**请求规范**:
```http
GET /api/status/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer {jwt_token}
X-Fallback-Mode: polling
```

**响应规范（处理中）**:
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Fallback-Mode: polling

{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": {
    "current_step": "community_discovery",
    "completed_steps": ["input_validation", "keyword_extraction"],
    "total_steps": 4,
    "percentage": 50
  },
  "created_at": "2025-01-21T10:30:00Z",
  "estimated_completion": "2025-01-21T10:35:00Z"
}
```

**响应规范（已完成）**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "completed_at": "2025-01-21T10:34:30Z",
  "analysis_summary": {
    "communities_analyzed": 18,
    "posts_processed": 1247,
    "insights_found": 23,
    "confidence_score": 0.87
  },
  "report_available": true
}
```

**响应规范（失败）**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "failed",
  "error": {
    "code": "REDDIT_API_LIMIT",
    "message": "Reddit API访问限制，已自动启用缓存模式",
    "recovery": {
      "strategy": "fallback_to_cache",
      "auto_applied": true,
      "cache_coverage": 0.87
    },
    "retry_after": "2025-01-21T11:00:00Z"
  },
  "created_at": "2025-01-21T10:30:00Z",
  "failed_at": "2025-01-21T10:32:15Z"
}
```

#### GET /api/report/{task_id} - 获取分析报告

**功能**: 获取已完成任务的完整分析报告

**请求规范**:
```http
GET /api/report/123e4567-e89b-12d3-a456-426614174000
Accept: application/json
Authorization: Bearer {jwt_token}
```

**响应规范**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "generated_at": "2025-01-21T10:34:30Z",
  "report": {
    "executive_summary": {
      "total_communities": 18,
      "key_insights": 23,
      "top_opportunity": "笔记应用间的数据迁移痛点"
    },
    "pain_points": [
      {
        "description": "现有笔记应用之间数据迁移困难",
        "frequency": 8,
        "sentiment_score": -0.75,
        "example_posts": [
          {
            "community": "r/productivity",
            "content": "从Notion迁移到Obsidian真的太痛苦了...",
            "upvotes": 156
          }
        ]
      }
    ],
    "competitors": [
      {
        "name": "Notion",
        "mentions": 45,
        "sentiment": "mixed",
        "strengths": ["功能丰富", "团队协作"],
        "weaknesses": ["性能慢", "学习曲线陡峭"]
      }
    ],
    "opportunities": [
      {
        "description": "开发更智能的笔记连接算法",
        "relevance_score": 0.92,
        "potential_users": "研究者和内容创作者",
        "source_communities": ["r/academia", "r/writing"]
      }
    ]
  },
  "metadata": {
    "analysis_version": "1.0",
    "confidence_score": 0.87,
    "processing_time_seconds": 267,
    "cache_hit_rate": 0.87,
    "recovery_applied": null
  }
}
```

### 3.2 错误处理规范（完整恢复机制）

#### HTTP状态码使用

| 状态码 | 使用场景 | 示例 |
|--------|---------|------|
| 200 | 成功获取资源 | 状态查询、报告获取 |
| 201 | 成功创建资源 | 任务创建 |
| 400 | 客户端输入错误 | 无效的产品描述 |
| 401 | 认证失败 | JWT token无效 |
| 404 | 资源不存在 | 任务ID不存在 |
| 409 | 资源状态冲突 | 获取未完成任务的报告 |
| 429 | 请求频率限制 | API调用过于频繁 |
| 500 | 服务器内部错误 | 数据库连接失败 |
| 503 | 服务暂时不可用 | 系统维护中 |

#### 增强的错误响应格式（包含恢复策略）

```json
{
  "error": {
    "code": "REDDIT_API_LIMIT",
    "message": "Reddit API访问限制",
    "severity": "warning",  # info/warning/error/critical
    "timestamp": "2025-01-21T10:30:00Z",
    "request_id": "req_123456789",
    
    # 核心：自动恢复策略
    "recovery": {
      "strategy": "fallback_to_cache",
      "auto_applied": true,
      "fallback_quality": {
        "cache_coverage": 0.87,
        "data_freshness_hours": 12,
        "estimated_accuracy": 0.91
      },
      "retry_info": {
        "retry_after": "2025-01-21T11:00:00Z",
        "max_retries": 3,
        "current_attempt": 1
      }
    },
    
    # 用户可执行操作
    "user_actions": {
      "recommended": {
        "action": "accept_cached_analysis",
        "label": "接受缓存数据分析（推荐）",
        "confidence": "high"
      },
      "alternatives": [
        {
          "action": "retry_later",
          "label": "30分钟后重试获得最新数据",
          "wait_time": 1800
        },
        {
          "action": "create_new_task",
          "label": "创建新任务"
        }
      ]
    },
    
    # 系统内部信息
    "internal": {
      "component": "reddit_api_client",
      "operation": "fetch_community_posts",
      "rate_limit_reset": "2025-01-21T11:00:00Z"
    }
  }
}
```

#### 完整的错误恢复策略（检测→恢复→降级）

```yaml
# 输入验证错误
INVALID_DESCRIPTION:
  message: "产品描述格式无效"
  recovery: null  # 用户端问题，无法自动恢复
  user_action: "请检查产品描述格式后重新提交"

DESCRIPTION_TOO_SHORT:
  message: "产品描述过短，至少需要10个字符"
  recovery: null
  user_action: "请扩展产品描述，提供更多细节"

# 资源错误
TASK_NOT_FOUND:
  message: "指定的任务不存在或已过期"
  recovery: "check_recent_tasks"  # 检查用户最近任务
  user_action: "请检查任务ID或创建新任务"

REPORT_NOT_READY:
  message: "分析报告尚未生成"
  recovery: "wait_for_completion"
  estimated_wait_seconds: 120
  user_action: "请等待分析完成或使用SSE连接监测进度"

# 系统错误（需要自动恢复）
REDDIT_API_LIMIT:
  message: "Reddit API访问限制"
  recovery:
    strategy: "fallback_to_cache"
    cache_coverage: 0.87  # 87%数据来自缓存
    quality_impact: "minimal"
  retry_after: "2025-01-21T11:00:00Z"
  user_action: "接受缓存数据分析（推荐）或30分钟后重试"

DATABASE_ERROR:
  message: "数据库连接错误"
  recovery:
    strategy: "retry_with_exponential_backoff"
    max_attempts: 3
    initial_delay: 1000  # 1秒
    max_delay: 5000      # 5秒
  user_action: "系统正在自动重试，请稍后"

ANALYSIS_TIMEOUT:
  message: "分析过程超时"
  recovery:
    strategy: "partial_results"
    available_sections: ["pain_points", "competitors"]
    missing_sections: ["opportunities"]
  user_action: "接受部分结果或重新启动分析"

# 限流错误
RATE_LIMIT_EXCEEDED:
  message: "请求频率过高"
  recovery:
    strategy: "queue_request"
    queue_position: 5
    estimated_wait: 120
  user_action: "您的请求已排队，预计等待2分钟"

SSE_CONNECTION_FAILED:
  message: "SSE连接失败"
  recovery:
    strategy: "fallback_to_polling"
    polling_interval: 2000  # 2秒
  user_action: "自动切换至轮询模式，功能不受影响"
```

### 3.3 配置参数（支持SSE和错误恢复）

```yaml
# api_config.yml
api:
  # 基础配置
  host: "0.0.0.0"
  port: 8000
  debug: false
  
  # 超时设置
  timeouts:
    request_timeout: 30
    analysis_timeout: 600  # 10分钟
    sse_timeout: 300       # SSE连接超时
    sse_heartbeat: 30      # SSE心跳间隔
    
  # 限流配置
  rate_limiting:
    requests_per_minute: 60
    concurrent_tasks_per_user: 3
    sse_connections_per_user: 2  # 每用户SSE连接数限制
    
  # SSE配置
  sse:
    enabled: true
    heartbeat_interval: 30      # 心跳间隔（秒）
    reconnect_attempts: 3       # 客户端重连尝试次数
    buffer_size: 1024          # 事件缓冲区大小
    compression: false         # SSE内容压缩
    
  # 错误恢复配置
  error_recovery:
    auto_recovery_enabled: true
    max_recovery_attempts: 3
    recovery_strategies:
      reddit_api_limit:
        strategy: "fallback_to_cache"
        min_cache_coverage: 0.7    # 最低70%缓存覆盖率
        max_cache_age_hours: 24
      database_error:
        strategy: "retry_with_backoff"
        initial_delay: 1000
        max_delay: 10000
        backoff_multiplier: 2.0
    
  # CORS设置
  cors:
    allowed_origins: ["http://localhost:3000"]
    allowed_methods: ["GET", "POST"]
    allowed_headers: ["Content-Type", "Accept", "Cache-Control", "Authorization"]
    expose_headers: ["X-Request-ID", "X-Recovery-Applied", "X-Fallback-Mode"]
    
  # 响应格式
  response:
    pretty_json: false
    include_request_id: true
    include_recovery_info: true  # 在响应中包含恢复信息

  # 认证配置
  auth:
    jwt_secret_key: "${JWT_SECRET}"
    jwt_expire_hours: 24
    jwt_algorithm: "HS256"
    required_for_all_endpoints: true
```

## 4. 验收标准

### 4.1 功能要求

**任务创建**：
- [ ] 能成功创建分析任务并返回task_id
- [ ] 输入验证能阻止无效请求
- [ ] 响应时间 < 200ms
- [ ] 并发创建10个任务无冲突
- [ ] 支持JWT认证

**SSE实时推送**：
- [ ] SSE连接能成功建立并推送进度
- [ ] 断线重连机制正常工作
- [ ] 心跳机制保持连接活跃
- [ ] 能正确推送completed/error事件

**Fallback轮询**：
- [ ] SSE失败时自动切换至轮询
- [ ] 轮询响应时间 < 50ms
- [ ] 状态更新准确及时

**错误恢复**：
- [ ] Reddit API限流时自动启用缓存模式
- [ ] 数据库错误时自动重试
- [ ] 超时时能返回部分结果
- [ ] 用户收到明确的恢复建议

**报告获取**：
- [ ] 完成的任务能返回完整报告JSON
- [ ] 未完成任务返回409状态码
- [ ] 报告内容结构正确且完整
- [ ] 大报告（500KB）响应时间 < 500ms

### 4.2 性能指标

| API端点 | 响应时间要求 | 并发要求 | 错误率要求 |
|---------|-------------|---------|-----------|
| POST /api/analyze | < 200ms | 50/秒 | < 1% |
| GET /api/analyze/stream | < 100ms（建立连接） | 200并发SSE | < 0.1% |
| GET /api/status/{id} | < 50ms | 200/秒 | < 0.1% |
| GET /api/report/{id} | < 500ms | 100/秒 | < 0.1% |

### 4.3 测试用例（包括SSE和错误恢复）

```python
# 功能测试示例
import pytest
import httpx
import asyncio
from unittest.mock import patch

def test_create_analysis_task():
    """测试任务创建"""
    response = httpx.post("/api/analyze", json={
        "product_description": "AI笔记应用，帮助研究者管理知识图谱"
    })
    
    assert response.status_code == 201
    assert "task_id" in response.json()
    assert response.json()["status"] == "pending"

async def test_sse_progress_stream():
    """测试SSE进度推送"""
    # 创建任务
    create_response = httpx.post("/api/analyze", json={
        "product_description": "测试产品描述足够长度"
    })
    task_id = create_response.json()["task_id"]
    
    # 测试SSE连接
    async with httpx.AsyncClient() as client:
        async with client.stream('GET', f'/api/analyze/stream/{task_id}') as response:
            assert response.status_code == 200
            assert response.headers['content-type'] == 'text/event-stream'
            
            events = []
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    event_data = json.loads(line[6:])  # 去除'data: '
                    events.append(event_data)
                    
                    if event_data.get('event') == 'completed':
                        break
            
            # 验证事件序列
            assert len(events) >= 3  # 至少：连接、进度、完成
            assert events[0]['event'] == 'connected'
            assert events[-1]['event'] == 'completed'

def test_error_recovery_mechanism():
    """测试错误恢复机制"""
    with patch('reddit_client.get_posts') as mock_reddit:
        # 模拟Reddit API限流
        mock_reddit.side_effect = RedditAPILimitException()
        
        response = httpx.post("/api/analyze", json={
            "product_description": "测试API限流情况"
        })
        
        task_id = response.json()["task_id"]
        
        # 等待处理完成
        final_status = wait_for_completion(task_id)
        
        # 验证自动降级生效
        assert final_status['status'] == 'completed'
        assert 'recovery' in final_status
        assert final_status['recovery']['strategy'] == 'fallback_to_cache'
        assert final_status['recovery']['cache_coverage'] > 0.7

def test_sse_fallback_to_polling():
    """测试SSE失败时的轮询fallback"""
    # 创建任务
    task_id = create_test_task()
    
    # 模拟SSE不可用
    with patch('sse.is_available', return_value=False):
        # 客户端尝试SSE，自动降级至轮询
        polling_response = httpx.get(f"/api/status/{task_id}")
        
        assert polling_response.status_code == 200
        assert "X-Fallback-Mode" in polling_response.headers
        assert polling_response.headers["X-Fallback-Mode"] == "polling"

def test_jwt_authentication():
    """测试JWT认证"""
    # 无token请求应该失败
    response = httpx.post("/api/analyze", json={
        "product_description": "测试描述"
    })
    assert response.status_code == 401
    
    # 有效token应该成功
    headers = {"Authorization": "Bearer valid_jwt_token"}
    response = httpx.post("/api/analyze", 
        json={"product_description": "测试描述"},
        headers=headers
    )
    assert response.status_code == 201
```

## 5. 风险管理

### 5.1 技术风险

**风险1**: SSE连接稳定性问题
- **影响**: 用户无法实时看到进度，体验下降
- **缓解**: 实现自动fallback到轮询，用户感知最小
- **监控**: SSE连接成功率，平均连接时长

**风险2**: 并发SSE连接过多消耗服务器资源
- **影响**: 服务器内存和连接数耗尽
- **缓解**: 限制每用户SSE连接数，实现连接池管理
- **监控**: 服务器内存使用率，活跃SSE连接数

**风险3**: 错误恢复策略失效
- **影响**: 系统在异常情况下无法自愈
- **缓解**: 多层降级策略，最终总有一个可用方案
- **监控**: 错误恢复成功率，降级策略触发频率

### 5.2 依赖项

**FastAPI框架**: >= 0.68.0 （支持SSE和异步）
**Pydantic**: >= 1.8.0 （数据验证）
**httpx**: >= 0.24.0 （HTTP客户端，用于测试）
**PyJWT**: >= 2.4.0 （JWT认证）

### 5.3 降级方案

**SSE服务不可用**：
- 自动切换至轮询模式
- 在响应头中标记fallback模式
- 保持相同的功能体验

**Redis缓存不可用**：
- 直接调用Reddit API（注意限流）
- 降低并发处理能力
- 增加分析时间预估

**数据库连接不稳定**：
- 实现重试机制，最多3次
- 使用内存临时存储（会话期间）
- 通知用户系统恢复中

---

## 附录A: SSE实现详细示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()

@app.get("/api/analyze/stream/{task_id}")
async def stream_analysis_progress(task_id: str, request: Request):
    """SSE端点：实时推送任务进度"""
    
    async def event_generator():
        try:
            # 发送连接确认
            yield f"data: {json.dumps({'event': 'connected', 'task_id': task_id})}\n\n"
            
            # 监控任务进度
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break
                
                # 获取任务状态
                status = await get_task_status(task_id)
                
                # 构造SSE事件
                event_data = {
                    "event": "progress",
                    "status": status.status,
                    "current_step": status.current_step,
                    "percentage": status.percentage,
                    "estimated_remaining": status.estimated_remaining_seconds
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
                
                # 任务完成或失败时发送最终事件
                if status.status in ['completed', 'failed']:
                    final_event = {
                        "event": status.status,
                        "task_id": task_id,
                        "processing_time": status.processing_time_seconds
                    }
                    
                    if status.status == 'completed':
                        final_event["report_available"] = True
                    elif status.status == 'failed':
                        final_event["error"] = status.error_info
                    
                    yield f"event: {status.status}\n"
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break
                
                # 等待1秒再次检查（避免过度轮询）
                await asyncio.sleep(1)
                
        except Exception as e:
            # 发送错误事件
            error_event = {
                "event": "error",
                "error": {
                    "code": "SSE_SERVER_ERROR",
                    "message": "服务器端事件流错误",
                    "recovery": {
                        "strategy": "fallback_to_polling",
                        "polling_endpoint": f"/api/status/{task_id}"
                    }
                }
            }
            yield f"event: error\n"
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # 发送连接关闭事件
            yield f"event: close\n"
            yield f"data: {json.dumps({'event': 'connection_closed'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "X-Request-ID"
        }
    )

class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    @staticmethod
    async def handle_reddit_api_limit(task_id: str):
        """处理Reddit API限流"""
        # 检查缓存覆盖率
        cache_coverage = await get_cache_coverage_for_task(task_id)
        
        if cache_coverage > 0.7:
            # 启用缓存模式
            await enable_cache_only_mode(task_id)
            return {
                "strategy": "fallback_to_cache",
                "cache_coverage": cache_coverage,
                "quality_impact": "minimal"
            }
        else:
            # 缓存覆盖率不足，延迟处理
            await delay_task(task_id, delay_minutes=30)
            return {
                "strategy": "delay_processing",
                "retry_after": datetime.now() + timedelta(minutes=30)
            }
    
    @staticmethod
    async def handle_database_error(operation, max_retries=3):
        """处理数据库错误"""
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(2 ** attempt)  # 指数退避
                return await operation()
            except DatabaseError as e:
                if attempt == max_retries - 1:
                    raise e
                continue
```

---

**文档版本**: 2.0（修复Linus致命问题）  
**最后更新**: 2025-01-21  
**关键修复**:  
- ✅ 改用SSE替代轮询（解决"300次无用HTTP请求"问题）
- ✅ 完整错误恢复机制（检测→恢复→降级）
- ✅ 自动fallback策略（SSE失败时自动轮询）
- ✅ 用户可执行的错误解决方案

**审核状态**: 等待Linus re-review  
**实施优先级**: P0 - 核心接口层（已修复致命缺陷）