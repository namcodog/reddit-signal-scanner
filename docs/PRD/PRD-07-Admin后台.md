# PRD-07: Admin后台设计

## 1. 问题陈述

### 1.1 背景
Reddit Signal Scanner需要一个内部管理工具，用于监控系统健康状态、分析用户行为模式、优化产品配置。但是，**Admin后台绝对不能成为数据破坏的风险源**。所有的系统配置和优化都必须通过Git管理的配置文件进行，而不是数据库直接操作。

**核心约束**：
- Admin后台只能"读取"，不能"写入"
- 所有配置修改通过Git工作流
- 单用户设计（内部团队使用）
- 保护用户隐私，只展示聚合数据

### 1.2 目标
设计一个纯读取的Admin监控面板：
- **系统监控**：实时展示系统健康状态和性能指标
- **用户分析**：匿名化的用户行为和产品使用模式
- **配置管理**：查看当前配置，但修改通过Git
- **数据洞察**：为产品优化提供数据支持
- **故障排查**：快速定位和诊断系统问题

### 1.3 非目标
- **绝对禁止**：任何数据库写入操作
- **绝对禁止**：用户数据的直接修改
- **绝对禁止**：生产配置的在线修改
- **不支持**：多用户权限管理（单用户足够）

## 2. 解决方案

### 2.1 核心设计：只读监控 + Git配置

基于"配置即代码"哲学，实现管理和监控的完全分离：

```
监控面板 ← 只读查询 ← 生产数据库
    ↓
配置展示 ← 只读 ← Git仓库配置文件
    ↓
优化建议 → Pull Request → 配置更新 → 自动部署
```

**核心原则**：
- **读写分离**：Admin只能读，配置文件控制写
- **审计完整**：所有配置变更都有Git记录
- **零数据风险**：即使Admin被入侵，也无法破坏数据
- **团队协作**：配置修改通过代码审查流程

### 2.2 功能模块

#### 系统健康监控
```
仪表盘概览
├── 系统状态指标
│   ├── API响应时间（P50, P95, P99）
│   ├── 任务队列长度和处理速度
│   ├── 数据库连接池状态
│   └── Redis缓存命中率
├── 错误监控
│   ├── 最近24小时错误趋势
│   ├── 高频错误类型统计
│   └── 任务失败率和重试成功率
└── 资源使用
    ├── CPU和内存使用率
    ├── 磁盘空间和网络流量
    └── 外部API调用配额使用
```

#### 用户行为分析（匿名化）
```
用户洞察
├── 使用统计
│   ├── 日活跃用户数和注册趋势
│   ├── 分析任务创建频率
│   └── 用户留存率（7天、30天）
├── 产品描述模式
│   ├── 高频关键词和行业分布
│   ├── 描述长度和质量分析
│   └── 成功分析的产品类型
└── 报告质量评估
    ├── 用户满意度指标（推断）
    ├── 报告查看时长统计
    └── 重复分析行为模式
```

### 2.3 关键决策

#### 决策1：只读 vs 管理功能
**选择**：纯只读设计
**理由**：避免人为错误，确保配置变更的可审计性
**代价**：配置修改需要额外的Git工作流，但换取了系统的稳定性

#### 决策2：单用户 vs 多用户权限
**选择**：单用户设计
**理由**：内部团队小，多用户权限增加复杂性而价值有限
**代价**：所有团队成员共享访问权限，但简化了开发和维护

#### 决策3：实时数据 vs 定期刷新
**选择**：5分钟定期刷新
**理由**：Admin监控不需要秒级精度，降低对生产系统的负载
**代价**：不是绝对实时，但满足监控需求

## 3. 技术规范

### 3.1 后端API设计

