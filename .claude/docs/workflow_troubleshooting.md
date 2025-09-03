# Workflow.py 故障排除指南

## 常见问题诊断与解决

### 1. 任务完成时的EOF错误

**症状**: 
```
EOFError: EOF when reading a line
```

**根本原因**: workflow.py在非交互环境中使用input()函数

**解决方案**:
```bash
# 使用--force参数跳过交互确认
python workflow.py complete <task_id> --force

# 或者使用--no-verify跳过所有验证
python workflow.py complete <task_id> --no-verify
```

### 2. Agent审核记录缺失

**症状**:
```
⚠️ 任务 prd03-05 没有找到审核记录
❌ 任务未通过必需的Agent审核流程
```

**根本原因**: Agent审核系统与workflow.py状态管理不同步

**解决方案**:
```bash
# 手动添加审核记录
python .claude/scripts/agent_audit_sync.py add <task_id>

# 验证审核记录
python .claude/scripts/agent_audit_sync.py verify <task_id>

# 强制完成任务（跳过审核检查）
python workflow.py complete <task_id> --force
```

### 3. 文件验证失败

**症状**:
```
⚠️ 验证失败 - 缺少文件: ['file1.py', 'file2.py']
```

**解决方案**:
```bash
# 创建缺失的文件（如果需要）
touch backend/app/services/missing_file.py

# 或者使用--force跳过文件验证
python workflow.py complete <task_id> --force
```

### 4. 问题跟踪器不可用

**症状**:
```
⚠️ 问题跟踪器不可用，使用传统审核检查
```

**原因**: .claude/scripts/issue_tracker.py 文件缺失或导入错误

**解决方案**:
```bash
# 检查文件是否存在
ls -la .claude/scripts/issue_tracker.py

# 如果不影响功能，可以忽略此警告
# 系统会自动回退到传统审核检查
```

## 预防措施

### 1. 定期同步审核记录
```bash
# 每完成几个任务后，检查审核记录同步
python .claude/scripts/agent_audit_sync.py sync
```

### 2. 使用非交互模式
```bash
# 在CI/CD或脚本中，总是使用--force或--no-verify
export WORKFLOW_NON_INTERACTIVE=1
python workflow.py complete <task_id> --force
```

### 3. 状态完整性验证
```bash
# 定期验证项目状态完整性
python workflow.py verify --fix
```

## 紧急修复命令

### 快速完成任务（跳过所有检查）
```bash
python workflow.py complete <task_id> --no-verify
```

### 重置异常状态
```bash
# 重置特定任务
python workflow.py reset --task <task_id>

# 重置所有状态（慎用）
python workflow.py reset --all
```

### 查看详细状态
```bash
# 获取任务上下文和依赖信息
python workflow.py context <task_id>

# 查看整体项目状态
python workflow.py status
```

## 开发建议

### 1. Agent系统集成改进
- 统一状态管理接口
- 自动同步审核记录
- 增加集成测试

### 2. 交互环境检测优化
- 自动检测运行环境
- 非交互环境下自动使用默认选项
- 提供环境变量配置选项

### 3. 错误处理增强
- 更详细的错误信息
- 自动修复建议
- 回滚机制

## 监控和日志

### 重要日志文件
```
.claude/logs/
├── agent_audit.json          # Agent审核记录
├── issue_tracker.log         # 问题跟踪日志
├── quality-gate.log          # 质量检查日志
└── workflow_state.json       # 工作流状态
```

### 状态文件位置
```
workflow/state.json           # 主要状态文件
```

定期检查这些文件有助于诊断和预防问题。