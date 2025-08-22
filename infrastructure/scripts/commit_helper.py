#!/usr/bin/env python3
"""
提交消息辅助工具
Reddit Signal Scanner 项目
基于 Conventional Commits 标准

帮助生成规范的提交消息
"""

import subprocess
import sys
import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import argparse


class Colors:
    """ANSI颜色代码"""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    NC = "\033[0m"


class CommitHelper:
    """提交消息辅助工具"""

    def __init__(self):
        self.commit_types = {
            "feat": {
                "desc": "新功能",
                "emoji": "✨",
                "examples": [
                    "feat(api): add analysis endpoint",
                    "feat(frontend): implement user dashboard",
                    "feat(analysis): add community discovery algorithm",
                ],
            },
            "fix": {
                "desc": "Bug修复",
                "emoji": "🐛",
                "examples": [
                    "fix(api): resolve timeout issues",
                    "fix(frontend): fix infinite loading loop",
                    "fix(analysis): handle empty Reddit response",
                ],
            },
            "docs": {
                "desc": "文档更新",
                "emoji": "📚",
                "examples": [
                    "docs(readme): update installation guide",
                    "docs(api): add endpoint documentation",
                    "docs(git): add workflow guidelines",
                ],
            },
            "style": {
                "desc": "代码格式化",
                "emoji": "💎",
                "examples": [
                    "style(backend): format code with black",
                    "style(frontend): fix eslint warnings",
                    "style: remove trailing whitespace",
                ],
            },
            "refactor": {
                "desc": "代码重构",
                "emoji": "♻️",
                "examples": [
                    "refactor(models): extract common base model",
                    "refactor(services): simplify Reddit client",
                    "refactor: reorganize utility functions",
                ],
            },
            "perf": {
                "desc": "性能优化",
                "emoji": "⚡",
                "examples": [
                    "perf(cache): implement Redis caching",
                    "perf(analysis): optimize community discovery",
                    "perf(api): reduce response time",
                ],
            },
            "test": {
                "desc": "测试相关",
                "emoji": "🧪",
                "examples": [
                    "test(analysis): add unit tests for signal extraction",
                    "test(api): add integration tests",
                    "test: increase coverage to 85%",
                ],
            },
            "build": {
                "desc": "构建系统",
                "emoji": "🔨",
                "examples": [
                    "build(docker): optimize container size",
                    "build(deps): update dependencies",
                    "build: add production build script",
                ],
            },
            "ci": {
                "desc": "CI/CD配置",
                "emoji": "👷",
                "examples": [
                    "ci(github): add automated testing",
                    "ci: add security scanning",
                    "ci(deploy): setup staging environment",
                ],
            },
            "chore": {
                "desc": "其他杂项",
                "emoji": "🔧",
                "examples": [
                    "chore(deps): update React to v18.2.0",
                    "chore: clean up temporary files",
                    "chore(config): update environment variables",
                ],
            },
            "revert": {
                "desc": "回滚提交",
                "emoji": "⏪",
                "examples": [
                    "revert: feat(api): add analysis endpoint",
                    'revert: "fix(frontend): resolve loading issue"',
                ],
            },
        }

        self.scopes = {
            # 模块范围
            "api": "后端API相关",
            "frontend": "前端界面相关",
            "admin": "管理后台相关",
            "analysis": "分析引擎相关",
            "models": "数据模型相关",
            "services": "服务层相关",
            "tests": "测试相关",
            "docs": "文档相关",
            "config": "配置相关",
            "scripts": "脚本工具相关",
            # PRD范围
            "prd01": "PRD-01 数据模型",
            "prd02": "PRD-02 API设计",
            "prd03": "PRD-03 分析引擎",
            "prd04": "PRD-04 任务系统",
            "prd05": "PRD-05 前端交互",
            "prd06": "PRD-06 用户认证",
            "prd07": "PRD-07 Admin后台",
            "prd08": "PRD-08 端到端测试",
        }

    def _print_colored(self, message: str, color: str = Colors.NC):
        """打印彩色消息"""
        print(f"{color}{message}{Colors.NC}")

    def _run_command(self, cmd: List[str]) -> Tuple[int, str]:
        """运行shell命令"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode, result.stdout.strip()
        except subprocess.SubprocessError as e:
            return 1, str(e)

    def _get_staged_files(self) -> List[str]:
        """获取暂存区文件"""
        code, output = self._run_command(["git", "diff", "--cached", "--name-only"])
        return output.split("\n") if output else []

    def _get_modified_files(self) -> List[str]:
        """获取修改的文件"""
        code, output = self._run_command(["git", "diff", "--name-only"])
        return output.split("\n") if output else []

    def _analyze_changes(self) -> Dict[str, str]:
        """分析代码变更，建议commit类型和范围"""
        staged_files = self._get_staged_files()
        if not staged_files:
            return {
                "suggested_type": "chore",
                "suggested_scope": "",
                "reason": "No staged files",
            }

        suggestions = {"suggested_type": "feat", "suggested_scope": "", "reason": ""}

        # 分析文件路径模式
        frontend_files = [f for f in staged_files if f.startswith("frontend/")]
        backend_files = [f for f in staged_files if f.startswith("backend/")]
        admin_files = [f for f in staged_files if f.startswith("admin/")]
        doc_files = [f for f in staged_files if f.endswith((".md", ".rst", ".txt"))]
        test_files = [f for f in staged_files if "test" in f.lower()]
        config_files = [
            f
            for f in staged_files
            if any(f.endswith(ext) for ext in [".yml", ".yaml", ".json", ".env"])
        ]

        # 建议范围
        if len(frontend_files) > len(backend_files) and len(frontend_files) > len(
            admin_files
        ):
            suggestions["suggested_scope"] = "frontend"
        elif len(backend_files) > len(frontend_files) and len(backend_files) > len(
            admin_files
        ):
            suggestions["suggested_scope"] = "api"
        elif len(admin_files) > 0:
            suggestions["suggested_scope"] = "admin"
        elif len(doc_files) > 0:
            suggestions["suggested_scope"] = "docs"
            suggestions["suggested_type"] = "docs"
        elif len(test_files) > 0:
            suggestions["suggested_scope"] = "tests"
            suggestions["suggested_type"] = "test"
        elif len(config_files) > 0:
            suggestions["suggested_scope"] = "config"
            suggestions["suggested_type"] = "chore"

        # 分析diff内容提示类型
        code, diff_output = self._run_command(["git", "diff", "--cached"])
        if diff_output:
            if "+++" in diff_output and "---" in diff_output:
                added_lines = len(
                    [line for line in diff_output.split("\n") if line.startswith("+")]
                )
                removed_lines = len(
                    [line for line in diff_output.split("\n") if line.startswith("-")]
                )

                if added_lines > removed_lines * 2:
                    suggestions["suggested_type"] = "feat"
                    suggestions["reason"] = (
                        f"主要是新增代码 (+{added_lines}/-{removed_lines})"
                    )
                elif removed_lines > added_lines:
                    suggestions["suggested_type"] = "refactor"
                    suggestions["reason"] = (
                        f"主要是删除/重构代码 (+{added_lines}/-{removed_lines})"
                    )
                else:
                    suggestions["suggested_type"] = "fix"
                    suggestions["reason"] = (
                        f"混合变更 (+{added_lines}/-{removed_lines})"
                    )

        return suggestions

    def show_status(self):
        """显示Git状态和分析"""
        self._print_colored("📊 Git 状态分析", Colors.BOLD + Colors.BLUE)

        # 基本状态
        code, output = self._run_command(["git", "status", "--porcelain"])
        if not output:
            self._print_colored("✅ 工作目录干净，没有需要提交的更改", Colors.GREEN)
            return

        print(f"\n{Colors.BLUE}当前变更:{Colors.NC}")
        self._run_command(["git", "status", "--short"])

        # 暂存区分析
        staged_files = self._get_staged_files()
        if staged_files:
            print(f"\n{Colors.GREEN}已暂存的文件 ({len(staged_files)} 个):{Colors.NC}")
            for file in staged_files[:10]:  # 只显示前10个
                print(f"  📄 {file}")
            if len(staged_files) > 10:
                print(f"  ... 还有 {len(staged_files) - 10} 个文件")

        # 智能建议
        suggestions = self._analyze_changes()
        if suggestions["suggested_type"]:
            print(f"\n{Colors.CYAN}💡 智能建议:{Colors.NC}")
            type_info = self.commit_types[suggestions["suggested_type"]]
            print(
                f"  类型: {type_info['emoji']} {suggestions['suggested_type']} ({type_info['desc']})"
            )
            if suggestions["suggested_scope"]:
                scope_desc = self.scopes.get(
                    suggestions["suggested_scope"], suggestions["suggested_scope"]
                )
                print(f"  范围: {suggestions['suggested_scope']} ({scope_desc})")
            if suggestions["reason"]:
                print(f"  原因: {suggestions['reason']}")

            # 生成建议的提交消息格式
            if suggestions["suggested_scope"]:
                suggested_format = f"{suggestions['suggested_type']}({suggestions['suggested_scope']}): <description>"
            else:
                suggested_format = f"{suggestions['suggested_type']}: <description>"
            print(f"  建议格式: {Colors.YELLOW}{suggested_format}{Colors.NC}")

    def interactive_commit(self):
        """交互式提交"""
        self._print_colored("✨ 交互式提交工具", Colors.BOLD + Colors.BLUE)

        # 检查是否有变更
        staged_files = self._get_staged_files()
        modified_files = self._get_modified_files()

        if not staged_files and not modified_files:
            self._print_colored("ℹ️  没有需要提交的变更", Colors.BLUE)
            return

        if not staged_files and modified_files:
            print(f"\n{Colors.YELLOW}⚠️  有修改但未暂存的文件:{Colors.NC}")
            for file in modified_files[:5]:
                print(f"  📄 {file}")

            add_all = input(
                f"\n{Colors.BLUE}是否暂存所有文件? (y/N): {Colors.NC}"
            ).lower() in ["y", "yes"]
            if add_all:
                self._run_command(["git", "add", "."])
                staged_files = self._get_staged_files()
            else:
                self._print_colored(
                    "❌ 请先暂存要提交的文件: git add <files>", Colors.RED
                )
                return

        # 显示暂存的文件
        self.show_status()

        # 获取智能建议
        suggestions = self._analyze_changes()

        # 1. 选择类型
        print(f"\n{Colors.BLUE}📋 选择提交类型:{Colors.NC}")
        types_list = list(self.commit_types.keys())

        for i, (commit_type, info) in enumerate(self.commit_types.items(), 1):
            indicator = "👉 " if commit_type == suggestions["suggested_type"] else "   "
            print(
                f"  {indicator}{i:2d}. {info['emoji']} {commit_type:8s} - {info['desc']}"
            )

        while True:
            default_choice = next(
                (
                    i
                    for i, t in enumerate(types_list, 1)
                    if t == suggestions["suggested_type"]
                ),
                1,
            )
            try:
                choice_input = input(
                    f"\n请输入选择 (1-{len(types_list)}, 默认 {default_choice}): "
                ).strip()
                choice = int(choice_input) if choice_input else default_choice

                if 1 <= choice <= len(types_list):
                    commit_type = types_list[choice - 1]
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入数字")

        # 2. 选择范围
        print(f"\n{Colors.BLUE}🎯 选择范围 (可选):{Colors.NC}")
        print("   0. 跳过范围")

        scopes_list = list(self.scopes.keys())
        for i, (scope, desc) in enumerate(self.scopes.items(), 1):
            indicator = "👉 " if scope == suggestions["suggested_scope"] else "   "
            print(f"  {indicator}{i:2d}. {scope:8s} - {desc}")

        scope = ""
        while True:
            default_choice = 0
            if (
                suggestions["suggested_scope"]
                and suggestions["suggested_scope"] in scopes_list
            ):
                default_choice = scopes_list.index(suggestions["suggested_scope"]) + 1

            try:
                choice_input = input(
                    f"\n请输入选择 (0-{len(scopes_list)}, 默认 {default_choice}): "
                ).strip()
                choice = int(choice_input) if choice_input else default_choice

                if choice == 0:
                    break
                elif 1 <= choice <= len(scopes_list):
                    scope = scopes_list[choice - 1]
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入数字")

        # 3. 输入描述
        print(f"\n{Colors.BLUE}✍️  输入描述:{Colors.NC}")
        type_info = self.commit_types[commit_type]
        print(f"参考示例:")
        for example in type_info["examples"][:2]:
            print(f"  • {example}")

        while True:
            description = input(f"\n请输入描述 (1-50字符): ").strip()
            if 1 <= len(description) <= 50:
                # 确保首字母小写
                if description[0].isupper():
                    description = description[0].lower() + description[1:]
                # 确保不以句号结尾
                if description.endswith("."):
                    description = description[:-1]
                break
            print("描述长度必须在1-50字符之间")

        # 4. 构建提交消息
        if scope:
            commit_msg = f"{commit_type}({scope}): {description}"
        else:
            commit_msg = f"{commit_type}: {description}"

        # 5. 是否为破坏性变更
        breaking_change = input(
            f"\n{Colors.BLUE}💥 是否为破坏性变更? (y/N): {Colors.NC}"
        ).lower() in ["y", "yes"]
        if breaking_change:
            if scope:
                commit_msg = f"{commit_type}({scope})!: {description}"
            else:
                commit_msg = f"{commit_type}!: {description}"

        # 6. 添加正文（可选）
        print(f"\n{Colors.BLUE}📝 添加详细说明 (可选):{Colors.NC}")
        add_body = input("是否添加提交正文? (y/N): ").lower() in ["y", "yes"]

        body = ""
        if add_body:
            print("请输入提交正文 (多行，按Ctrl+D结束):")
            try:
                lines = []
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                body = "\n".join(lines).strip()

        # 7. 添加Footer（如破坏性变更或关联Issue）
        footer = ""
        if breaking_change and not body:
            breaking_desc = input(
                f"\n{Colors.BLUE}请描述破坏性变更: {Colors.NC}"
            ).strip()
            if breaking_desc:
                footer = f"BREAKING CHANGE: {breaking_desc}"

        # 关联Issue
        link_issue = input(
            f"\n{Colors.BLUE}是否关联Issue? (y/N): {Colors.NC}"
        ).lower() in ["y", "yes"]
        if link_issue:
            issue_number = input("Issue编号: ").strip()
            if issue_number:
                issue_line = f"Closes #{issue_number}"
                footer = f"{footer}\n\n{issue_line}" if footer else issue_line

        # 8. 构建最终提交消息
        final_msg = commit_msg
        if body:
            final_msg += f"\n\n{body}"
        if footer:
            final_msg += f"\n\n{footer}"

        # 9. 预览和确认
        print(f"\n{Colors.BLUE}📋 提交消息预览:{Colors.NC}")
        print("=" * 60)
        print(final_msg)
        print("=" * 60)

        # 验证格式
        first_line = final_msg.split("\n")[0]
        if len(first_line) > 50:
            self._print_colored(
                f"⚠️  警告: 标题行过长 ({len(first_line)} > 50)", Colors.YELLOW
            )

        # 确认提交
        confirm = input(f"\n{Colors.BLUE}确认提交? (Y/n): {Colors.NC}").lower()
        if confirm in ["", "y", "yes"]:
            # 执行提交
            code, output = self._run_command(["git", "commit", "-m", final_msg])
            if code == 0:
                self._print_colored("✅ 提交成功!", Colors.GREEN)

                # 显示提交信息
                code, commit_hash = self._run_command(
                    ["git", "rev-parse", "--short", "HEAD"]
                )
                if code == 0:
                    print(
                        f"\n{Colors.BLUE}📝 提交哈希: {Colors.GREEN}{commit_hash}{Colors.NC}"
                    )

                # 建议下一步
                print(f"\n{Colors.BLUE}💡 建议的下一步:{Colors.NC}")
                print(
                    f"  • 推送到远程: {Colors.YELLOW}git push{Colors.NC} 或 {Colors.YELLOW}git pushup{Colors.NC}"
                )
                print(f"  • 查看提交历史: {Colors.YELLOW}git lg{Colors.NC}")
                print(
                    f"  • 更新工作流状态: {Colors.YELLOW}python workflow.py complete <task_id>{Colors.NC}"
                )
            else:
                self._print_colored(f"❌ 提交失败: {output}", Colors.RED)
        else:
            self._print_colored("❌ 提交已取消", Colors.YELLOW)

    def validate_message(self, message: str) -> Dict[str, any]:
        """验证提交消息格式"""
        validation = {"valid": False, "errors": [], "warnings": [], "suggestions": []}

        lines = message.strip().split("\n")
        if not lines:
            validation["errors"].append("提交消息不能为空")
            return validation

        header = lines[0]

        # 检查基本格式
        commit_regex = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: .+"
        if not re.match(commit_regex, header):
            validation["errors"].append("标题格式不符合 Conventional Commits 标准")
            return validation

        # 检查长度
        if len(header) > 50:
            validation["warnings"].append(f"标题过长 ({len(header)} > 50 字符)")

        # 检查首字母
        description_match = re.search(r": (.+)", header)
        if description_match:
            description = description_match.group(1)
            if description[0].isupper():
                validation["warnings"].append("描述应该以小写字母开头")
            if description.endswith("."):
                validation["warnings"].append("描述不应该以句号结尾")

        # 检查正文格式
        if len(lines) > 1:
            if lines[1].strip():
                validation["warnings"].append("标题和正文之间应该有空行")

            for i, line in enumerate(lines[2:], 2):
                if len(line) > 72:
                    validation["warnings"].append(
                        f"第{i+1}行过长 ({len(line)} > 72 字符)"
                    )

        validation["valid"] = len(validation["errors"]) == 0
        return validation

    def suggest_from_diff(self):
        """基于diff内容建议提交消息"""
        self._print_colored("🔮 基于代码变更的智能建议", Colors.BOLD + Colors.BLUE)

        suggestions = self._analyze_changes()
        staged_files = self._get_staged_files()

        if not staged_files:
            self._print_colored("ℹ️  没有暂存的文件", Colors.BLUE)
            return

        print(f"\n{Colors.BLUE}📊 变更分析:{Colors.NC}")
        print(f"  暂存文件数: {len(staged_files)}")

        # 文件类型分析
        file_types = {}
        for file in staged_files:
            ext = file.split(".")[-1] if "." in file else "other"
            file_types[ext] = file_types.get(ext, 0) + 1

        print(f"  文件类型: {', '.join(f'{k}({v})' for k, v in file_types.items())}")

        # 代码变更统计
        code, diff_output = self._run_command(["git", "diff", "--cached", "--stat"])
        if diff_output:
            print(f"\n{Colors.BLUE}📈 变更统计:{Colors.NC}")
            for line in diff_output.split("\n")[-3:]:  # 显示最后几行统计信息
                if line.strip():
                    print(f"  {line}")

        # 生成建议
        if suggestions["suggested_type"]:
            type_info = self.commit_types[suggestions["suggested_type"]]
            print(f"\n{Colors.CYAN}💡 建议的提交类型:{Colors.NC}")
            print(
                f"  {type_info['emoji']} {suggestions['suggested_type']} - {type_info['desc']}"
            )

            if suggestions["suggested_scope"]:
                scope_desc = self.scopes.get(
                    suggestions["suggested_scope"], suggestions["suggested_scope"]
                )
                print(f"\n{Colors.CYAN}🎯 建议的范围:{Colors.NC}")
                print(f"  {suggestions['suggested_scope']} - {scope_desc}")

            print(f"\n{Colors.CYAN}📝 建议的消息格式:{Colors.NC}")
            if suggestions["suggested_scope"]:
                format_example = f"{suggestions['suggested_type']}({suggestions['suggested_scope']}): <简洁描述>"
            else:
                format_example = f"{suggestions['suggested_type']}: <简洁描述>"
            print(f"  {Colors.YELLOW}{format_example}{Colors.NC}")

            # 显示相关示例
            print(f"\n{Colors.CYAN}📚 参考示例:{Colors.NC}")
            for example in type_info["examples"][:2]:
                print(f"  • {example}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="提交消息辅助工具 - Reddit Signal Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s commit                    # 交互式提交
  %(prog)s status                    # 显示状态和建议
  %(prog)s suggest                   # 基于diff建议提交消息
  %(prog)s validate "feat: add api"  # 验证提交消息格式
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 交互式提交
    subparsers.add_parser("commit", help="交互式创建提交")

    # 状态显示
    subparsers.add_parser("status", help="显示Git状态和智能建议")

    # 智能建议
    subparsers.add_parser("suggest", help="基于代码变更建议提交消息")

    # 验证消息
    validate_parser = subparsers.add_parser("validate", help="验证提交消息格式")
    validate_parser.add_argument("message", help="要验证的提交消息")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    helper = CommitHelper()

    try:
        if args.command == "commit":
            helper.interactive_commit()
        elif args.command == "status":
            helper.show_status()
        elif args.command == "suggest":
            helper.suggest_from_diff()
        elif args.command == "validate":
            validation = helper.validate_message(args.message)
            if validation["valid"]:
                helper._print_colored("✅ 提交消息格式正确", Colors.GREEN)
            else:
                helper._print_colored("❌ 提交消息格式错误:", Colors.RED)
                for error in validation["errors"]:
                    print(f"  • {error}")

            if validation["warnings"]:
                helper._print_colored("⚠️  警告:", Colors.YELLOW)
                for warning in validation["warnings"]:
                    print(f"  • {warning}")

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}❌ 操作已取消{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 错误: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