```python
# api/v1/endpoints/admin.py
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import json

router = APIRouter()

@router.get("/dashboard/overview")
async def get_dashboard_overview():
    """获取系统概览数据（只读）"""
    with get_db() as db:
        # 系统健康指标
        total_users = db.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
        active_tasks = db.execute("SELECT COUNT(*) as count FROM task WHERE status IN ('pending', 'processing')").fetchone()["count"]
        completed_today = db.execute(
            "SELECT COUNT(*) as count FROM task WHERE status = 'completed' AND DATE(completed_at) = DATE('now')"
        ).fetchone()["count"]
        
        # 错误统计
        failed_tasks = db.execute(
            "SELECT COUNT(*) as count FROM task WHERE status = 'failed' AND created_at > datetime('now', '-24 hours')"
        ).fetchone()["count"]
        
        return {
            "system_health": {
                "total_users": total_users,
                "active_tasks": active_tasks,
                "completed_today": completed_today,
                "error_rate": failed_tasks / max(completed_today + failed_tasks, 1)
            },
            "last_updated": datetime.utcnow().isoformat()
        }

@router.get("/analytics/user-patterns")
async def get_user_patterns():
    """获取用户行为模式（匿名化）"""
    with get_db() as db:
        # 注册趋势（最近30天）
        registration_trend = db.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as new_users
            FROM users 
            WHERE created_at > datetime('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """).fetchall()
        
        # 产品描述关键词分析
        top_keywords = db.execute("""
            SELECT 
                CASE 
                    WHEN product_description LIKE '%AI%' THEN 'AI'
                    WHEN product_description LIKE '%app%' OR product_description LIKE '%应用%' THEN 'App'
                    WHEN product_description LIKE '%SaaS%' OR product_description LIKE '%软件%' THEN 'SaaS'
                    ELSE 'Other'
                END as category,
                COUNT(*) as count
            FROM task
            WHERE created_at > datetime('now', '-30 days')
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()
        
        return {
            "registration_trend": [
                {"date": row["date"], "count": row["new_users"]} 
                for row in registration_trend
            ],
            "product_categories": [
                {"category": row["category"], "count": row["count"]}
                for row in top_keywords
            ]
        }

@router.get("/system/performance")
async def get_system_performance():
    """获取系统性能指标"""
    with get_db() as db:
        # 任务处理时间统计
        task_durations = db.execute("""
            SELECT 
                AVG((julianday(completed_at) - julianday(started_at)) * 24 * 60) as avg_minutes,
                MAX((julianday(completed_at) - julianday(started_at)) * 24 * 60) as max_minutes,
                MIN((julianday(completed_at) - julianday(started_at)) * 24 * 60) as min_minutes
            FROM task 
            WHERE status = 'completed' 
            AND completed_at > datetime('now', '-24 hours')
        """).fetchone()
        
        # 队列长度历史
        queue_stats = db.execute("""
            SELECT 
                strftime('%H', created_at) as hour,
                COUNT(*) as tasks_created
            FROM task
            WHERE created_at > datetime('now', '-24 hours')
            GROUP BY strftime('%H', created_at)
            ORDER BY hour
        """).fetchall()
        
        return {
            "task_performance": {
                "avg_duration_minutes": round(task_durations["avg_minutes"] or 0, 2),
                "max_duration_minutes": round(task_durations["max_minutes"] or 0, 2),
                "min_duration_minutes": round(task_durations["min_minutes"] or 0, 2)
            },
            "hourly_load": [
                {"hour": int(row["hour"]), "count": row["tasks_created"]}
                for row in queue_stats
            ]
        }

@router.get("/config/current")
async def get_current_config():
    """获取当前配置文件内容（只读）"""
    import yaml
    
    try:
        # 读取分析引擎配置
        with open("config/analysis_engine.yml", "r") as f:
            analysis_config = yaml.safe_load(f)
        
        # 读取系统配置
        with open("config/system.yml", "r") as f:
            system_config = yaml.safe_load(f)
        
        return {
            "analysis_engine": analysis_config,
            "system": system_config,
            "last_git_commit": get_last_git_commit(),
            "config_version": get_config_version()
        }
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"配置文件不存在: {str(e)}")

def get_last_git_commit():
    """获取最后一次Git提交信息"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%cr"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            hash, subject, date = result.stdout.strip().split("|")
            return {
                "hash": hash[:8],
                "subject": subject,
                "date": date
            }
    except Exception:
        pass
    return {"hash": "unknown", "subject": "未知", "date": "未知"}
```

### 3.2 前端Dashboard设计

