# Reddit Signal Scanner 工作流管理工具

基于 **Linus Torvalds 设计哲学**：数据结构优先、简单胜过聪明

## 🎯 设计目标

这是一个专为 **Claude Code** 上下文窗口限制优化的工作流管理工具，解决以下问题：

1. **上下文窗口有限**：将大型PRD文档拆分为适合Claude Code处理的原子任务
2. **依赖关系复杂**：自动管理任务间的依赖关系，确保开发顺序正确  
3. **状态管理混乱**：提供可靠的任务状态跟踪和进度管理
4. **项目连贯性**：每次初始化都能快速了解项目状态和下一步任务

## 📊 项目概况

- **总任务数**: 69个原子任务
- **覆盖PRD**: 8个核心PRD文档
- **任务粒度**: 适合Claude Code单次会话完成
- **依赖管理**: 自动验证和解锁机制

## 🚀 快速开始

### 每次Claude Code初始化时的标准流程

```bash
# 1. 查看项目整体状态
python workflow.py status

# 2. 获取下一个任务的上下文
python workflow.py context <task_id>

# 3. [执行开发任务]

# 4. 标记任务完成
python workflow.py complete <task_id>

# 5. 确认新状态
python workflow.py status
```

## 📋 命令详解

### 核心命令

#### `status` - 项目状态总览
```bash
python workflow.py status
```
显示：
- 整体完成进度
- 可开始的任务列表
- 各PRD完成度统计
- 被阻塞任务数量

#### `context <task_id>` - 获取任务上下文
```bash
python workflow.py context prd01-01
```
显示：
- 任务详细描述和要求
- 相关文件列表（相对路径）
- 依赖关系检查
- 最小必要上下文信息

#### `complete <task_id>` - 标记任务完成
```bash
python workflow.py complete prd01-01
# 跳过文件验证
python workflow.py complete prd01-01 --no-verify
```
功能：
- 验证依赖关系满足
- 可选的文件存在性检查
- 自动解锁后续任务
- 更新整体进度

### 辅助命令

#### `list` - 任务列表
```bash
# 显示所有任务
python workflow.py list

# 只显示可开始的任务
python workflow.py list --ready

# 只显示已完成的任务  
python workflow.py list --completed

# 按PRD过滤任务
python workflow.py list --prd prd-01
```

#### `verify` - 状态完整性检查
```bash
# 验证状态文件完整性
python workflow.py verify

# 自动修复发现的问题
python workflow.py verify --fix
```

#### `reset` - 状态重置
```bash
# 重置特定任务
python workflow.py reset --task prd01-01

# 重置所有状态（危险操作）
python workflow.py reset --all
```

## 📁 文件结构

```
workflow/
├── workflow.py          # 主程序
├── config.yaml         # 配置文件
├── state.yaml          # 状态文件（自动生成）
├── tasks/              # 任务定义
│   ├── prd-01.yaml    # PRD-01的10个子任务
│   ├── prd-02.yaml    # PRD-02的9个子任务
│   ├── prd-03.yaml    # PRD-03的8个子任务
│   ├── prd-04.yaml    # PRD-04的8个子任务
│   ├── prd-05.yaml    # PRD-05的9个子任务
│   ├── prd-06.yaml    # PRD-06的8个子任务
│   ├── prd-07.yaml    # PRD-07的8个子任务
│   └── prd-08.yaml    # PRD-08的9个子任务
└── README.md           # 本文档
```

## 🔧 任务设计原则

### 任务大小分级
- **S (Small)**: 1-2小时，单文件修改，<1000行上下文
- **M (Medium)**: 2-4小时，多文件修改，<3000行上下文
- **L (Large)**: 4-8小时，模块级实现，<5000行上下文

### 依赖关系设计
- **硬依赖**: 必须先完成前置任务才能开始
- **清晰的依赖路径**: 避免循环依赖
- **并行友好**: 最大化并行开发可能性

### 上下文优化
每个任务包含：
- **最小必要上下文**: 只加载相关文件和文档
- **具体实现指导**: 明确的技术要求和验收标准
- **文件路径**: 相对路径，便于快速定位

## 🛠️ 故障恢复机制

### 自动修复
- 状态文件损坏自动检测和修复
- 依赖关系违规自动纠正
- 无效任务ID自动清理

### 手动干预
- `verify --fix`: 一键修复常见问题
- `reset --task`: 重置有问题的任务
- `reset --all`: 紧急情况下的完全重置

### 数据安全
- 自动备份机制：state.yaml.backup
- 操作确认：危险操作需要用户确认
- 版本历史：通过Git管理所有配置

## 📈 使用最佳实践

### 每日开发流程
1. **开始前**: `python workflow.py status` 了解项目状态
2. **选择任务**: 选择Ready状态的任务
3. **获取上下文**: `python workflow.py context <task_id>`
4. **执行开发**: 根据上下文信息实施任务
5. **完成标记**: `python workflow.py complete <task_id>`
6. **验证状态**: 确认新任务已解锁

### 团队协作
- 使用Git同步状态文件
- 定期运行`verify`检查状态一致性
- 通过PRD分工：不同开发者负责不同PRD

### 问题排查
1. **状态不一致**: `python workflow.py verify --fix`
2. **任务卡住**: 检查依赖关系，可能需要重置上游任务
3. **文件丢失**: 使用`--no-verify`跳过文件检查
4. **进度丢失**: 从state.yaml.backup恢复

## 🎯 核心价值

1. **上下文适配**: 专为Claude Code的限制设计
2. **依赖自动化**: 无需手动管理复杂依赖关系  
3. **状态可靠**: 故障自愈，数据安全
4. **进度透明**: 实时了解项目真实进度
5. **开发连贯**: 每次初始化都能快速接续工作

## 💡 设计哲学

基于Linus Torvalds的核心原则：

> "Bad programmers worry about the code. Good programmers worry about data structures and their relationships."

- **数据结构优先**: 任务和依赖关系的清晰建模
- **消除特殊情况**: 统一的状态管理，没有例外
- **简单胜过聪明**: 69个原子任务，不是复杂的元编程
- **Never break userspace**: 向后兼容，不破坏现有工作流

---

**记住**: "Talk is cheap. Show me the code." - 现在开始使用这个工具，将PRD转化为可执行的代码！