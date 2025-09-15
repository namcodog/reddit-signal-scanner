#!/usr/bin/env python3
"""
技术债务自动修复脚本

用于自动修复部分技术债务问题：
- 删除备份文件
- 删除存档文件夹
- 运行代码格式化
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple
import argparse


class TechDebtFixer:
    """技术债务修复器"""

    def __init__(self, root_path: str = "backend", dry_run: bool = False):
        self.root_path = Path(root_path)
        self.dry_run = dry_run
        self.actions_taken = []

    def fix_backup_files(self) -> List[Path]:
        """删除备份文件"""
        print("🔍 查找备份文件...")
        patterns = ["*.backup", "*.bak", "*_old.py", "*_deprecated.py"]
        files_removed = []

        for pattern in patterns:
            for path in self.root_path.rglob(pattern):
                if "__pycache__" not in str(path) and "venv" not in str(path):
                    if self.dry_run:
                        print(f"  [DRY RUN] 将删除: {path}")
                    else:
                        print(f"  删除: {path}")
                        path.unlink()
                    files_removed.append(path)
                    self.actions_taken.append(f"删除备份文件: {path}")

        return files_removed

    def fix_archive_folders(self) -> List[Path]:
        """删除存档文件夹"""
        print("🔍 查找存档文件夹...")
        folders_removed = []

        for path in self.root_path.rglob("archive*/"):
            if (
                path.is_dir()
                and "venv" not in str(path)
                and ".mypy_cache" not in str(path)
            ):
                if self.dry_run:
                    print(f"  [DRY RUN] 将删除文件夹: {path}")
                else:
                    print(f"  删除文件夹: {path}")
                    shutil.rmtree(path)
                folders_removed.append(path)
                self.actions_taken.append(f"删除存档文件夹: {path}")

        return folders_removed

    def run_code_formatting(self) -> Tuple[bool, str]:
        """运行代码格式化"""
        print("🎨 运行代码格式化...")

        if self.dry_run:
            print("  [DRY RUN] 将运行 black 和 isort")
            return True, "Dry run - 未实际执行"

        try:
            # 运行 black
            print("  运行 Black...")
            black_result = subprocess.run(
                ["python", "-m", "black", str(self.root_path)],
                capture_output=True,
                text=True,
            )

            # 运行 isort
            print("  运行 isort...")
            isort_result = subprocess.run(
                ["python", "-m", "isort", str(self.root_path)],
                capture_output=True,
                text=True,
            )

            if black_result.returncode == 0 and isort_result.returncode == 0:
                self.actions_taken.append("运行代码格式化: 成功")
                return True, "格式化成功"
            else:
                error_msg = ""
                if black_result.returncode != 0:
                    error_msg += f"Black错误: {black_result.stderr}\n"
                if isort_result.returncode != 0:
                    error_msg += f"isort错误: {isort_result.stderr}\n"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def create_gitignore_entries(self) -> List[str]:
        """生成建议添加到.gitignore的条目"""
        gitignore_suggestions = [
            "# 备份文件",
            "*.backup",
            "*.bak",
            "*_old.py",
            "*_deprecated.py",
            "",
            "# 存档文件夹",
            "archive*/",
            "archive_*/",
        ]

        return gitignore_suggestions

    def generate_report(self) -> str:
        """生成修复报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("🔧 技术债务修复报告")
        lines.append("=" * 60)

        if self.dry_run:
            lines.append("⚠️  DRY RUN 模式 - 未实际执行任何修改")
            lines.append("")

        if self.actions_taken:
            lines.append("✅ 已完成的操作:")
            for action in self.actions_taken:
                lines.append(f"  - {action}")
        else:
            lines.append("ℹ️  没有需要修复的问题")

        lines.append("")
        lines.append("📝 建议添加到 .gitignore:")
        lines.append("")
        for entry in self.create_gitignore_entries():
            lines.append(entry)

        lines.append("")
        lines.append("🎯 下一步建议:")
        lines.append("  1. 运行 git add -A && git commit -m 'chore: 清理技术债务'")
        lines.append("  2. 更新 .gitignore 文件")
        lines.append("  3. 运行质量检查: python scripts/quality_gate.py")
        lines.append("  4. 修复剩余的 type: ignore 问题")

        lines.append("=" * 60)

        return "\n".join(lines)

    def fix_all(self) -> None:
        """执行所有修复操作"""
        print("🚀 开始修复技术债务...")
        print()

        # 修复备份文件
        backup_files = self.fix_backup_files()
        if backup_files:
            print(f"  ✅ 删除了 {len(backup_files)} 个备份文件")
        else:
            print("  ℹ️  没有发现备份文件")
        print()

        # 修复存档文件夹
        archive_folders = self.fix_archive_folders()
        if archive_folders:
            print(f"  ✅ 删除了 {len(archive_folders)} 个存档文件夹")
        else:
            print("  ℹ️  没有发现存档文件夹")
        print()

        # 运行代码格式化
        format_success, format_msg = self.run_code_formatting()
        if format_success:
            print(f"  ✅ {format_msg}")
        else:
            print(f"  ❌ 格式化失败: {format_msg}")
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="技术债务自动修复工具")
    parser.add_argument("--path", default="backend", help="修复路径（默认: backend）")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际修改")
    parser.add_argument("--no-format", action="store_true", help="跳过代码格式化")

    args = parser.parse_args()

    fixer = TechDebtFixer(args.path, args.dry_run)

    # 执行修复
    fixer.fix_all()

    # 生成报告
    report = fixer.generate_report()
    print(report)

    # 如果不是dry run，保存报告
    if not args.dry_run:
        report_path = Path("tech_debt_fix_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 详细报告已保存到: {report_path}")


if __name__ == "__main__":
    main()
