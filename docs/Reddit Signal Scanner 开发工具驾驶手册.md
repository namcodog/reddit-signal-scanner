🚗 Reddit Signal Scanner 开发工具驾驶手册

  一、你的"座驾"配置

  你拥有一个三层智能化开发系统：

  🎯 任务管理层 (workflow.py) - 69个原子任务的智能调度
  🛡️ 质量保证层 (5个Agent) - 自动化代码质量和性能监控
  ⚡ 便捷操作层 (Makefile) - 一键执行常用命令

  二、标准驾驶流程（每日开发）

  🌅 早晨启动 - 项目初始化

  # 1. 查看项目整体状态
  python workflow.py status

  # 2. 检查Git状态和建议
  make git-status

  # 3. 快速健康检查
  make verify

  🚀 开始工作 - 任务执行

  # 1. 选择任务（workflow会告诉你哪些任务ready）
  python workflow.py status

  # 2. 获取任务上下文（自动加载最小必要信息）
  python workflow.py context prd01-03

  # 3. 开始编码
  # 当你使用Edit/Write/MultiEdit时，质量门控Agent会自动触发
  # 无需手动运行检查！

  🛡️ 自动保护 - Agent守护

  系统配置了5个智能Agent，它们会自动触发：

  1. 质量门控Agent - 编辑文件前自动检查代码质量
  2. Linus架构Agent - 多文件编辑时自动审查架构
  3. 性能监控Agent - API调用后自动记录性能
  4. Git工作流Agent - 会话结束时提醒提交
  5. 配置同步Agent - 会话结束时验证配置一致性

  ✅ 任务完成 - 标记进度

  # 1. 标记任务完成（会自动验证依赖和文件）
  python workflow.py complete prd01-03

  # 2. 交互式Git提交
  make git-commit

  # 3. 查看新解锁的任务
  python workflow.py status

  三、高级驾驶技巧

  🏎️ 性能模式 - 并行开发

  # 查看所有可并行的任务
  python workflow.py list --ready

  # 多个开发者可以同时处理不同PRD
  # Developer A: python workflow.py context prd01-*
  # Developer B: python workflow.py context prd02-*

  🔧 维护模式 - 项目清理

  # 清理临时文件
  make clean-temp

  # 深度清理（重置环境）
  make clean-all

  # 验证项目结构
  make verify

  🚨 紧急模式 - 问题处理

  # Agent造成困扰时，临时禁用
  export QUALITY_GATE_SKIP=1

  # 状态文件损坏，自动修复
  python workflow.py verify --fix

  # 任务卡住，重置特定任务
  python workflow.py reset --task prd01-03

  四、最佳驾驶习惯

  ✅ 推荐做法

  1. 每次开始前运行 workflow.py status - 了解全局状态
  2. 相信Agent系统 - 它们会自动工作，不要重复检查
  3. 使用任务上下文 - 只加载必要信息，避免上下文溢出
  4. 频繁提交 - 使用 make git-commit 保持代码同步

  ❌ 避免做法

  1. 不要跳过依赖 - workflow会自动管理
  2. 不要手动运行质量检查 - Agent会自动执行
  3. 不要在根目录创建临时文件 - 使用正确的目录结构
  4. 不要忽略Agent警告 - 它们是基于Linus哲学设计的

  五、仪表盘指标

  📊 关键指标监控

  # 项目整体进度
  python workflow.py status
  # 显示：完成率、可用任务、阻塞数量

  # 性能监控
  python3 .claude/scripts/perf_metrics.py --all
  # 显示：API响应时间、缓存命中率、资源使用

  # 代码质量
  # 自动运行，查看日志：
  tail -f .claude/logs/quality-gate.log

  六、快速参考卡

  # 🎯 任务管理
  workflow.py status          # 看状态
  workflow.py context <id>    # 获取上下文
  workflow.py complete <id>   # 标记完成

  # ⚡ 快捷命令
  make help                   # 查看所有命令
  make git-commit            # 智能提交
  make clean-temp            # 清理垃圾

  # 🛡️ Agent控制
  export QUALITY_GATE_SKIP=1     # 跳过质量检查
  export QUALITY_GATE_STRICT=1   # 严格模式
  export CLAUDE_HOOK_MODE=1      # 调试模式

  七、核心理念

  记住Linus的话：
  "Talk is cheap. Show me the code."

  这个工具系统的设计理念：
  - 数据结构优先 - 69个原子任务的清晰定义
  - 消除特殊情况 - 所有任务统一管理
  - 自动化一切 - Agent自动触发，无需手动
  - 故障自愈 - 状态损坏自动修复

  你只需要专注于编码，工具会处理其他一切！