```jsx
// src/components/AdminDashboard.jsx
function AdminDashboard() {
    const [overview, setOverview] = useState(null);
    const [performance, setPerformance] = useState(null);
    const [config, setConfig] = useState(null);
    
    useEffect(() => {
        // 每5分钟刷新一次数据
        const fetchData = async () => {
            const [overviewRes, performanceRes, configRes] = await Promise.all([
                fetch('/api/admin/dashboard/overview'),
                fetch('/api/admin/system/performance'),
                fetch('/api/admin/config/current')
            ]);
            
            setOverview(await overviewRes.json());
            setPerformance(await performanceRes.json());
            setConfig(await configRes.json());
        };
        
        fetchData();
        const interval = setInterval(fetchData, 5 * 60 * 1000);
        return () => clearInterval(interval);
    }, []);
    
    return (
        <div className="admin-dashboard">
            <Header />
            
            <div className="dashboard-grid">
                <SystemHealthCard data={overview?.system_health} />
                <PerformanceChart data={performance} />
                <UserAnalytics />
                <ConfigurationPanel config={config} />
                <RecentErrors />
                <OptimizationSuggestions />
            </div>
        </div>
    );
}

function SystemHealthCard({ data }) {
    if (!data) return <div className="card loading">加载中...</div>;
    
    const healthScore = calculateHealthScore(data);
    
    return (
        <div className="card system-health">
            <h3>系统健康状态</h3>
            <div className={`health-indicator ${getHealthClass(healthScore)}`}>
                {healthScore}分
            </div>
            <div className="metrics">
                <div className="metric">
                    <label>总用户数</label>
                    <value>{data.total_users}</value>
                </div>
                <div className="metric">
                    <label>活跃任务</label>
                    <value>{data.active_tasks}</value>
                </div>
                <div className="metric">
                    <label>今日完成</label>
                    <value>{data.completed_today}</value>
                </div>
                <div className="metric">
                    <label>错误率</label>
                    <value>{(data.error_rate * 100).toFixed(1)}%</value>
                </div>
            </div>
        </div>
    );
}

function ConfigurationPanel({ config }) {
    if (!config) return <div className="card loading">加载配置...</div>;
    
    return (
        <div className="card configuration">
            <h3>当前配置</h3>
            <div className="config-info">
                <div className="git-info">
                    <strong>最新提交:</strong> {config.last_git_commit.hash}
                    <br />
                    <span>{config.last_git_commit.subject}</span>
                    <br />
                    <small>{config.last_git_commit.date}</small>
                </div>
                
                <div className="config-summary">
                    <h4>分析引擎配置</h4>
                    <ul>
                        <li>目标社区数: {config.analysis_engine.discovery.max_communities_to_scan}</li>
                        <li>痛点权重: {config.analysis_engine.ranking.pain_point_weight}</li>
                        <li>机会权重: {config.analysis_engine.ranking.opportunity_signal_weight}</li>
                    </ul>
                </div>
                
                <div className="config-notice">
                    <strong>⚠️ 注意：</strong>配置修改请通过Git提交，不支持在线修改。
                </div>
            </div>
        </div>
    );
}
```

### 3.3 配置文件管理

```yaml
# config/analysis_engine.yml - 分析引擎配置
version: "1.2"
last_updated: "2025-01-21T10:00:00Z"
updated_by: "team@example.com"

discovery:
  max_communities_to_scan: 20
  community_relevance_threshold: 0.7
  cache_fallback_enabled: true

ranking:
  pain_point_weight: 1.5
  competitor_mention_weight: 1.2
  opportunity_signal_weight: 1.8
  recency_boost_factor: 1.1

nlp:
  model_name: "reddit-sentiment-analysis/roberta-base-reddit"
  fallback_model: "cardiffnlp/twitter-roberta-base-sentiment"
  confidence_threshold: 0.8

caching:
  redis_ttl_hours: 24
  cache_warming_enabled: true
  cache_hit_ratio_target: 0.9
```

```yaml
# config/system.yml - 系统配置
version: "1.0"
deployment_environment: "production"

celery:
  worker_concurrency: 2
  max_retries: 3
  retry_delay_seconds: 60

monitoring:
  max_queue_length: 50
  max_task_duration_minutes: 10
  max_failure_rate: 0.1
  alert_email: "alerts@example.com"

api:
  rate_limit_per_user: 100  # 每小时请求限制
  jwt_expiration_hours: 24
  max_concurrent_tasks_per_user: 1

reddit_api:
  requests_per_minute: 50
  fallback_strategy: "cache_only"
  quota_warning_threshold: 0.8
```

### 3.4 配置更新工作流

```bash
#!/bin/bash
# scripts/deploy_config.sh - 配置部署脚本

echo "🔍 验证配置文件格式..."
python scripts/validate_config.py

if [ $? -ne 0 ]; then
    echo "❌ 配置文件验证失败，请检查YAML格式"
    exit 1
fi

echo "📝 创建配置备份..."
cp config/analysis_engine.yml config/backups/analysis_engine_$(date +%Y%m%d_%H%M%S).yml
cp config/system.yml config/backups/system_$(date +%Y%m%d_%H%M%S).yml

echo "🚀 重启相关服务..."
sudo systemctl reload reddit-scanner
sudo systemctl restart celery-worker

echo "✅ 配置部署完成"
echo "📊 请检查Admin面板确认配置生效"
```

## 4. 验收标准

### 4.1 功能要求

**监控面板**：
- ✅ 实时显示系统健康评分（0-100）
- ✅ 展示用户数、任务数、完成率等关键指标
- ✅ 错误率和性能趋势图表
- ✅ 5分钟自动刷新机制

**用户分析**：
- ✅ 匿名化用户行为统计（无个人信息）
- ✅ 产品描述模式和关键词分析
- ✅ 用户留存和活跃度趋势

**配置管理**：
- ✅ 只读展示当前配置文件内容
- ✅ 显示最新Git提交信息
- ✅ 配置修改提示和文档链接
- ✅ **禁止**任何在线配置修改功能

