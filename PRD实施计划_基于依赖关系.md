## TODO 热点拆分（依据技术债报告与PRD索引）

- 导出服务/报告真实实现（后端）
  - 位置：`backend/app/api/v1/endpoints/report.py`
  - 卡片：实现导出API（CSV/JSON），接入权限与速率限制
  - 依赖：报告模型与序列化、权限中间件、速率限制

- 真实 Reddit API 客户端
  - 位置：`backend/app/tasks/background_crawler.py`
  - 卡片：替换Mock为真实Reddit API（PRAW/HTTP），加入重试与配额保护
  - 依赖：密钥管理、限流中间件、缓存策略

- 异常/性能告警链路完善
  - 位置：`backend/app/api/v1/endpoints/analyze.py`、`app/middleware/analysis_monitor.py`
  - 卡片：补全告警上报、阈值配置化、告警历史查询API
  - 依赖：`AlertProcessor`、监控后端、配置系统

- 分析监控持久化
  - 位置：`backend/app/middleware/analysis_monitor.py`
  - 卡片：将热数据异步落库（PostgreSQL），新增查询接口和清理策略
  - 依赖：数据库表结构、异步任务队列

- 任务取消逻辑
  - 位置：`backend/app/api/v1/endpoints/analyze.py`
  - 卡片：实现任务取消API与幂等处理，补充状态机
  - 依赖：任务执行器、状态管理、幂等键

- 前端业务 any 清零（剩余全面治理）
  - 位置：`frontend/src/**`
  - 卡片：为业务hooks与组件补完类型；保留测试宽松
  - 依赖：类型定义文件、eslint type规则

- `reddit_v0界面` 去留决策
  - 位置：`reddit_v0界面/`
  - 卡片：如非现网，迁至 `archive/` 并在 `README.md` 标注
  - 依赖：产品决策、迁移文档


