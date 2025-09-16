#!/usr/bin/env python3
"""
技术债务自动检查脚本

用于检测和报告项目中的技术债务，包括：
- type: ignore 使用情况
- 备份文件
- TODO/FIXME 注释
- v2后缀文件
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime


class TechDebtChecker:
    """技术债务检查器"""

    def __init__(self, root_path: str = "backend"):
        self.root_path = Path(root_path)
        self.results = {
            "type_ignores": [],
            "backup_files": [],
            "todos": [],
            "v2_files": [],
            "deprecated_files": [],
        }

    def check_type_ignores(self) -> List[Tuple[Path, int, List[int]]]:
        """检查type: ignore使用"""
        pattern = re.compile(r"#\s*type:\s*ignore")
        results = []

        for path in self.root_path.rglob("*.py"):
            if "__pycache__" in str(path) or "venv" in str(path):
                continue

            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    line_numbers = []

                    for i, line in enumerate(lines, 1):
                        if pattern.search(line):
                            line_numbers.append(i)

                    if line_numbers:
                        results.append((path, len(line_numbers), line_numbers))
            except Exception as e:
                print(f"Error reading {path}: {e}")

        self.results["type_ignores"] = results
        return results

    def check_backup_files(self) -> List[Path]:
        """检查备份文件"""
        patterns = ["*.backup", "*.bak", "*_old.py", "*_deprecated.py"]
        files = []

        for pattern in patterns:
            files.extend(self.root_path.rglob(pattern))

        # 排除__pycache__和venv
        files = [
            f for f in files if "__pycache__" not in str(f) and "venv" not in str(f)
        ]

        self.results["backup_files"] = files
        return files

    def check_todos(self) -> List[Tuple[Path, int, List[Tuple[int, str]]]]:
        """检查TODO/FIXME"""
        pattern = re.compile(
            r"#\s*(?:TODO|FIXME|HACK|XXX)(?::?\s*)(.*)$", re.IGNORECASE
        )
        results = []

        for path in self.root_path.rglob("*.py"):
            if "__pycache__" in str(path) or "venv" in str(path):
                continue

            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    todos = []

                    for i, line in enumerate(lines, 1):
                        match = pattern.search(line)
                        if match:
                            todos.append((i, match.group(0).strip()))

                    if todos:
                        results.append((path, len(todos), todos))
            except Exception as e:
                print(f"Error reading {path}: {e}")

        self.results["todos"] = results
        return results

    def check_v2_files(self) -> List[Path]:
        """检查v2后缀文件"""
        v2_files = []

        # 查找v2后缀的Python文件
        for path in self.root_path.rglob("*_v2.py"):
            if "__pycache__" not in str(path) and "venv" not in str(path):
                v2_files.append(path)

        # 查找v2目录
        for path in self.root_path.rglob("*v2/"):
            if (
                path.is_dir()
                and "__pycache__" not in str(path)
                and "venv" not in str(path)
            ):
                v2_files.append(path)

        self.results["v2_files"] = v2_files
        return v2_files

    def check_deprecated(self) -> List[Path]:
        """检查废弃文件和文件夹"""
        deprecated = []

        # 查找archive文件夹
        for path in self.root_path.rglob("archive*/"):
            if (
                path.is_dir()
                and "venv" not in str(path)
                and ".mypy_cache" not in str(path)
            ):
                deprecated.append(path)

        # 查找deprecated标记的文件
        for path in self.root_path.rglob("*deprecated*"):
            if (
                "__pycache__" not in str(path)
                and "venv" not in str(path)
                and ".mypy_cache" not in str(path)
            ):
                deprecated.append(path)

        self.results["deprecated_files"] = deprecated
        return deprecated

    def generate_report(self) -> str:
        """生成报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("🔍 Reddit Signal Scanner - 技术债务检查报告")
        lines.append("=" * 60)
        lines.append(f"📅 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"📁 检查路径: {self.root_path.absolute()}")
        lines.append("")

        # Type ignores
        type_ignore_count = sum(count for _, count, _ in self.results["type_ignores"])
        lines.append(f"❌ Type ignores: {type_ignore_count}处")
        if self.results["type_ignores"]:
            lines.append("   详细位置:")
            for path, count, line_nums in sorted(
                self.results["type_ignores"], key=lambda x: x[1], reverse=True
            ):
                rel_path = path.relative_to(self.root_path)
                lines.append(
                    f"   - {rel_path}: {count}处 (行号: {', '.join(map(str, line_nums))})"
                )
        lines.append("")

        # 备份文件
        lines.append(f"📦 备份文件: {len(self.results['backup_files'])}个")
        if self.results["backup_files"]:
            for path in sorted(self.results["backup_files"]):
                rel_path = path.relative_to(self.root_path)
                lines.append(f"   - {rel_path}")
        lines.append("")

        # v2文件
        lines.append(f"🔄 v2版本文件: {len(self.results['v2_files'])}个")
        if self.results["v2_files"]:
            for path in sorted(self.results["v2_files"]):
                rel_path = path.relative_to(self.root_path)
                lines.append(f"   - {rel_path}")
        lines.append("")

        # TODO/FIXME
        todo_count = sum(count for _, count, _ in self.results["todos"])
        lines.append(f"📝 TODO/FIXME: {todo_count}处")
        if self.results["todos"]:
            lines.append("   分布统计:")
            for path, count, _ in sorted(
                self.results["todos"], key=lambda x: x[1], reverse=True
            )[:10]:
                rel_path = path.relative_to(self.root_path)
                lines.append(f"   - {rel_path}: {count}处")
            if len(self.results["todos"]) > 10:
                lines.append(f"   ... 还有{len(self.results['todos']) - 10}个文件")
        lines.append("")

        # 废弃文件
        lines.append(f"🗑️ 废弃文件/文件夹: {len(self.results['deprecated_files'])}个")
        if self.results["deprecated_files"]:
            for path in sorted(self.results["deprecated_files"]):
                rel_path = path.relative_to(self.root_path)
                lines.append(f"   - {rel_path}")
        lines.append("")

        # 总结
        lines.append("=" * 60)
        lines.append("📊 总结")
        lines.append("=" * 60)

        severity_score = 0
        if type_ignore_count > 0:
            lines.append("⚠️  发现违反类型安全原则的代码！[严重]")
            severity_score += type_ignore_count * 5

        if self.results["backup_files"]:
            lines.append("⚠️  发现备份文件，建议删除！[中等]")
            severity_score += len(self.results["backup_files"]) * 2

        if self.results["v2_files"]:
            lines.append("⚠️  发现v2版本文件，需要迁移！[中等]")
            severity_score += len(self.results["v2_files"]) * 2

        if todo_count > 30:
            lines.append("⚠️  TODO数量过多，需要计划清理！[轻微]")
            severity_score += 5

        if self.results["deprecated_files"]:
            lines.append("⚠️  发现废弃文件/文件夹！[轻微]")
            severity_score += len(self.results["deprecated_files"])

        lines.append("")
        lines.append(f"🎯 技术债务评分: {severity_score} (越低越好)")

        if severity_score == 0:
            lines.append("✅ 恭喜！没有发现技术债务问题。")
        elif severity_score < 10:
            lines.append("🟢 技术债务较少，建议尽快清理。")
        elif severity_score < 50:
            lines.append("🟡 技术债务中等，需要制定清理计划。")
        else:
            lines.append("🔴 技术债务严重，需要立即行动！")

        lines.append("=" * 60)

        return "\n".join(lines)

    def run_full_check(self) -> Dict:
        """运行完整检查"""
        print("🔍 开始技术债务检查...")

        print("  检查 type: ignore...")
        self.check_type_ignores()

        print("  检查备份文件...")
        self.check_backup_files()

        print("  检查 TODO/FIXME...")
        self.check_todos()

        print("  检查 v2 文件...")
        self.check_v2_files()

        print("  检查废弃文件...")
        self.check_deprecated()

        print("✅ 检查完成！")
        return self.results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="技术债务自动检查工具")
    parser.add_argument("--path", default="backend", help="检查路径（默认: backend）")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--save", help="保存报告到文件")

    args = parser.parse_args()

    checker = TechDebtChecker(args.path)
    results = checker.run_full_check()

    if args.json:
        import json

        # 转换Path对象为字符串
        json_results = {}
        for key, value in results.items():
            if key in ["backup_files", "v2_files", "deprecated_files"]:
                json_results[key] = [str(p) for p in value]
            elif key in ["type_ignores", "todos"]:
                json_results[key] = [(str(p), c, d) for p, c, d in value]
            else:
                json_results[key] = value

        output = json.dumps(json_results, indent=2, ensure_ascii=False)
    else:
        output = checker.generate_report()

    print(output)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n📄 报告已保存到: {args.save}")


if __name__ == "__main__":
    main()