**故障排查**：
- ✅ 最近错误日志和频次统计
- ✅ 任务失败原因分析
- ✅ 性能瓶颈识别和建议

### 4.2 安全标准

| 安全项 | 要求 | 验证方法 |
|--------|------|----------|
| 数据库写权限 | 绝对禁止写操作 | 代码审查，数据库权限检查 |
| 用户隐私保护 | 只显示聚合数据 | 数据脱敏检查 |
| 配置文件权限 | 只读访问 | 文件系统权限验证 |
| Admin访问控制 | 单用户，IP限制 | 网络配置检查 |

### 4.3 测试用例

```python
# tests/test_admin.py
def test_admin_readonly_access():
    """测试Admin只读访问"""
    response = client.get("/api/admin/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    
    # 验证返回数据结构
    assert "system_health" in data
    assert "last_updated" in data
    assert data["system_health"]["total_users"] >= 0

def test_no_write_endpoints():
    """确保没有写入端点"""
    # 尝试POST请求到Admin端点
    response = client.post("/api/admin/config/update", json={"test": "data"})
    assert response.status_code == 404  # 端点不存在
    
    # 尝试PUT请求
    response = client.put("/api/admin/users/disable", json={"user_id": "test"})
    assert response.status_code == 404  # 端点不存在

def test_user_data_anonymization():
    """测试用户数据匿名化"""
    response = client.get("/api/admin/analytics/user-patterns")
    data = response.json()
    
    # 确保没有用户个人信息
    json_str = json.dumps(data)
    assert "@" not in json_str  # 不包含邮箱
    assert "user_id" not in json_str  # 不包含用户ID
```

## 5. 风险管理

### 5.1 技术风险

**风险1：配置文件损坏**
- **影响**：系统无法读取配置，服务异常
- **缓解**：配置文件版本控制，自动备份机制
- **降级方案**：硬编码默认配置，确保系统基本可用

**风险2：Admin面板故障**
- **影响**：无法监控系统状态
- **缓解**：独立部署，不依赖主系统
- **降级方案**：直接查询数据库，命令行工具

**风险3：数据隐私泄露**
- **影响**：用户个人信息通过Admin面板泄露
- **缓解**：严格的数据脱敏，只显示聚合统计
- **降级方案**：关闭用户分析功能，只保留系统监控

### 5.2 降级方案

**完全降级：命令行监控**
```bash
#!/bin/bash
# scripts/emergency_status.sh
echo "=== 紧急系统状态检查 ==="

echo "用户总数:"
sqlite3 data/reddit.db "SELECT COUNT(*) FROM users;"

echo "今日完成任务:"
sqlite3 data/reddit.db "SELECT COUNT(*) FROM task WHERE status='completed' AND DATE(completed_at)=DATE('now');"

echo "失败任务:"
sqlite3 data/reddit.db "SELECT COUNT(*) FROM task WHERE status='failed' AND created_at > datetime('now', '-24 hours');"

echo "当前配置版本:"
git log -1 --format="%h %s %cr"
```

**部分降级：最小监控面板**
```html
<!-- 当React Admin不可用时的静态HTML -->
<!DOCTYPE html>
<html>
<head><title>System Status</title></head>
<body>
    <h1>Reddit Scanner - Emergency Status</h1>
    <div id="status">Loading...</div>
    
    <script>
        fetch('/api/admin/dashboard/overview')
            .then(r => r.json())
            .then(data => {
                document.getElementById('status').innerHTML = `
                    <p>Total Users: ${data.system_health.total_users}</p>
                    <p>Active Tasks: ${data.system_health.active_tasks}</p>
                    <p>Error Rate: ${(data.system_health.error_rate * 100).toFixed(1)}%</p>
                `;
            });
    </script>
</body>
</html>
```

---

## 总结

这个Admin后台设计**严格遵循了"只读监控"的安全哲学**：

1. **安全第一**：零写入权限，配置通过Git管理，杜绝人为破坏
2. **数据透明**：完整的系统监控和用户分析，但严格保护隐私
3. **运维友好**：清晰的配置展示和性能指标，便于故障排查
4. **团队协作**：配置修改通过代码审查，确保变更质量

**最关键的是，我们诚实地承认了Admin后台的风险性。**传统的Admin系统往往成为数据破坏的入口，我们通过"只读 + Git配置"的模式，从架构层面杜绝了这种风险。

这不是最"方便"的Admin系统，但它是最"安全"和最"可审计"的Admin系统。正如Linus所说，"Never break userspace"，我们的Admin设计确保永远不会破坏用户数据。

**至此，完整的PRD体系（PRD-01到PRD-07）已经完成，形成了一个诚实、简单、可靠的技术架构。**