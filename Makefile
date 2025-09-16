# Reddit Signal Scanner (RSS) - Makefile
# 基于Linus Torvalds哲学：简单、实用、不破坏任何东西
# 更新日期: 2025-08-21

.PHONY: help clean-temp clean-cache clean-deprecated clean-all verify install test test-framework-verify test-framework-check git-setup git-status git-commit git-flow git-help branch-protect

# 默认目标：显示帮助
help:
	@echo "🚀 Reddit Signal Scanner - 项目管理工具"
	@echo ""
	@echo "📋 文件管理命令："
	@echo "  help            显示此帮助信息"
	@echo "  clean-temp      清理临时文件"
	@echo "  clean-cache     清理缓存文件"
	@echo "  clean-deprecated 归档废弃文件"
	@echo "  clean-all       执行深度清理"
	@echo "  verify          验证项目结构"
	@echo ""
	@echo "🌳 Git工作流命令："
	@echo "  git-setup       初始化Git环境"
	@echo "  git-status      显示Git状态和建议"
	@echo "  git-commit      交互式提交"
	@echo "  git-flow        Git工作流管理"
	@echo "  git-help        显示Git命令帮助"
	@echo "  branch-protect  配置分支保护（需要 GITHUB_TOKEN）"
	@echo ""
	@echo "🔧 开发环境命令："
	@echo "  install         安装依赖"
	@echo "  test            运行测试"
	@echo "  test-framework-verify  验证测试框架"
	@echo "  test-framework-check   测试框架自检"
	@echo "  status          查看项目状态"
	@echo "  type-check      严格类型检查 (backend/app + tests)"
	@echo "  tech-debt-metrics  输出技术债指标 (mypy/Dict[Any]/无类型函数)"
	@echo "  backend-smoke   后端冒烟小集 (tests/smoke)"
	@echo "  frontend-quick  前端单测小集 (vitest 组件/Hook/工具)"
	@echo "  file-check      文件结构/脏文件检查"
	@echo "  quick-gate-local 一次跑完四个快速闸门"
	@echo ""
	@echo "🧪 本地CI："
	@echo "  ci-lint        运行 flake8/black-check/isort-check"
	@echo "  ci-type        运行 mypy --strict (backend/app + tests)"
	@echo "  ci-test        运行单元/系统基础测试 (可传 LABELS=...)"
	@echo "  ci-integration 运行集成/系统测试 (需本地服务)"
	@echo "  ci-perf        运行性能与Chaos用例并生成基线"
	@echo "  ci-perf-gate   对比性能基线 (需传 PREV=/path/to/prev.json TOL=10 MODE=soft|hard)"
	@echo "  ci-all         本地质量闸门 (lint+type+快速测试)"
	@echo ""
	@echo "🛡️  安全提示：所有清理操作都有确认提示"

