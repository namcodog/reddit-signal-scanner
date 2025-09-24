# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### P1阶段完成 - 结构化洞察与端到端验证

#### Added
- **结构化洞察落库功能**：完整实现分析结果持久化到数据库
- **5块核心数据结构**：executive_summary、market_metrics、pain_points、competitors、opportunities
- **端到端测试覆盖**：从数据抓取到API响应的完整测试链路
- **前端真数据绑定**：React组件支持真实API数据渲染
- **SSE实时推送**：包含心跳机制，任务完成自动断开连接
- **Demo模式对齐**：模拟器输出与正式契约完全一致

#### Changed
- **报告格式化器增强**：确保所有输入形态下的完整字段覆盖
- **前端组件优化**：InsightsReport.tsx和ReportPageV0.tsx支持真实数据
- **分析引擎改进**：PipelineData → Database → Formatter 数据传递链路优化
- **API契约统一**：所有环境下返回一致的数据结构

#### Fixed
- **结构化洞察未落库问题**：修复AnalysisReport数据持久化
- **前端空态显示问题**：消除mock/空态提示，显示真实数据
- **API契约不一致问题**：统一Demo模式和正式模式的响应格式
- **SSE连接管理**：修复连接泄漏和心跳机制

#### Technical Improvements
- **类型安全增强**：减少Any类型使用，提高类型覆盖率
- **测试覆盖扩展**：新增integration/test_report_endpoint.py
- **错误处理优化**：改进异常捕获和用户反馈机制

### API Changes
- **新增字段**：Report API新增market_metrics.sample_size字段
- **字段类型调整**：所有时间字段统一为ISO-8601格式（带Z后缀）
- **响应结构优化**：executive_summary增加confidence_score字段
- **兼容性保证**：向后兼容，新字段有默认值

### Infrastructure
- **质量门控强化**：make quick-gate-local覆盖类型/后端/前端/文件检查
- **CI/CD优化**：集成测试流水线包含端到端验证
- **文档完善**：更新PRD-05前端交互文档，新增API契约文档

## [0.1.0-p1] - 2025-09-24

### P0阶段完成 - 基础架构与核心功能

#### Added
- **基础项目架构**：FastAPI后端 + React前端 + PostgreSQL数据库
- **Reddit数据抓取**：支持Mock模式和实网抓取切换
- **分析引擎核心**：四步编排（发现→收集→提取→排序）
- **用户认证系统**：JWT认证 + 多租户支持
- **管理后台基础**：用户管理、任务监控、系统配置
- **实时任务系统**：Celery + Redis异步任务处理

#### Infrastructure
- **开发环境**：Docker Compose一键启动
- **代码质量**：MyPy严格类型检查 + ESLint + Prettier
- **测试框架**：pytest + vitest + 集成测试
- **CI/CD流水线**：GitHub Actions自动化测试和部署

#### Configuration
- **环境切换**：USE_MOCKS环境变量控制数据源
- **API限流**：Reddit API速率限制和退避策略
- **安全配置**：密钥管理、CORS设置、输入验证

## [0.0.1] - 2025-09-01

### Added
- 项目初始化和基础目录结构
- 开发环境配置和依赖管理
- Git工作流和分支策略建立

---

## 风险评估与回滚方案

### 高风险变更
- **数据库Schema变更**：新增Report表字段，已包含migration脚本
- **API契约变更**：新增字段向后兼容，客户端可选择性使用

### 回滚方案
1. **代码回滚**：`git revert` 到上一个稳定版本
2. **数据库回滚**：执行migration down脚本
3. **配置回滚**：恢复环境变量到默认Mock模式
4. **服务重启**：`docker-compose down && docker-compose up -d`

### 监控指标
- API响应时间 < 2秒
- 数据库连接池使用率 < 80%
- 内存使用 < 1GB
- 错误率 < 1%

### 应急联系
- 技术负责人：检查GitHub Issues
- 运维支持：查看Docker容器日志
- 回滚决策：超过5分钟无法修复立即回滚
