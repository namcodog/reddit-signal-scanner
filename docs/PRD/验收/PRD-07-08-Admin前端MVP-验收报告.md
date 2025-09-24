# PRD-07-08 Admin 前端 MVP 完整验收报告

更新时间：2025-09-19
关联PRD：docs/PRD/PRD-07-Admin后台.md §7.4/§7.5/§7.6/§7.7
关联任务：workflow/tasks/prd-07.yaml → prd07-08

## 一、结论

- 当前仅具备“查看类”的最小能力，核心“管理操作/权限/埋点/测试”显著缺失。
- 总体完成度（综合功能/安全/体验/测试）：约 25%。
- 建议在合并前补齐最小闭环：操作按钮 → 权限 → trace_id → 埋点 → 单测。

## 二、已完成（✅）

1) 基础页面结构（frontend/src/pages/admin/）
- `communities.tsx` 社区管理页框架
- `analysis.tsx` 分析管理页框架
- `feedback.tsx` 反馈汇总页框架

2) API 服务层（frontend/src/services/adminApi.ts）
- TS 类型定义与基础查询封装
- 查询接口：`getCommunitiesSummary` / `getAnalysisSummary` / `getFeedbackSummary`

3) 后端 API 支撑（backend）
- 反馈相关端点具备最小可用：
  - 导出原始事件：`/api/v1/admin/feedback/export`（JSON/CSV，时间范围，DB→Redis→文件三级回退）
    - 参考：`backend/app/api/v1/endpoints/admin_feedback.py:export_feedback_events`
    - 覆盖用例：`backend/tests/integration/api/test_admin_feedback_export.py`
  - 管理员反馈（满意/不满意）：`/api/v1/admin/feedback/analysis`（已就绪）
  - 汇总接口：`/api/v1/admin/feedback/summary`（存在实现与用例，稳定性待进一步验证）

## 三、严重缺失（❌）

1) 操作按钮功能（交互空壳）
- Communities：缺少“通过/实验/黑名单”等操作按钮 → 需调用 `POST /api/v1/admin/decisions/community`
- Analysis：缺少“满意/不满意/仅核心重跑”等操作 → 需调用 `POST /api/v1/admin/feedback/analysis`

2) 前端权限控制（0%）
- 未做 JWT 检查与权限门控（Admin/只读）
- 未做基于权限的组件级隐藏/禁用

3) trace_id 显示（部分缺失）
- 响应模型含 `trace_id`，但 UI 未展示；建议页脚/抽屉统一展示，便于故障回溯

4) Admin 操作埋点（未集成）
- PRD-05 事件契约已定义，但前端未调用埋点 API（`POST /api/v1/feedback/events`）

5) 测试覆盖（0%）
- 无 admin 页面组件/交互单测
- 无 admin API service 单测
- 无端到端交互用例（Cypress）

## 四、完成度评估（量化）

- 基础架构: 70%
- 核心业务功能: 25%
- 权限安全: 0%
- 用户体验: 30%
- 测试保障: 0%

总体完成度：≈ 25%

## 五、整改清单（按优先级）

P0（发布必需）
- [ ] Communities：新增“通过/实验/黑名单/打标签”按钮，调用 `POST /admin/decisions/community`
- [ ] Analysis：新增“满意/不满意/仅核心重跑”操作，调用 `POST /admin/feedback/analysis`
- [ ] 全局 Admin 权限门控：JWT 校验 + 基于权限的 UI 控制（无权限隐藏/禁用）
- [ ] UI 展示 trace_id（统一放在详情抽屉和页脚）
- [ ] 埋点对齐 PRD‑05：操作成功/失败、导出点击、详情抽屉打开时上报 `POST /api/v1/feedback/events`
- [ ] 前端单元测试（vitest + RTL）：
  - `adminApi` 的查询/错误分支
  - 操作按钮组件：点击→API 调用→乐观更新/失败回滚

P1（稳态保障）
- [ ] 管理端页面加载骨架/空态/错误态完善
- [ ] 列表分页与过滤状态与 URL 同步
- [ ] 组件 props 类型化与契约测试（与后端 DTO 对齐）
- [ ] 简单 E2E（Cypress）：三页加载 + 至少一个操作流贯通

## 六、任务映射（到 workflow）

- prd07-10（S）：原始事件导出联通 + 用例完善（已新增集成测文件，可标记完成后合并）
- prd07-12（S）：前端“反馈埋点”类型与契约落地（强烈建议先做，解耦 UI 与后端）
- prd07-08（L/进行中）：补齐操作按钮、权限、trace_id、埋点与测试

## 七、风险与回滚

- 权限缺失导致敏感操作暴露：先行加 UI 层门控与接口 403 兜底
- 操作无埋点：无法追溯问题与审计，须尽快补齐
- 无测试：引入回归风险，建议优先补齐最小单测集

## 八、快速验证指南

后端快速闸门（本地）
```
make quick-gate-local
```

仅跑 Admin 导出相关集成测试
```
PYTHONPATH=backend:. backend/venv/bin/pytest -q backend/tests/integration/api/test_admin_feedback_export.py -q
```

前端类型/测试（示例）
```
cd frontend
npm run type-check && npm test
```

## 九、附：关键文件索引（便于Review）

- 页面骨架：`frontend/src/pages/admin/communities.tsx`
- 页面骨架：`frontend/src/pages/admin/analysis.tsx`
- 页面骨架：`frontend/src/pages/admin/feedback.tsx`
- 服务封装：`frontend/src/services/adminApi.ts`
- 后端导出：`backend/app/api/v1/endpoints/admin_feedback.py:1`
- 新增用例：`backend/tests/integration/api/test_admin_feedback_export.py:1`
