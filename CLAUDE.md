# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Reddit Signal Scanner - 商业信号分析工具，从Reddit讨论中发现商业机会。

**核心架构**: React前端 + FastAPI后端 + 工作流管理 + Agent自动化系统

## 🚨 会话初始化（必须执行）

**每次新会话开始前，必须按顺序执行**：

使用sernea工具审核代码库

```bash
# 1. 检查项目状态和可用任务
python workflow.py status

# 2. 获取任务上下文（避免context溢出）
python workflow.py context <task_id>

# 3. 调用Serena MCP了解代码库状态
mcp__serena__get_symbols_overview
mcp__serena__list_memories
```

## 🛠️ 常用开发命令

### 项目管理
```bash
python workflow.py status           # 查看项目状态和可用任务
python workflow.py context <id>     # 获取任务详细上下文
python workflow.py complete <id>    # 标记任务完成（自动验证依赖）
python workflow.py verify --fix     # 修复状态不一致问题
python workflow.py list --ready     # 列出所有可开始的任务
```

### 快速工具
```bash
make help                   # 显示所有可用命令
make status                 # 项目状态报告
make verify                 # 验证项目结构
make git-commit             # 智能提交
make clean-temp             # 清理临时文件
make install                # 安装依赖
make test                   # 运行测试
```

### 问题跟踪和质量管理
```bash
# 问题跟踪系统
python .claude/scripts/issue_tracker.py list --blocking    # 查看阻塞性问题
python .claude/scripts/issue_tracker.py check --task <id>  # 检查特定任务问题
python .claude/scripts/issue_tracker.py stats              # 查看问题统计
python .claude/scripts/issue_tracker.py add <task> <agent> <severity> <title> <desc>  # 添加问题

# 质量检查系统
python .claude/scripts/quality_check.py <file>             # 检查文件质量
python .claude/scripts/quality_check.py <file> --verify-fixes  # 验证修复
python .claude/scripts/quality_check.py <file> --force-continue # 强制跳过问题

# Agent协调中心
python .claude/scripts/agent_coordinator.py --action status    # 查看Agent状态
python .claude/scripts/agent_coordinator.py --action execute   # 执行Agent协调
```

### 开发环境
```bash
# 后端开发
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端开发  
cd frontend
npm install
npm run dev

# 管理后台
cd admin
npm install
npm run dev
```

## 🏗️ 项目架构

### 目录结构
```
最小化Navigator/
├── backend/                 # FastAPI后端
│   ├── app/main.py         # 应用入口
│   ├── app/api/            # API端点
│   ├── app/services/       # 业务逻辑
│   ├── app/models/         # 数据模型
│   └── app/schemas/        # Pydantic模式
├── frontend/               # React前端
│   ├── src/App.tsx        # 主应用
│   ├── src/pages/         # 页面组件
│   └── src/services/      # API调用
├── admin/                 # 管理后台
├── workflow/              # 工作流管理
│   ├── workflow.py        # 任务管理核心
│   └── tasks/*.yaml       # 任务定义（8个PRD模块）
├── .claude/               # AI Agent系统
│   ├── agents/*.md        # 专业Agent配置
│   └── scripts/*.py       # Agent执行脚本
├── docs/                  # 文档
├── tests/                 # 测试
└── infrastructure/        # 基础设施脚本
```

### 核心组件
- **workflow.py**: 工作流管理器，基于YAML任务定义的状态机，集成问题跟踪
- **Agent系统**: 11个专业Agent提供自动化代码审核和质量保证
- **任务系统**: 69个原子任务，分布在8个PRD模块中
- **问题跟踪系统**: 强制修复循环，发现问题→解决问题→验证修复→继续流程
- **质量门控系统**: 文件修改前自动质量检查，阻塞未修复问题

## 🤖 Agent审核系统 (v2.0 - 强制修复循环版)

项目使用强化的7步架构优先开发流程，集成强制修复循环机制：

### 🔄 强制修复循环流程
1. **质量门控触发**: Edit/Write工具自动触发质量检查
2. **问题发现**: 质量检查发现代码问题（flake8、mypy、linting）
3. **阻塞机制**: 有未解决问题时阻止后续操作
4. **自动修复**: 系统尝试自动修复（black格式化、导入清理）
5. **修复验证**: 重新检查确认问题已解决
6. **继续流程**: 所有问题解决后才能继续

