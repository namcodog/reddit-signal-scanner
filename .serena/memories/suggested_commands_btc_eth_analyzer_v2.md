# 常用命令速查（BTC/ETH 决策分析器 v2）

## 启动/运行
- 后端（建议 uvicorn 自动重载）
  - `cd btc-eth-analyzer-v2/backend && uvicorn main:app --host 0.0.0.0 --port 8001 --reload`
  - 或：`cd btc-eth-analyzer-v2/backend && python3 main.py`
- 前端（开发）
  - `cd btc-eth-analyzer-v2/frontend && npm install && npm run dev`
  - 访问：`http://localhost:5173`（Vite 默认端口）

## 验收/测试
- 热修复验收（脚本化）
  - `cd btc-eth-analyzer-v2/backend && python3 test_hotfix_v1.py`
- 性能测试
  - `cd btc-eth-analyzer-v2/backend && python3 test_performance.py`
- 模拟服务器（独立端口 8002）
  - `cd btc-eth-analyzer-v2/backend && python3 test_server.py`

## 实用排查
- 确认后端心跳：`curl http://localhost:8001/heartbeat`
- 拉取最新信号：`curl 'http://localhost:8001/signals/latest?symbol=BTCUSDT&timeframe=5m'`
- 图表数据：`curl 'http://localhost:8001/chart/candles?symbol=BTCUSDT&timeframe=5m&limit=200'`
- A/B 报告：`curl http://localhost:8001/ab-test/report`
- 监控告警：`curl http://localhost:8001/monitoring/alerts`

## Darwin/macOS 常用工具
- 查找文件：`rg -n 'keyword' path` 或 `grep -RIn 'keyword' .`
- 进程占用端口：`lsof -i :8001`
- 杀进程：`kill -9 <pid>`

## 端口/地址
- 后端 API：`http://localhost:8001`
- WebSocket：`ws://localhost:8001/ws/stream/candles`
- 前端：`http://localhost:5173`

> 注：生产/远程部署请配置 `VITE_API_BASE`（前端）与 CORS 白名单（后端）。