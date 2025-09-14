#!/usr/bin/env python3
"""
Reddit Signal Scanner - 类型安全检查脚本
基于Linus原则："编译器永远比人更可靠"

使用说明:
    python scripts/type_check.py           # 检查所有核心文件
    python scripts/type_check.py --strict  # 严格模式检查
    python scripts/type_check.py --fix     # 自动修复部分问题
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def run_mypy_check(files: List[str], strict: bool = False) -> Dict[str, Any]:
    """
    运行MyPy类型检查

    Args:
        files: 要检查的文件列表
        strict: 是否使用严格模式

    Returns:
        检查结果字典
    """

    cmd = ["python", "-m", "mypy"]
    cmd.extend(files)
    cmd.extend(["--config-file=mypy.ini", "--show-error-codes"])

    if strict:
        cmd.append("--strict")

    print(f"🔍 执行类型检查: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "errors": [] if result.returncode == 0 else result.stdout.split("\n"),
        }

    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "errors": [str(e)]}


def parse_errors(errors: List[str]) -> Dict[str, List[str]]:
    """解析错误信息，按文件分组"""

    error_by_file = {}

    for error in errors:
        if not error.strip():
            continue

        if "error:" in error:
            # 提取文件名
            try:
                file_path = error.split(":")[0]
                if file_path not in error_by_file:
                    error_by_file[file_path] = []
                error_by_file[file_path].append(error)
            except IndexError:
                continue

    return error_by_file


def main():
    parser = argparse.ArgumentParser(description="类型安全检查工具")
    parser.add_argument("--strict", action="store_true", help="严格模式检查")
    parser.add_argument("--fix", action="store_true", help="自动修复部分问题")
    parser.add_argument("--files", nargs="*", help="指定检查的文件")

    args = parser.parse_args()

    # 默认检查的核心文件
    core_files = [
        "app/main.py",
        "app/api/models.py",
        "app/api/v1/endpoints/analyze.py",
        "app/api/v1/endpoints/status.py",
        "app/api/v1/endpoints/report.py",
    ]

    files_to_check = args.files if args.files else core_files

    print("🔍 Reddit Signal Scanner - 类型安全检查")
    print("=" * 50)

    # 执行类型检查
    result = run_mypy_check(files_to_check, args.strict)

    if result["success"]:
        print("✅ 所有检查文件类型安全！")
        print(f"📊 检查文件数: {len(files_to_check)}")
        return 0
    else:
        print("❌ 发现类型安全问题:")
        print("-" * 30)

        # 解析和显示错误
        error_by_file = parse_errors(result["errors"])

        total_errors = sum(len(errors) for errors in error_by_file.values())

        for file_path, errors in error_by_file.items():
            print(f"\n📁 {file_path} ({len(errors)}个错误):")
            for error in errors[:3]:  # 只显示前3个错误
                print(f"   {error}")
            if len(errors) > 3:
                print(f"   ... 还有{len(errors) - 3}个错误")

        print(f"\n📊 总计: {total_errors}个类型错误")
        print("💡 建议运行: python scripts/type_check.py --fix")

        return 1


if __name__ == "__main__":
    sys.exit(main())