### 📋 Agent工作流程
1. **task-analyzer**: 任务分析专家（每个任务必须执行）
2. **pre-linus-check**: 架构预审专家（60秒快速验证）
3. **功能实现**: 基于预审方案编写代码
4. **quality-gate**: 代码质量检查（**强制修复循环**）
5. **专业验证**: 根据任务特点选择相应专家Agent
6. **linus-architect**: 最终架构审核专家
7. **任务完成**: 所有审核通过且无阻塞性问题后标记完成

### 🛡️ 质量保证机制
- **零容忍原则**: 发现问题必须先修复才能继续
- **自动修复**: 支持代码格式化、导入清理等常见问题
- **智能解析**: 20+种Agent输出格式解析模式
- **问题跟踪**: 完整的问题生命周期管理
- **强制验证**: 修复后自动验证确保问题真正解决

**⚠️ 重要**: 系统现在强制执行修复循环，不允许跳过问题解决步骤。

## 📝 代码规范

### 强制要求
- **类型注解100%**: 所有函数参数、返回值必须有类型注解
- **完整文档字符串**: 公共函数必须有docstring（Args/Returns/Raises）
- **语义化命名**: 使用具体名称，避免模糊命名
- **配置化常量**: 禁止硬编码，使用环境变量或config文件
- **完整错误处理**: 每个外部调用都必须有try-catch

### 自动化检查
```bash
black . && mypy . --strict && flake8 . --max-line-length=88
```

## 🧪 测试和验证

```bash
# 运行后端测试
cd backend && pytest --cov=app tests/

# 运行前端测试
cd frontend && npm test

# 运行集成测试
cd tests && python -m pytest integration/

# 验证项目状态
python workflow.py verify --fix
```

## 📊 项目状态

当前进度：25/69 任务完成（36.2%）
- ✅ PRD-01: 基础设施（100%完成）
- ✅ PRD-02: 数据管道（100%完成）  
- 🔄 PRD-03: 分析引擎（38%完成）
- 🔄 PRD-04-08: 核心功能模块（0-12%完成）

## ⚠️ 重要原则

### 必须遵守
- **数据结构优先**: 先设计数据模型，再写业务逻辑
- **消除特殊情况**: 每个if-else分支都是设计缺陷，重构消除
- **使用Agent系统**: 相信自动化，不要跳过质量检查
- **强制修复循环**: 发现问题必须先修复才能继续操作
- **最小上下文**: 只加载当前任务必需的文件和信息
- **配置即代码**: 所有参数通过YAML文件管理，版本控制

### 绝对禁止
- **超过3层嵌套**: 函数复杂度过高，立即重构
- **跳过验证步骤**: 质量优先于速度
- **跳过问题修复**: 发现问题必须先解决再继续
- **硬编码常量**: 使用环境变量或配置文件
- **缺失类型注解**: Python和TypeScript必须100%覆盖
- **破坏向后兼容**: 任何改动不能破坏现有功能

## 🔧 故障排除

### 常见问题
- **任务被阻塞**: 检查依赖关系 `python workflow.py context <task_id>`
- **质量检查失败**: 先修复问题再继续，使用 `python .claude/scripts/quality_check.py <file> --verify-fixes`
- **Agent审核失败**: 查看 `.claude/logs/agent_audit.json`
- **问题跟踪阻塞**: 检查阻塞性问题 `python .claude/scripts/issue_tracker.py list --blocking`
- **构建失败**: 清理缓存 `make clean-cache`
- **依赖问题**: 重新安装 `make install`

### 调试工具
```bash
# 查看详细错误日志
tail -f .claude/logs/*.log

# 检查问题跟踪状态
python .claude/scripts/issue_tracker.py stats

# Agent审核解析调试
python .claude/scripts/agent_audit_logger.py --debug --test "测试内容"

# 质量检查调试
AGENT_AUDIT_DEBUG=1 python .claude/scripts/quality_check.py <file>

# 检查Git状态
make git-status

# 验证项目完整性
make verify
```

---

**核心哲学**: "简单胜过聪明" - Linus Torvalds

使用Agent系统确保代码质量，使用workflow系统管理任务进度，始终优先考虑架构设计。