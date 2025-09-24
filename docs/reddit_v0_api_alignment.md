# Reddit V0 真实接口对接清单

| 功能 | 现有前端调用 (真实环境) | 设计版预期 | 现状差异 / 注意点 | 后续行动 |
| --- | --- | --- | --- | --- |
| 登录 | `auth.service` → `POST /api/v1/auth/login` (经 `api.client`) | `apiService.login` → `POST /auth/login` | 路径与返回 envelope 不同，但能力匹配；现实现依赖 `useSecureAuth`。 | 保留现有登录流程，在 UI 中复用；设计版调用点改用 `useSecureAuth` 暴露的 `login/register/logout`。 |
| 注册 | `POST /api/v1/auth/register` | `POST /auth/signup` | 路径差异；返回 envelope 一致。 | 同登录。 |
| 当前用户 | `GET /api/v1/auth/me` | `GET /auth/me` | 路径差异；现实现已提供。 | 在 AppState 初始化时调用现有接口，保持 token 管理。 |
| 启动分析 | `HttpClient.post(configService.getAnalyzeEndpoint())` → `POST /api/v1/discovery/analyze` | `POST /analysis/tasks` | 路径、payload 字段不同（现用 `description`→`product_description` 映射）。 | `AppState.startAnalysis` 统一调用真实端点，输出 TaskId；UI 部分移除 mock，沿用现逻辑。 |
| 任务状态轮询 | `GET /api/v1/status/:taskId` | `GET /analysis/tasks/:id` | 路径与字段命名差异（现服务返回 `current_step`, `stats` 等 v0 扩展字段）。 | 保留 `configService.getStatusEndpoint`；在新 UI 中映射字段到步骤组件。 |
| SSE 实时流 | `SSEManager` 直接连接 `GET /api/v1/events/:taskId` | 预期 `EventSource /analysis/tasks/:id/stream` | 现代码与配置 (`/stream/:id`) 不一致，需要确定最终端点。 | 与后端确认统一路径；重构时只保留一处配置，避免硬编码。 |
| WebSocket 实时流 | `ws://{host}/ws/tasks/:taskId` | `ws(s)://.../analysis/tasks/:id/ws` | 路径不同；现实现已支持指数退避、心跳。 | 若后端提供 `/ws/tasks`，继续沿用；否则提供配置项。UI 需兼容 fallback。 |
| 取消任务 | `DELETE /api/v1/discovery/analyze/:taskId`? (未实现) | `POST /analysis/tasks/:id/cancel` | 现前端仅调用 `useTaskProgress.disconnect`，无真实 cancel API。 | 与后端确认是否提供；若有，扩展 `AppState` 与 UI。 |
| 报告获取 | `reportService.getReport` → `GET /api/v1/report/:taskId?format=` | `GET /reports/:id` | 路径差异；返回 envelope 满足需求。 | 复用现有服务，UI 调整字段映射。 |
| 报告导出 | `GET /api/v1/report/:taskId/export?format=` | `POST /reports/:id/export` | 方法与 envelope 差异。 | 继续使用现服务，按钮状态按返回字段 (`download_url`, `filename`) 更新。 |
| 报告反馈/指标 | `feedback.service` → `POST /api/v1/feedback/events` | `POST /reports/:id/feedback` | 现实现采用事件总线，上报 metrics；设计版使用简单 rating 接口。 | 在 UI 中调用现 `feedback.service` 封装；如需显式 rating 接口，与后端确认是否映射。 |
| 任务统计 | SSE 返回 `stats` 字段；轮询亦包含 | 设计版在组件内手工生成 mock 数据 | 实际数据结构兼容 v0 组件，需调整显示格式。 | 在 `AnalysisProgress` 中消费真实 stats，移除模拟逻辑。 |

## 其他配置要点
- **Mock 开关**：需确保 `.env` 中 `VITE_USE_MOCK_API=false`，否则 `configService` 会路由到 `/api/v1/mock/*`。
- **Base URL**：`HttpClient` 默认 `http://localhost:8008`，可通过 `VITE_API_BASE_URL` 配置；设计版使用 `NEXT_PUBLIC_API_URL`。
- **鉴权头**：现前端通过 Cookie/CSRF 方案，无显式 Bearer Token；设计版 token 驱动的 Header 可忽略。
- **SSE/WS 重试策略**：现前端实现已满足设计稿的「可视重连提示」需求，UI 需同步展示 `connectionAttempts`、`strategy` 等信息。

该清单将在 Phase 2/3 改造中作为接口对照表，确保所有组件迁移到真实数据路径。 
