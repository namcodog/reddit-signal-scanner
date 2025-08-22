#!/bin/bash
# Git环境初始化脚本
# Reddit Signal Scanner 项目
# 基于 Linus Torvalds Git 哲学设计

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}"
echo "🌳 Reddit Signal Scanner - Git 环境初始化"
echo "基于 Linus Torvalds Git 哲学"
echo "================================================"
echo -e "${NC}"

# 检查是否在项目根目录
if [ ! -f "Makefile" ] || [ ! -d ".git" ]; then
    echo -e "${RED}❌ Error: 请在项目根目录运行此脚本${NC}"
    echo -e "${YELLOW}💡 确保你在包含 Makefile 和 .git 的目录中${NC}"
    exit 1
fi

# 检查Git是否已安装
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Error: Git 未安装${NC}"
    echo -e "${YELLOW}💡 请先安装 Git: https://git-scm.com/downloads${NC}"
    exit 1
fi

echo -e "${BLUE}📋 当前 Git 版本:${NC}"
git --version

# 1. 配置 Git 用户信息（如果未配置）
echo -e "\n${BLUE}👤 配置 Git 用户信息...${NC}"

current_name=$(git config user.name 2>/dev/null || echo "")
current_email=$(git config user.email 2>/dev/null || echo "")

if [ -z "$current_name" ]; then
    echo -n "请输入您的姓名: "
    read -r user_name
    git config --global user.name "$user_name"
    echo -e "${GREEN}✅ 设置用户名: $user_name${NC}"
else
    echo -e "${GREEN}✅ 当前用户名: $current_name${NC}"
fi

if [ -z "$current_email" ]; then
    echo -n "请输入您的邮箱: "
    read -r user_email
    git config --global user.email "$user_email"
    echo -e "${GREEN}✅ 设置邮箱: $user_email${NC}"
else
    echo -e "${GREEN}✅ 当前邮箱: $current_email${NC}"
fi

# 2. 应用推荐的 Git 配置
echo -e "\n${BLUE}⚙️  应用推荐的 Git 配置...${NC}"

# 基础配置
git config --global color.ui auto
git config --global core.autocrlf input
git config --global init.defaultBranch main
git config --global push.default current
git config --global pull.rebase true
git config --global rerere.enabled true

# 设置编辑器
if command -v code &> /dev/null; then
    git config --global core.editor "code --wait"
    echo -e "${GREEN}✅ 设置编辑器为 VS Code${NC}"
elif command -v vim &> /dev/null; then
    git config --global core.editor vim
    echo -e "${GREEN}✅ 设置编辑器为 Vim${NC}"
fi

# 3. 配置项目级别的 Git 设置
echo -e "\n${BLUE}🔧 配置项目级别的 Git 设置...${NC}"

# 设置项目特定的用户信息（可选）
git config --local user.name "Reddit Signal Scanner Developer"
git config --local user.email "dev@reddit-signal-scanner.local"

# 配置 hooks 路径
git config --local core.hooksPath .githooks
echo -e "${GREEN}✅ 设置 Git hooks 路径为 .githooks${NC}"

# 4. 设置有用的 Git 别名
echo -e "\n${BLUE}🔗 设置 Git 别名...${NC}"

git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.cm "commit -m"
git config --global alias.ca "commit -am"
git config --global alias.sw switch
git config --global alias.lg "log --graph --oneline --decorate --all"
git config --global alias.ll "log --oneline -10"
git config --global alias.unstage "reset HEAD --"
git config --global alias.undo "reset --soft HEAD~1"
git config --global alias.amend "commit --amend --no-edit"
git config --global alias.pushup "push -u origin HEAD"
git config --global alias.cleanup "!git branch --merged | grep -v '\\*\\|main\\|develop' | xargs -n 1 git branch -d"

echo -e "${GREEN}✅ Git 别名设置完成${NC}"

# 5. 验证 hooks 是否正确设置
echo -e "\n${BLUE}🪝 验证 Git hooks...${NC}"

if [ -f ".githooks/pre-commit" ] && [ -x ".githooks/pre-commit" ]; then
    echo -e "${GREEN}✅ pre-commit hook 已正确配置${NC}"
else
    echo -e "${YELLOW}⚠️  pre-commit hook 未找到或不可执行${NC}"
