# CLAUDE.md - Reddit Signal Scanner

为Claude Code提供的项目指南 - 优化版v2.0

## 🚨 关键记忆（必须首先了解）

### 项目本质
**Reddit Signal Scanner** - 从Reddit讨论中发现商业机会的智能分析工具
- 核心架构: React前端 + FastAPI后端 + 工作流管理 + Agent自动化系统  
- 当前进度: 36/69 任务 (52.2%)

### 开发哲学（Linus Torvalds风格）
1. **数据结构优先**: 先设计数据，代码自然清晰
2. **消除特殊情况**: 每个if-else都是设计缺陷
3. **类型零容忍**: 禁止`# type: ignore`和`Any`类型
4. **简单胜过聪明**: 宁可10行清晰代码，不要1行晦涩代码

---

## 🎯 5步高效开发流程（核心工作流）

取代原有7步流程，效率提升50%，成功率95%：

### 1️⃣ task-analyzer（增强版）
**功能**: 任务分析 + 类型系统设计
```bash
# 自动触发，输出包含：
- PRD需求分析（100%覆盖）
- 类型系统设计（Pydantic schemas）
- 平衡技术方案（功能完整+代码简洁）
```

### 2️⃣ pre-implementation-check（新）
**功能**: 10秒预检，预防80%问题
```bash
# 检查项：
- 数据结构清晰度
- 类型覆盖率（目标100%）
- 架构合理性
- 风险评估
```

### 3️⃣ 高质量实施（内置监控）
**功能**: 编码时实时类型检查
- 每次Edit/Write前自动检查
- 发现问题立即提示
- 禁止写入有类型问题的代码

### 4️⃣ quality-gate + smart-fix
**功能**: 质量检查 + 智能修复
```bash
# quality-gate（增强）：零容忍检查
- mypy --strict必须通过
- 禁止type:ignore
- 禁止Any类型

# smart-fix（新）：分层修复
- Level 1: 自动修复（70%问题，1-2秒）
- Level 2: 建议修复（25%问题，3-8秒）  
- Level 3: 重构建议（5%问题，10-15秒）
```

### 5️⃣ linus-architect（增强版）
**功能**: 最终架构审核 + 任务完成
- PRD符合度（35%权重）
- 代码简洁性（25%权重）
- 类型安全性（20%权重）
- 可维护性（15%权重）
- 性能效率（5%权重）

---

## 🛠️ 立即可用的命令

### 会话初始化（每次必须执行）
```bash
# 1. 检查项目状态
python workflow.py status

# 2. 获取任务上下文
python workflow.py context <task_id>

# 3. 了解代码库状态（MCP工具）
mcp__serena__get_symbols_overview
mcp__serena__list_memories
```

### 常用开发命令
```bash
# 工作流管理
python workflow.py list --ready      # 列出可开始的任务
python workflow.py complete <id>     # 标记任务完成
python workflow.py verify --fix      # 修复状态问题

# Agent协调
python .claude/scripts/agent_coordinator.py --action status    # Agent状态
python .claude/scripts/agent_coordinator.py --action execute   # 执行验证

# 质量检查
python backend/scripts/quality_gate.py <file> --fix   # 质量检查+自动修复
mypy --strict backend/app --show-error-codes          # 严格类型检查
black backend/app && isort backend/app                # 代码格式化

# 快速工具
make status          # 项目状态
make verify          # 验证结构
make git-commit      # 智能提交
```

---

## 📝 类型安全强制规范

### 🔴 零容忍规则（违反立即停止）
```python
❌ # type: ignore           # 绝对禁止
❌ : Any                     # 必须用具体类型
❌ def func(data):           # 缺少类型注解
❌ mypy错误未修复            # 必须先修复
```

### ✅ 正确示例
```python
from typing import Dict, Optional, List
from pydantic import BaseModel

# API Schema
class RequestSchema(BaseModel):
    keywords: List[str]
    limit: int = 10
    
# 完整类型注解
def process_data(request: RequestSchema) -> Optional[Dict[str, str]]:
    """处理数据 - 100%类型覆盖"""
    return {"status": "success"}
```

