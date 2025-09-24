# MCP工具完整使用指南

## 🎯 概述

您的项目已配置了12个强大的MCP工具，所有工具都已正常工作。这些工具通过模型上下文协议(MCP)与Claude Code集成，提供无缝的开发体验。

## 📋 已配置的MCP工具列表

### 1. **v0-mcp** ✨ 新配置
- **功能**: Vercel v0 UI组件生成
- **用途**: 从文本描述或图片生成React组件
- **API密钥**: 已配置 (V0_API_KEY)
- **状态**: ✅ 正常工作

**可用工具**:
- `create_component` - 创建新的UI组件
- `get_chat_list` - 获取聊天列表
- `get_file_list` - 获取文件列表
- `get_file_content` - 获取文件内容

### 2. **tavily-mcp**
- **功能**: 智能网络搜索
- **用途**: 获取最新技术信息、文档、解决方案
- **API密钥**: 已配置 (TAVILY_API_KEY)
- **状态**: ✅ 正常工作

### 3. **context7**
- **功能**: 代码库上下文分析
- **用途**: 理解项目结构、依赖关系
- **状态**: ✅ 正常工作

### 4. **sequential-thinking**
- **功能**: 结构化思维分析
- **用途**: 复杂问题分解、逻辑推理
- **状态**: ✅ 正常工作

### 5. **mcp-feedback-enhanced**
- **功能**: 增强反馈系统
- **用途**: 交互式反馈收集
- **状态**: ✅ 正常工作

### 6. **devcontext**
- **功能**: 开发上下文管理
- **用途**: 项目状态跟踪、数据库连接
- **数据库**: 已配置 Turso
- **状态**: ✅ 正常工作

### 7. **openmemory-local**
- **功能**: 本地记忆存储
- **用途**: 会话记忆、知识积累
- **状态**: ✅ 正常工作

### 8. **serena**
- **功能**: 代码符号分析
- **用途**: 代码结构分析、符号查找
- **状态**: ✅ 正常工作

### 9. **ide**
- **功能**: IDE集成工具
- **用途**: 编辑器功能增强
- **状态**: ✅ 正常工作

### 10. **filesystem**
- **功能**: 文件系统操作
- **用途**: 文件读写、目录管理
- **状态**: ✅ 正常工作

### 11. **git**
- **功能**: Git版本控制
- **用途**: 代码版本管理、提交历史
- **状态**: ✅ 正常工作

### 12. **postgres**
- **功能**: PostgreSQL数据库
- **用途**: 数据库操作
- **状态**: 🔒 已禁用 (可按需启用)

## 🚀 v0-mcp使用示例

### 基础UI组件生成
```
请使用v0-mcp创建一个现代的登录表单，包含：
- 邮箱输入框
- 密码输入框
- 记住我复选框
- 登录按钮
- 忘记密码链接
使用Tailwind CSS和shadcn/ui组件
```

### 从图片生成组件
```
使用v0-mcp将这个设计图转换为React组件：
[上传图片或提供图片URL]
请确保组件是响应式的，并使用现代的设计风格
```

### 迭代改进组件
```
基于之前创建的登录表单，请添加：
- 表单验证
- 加载状态
- 错误提示
- 社交登录按钮
```

### 复杂组件生成
```
创建一个管理仪表板组件，包含：
- 侧边栏导航
- 顶部导航栏
- KPI卡片网格
- 数据图表区域
- 用户配置文件下拉菜单
```

## 🔧 工具组合使用

### 1. 研究 + 设计 + 实现
```
1. 使用tavily-mcp搜索最新的UI设计趋势
2. 使用v0-mcp生成基础组件
3. 使用serena分析现有代码结构
4. 使用git管理版本控制
```

### 2. 问题分析 + 解决方案
```
1. 使用sequential-thinking分析问题
2. 使用context7理解代码上下文
3. 使用tavily-mcp搜索解决方案
4. 使用filesystem实施修改
```

## 📊 工具状态检查

### 快速检查命令
```bash
# 检查所有MCP工具状态
python3 scripts/mcp_tools_check.py

# 测试v0-mcp功能
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' | npx -y v0-mcp@latest
```

### 环境变量检查
```bash
# 检查关键API密钥
echo "V0_API_KEY: ${V0_API_KEY:0:10}..."
echo "TAVILY_API_KEY: ${TAVILY_API_KEY:0:10}..."
echo "TURSO_DATABASE_URL: ${TURSO_DATABASE_URL:0:20}..."
```

## 🛠️ 故障排除

### 常见问题

1. **工具无响应**
   ```bash
   # 重启Claude Code
   # 检查网络连接
   # 验证API密钥
   ```

2. **API密钥错误**
   ```bash
   # 检查.env文件
   cat .env | grep -E "(V0_API_KEY|TAVILY_API_KEY)"

   # 重新加载环境变量
   source .env
   ```

3. **权限问题**
   ```bash
   # 检查文件权限
   ls -la .claude/mcp.json

   # 修复权限
   chmod 644 .claude/mcp.json
   ```

### 重置配置
```bash
# 备份当前配置
cp .claude/mcp.json .claude/mcp.json.backup

# 重新运行配置脚本
python3 scripts/setup_v0_mcp.py
```

## 🎯 最佳实践

### 1. 工具选择策略
- **UI设计**: 优先使用v0-mcp
- **技术研究**: 使用tavily-mcp
- **代码分析**: 使用serena + context7
- **问题分解**: 使用sequential-thinking

### 2. 工作流程建议
1. **分析阶段**: sequential-thinking + context7
2. **研究阶段**: tavily-mcp
3. **设计阶段**: v0-mcp
4. **实现阶段**: filesystem + git
5. **反馈阶段**: mcp-feedback-enhanced

### 3. 性能优化
- 合理使用工具，避免过度调用
- 缓存常用结果
- 定期清理临时文件

## 📈 工具能力矩阵

| 工具 | UI生成 | 代码分析 | 网络搜索 | 文件操作 | 数据库 |
|------|--------|----------|----------|----------|--------|
| v0-mcp | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| tavily-mcp | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| serena | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| context7 | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| filesystem | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| git | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |
| devcontext | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎉 总结

您的MCP工具生态系统已完全配置并正常工作！这12个工具为您提供了：

- **完整的UI开发能力** (v0-mcp)
- **强大的代码分析能力** (serena, context7)
- **智能搜索和研究能力** (tavily-mcp)
- **全面的文件和版本管理** (filesystem, git)
- **结构化思维和反馈系统** (sequential-thinking, mcp-feedback-enhanced)

现在您可以充分利用这些工具来加速开发流程，提高代码质量，并创建出色的用户界面！
