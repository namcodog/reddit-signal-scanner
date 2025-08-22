#!/usr/bin/env python3
"""
Git 工作流辅助工具
Reddit Signal Scanner 项目
基于 Linus Torvalds Git 哲学设计

提供标准化的 Git 工作流操作
"""

import subprocess
import sys
import re
import argparse
from typing import List, Optional, Tuple
from datetime import datetime
import json


class Colors:
    """ANSI颜色代码"""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    BOLD = "\033[1m"
    NC = "\033[0m"  # No Color


class GitFlow:
    """Git工作流管理器"""

    def __init__(self):
        self.current_branch = self._get_current_branch()
        self.valid_types = [
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "perf",
            "test",
            "build",
            "ci",
            "chore",
            "revert",
        ]
        self.valid_scopes = [
            "api",
            "frontend",
            "admin",
            "analysis",
            "models",
            "services",
            "tests",
            "docs",
            "config",
            "scripts",
            "prd01",
            "prd02",
            "prd03",
            "prd04",
            "prd05",
            "prd06",
            "prd07",
            "prd08",
        ]

    def _run_command(
        self, cmd: List[str], capture_output: bool = True
    ) -> Tuple[int, str]:
        """运行shell命令"""
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode, result.stdout.strip()
            else:
                result = subprocess.run(cmd)
                return result.returncode, ""
        except subprocess.SubprocessError as e:
            return 1, str(e)

    def _get_current_branch(self) -> str:
        """获取当前分支名"""
        code, output = self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return output if code == 0 else "unknown"

    def _print_colored(self, message: str, color: str = Colors.NC):
        """打印彩色消息"""
        print(f"{color}{message}{Colors.NC}")

    def _validate_branch_name(self, branch_name: str) -> bool:
        """验证分支名称格式"""
        patterns = [
            r"^feature/prd-\d{2}-.+$",  # feature/prd-01-description
            r"^feature/.+$",  # feature/description
            r"^hotfix/issue-\d+-.+$",  # hotfix/issue-123-description
            r"^hotfix/.+$",  # hotfix/description
            r"^release/v\d+\.\d+\.\d+$",  # release/v1.0.0
            r"^experimental/.+$",  # experimental/description
        ]
        return any(re.match(pattern, branch_name) for pattern in patterns)

    def create_feature_branch(self, description: str, prd_number: Optional[str] = None):
        """创建功能分支"""
        self._print_colored("🌿 创建功能分支...", Colors.BLUE)

        # 确保在develop分支
        if self.current_branch != "develop":
            self._print_colored("⚠️  建议从 develop 分支创建功能分支", Colors.YELLOW)
            response = input("是否切换到 develop 分支? (y/N): ")
            if response.lower() in ["y", "yes"]:
                code, _ = self._run_command(["git", "checkout", "develop"])
                if code != 0:
                    # 如果没有develop分支，从main创建
                    self._print_colored(
                        "📝 develop 分支不存在，从 main 创建...", Colors.YELLOW
                    )
                    self._run_command(["git", "checkout", "main"])
                    self._run_command(["git", "checkout", "-b", "develop"])

                # 拉取最新代码
                self._run_command(["git", "pull", "origin", "develop"])

        # 生成分支名
        if prd_number:
            branch_name = f"feature/prd-{prd_number:02d}-{description}"
        else:
            branch_name = f"feature/{description}"

        # 创建分支
        code, _ = self._run_command(["git", "checkout", "-b", branch_name])
        if code == 0:
            self._print_colored(f"✅ 成功创建分支: {branch_name}", Colors.GREEN)
            self._print_colored("💡 记住定期推送到远程: git pushup", Colors.BLUE)
        else:
            self._print_colored("❌ 分支创建失败", Colors.RED)
            sys.exit(1)

    def create_hotfix_branch(
        self, description: str, issue_number: Optional[int] = None
    ):
        """创建热修复分支"""
        self._print_colored("🔥 创建热修复分支...", Colors.BLUE)

        # 确保在main分支
        if self.current_branch != "main":
            self._print_colored("⚠️  热修复应该从 main 分支创建", Colors.YELLOW)
            response = input("是否切换到 main 分支? (y/N): ")
            if response.lower() in ["y", "yes"]:
                self._run_command(["git", "checkout", "main"])
                self._run_command(["git", "pull", "origin", "main"])

        # 生成分支名
        if issue_number:
            branch_name = f"hotfix/issue-{issue_number:03d}-{description}"
        else:
            branch_name = f"hotfix/{description}"

        # 创建分支
        code, _ = self._run_command(["git", "checkout", "-b", branch_name])
        if code == 0:
            self._print_colored(f"✅ 成功创建热修复分支: {branch_name}", Colors.GREEN)
            self._print_colored(
                "🚨 热修复完成后记得合并到 main 和 develop", Colors.YELLOW
            )
        else:
            self._print_colored("❌ 分支创建失败", Colors.RED)
            sys.exit(1)

    def interactive_commit(self):
        """交互式提交"""
        self._print_colored("📝 交互式提交工具", Colors.BOLD + Colors.BLUE)

        # 检查是否有变更
        code, output = self._run_command(["git", "status", "--porcelain"])
        if not output:
            self._print_colored("ℹ️  没有需要提交的变更", Colors.BLUE)
            return

        print("\n当前变更:")
        self._run_command(["git", "status", "--short"], capture_output=False)

        # 选择类型
        print(f"\n{Colors.BLUE}选择提交类型:{Colors.NC}")
        for i, commit_type in enumerate(self.valid_types, 1):
            print(f"  {i:2d}. {commit_type}")

        while True:
            try:
                choice = int(input("\n请输入选择 (1-11): ")) - 1
                if 0 <= choice < len(self.valid_types):
                    commit_type = self.valid_types[choice]
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入数字")

        # 选择范围（可选）
        print(f"\n{Colors.BLUE}选择范围 (可选):{Colors.NC}")
        print("  0. 跳过")
        for i, scope in enumerate(self.valid_scopes, 1):
            print(f"  {i:2d}. {scope}")

        scope = ""
        while True:
            try:
                choice = int(input(f"\n请输入选择 (0-{len(self.valid_scopes)}): "))
                if choice == 0:
                    break
                elif 1 <= choice <= len(self.valid_scopes):
                    scope = self.valid_scopes[choice - 1]
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入数字")

        # 输入描述
        while True:
            description = input(
                f"\n{Colors.BLUE}请输入描述 (1-50字符): {Colors.NC}"
            ).strip()
            if 1 <= len(description) <= 50:
                break
            print("描述长度必须在1-50字符之间")

        # 构建提交消息
        if scope:
            commit_msg = f"{commit_type}({scope}): {description}"
        else:
            commit_msg = f"{commit_type}: {description}"

        # 询问是否添加正文
        add_body = input(
            f"\n{Colors.BLUE}是否添加提交正文? (y/N): {Colors.NC}"
        ).lower() in ["y", "yes"]
        body = ""
        if add_body:
            print("请输入提交正文 (按Ctrl+D结束):")
            try:
                lines = []
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                body = "\n".join(lines)

        # 显示最终提交消息
        final_msg = commit_msg
        if body:
            final_msg += f"\n\n{body}"

        print(f"\n{Colors.BLUE}提交消息预览:{Colors.NC}")
        print("-" * 50)
        print(final_msg)
        print("-" * 50)

        # 确认提交
        confirm = input(f"\n{Colors.BLUE}确认提交? (y/N): {Colors.NC}").lower() in [
            "y",
            "yes",
        ]
        if confirm:
            # 添加所有文件
            self._run_command(["git", "add", "."])

            # 提交
            code, _ = self._run_command(["git", "commit", "-m", final_msg])
            if code == 0:
                self._print_colored("✅ 提交成功!", Colors.GREEN)

                # 建议下一步操作
                print(f"\n{Colors.BLUE}建议的下一步操作:{Colors.NC}")
                print(f"  • 推送到远程: {Colors.YELLOW}git pushup{Colors.NC}")
                print(f"  • 查看日志: {Colors.YELLOW}git lg{Colors.NC}")
            else:
                self._print_colored("❌ 提交失败", Colors.RED)
        else:
            self._print_colored("❌ 提交已取消", Colors.YELLOW)

    def finish_feature(self):
        """完成功能分支"""
        if not self.current_branch.startswith("feature/"):
            self._print_colored("❌ 当前不在功能分支", Colors.RED)
            return

        self._print_colored(f"🎯 完成功能分支: {self.current_branch}", Colors.BLUE)

        # 推送当前分支
        print("推送当前分支...")
        code, _ = self._run_command(
            ["git", "push", "-u", "origin", self.current_branch]
        )

        if code == 0:
            self._print_colored("✅ 分支已推送到远程", Colors.GREEN)
            print(f"\n{Colors.BLUE}下一步:{Colors.NC}")
            print(f"  1. 创建 Pull Request: {self.current_branch} → develop")
            print(f"  2. 等待代码审查")
            print(f"  3. 合并后删除分支: {Colors.YELLOW}git cleanup{Colors.NC}")
        else:
            self._print_colored("❌ 推送失败", Colors.RED)

    def create_release(self, version: str):
        """创建发布分支"""
        self._print_colored(f"📦 创建发布分支: v{version}", Colors.BLUE)

        # 验证版本格式
        if not re.match(r"^\d+\.\d+\.\d+$", version):
            self._print_colored("❌ 版本格式错误，应为: x.y.z", Colors.RED)
            return

        # 从develop创建发布分支
        self._run_command(["git", "checkout", "develop"])
        self._run_command(["git", "pull", "origin", "develop"])

        branch_name = f"release/v{version}"
        code, _ = self._run_command(["git", "checkout", "-b", branch_name])

        if code == 0:
            self._print_colored(f"✅ 成功创建发布分支: {branch_name}", Colors.GREEN)
            print(f"\n{Colors.BLUE}发布流程:{Colors.NC}")
            print("  1. 更新版本号")
            print("  2. 更新 CHANGELOG.md")
            print("  3. 最终测试")
            print("  4. 合并到 main 并打标签")
            print("  5. 合并回 develop")
        else:
            self._print_colored("❌ 发布分支创建失败", Colors.RED)

    def branch_status(self):
        """显示分支状态"""
        self._print_colored("🌳 分支状态报告", Colors.BOLD + Colors.BLUE)

        # 当前分支信息
        print(
            f"\n{Colors.BLUE}当前分支:{Colors.NC} {Colors.GREEN}{self.current_branch}{Colors.NC}"
        )

        # 未提交的更改
        code, output = self._run_command(["git", "status", "--porcelain"])
        if output:
            print(f"\n{Colors.YELLOW}⚠️  未提交的更改:{Colors.NC}")
            for line in output.split("\n"):
                print(f"  {line}")
        else:
            print(f"\n{Colors.GREEN}✅ 工作目录干净{Colors.NC}")

        # 本地分支
        print(f"\n{Colors.BLUE}本地分支:{Colors.NC}")
        code, output = self._run_command(["git", "branch", "-v"])
        if code == 0:
            for line in output.split("\n"):
                if line.strip():
                    print(f"  {line}")

        # 远程分支同步状态
        print(f"\n{Colors.BLUE}远程同步状态:{Colors.NC}")
        code, _ = self._run_command(["git", "fetch", "origin"])

        code, output = self._run_command(["git", "status", "-b", "--porcelain"])
        if "ahead" in output or "behind" in output:
            print(f"  {Colors.YELLOW}需要同步{Colors.NC}")
            print(f"  {output.split(']')[0]}]")
        else:
            print(f"  {Colors.GREEN}✅ 与远程同步{Colors.NC}")

        # 最近的提交
        print(f"\n{Colors.BLUE}最近的提交:{Colors.NC}")
        code, output = self._run_command(["git", "log", "--oneline", "-5"])
        if code == 0:
            for line in output.split("\n"):
                if line.strip():
                    print(f"  {line}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Git工作流辅助工具 - Reddit Signal Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s feature "implement analysis api" --prd 2
  %(prog)s hotfix "fix critical bug" --issue 123
  %(prog)s commit
  %(prog)s finish
  %(prog)s release 1.0.0
  %(prog)s status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 功能分支命令
    feature_parser = subparsers.add_parser("feature", help="创建功能分支")
    feature_parser.add_argument("description", help="分支描述")
    feature_parser.add_argument("--prd", type=int, help="PRD编号 (1-8)")

    # 热修复分支命令
    hotfix_parser = subparsers.add_parser("hotfix", help="创建热修复分支")
    hotfix_parser.add_argument("description", help="修复描述")
    hotfix_parser.add_argument("--issue", type=int, help="Issue编号")

    # 交互式提交命令
    subparsers.add_parser("commit", help="交互式提交")

    # 完成功能命令
    subparsers.add_parser("finish", help="完成当前功能分支")

    # 发布命令
    release_parser = subparsers.add_parser("release", help="创建发布分支")
    release_parser.add_argument("version", help="版本号 (如: 1.0.0)")

    # 状态命令
    subparsers.add_parser("status", help="显示分支状态")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    git_flow = GitFlow()

    try:
        if args.command == "feature":
            git_flow.create_feature_branch(args.description, args.prd)
        elif args.command == "hotfix":
            git_flow.create_hotfix_branch(args.description, args.issue)
        elif args.command == "commit":
            git_flow.interactive_commit()
        elif args.command == "finish":
            git_flow.finish_feature()
        elif args.command == "release":
            git_flow.create_release(args.version)
        elif args.command == "status":
            git_flow.branch_status()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}❌ 操作已取消{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 错误: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
