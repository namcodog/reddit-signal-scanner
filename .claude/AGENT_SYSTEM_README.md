# Reddit Signal Scanner - Subagent系统使用指南

## 系统概述

基于Linus Torvalds哲学设计的智能化开发助手系统，包含5个核心专业Agent：

- **质量门控Agent**: 代码质量自动检查
- **信号验证Agent**: Reddit数据质量验证  
- **性能监控Agent**: 系统性能实时监控
- **任务编排Agent**: 智能任务流程管控
- **配置同步Agent**: 配置文件一致性管理

## 🚀 快速开始

### 1. 系统状态检查
```bash
# 检查所有Agent配置
ls -la .claude/agents/

# 验证hooks配置
cat .claude/settings.json

# 测试脚本权限
ls -la .claude/scripts/
```

### 2. 手动触发测试
```bash
# 质量检查
python3 .claude/scripts/quality_check.py <文件路径>

# 性能监控  
python3 .claude/scripts/perf_metrics.py --all

# 信号验证
python3 .claude/scripts/signal_validate.py <数据文件>

# 配置同步
python3 .claude/scripts/config_sync.py --validate
```

### 3. 自动触发验证
创建/编辑任意文件，系统会自动执行质量检查：
```bash
echo "print('test')" > test_file.py
# 质量门控Agent会自动触发
```

## 📋 Agent详细说明

### 1. 质量门控Agent (`quality-gate`)

**触发条件**: Edit/Write/MultiEdit工具使用前
**执行时间**: <30秒
**主要功能**:
- Python语法和风格检查 (flake8)
- TypeScript编译检查 (tsc)
- Linus风格代码规范检查
- 安全问题检测（硬编码密钥等）

**配置选项**:
```bash
export QUALITY_GATE_STRICT=1    # 严格模式
export QUALITY_GATE_SKIP=1      # 跳过检查（紧急情况）
export QUALITY_GATE_LOG=1       # 详细日志
```

### 2. 信号验证Agent (`signal-validator`)

**触发条件**: WebFetch等数据获取后
**执行时间**: <60秒  
**主要功能**:
- 数据源可信度评估
- 统计显著性验证
- 假阳性风险检测
- 商业可行性分析

**输出标准**:
- 高置信度 (>0.8): 直接使用
- 中等置信度 (0.5-0.8): 谨慎使用  
- 低置信度 (<0.5): 重新分析

### 3. 性能监控Agent (`perf-monitor`)

**触发条件**: API调用后 + 定时监控
**执行时间**: <10秒
**监控指标**:
- API响应时间 (目标<200ms)
- Redis缓存命中率 (目标>85%)
- 系统资源使用 (CPU<70%, Memory<80%)

**告警阈值**:
```json
{
  "api_response_time": {"critical": 2000, "warning": 500},
  "cache_hit_rate": {"critical": 0.5, "warning": 0.6},
  "cpu_usage": {"critical": 85, "warning": 70}
}
```

### 4. 任务编排Agent (`task-orchestrator`)

**触发条件**: TodoWrite工具使用后
**执行时间**: <20秒
**核心能力**:
- 自动依赖关系分析
- 阻塞任务智能处理
- 动态优先级调整
- 并行执行机会识别

**优化原则**:
- 最小化总完成时间
- 最大化并行执行
- 风险分散策略

### 5. 配置同步Agent (`config-sync`)

**触发条件**: 会话结束时
**执行时间**: <15秒
**验证内容**:
- YAML语法检查
- 配置结构验证
- 环境间一致性
- 安全性审计

## 🔧 故障排除

### 常见问题

#### 1. Agent脚本权限错误
```bash
# 解决方案
chmod +x .claude/scripts/*.py
```

#### 2. Python依赖缺失
```bash
# 安装必需依赖
pip install psutil pyyaml requests
```

#### 3. Hooks不触发
检查settings.json格式：
```json
{
  "PreToolUse": [{"script": "$CLAUDE_PROJECT_DIR/.claude/scripts/quality_check.py"}]
}
```

#### 4. 脚本执行超时
调整超时设置或优化脚本性能：
```bash
# 设置环境变量跳过耗时检查
export QUALITY_GATE_SKIP=1
```