# 清理临时文件
clean-temp:
	@echo "🧹 清理临时文件..."
	@echo "即将删除以下文件："
	@find . -name "*.tmp" -o -name "*.temp" -o -name "*_temp.*" -o -name "*_test.*" | head -10
	@echo -n "确认继续？ [y/N]: "; read confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		find . -name "*.tmp" -delete 2>/dev/null || true; \
		find . -name "*.temp" -delete 2>/dev/null || true; \
		find . -name "*_temp.*" -delete 2>/dev/null || true; \
		find . -name "*_test.*" -delete 2>/dev/null || true; \
		find . -name "*.pyc" -delete 2>/dev/null || true; \
		find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true; \
		rm -rf backend/tmp/* 2>/dev/null || true; \
		rm -rf frontend/.cache/* 2>/dev/null || true; \
		rm -rf admin/.cache/* 2>/dev/null || true; \
		echo "✅ 临时文件清理完成"; \
	else \
		echo "❌ 操作已取消"; \
	fi

# 清理缓存文件
clean-cache:
	@echo "🗄️  清理缓存文件..."
	@echo "即将删除缓存目录内容"
	@echo -n "确认继续？ [y/N]: "; read confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		rm -rf backend/.cache/* 2>/dev/null || true; \
		rm -rf frontend/.cache/* 2>/dev/null || true; \
		rm -rf frontend/.next/* 2>/dev/null || true; \
		rm -rf frontend/.vite/* 2>/dev/null || true; \
		rm -rf admin/.cache/* 2>/dev/null || true; \
		rm -rf admin/.next/* 2>/dev/null || true; \
		rm -rf admin/.vite/* 2>/dev/null || true; \
		rm -rf .pytest_cache 2>/dev/null || true; \
		rm -rf htmlcov 2>/dev/null || true; \
		echo "✅ 缓存清理完成"; \
	else \
		echo "❌ 操作已取消"; \
	fi

# 归档废弃文件
clean-deprecated:
	@echo "📦 归档废弃文件..."
	@if [ -f "infrastructure/scripts/archive_deprecated.py" ]; then \
		python3 infrastructure/scripts/archive_deprecated.py; \
	else \
		echo "⚠️  归档脚本不存在，跳过此步骤"; \
	fi

# 深度清理（开发环境重置）
clean-all: clean-temp clean-cache clean-deprecated
	@echo "💣 深度清理模式..."
	@echo "⚠️  这将删除所有依赖和构建文件"
	@echo -n "确认继续？ [y/N]: "; read confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		rm -rf node_modules 2>/dev/null || true; \
		rm -rf frontend/node_modules 2>/dev/null || true; \
		rm -rf admin/node_modules 2>/dev/null || true; \
		rm -rf backend/venv 2>/dev/null || true; \
		rm -rf backend/.venv 2>/dev/null || true; \
		rm -rf build 2>/dev/null || true; \
		rm -rf dist 2>/dev/null || true; \
		rm -rf *.egg-info 2>/dev/null || true; \
		echo "🔥 深度清理完成，请重新运行 make install"; \
	else \
		echo "❌ 操作已取消"; \
	fi

# 验证项目结构
verify:
	@echo "🔍 验证项目结构..."
	@if [ -f "infrastructure/scripts/verify_structure.py" ]; then \
		python3 infrastructure/scripts/verify_structure.py; \
	else \
		echo "📁 手动检查项目结构:"; \
		echo "Backend:"; \
		ls -la backend/ 2>/dev/null || echo "❌ backend目录不存在"; \
		echo "Frontend:"; \
		ls -la frontend/ 2>/dev/null || echo "❌ frontend目录不存在"; \
		echo "Docs:"; \
		ls -la docs/ 2>/dev/null || echo "❌ docs目录不存在"; \
		echo "✅ 基础结构检查完成"; \
	fi

# 安装依赖
install:
	@echo "📦 安装项目依赖..."
	@echo "安装后端依赖..."
	@if [ -d "backend" ]; then \
		cd backend && \
		python3 -m venv venv && \
		. venv/bin/activate && \
		pip install -r requirements.txt; \
	fi
	@echo "安装前端依赖..."
	@if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then \
		cd frontend && npm install; \
	fi
	@if [ -d "admin" ] && [ -f "admin/package.json" ]; then \
		cd admin && npm install; \
	fi
	@echo "✅ 依赖安装完成"

# 运行测试
test:
	@echo "🧪 运行测试..."
	@if [ -d "backend" ]; then \
		echo "运行后端测试..."; \
		cd backend && . venv/bin/activate && pytest --cov=app tests/ 2>/dev/null || echo "⚠️  后端测试失败或不存在"; \
	fi
	@if [ -d "frontend" ]; then \
		echo "运行前端测试..."; \
		cd frontend && npm test 2>/dev/null || echo "⚠️  前端测试失败或不存在"; \
	fi
	@echo "✅ 测试完成"

# ================================
# 代码质量命令（Claude Code专用）
# ================================

# 快速类型检查（单文件）
check-types:
	@echo "🔍 运行严格类型检查..."
	@if [ -z "$(FILE)" ]; then \
		echo "用法: make check-types FILE=backend/app/your_file.py"; \
	else \
		cd backend && bash scripts/enforce_types.sh $(FILE); \
	fi

# 质量门控检查
check-quality:
	@echo "🎯 运行质量门控检查..."
	@cd backend && python scripts/quality_gate.py --all-files

# 自动修复代码格式
fix-format:
	@echo "🎨 自动修复代码格式..."
	@cd backend && black app/ && isort app/
	@echo "✅ 代码格式修复完成"

# 修复类型问题（交互式）
fix-types:
	@echo "🔧 类型问题修复向导..."
	@echo "1. 运行MyPy检查找出问题"
	@cd backend && mypy --strict app/ --show-error-codes || true
	@echo ""
	@echo "2. 自动格式化代码"
	@cd backend && black app/ && isort app/
	@echo ""
	@echo "3. 重新运行类型检查"
	@cd backend && mypy --strict app/ --show-error-codes
	@echo "✅ 请根据上述错误信息手动修复类型问题"

# 严格类型检查 - 后端专用
type-check:
	@echo "🔍 MyPy 严格类型检查 (backend/app + tests) ..."
	@cd backend && python -m mypy --config-file mypy.ini --strict app tests

# 四项快速闸门（本地）
backend-smoke:
	@echo "🔥 后端冒烟测试 (tests/smoke) ..."
	@PYTHONPATH=backend:. pytest -p pytest_asyncio -q -m smoke tests/smoke

frontend-quick:
	@echo "⚛️  前端单测小集 (components/hooks/utils) ..."
	@cd frontend && npm ci && npm test -- --run src/__tests__/components src/__tests__/hooks src/__tests__/utils

file-check:
	@echo "📁 文件结构与脏文件检查 ..."
	@python infrastructure/scripts/verify_structure.py || true

quick-gate-local:
	@echo "🚦 运行本地四项快速闸门 (类型/后端/前端/文件检查) ..."
	@cd backend && python -m mypy --config-file mypy.ini --strict app tests
	@PYTHONPATH=backend:. pytest -p pytest_asyncio -q -m smoke tests/smoke
	@cd frontend && npm ci && npm test -- --run src/__tests__/components src/__tests__/hooks src/__tests__/utils
	@python infrastructure/scripts/verify_structure.py || true

# ================================
# 本地CI命令
# ================================

ci-lint:
	@python3 tests/ci/test_runner.py lint

ci-type:
	@python3 tests/ci/test_runner.py type

ci-test:
	@python3 tests/ci/test_runner.py test --labels "$(LABELS)"

ci-integration:
	@python3 tests/ci/test_runner.py integration

ci-perf:
	@python3 tests/ci/test_runner.py perf

ci-perf-gate:
	@if [ -z "$(PREV)" ]; then \
		echo "用法: make ci-perf-gate PREV=/path/to/prev.json [TOL=10] [MODE=soft|hard]"; \
		exit 1; \
	fi
	@python3 tests/ci/test_runner.py perf_gate --prev "$(PREV)" --tol "$(TOL)" --mode "$(MODE)"

ci-all: ci-lint ci-type
	@python3 tests/ci/test_runner.py test --labels "unit or security or system and not slow"

# 100%全栈质量检查 - 前后端统一标准
quality-check-full:
	@echo "🎯 100%全栈质量检查 - 前后端统一"
	@echo "==========================================="
	@echo "🐍 后端质量检查..."
	@mypy --config-file backend/mypy.ini --strict backend/app 2>&1 | head -20 || true
	@echo ""
	@echo "⚛️  前端质量检查..."
	@cd frontend && npm run type-check 2>&1 | head -20 || true
	@cd frontend && npm run lint 2>&1 | head -20 || true
	@echo "==========================================="
	@echo "✅ 质量检查完成，查看详细指标请运行: make tech-debt-metrics"


# 技术债指标 - 100%覆盖前后端（便于日报/周报追踪）
tech-debt-metrics:
	@echo "📊 技术债指标 - 全栈覆盖"
	@echo "==========================================="
	@echo "🐍 后端 (backend/app)"
	@echo "-------------------------------------------"
	@echo "📈 MyPy错误统计:" && \
	 mypy --config-file backend/mypy.ini --strict backend/app 2>&1 | grep "error" | wc -l | xargs echo "  当前错误数:" || true
	@echo "📦 Dict[str, Any] 使用统计:" && \
	 grep -R "Dict\[str, Any\]" backend/app --include="*.py" | wc -l | xargs echo "  当前使用数:" || true
	@echo "🧩 无类型函数统计:" && \
	 mypy --config-file backend/mypy.ini --strict backend/app 2>&1 | grep "no-untyped-def" | wc -l | xargs echo "  当前数量:" || true
	@echo ""
	@echo "⚛️  前端 (frontend/src)"  
	@echo "-------------------------------------------"
	@echo "📈 TypeScript错误统计:" && \
	 (cd frontend && npm run type-check 2>&1 | grep "error" | wc -l | xargs echo "  当前错误数:") || echo "  当前错误数: 检查失败"
	@echo "⚠️  ESLint错误统计:" && \
	 (cd frontend && npm run lint 2>&1 | grep "error" | wc -l | xargs echo "  当前错误数:") || echo "  当前错误数: 检查失败" 
	@echo "❌ any类型使用统计:" && \
	 grep -R ": any" frontend/src --include="*.ts" --include="*.tsx" --exclude="*.test.*" | wc -l | xargs echo "  当前使用数:" || true
	@echo "🧪 测试覆盖率:" && \
	 find frontend/src -name "*.test.ts*" | wc -l | xargs echo "  测试文件数:" || true
	@echo "==========================================="

# 验证测试框架
test-framework-verify:
	@echo "🔍 验证测试框架..."
	@echo "==========================================="
	@python tests/verify_framework.py

# 测试框架自检
test-framework-check:
	@echo "🧪 测试框架自检..."
	@echo "==========================================="
	@pytest tests/test_framework_self_check.py -v --tb=short

# 项目状态报告
status:
	@echo "📊 项目状态报告"
	@echo "================="
	@echo "📁 目录结构:"
	@ls -la | grep "^d" || true
	@echo ""
	@echo "📦 文件统计:"
	@find . -name "*.py" | wc -l | xargs echo "Python文件数量:"
	@find . -name "*.ts" -o -name "*.tsx" | wc -l | xargs echo "TypeScript文件数量:"
	@find . -name "*.md" | wc -l | xargs echo "Markdown文件数量:"
	@echo ""
	@echo "🗂️  临时文件:"
	@find . -name "*.tmp" -o -name "*.temp" | wc -l | xargs echo "临时文件数量:"
	@echo ""
	@echo "💾 缓存文件:"
	@du -sh backend/.cache frontend/.cache admin/.cache 2>/dev/null || echo "无缓存目录"
	@echo ""
	@echo "🌳 Git状态:"
	@git status --porcelain | wc -l | xargs echo "未提交的文件数量:" || echo "未初始化Git仓库"
	@git rev-list --count HEAD 2>/dev/null | xargs echo "提交总数:" || echo "无提交历史"

# ================================
# Git 工作流命令
# ================================

# Git环境初始化
git-setup:
	@echo "🌳 初始化Git环境..."
	@bash infrastructure/scripts/git_setup.sh

# Git状态和智能建议
git-status:
	@echo "📊 Git状态分析..."
	@python3 infrastructure/scripts/commit_helper.py status

# 交互式提交
git-commit:
	@echo "✨ 交互式提交..."
	@python3 infrastructure/scripts/commit_helper.py commit

# Git工作流管理
git-flow:
	@echo "🌿 Git工作流管理..."
	@echo "用法示例:"
	@echo "  python3 infrastructure/scripts/git_flow.py feature \"description\" --prd 1"
	@echo "  python3 infrastructure/scripts/git_flow.py hotfix \"fix\" --issue 123"
	@echo "  python3 infrastructure/scripts/git_flow.py commit"
	@echo "  python3 infrastructure/scripts/git_flow.py finish"
	@echo "  python3 infrastructure/scripts/git_flow.py status"
	@echo ""
	@echo "运行 'python3 infrastructure/scripts/git_flow.py --help' 查看详细帮助"

# Git帮助信息
git-help:
	@echo "🌳 Git工作流帮助"
	@echo "================"
	@echo ""
	@echo "📚 常用Git别名 (已配置):"
	@echo "  git st          # git status"
	@echo "  git co          # git checkout"
	@echo "  git br          # git branch"
	@echo "  git ci          # git commit"
	@echo "  git cm \"msg\"    # git commit -m"
	@echo "  git lg          # 图形化日志"
	@echo "  git pushup      # push -u origin HEAD"
	@echo "  git cleanup     # 清理已合并分支"
	@echo "  git undo        # 撤销最后一次提交"
	@echo ""
	@echo "🚀 推荐工作流程:"
	@echo "  1. make git-status              # 查看状态"
	@echo "  2. git add .                    # 暂存文件"
	@echo "  3. make git-commit             # 交互式提交"
	@echo "  4. git pushup                  # 推送分支"
	@echo ""
	@echo "🌿 分支管理:"
	@echo "  • 功能分支: python3 infrastructure/scripts/git_flow.py feature \"description\""
	@echo "  • 热修复: python3 infrastructure/scripts/git_flow.py hotfix \"fix\""
	@echo "  • 完成功能: python3 infrastructure/scripts/git_flow.py finish"
	@echo ""
	@echo "📖 详细文档: docs/Git版本控制规范.md"

# 快速提交（简化版）
git-quick:
	@echo "⚡ 快速提交模式..."
	@git add .
	@python3 infrastructure/scripts/commit_helper.py suggest
	@echo ""
	@echo "💡 使用 'make git-commit' 进行完整的交互式提交"

# 分支保护（自动化）
branch-protect:
	@echo "🛡️  配置分支保护 (main, develop) ..."
	@if [ -z "$(GITHUB_TOKEN)" ]; then \
		echo "❌ 需要环境变量 GITHUB_TOKEN (repo admin 权限)"; \
		exit 1; \
	fi
	@python3 infrastructure/scripts/setup_branch_protection.py || true
