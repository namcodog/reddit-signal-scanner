#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 允许使用 .env.local 覆盖本地配置（不提交到仓库）
if [ -f .env.local ]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

# 本地开发时将 Docker 内部主机名映射为 localhost
if [[ "${DATABASE_URL:-}" == *@postgres:* ]]; then
  export DATABASE_URL="${DATABASE_URL//@postgres:/@127.0.0.1:}"
fi
if [[ "${REDIS_URL:-}" == redis://redis:* ]]; then
  export REDIS_URL="${REDIS_URL//redis:6379/127.0.0.1:6379}"
fi
if [[ "${CELERY_BROKER_URL:-}" == redis://redis:* ]]; then
  export CELERY_BROKER_URL="${CELERY_BROKER_URL//redis:6379/127.0.0.1:6379}"
fi
if [[ "${CELERY_RESULT_BACKEND:-}" == redis://redis:* ]]; then
  export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND//redis:6379/127.0.0.1:6379}"
fi

BACKEND_PORT=${BACKEND_PORT:-8008}
FRONTEND_PORT=${FRONTEND_PORT:-3008}
REDIS_SERVICE=${REDIS_SERVICE:-redis}

check_port_free() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    if lsof -ti tcp:"${port}" >/dev/null 2>&1; then
      echo "Port ${port} is already in use. Adjust BACKEND_PORT/FRONTEND_PORT or stop the other process."
      exit 1
    fi
  fi
}

check_port_free "$BACKEND_PORT"
check_port_free "$FRONTEND_PORT"

POSTGRES_SERVICE=${POSTGRES_SERVICE:-postgres}

COMPOSE_CMD="docker compose"
if ! $COMPOSE_CMD version >/dev/null 2>&1; then
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    COMPOSE_CMD=""
  fi
fi

if [ -n "$COMPOSE_CMD" ]; then
  $COMPOSE_CMD up -d postgres redis >/dev/null 2>&1 || true
fi

if [ ! -d backend/venv ]; then
  echo "📦 后端虚拟环境不存在，运行 make install..."
  make install
fi

source backend/venv/bin/activate

UVICORN_CMD=(uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload)
(
  cd backend
  echo "🚀 启动后端 API (端口 $BACKEND_PORT)..."
  "${UVICORN_CMD[@]}"
) &
BACKEND_PID=$!

echo "🚀 启动 Celery worker..."
(
  cd backend
  celery -A app.core.celery_app worker --loglevel=info
) &
WORKER_PID=$!

if [ ! -d frontend/node_modules ]; then
  echo "📦 安装前端依赖..."
  (cd frontend && npm install)
fi

echo "🚀 启动前端开发服务器 (端口 $FRONTEND_PORT)..."
(
  cd frontend
  npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

function cleanup() {
  echo "\n🛑 清理本地服务..."
  kill -TERM "$BACKEND_PID" "$WORKER_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT

# 轮询监听任一进程退出（兼容不支持 wait -n 的 shell）
pids=("$BACKEND_PID" "$WORKER_PID" "$FRONTEND_PID")
while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      if wait "$pid"; then
        exit 0
      else
        status=$?
        exit $status
      fi
    fi
  done
  sleep 2
done
