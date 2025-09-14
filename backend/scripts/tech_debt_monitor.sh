#!/usr/bin/env bash
set -euo pipefail

# 技术债务进度监控脚本
# 使用方法：在仓库根目录或 backend 目录运行均可

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

APP_DIR="app"

echo "=== 技术债务进度监控 ==="
if command -v mypy >/dev/null 2>&1; then
  # 在 backend 目录内执行，使用本地 mypy.ini 配置
  if [ -f "mypy.ini" ] || [ -f "backend/mypy.ini" ]; then
    if [ -d "app" ]; then
      ERRORS=$(mypy --strict "$APP_DIR" 2>&1 | grep -c "error" || true)
    else
      ERRORS=$(cd backend && mypy --strict app 2>&1 | grep -c "error" || true)
    fi
    echo "MyPy错误数: ${ERRORS}"
  else
    echo "MyPy错误数: (未找到mypy.ini，跳过)"
  fi
else
  echo "MyPy错误数: (mypy未安装，跳过)"
fi

if [ -d "app" ]; then
  SEARCH_PATHS=("app")
else
  SEARCH_PATHS=("backend/app")
fi

# 默认排除 tests/ 目录，专注业务代码
EXCLUDES=("--exclude-dir=tests" "--exclude-dir=.mypy_cache" "--exclude-dir=.pytest_cache")

DICT_ANY=$(grep -R "Dict\\[str, Any\\]" "${EXCLUDES[@]}" ${SEARCH_PATHS[@]} | wc -l | tr -d ' ')
TYPE_IGNORE=$(grep -R "# type: ignore" "${EXCLUDES[@]}" ${SEARCH_PATHS[@]} | wc -l | tr -d ' ')
TODO_COUNT=$(grep -R "TODO\|FIXME" "${EXCLUDES[@]}" ${SEARCH_PATHS[@]} | wc -l | tr -d ' ')

echo "Dict[str, Any]: ${DICT_ANY}"
echo "type: ignore: ${TYPE_IGNORE}"
echo "TODO/FIXME: ${TODO_COUNT}"
echo "========================"
