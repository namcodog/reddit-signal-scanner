# Reddit V0 核心组件差异与复用策略

| 模块 | 现有实现 (frontend) | 设计版 (reddit_v0界面) | 主要差异 | 处理策略 |
| --- | --- | --- | --- | --- |
| 布局框架 | `src/components/layout/AppShell.tsx` | `app/page.tsx` 内联头部 + 容器 | 现有 AppShell 强制路由场景、登录后才显示输入；设计版头部始终显示登录/注册按钮，主体为单页多状态。 | 升级 AppShell 或新建 `ExperienceShell`，复用现有 Auth/用户入口，同时容纳三步骤内容。 |
| 全局状态 | `src/hooks/appStateContext.tsx` + 多个业务 hook | `hooks/use-app-state.ts` | 现有上下文仅处理分析任务与报告加载，不含登录、轮询、取消、反馈；设计版集中管理 auth、task、report、模态控制。 | 重构 AppStateProvider：扩展 action 与 state，桥接 `useSecureAuth` 与真实 API，提供设计版需要的回调。 |
| ProductInputForm | `src/components/v0/ProductInputForm.tsx` | `components/product-input-form.tsx` | 差异包括：字符上限（500 vs 500/可扩展）、按钮文案/禁用逻辑、示例卡片 hover 样式、未登录交互提示、表单容器样式。 | 以设计版为蓝本重写 UI 层；保留现有 `onStartAnalysis` 接口，扩展校验（支持 2000 字）、登录弹窗触发。 |
| NavigationBreadcrumb | `src/components/v0/NavigationBreadcrumb.tsx` | `components/navigation-breadcrumb.tsx` | 布局接近，但设计版按钮态、颜色、禁用逻辑、分隔箭头、无障碍属性更完整。 | 合并两者：采纳设计版结构，补充禁用/可回退规则，与 AppState `currentStep` 同步。 |
| AnalysisProgress | `src/components/v0/AnalysisProgress.tsx` | `components/analysis-progress.tsx` | 现有组件消费 SSE/WS 数据，提供实时统计/重连/查看报告；设计版模拟 15s 流程、含登录弹窗和标签页。UI 上设计版强调步骤清单、进度条、统计卡样式。 | 以现有数据结构为基础，将设计版 UI 套用，扩展 props（连接状态、onRetry、实时数据）保持真实后端兼容。登录弹窗复用 `AuthDialog`。 |
| InsightsReport | `src/components/v0/InsightsReport.tsx` | `components/insights-report.tsx` | 现实现映射后端 `ReportData`，但样式与卡片布局已接近设计；设计版包含更多 tooltip、Tab 内容、反馈对话框、导出按钮状态。 | 在现有组件上补全设计版缺失元素：Tab 布局、tooltip、统计卡、导出/反馈交互，并确保数据映射准确。 |
| AuthDialog | `src/components/auth/AuthDialog.tsx` | `components/auth-dialog.tsx` | 现实现基于 `useSecureAuth`，设计版更轻量并假设 `apiService`。UI 结构类似但按钮文案、切换状态有差异。 | 维持现有安全逻辑，按设计调整文案与布局；增加复用入口（进度页顶部登录按钮等）。 |
| 分析流程 Hook | `src/hooks/useTaskProgress.ts` | `hooks/use-analysis-progress.ts` | 设计版为模拟 + 轮询兜底，现实现含 hybridRealTimeService + SSE。需要把真实数据注入设计 UI。 | 保留现 hook，实现数据到组件的映射层，提供步骤描述/剩余时间等格式化函数。 |
| 服务层 | `src/services/report.service.ts`, `src/utils/httpClient.ts` | `services/api.ts` | 命名与返回结构不同，设计版调用 `apiService`、`reportService`（简化）。 | 创建适配函数或在 AppState action 中直接使用现有服务，确保 UI 层调用一致。 |

## 结论
- **可复用**：现有服务层、SSE/polling 能力、真实报告数据结构；`InsightsReport` 与 `AuthDialog` 可在调整样式后继续使用。
- **需重构/重写**：`AppStateProvider`、页面组装结构、`ProductInputForm`、`AnalysisProgress`、`NavigationBreadcrumb`（以设计稿为准）。
- **新增工作**：统一主题 Token、登录弹窗触发逻辑、导出/反馈按钮行为的真实 API 对接、Story/测试覆盖。

后续阶段将基于此清单安排开发顺序，避免遗漏关键交互。 