### 调试模式

启用详细日志：
```bash
export CLAUDE_HOOK_MODE=1
export QUALITY_GATE_LOG=1

# 查看日志
tail -f .claude/logs/quality-gate.log
```

### 性能调优

#### 脚本执行时间优化
```python
# 在脚本中添加性能监控
import time
start_time = time.time()
# ... 执行逻辑
print(f"执行时间: {time.time() - start_time:.2f}秒")
```

#### 并发限制
避免多个Agent同时执行造成系统负载：
```bash
# 检查运行中的Agent进程
ps aux | grep claude/scripts
```

## 📊 系统监控

### 状态检查命令
```bash
# Agent系统健康检查
python3 .claude/scripts/perf_metrics.py --all

# 配置完整性验证
python3 .claude/scripts/config_sync.py --validate

# 查看所有Agent状态
find .claude/agents/ -name "*.md" -exec echo "=== {} ===" \; -exec head -5 {} \;
```

### 日志位置
```bash
.claude/logs/
├── quality-gate.log      # 质量检查日志
├── performance/          # 性能监控历史数据
│   ├── metrics_2025-08-21.jsonl
│   └── ...
└── agent_results/        # Agent执行结果
```

### 性能指标
监控Agent系统影响：
- Hook执行时间 < 各Agent超时限制
- 系统整体响应延迟 < 5秒  
- Agent成功执行率 > 95%

## 🎯 最佳实践

### 1. Agent使用原则
- **渐进启用**: 先启用单个Agent，验证稳定后再启用全部
- **监控优先**: 密切关注Agent执行时间和成功率
- **优雅降级**: 遇到问题时可临时禁用特定Agent

### 2. 自定义配置
```bash
# 项目特定配置
cp .claude/settings.json .claude/settings.local.json
# 修改local版本，保持原版本作为模板
```

### 3. 团队协作
- Agent配置文件提交到版本控制
- 敏感配置（密钥等）使用环境变量
- 定期同步Agent版本和配置

### 4. 持续优化
- 根据执行日志优化Agent性能
- 定期review和更新Agent逻辑
- 收集团队反馈改进User Experience

## 🚨 紧急情况处理

### 完全禁用Agent系统
```bash
# 重命名settings.json临时禁用
mv .claude/settings.json .claude/settings.json.disabled
```

### 单独禁用特定Agent
```bash
# 修改特定Agent脚本返回成功
echo "exit 0" > .claude/scripts/problem_agent.py
```

### 系统恢复
```bash
# 从备份恢复配置
git checkout -- .claude/settings.json
chmod +x .claude/scripts/*.py
```

---

**记住Linus的话**: "代码胜于雄辩。如果Agent不能让你的工作更简单，那就是设计问题。"

这个Agent系统的设计初衷是**减少** 开发摩擦，而不是增加。如果任何Agent造成困扰，请立即禁用并报告问题。

**系统版本**: v1.0  
**最后更新**: 2025-08-21  
**维护责任**: 开发团队

---

## 附录

### A. 完整的Agent文件列表
```bash
.claude/
├── agents/
│   ├── quality-gate.md         # 质量门控Agent
│   ├── signal-validator.md     # 信号验证Agent
│   ├── perf-monitor.md         # 性能监控Agent
│   ├── task-orchestrator.md   # 任务编排Agent
│   └── config-sync.md          # 配置同步Agent
├── scripts/
│   ├── quality_check.py        # 质量检查脚本
│   ├── signal_validate.py      # 信号验证脚本
│   ├── perf_metrics.py         # 性能监控脚本
│   └── config_sync.py          # 配置同步脚本
├── settings.json               # Hooks配置
└── AGENT_SYSTEM_README.md      # 本文档
```

### B. 环境变量完整列表
```bash
# 质量门控
QUALITY_GATE_STRICT=1          # 严格模式
QUALITY_GATE_SKIP=1            # 跳过检查
QUALITY_GATE_LOG=1             # 详细日志

# 调试模式
CLAUDE_HOOK_MODE=1             # Hook调试模式
CLAUDE_PROJECT_DIR             # 项目根目录(自动设置)

# 性能监控
PERF_MONITOR_INTERVAL=300      # 监控间隔(秒)
```