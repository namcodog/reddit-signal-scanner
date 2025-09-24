# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- P0 结构化洞察落库功能完成
- P1 引擎字段复核和前端真数据联调完成
- 端到端测试覆盖完整数据流
- 报告接口返回5块结构化数据：executive_summary、market_metrics、pain_points、competitors、opportunities
- SSE连接含心跳，任务结束自动断开
- Demo模式与正式契约一致

### Changed
- 更新报告格式化器以确保完整字段覆盖
- 优化前端组件以支持真实数据渲染
- 改进分析引擎的数据传递机制

### Fixed
- 修复结构化洞察未落库的问题
- 修复前端空态显示问题
- 修复API契约不一致问题

### Technical Debt
- MyPy错误数：937个（主要集中在测试文件）
- 需要持续改进类型注解覆盖率
- 测试文件类型定义需要补全

## [0.1.0-p1] - 2025-09-24

### Added
- 基础项目架构搭建
- Reddit数据抓取功能
- 分析引擎核心算法
- 前端React界面
- 后端FastAPI服务
- 用户认证系统
- 管理后台基础功能

### Infrastructure
- 建立CI/CD流水线
- 配置质量门控系统
- 设置代码格式化和类型检查
- 建立测试框架

## [0.0.1] - 2025-09-01

### Added
- 项目初始化
- 基础目录结构
- 开发环境配置