fi

if [ -f ".githooks/commit-msg" ] && [ -x ".githooks/commit-msg" ]; then
    echo -e "${GREEN}✅ commit-msg hook 已正确配置${NC}"
else
    echo -e "${YELLOW}⚠️  commit-msg hook 未找到或不可执行${NC}"
fi

if [ -f ".githooks/pre-push" ] && [ -x ".githooks/pre-push" ]; then
    echo -e "${GREEN}✅ pre-push hook 已正确配置${NC}"
else
    echo -e "${YELLOW}⚠️  pre-push hook 未找到或不可执行${NC}"
fi

# 6. 创建推荐的分支结构
echo -e "\n${BLUE}🌿 初始化分支结构...${NC}"

current_branch=$(git rev-parse --abbrev-ref HEAD)
echo -e "${BLUE}当前分支: $current_branch${NC}"

# 如果不是 main 分支，建议重命名
if [ "$current_branch" != "main" ]; then
    echo -e "${YELLOW}⚠️  当前分支不是 'main'${NC}"
    echo -n "是否将当前分支重命名为 'main'? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        git branch -m main
        echo -e "${GREEN}✅ 分支已重命名为 'main'${NC}"
    fi
fi

# 7. 检查和建议远程仓库配置
echo -e "\n${BLUE}🔗 检查远程仓库...${NC}"

if git remote | grep -q origin; then
    origin_url=$(git remote get-url origin)
    echo -e "${GREEN}✅ Origin 远程仓库: $origin_url${NC}"
else
    echo -e "${YELLOW}⚠️  未配置 origin 远程仓库${NC}"
    echo -e "${YELLOW}💡 稍后可以使用以下命令添加:${NC}"
    echo -e "${YELLOW}   git remote add origin <repository-url>${NC}"
fi

# 8. 创建初始提交（如果需要）
echo -e "\n${BLUE}📝 检查仓库状态...${NC}"

if [ -z "$(git log --oneline 2>/dev/null)" ]; then
    echo -e "${YELLOW}⚠️  仓库中还没有提交${NC}"
    echo -n "是否创建初始提交? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        git add .
        git commit -m "feat: initial project setup

- Add project structure and configuration
- Set up Git workflow and hooks
- Configure build tools and scripts

🤖 Generated with Reddit Signal Scanner Git Setup"
        echo -e "${GREEN}✅ 初始提交已创建${NC}"
    fi
else
    commit_count=$(git rev-list --count HEAD)
    echo -e "${GREEN}✅ 仓库包含 $commit_count 个提交${NC}"
fi

# 9. 显示配置总结
echo -e "\n${BOLD}${GREEN}"
echo "🎉 Git 环境初始化完成！"
echo "================================="
echo -e "${NC}"

echo -e "${BLUE}📋 配置总结:${NC}"
echo -e "  • Git hooks: ${GREEN}已配置${NC}"
echo -e "  • 别名: ${GREEN}已设置${NC}"
echo -e "  • 推荐配置: ${GREEN}已应用${NC}"
echo -e "  • 分支: ${GREEN}$(git rev-parse --abbrev-ref HEAD)${NC}"

echo -e "\n${BLUE}🚀 下一步:${NC}"
echo -e "  1. 开始开发: ${YELLOW}git checkout -b feature/your-feature${NC}"
echo -e "  2. 查看状态: ${YELLOW}git st${NC}"
echo -e "  3. 提交代码: ${YELLOW}git cm \"feat: your commit message\"${NC}"
echo -e "  4. 推送代码: ${YELLOW}git pushup${NC}"

echo -e "\n${BLUE}📚 有用的命令:${NC}"
echo -e "  • ${YELLOW}git lg${NC} - 查看图形化日志"
echo -e "  • ${YELLOW}git cleanup${NC} - 清理已合并的分支"
echo -e "  • ${YELLOW}git undo${NC} - 撤销最后一次提交"
echo -e "  • ${YELLOW}make git-help${NC} - 查看 Git 帮助"

echo -e "\n${BLUE}📖 参考文档:${NC}"
echo -e "  • ${YELLOW}docs/Git版本控制规范.md${NC} - 完整的 Git 工作流指南"

echo -e "\n${BOLD}${GREEN}✨ 祝你编码愉快！${NC}"