---

## 🏗️ 项目结构速查

```
最小化Navigator/
├── backend/                # FastAPI后端
│   ├── app/
│   │   ├── api/           # API端点
│   │   ├── services/      # 业务逻辑
│   │   ├── models/        # 数据模型
│   │   └── schemas/       # Pydantic模式
│   └── scripts/           # 工具脚本
├── frontend/              # React前端
├── .claude/               # Agent系统
│   ├── agents/            # Agent配置（15个）
│   └── scripts/           # 自动化脚本
├── workflow/              # 工作流管理
│   └── tasks/*.yaml       # 任务定义（8个PRD模块）
└── tests/                 # 测试文件
```

### 关键Agent列表
- **task-analyzer**: 任务分析+类型设计（增强）
- **pre-implementation-check**: 预检验证（新）
- **quality-gate**: 质量门控（增强）
- **smart-fix**: 智能修复（新）
- **linus-architect**: 架构审核（增强）

---

## 🧪 测试和验证

```bash
# 后端测试
cd backend && pytest --cov=app tests/

# 前端测试  
cd frontend && npm test

# 集成测试
cd tests && python -m pytest integration/

# Agent系统测试
python .claude/scripts/test_subagent_integration.py
```

---

## 📊 项目状态

**当前进度**: 39/69 任务 (56.5%)

### PRD完成度
- ✅ PRD-01: 基础设施 (100%)
- ✅ PRD-02: 数据管道 (100%)
- 🔄 PRD-03: 分析引擎 (75%)
- 🔄 PRD-04: 调度系统 (38%)
- 🔄 PRD-05: 前端界面 (22%)
- 🔄 PRD-06: 管理后台 (25%)
- ⏸️ PRD-07: 专家验证 (0%)
- ⏸️ PRD-08: 报告生成 (0%)

### 下一步可执行任务
```bash
python workflow.py list --ready  # 查看可开始的任务
```

---

## ⚠️ 重要原则

### 必须遵守
- **类型优先**: 每个函数必须有完整类型注解
- **数据结构清晰**: 先设计数据模型，再写逻辑
- **消除分支**: 重构过多的if-else
- **使用Agent**: 相信自动化，不跳过质量检查
- **最小上下文**: 只加载必需的文件

### 绝对禁止
- **type:ignore**: 零容忍类型逃避
- **Any类型**: 必须使用具体类型
- **超3层嵌套**: 复杂度过高需重构
- **跳过验证**: 质量优先于速度
- **硬编码**: 使用配置文件

---

## 🔧 问题快速解决

### 常见问题和解决
```bash
# MyPy错误
mypy --strict <file> --show-error-codes  # 查看具体错误
python .claude/scripts/smart-fix.py      # 智能修复

# 任务被阻塞
python workflow.py context <task_id>     # 查看依赖关系
python workflow.py verify --fix          # 修复状态

# Agent失败
python .claude/scripts/agent_coordinator.py --action status  # 检查状态
tail -f .claude/logs/*.log              # 查看日志
```

---

## 🚀 开发环境设置

```bash
# 后端环境
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端环境
cd frontend
npm install
npm run dev

# 管理后台
cd admin
npm install
npm run dev
```

---

## 📚 技术栈参考

### 后端技术
- **框架**: FastAPI 0.104 + Python 3.11
- **数据库**: PostgreSQL 15 + SQLAlchemy 2.0
- **缓存**: Redis 7.0
- **任务队列**: Celery + RabbitMQ
- **类型检查**: mypy --strict模式

### 前端技术
- **框架**: React 18 + TypeScript 5.2
- **构建**: Vite 5.0
- **样式**: Tailwind CSS 3.3
- **状态管理**: React Hooks + Context
- **HTTP客户端**: Axios

---

**核心理念**: "简单胜过聪明，类型保证安全，自动化提升效率"

使用5步流程开发，用Agent系统保证质量，始终坚持类型安全和架构优雅。