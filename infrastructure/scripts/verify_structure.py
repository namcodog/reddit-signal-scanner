#!/usr/bin/env python3
"""
项目结构验证脚本
基于Linus哲学：简单、直接、有效

验证项目是否符合预定义的目录结构规范
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import json
from datetime import datetime


class ProjectStructureValidator:
    """项目结构验证器"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self.errors = []
        self.warnings = []
        self.passed = []

        # 定义期望的目录结构
        self.expected_structure = {
            "backend": {
                "type": "dir",
                "required": True,
                "children": {
                    "app": {"type": "dir", "required": True},
                    "tests": {"type": "dir", "required": True},
                    "requirements.txt": {"type": "file", "required": True},
                },
            },
            "frontend": {
                "type": "dir",
                "required": True,
                "children": {
                    "src": {"type": "dir", "required": True},
                    "package.json": {"type": "file", "required": True},
                },
            },
            "admin": {
                "type": "dir",
                "required": False,
                "children": {"src": {"type": "dir", "required": True}},
            },
            "docs": {
                "type": "dir",
                "required": True,
                "children": {"PRD": {"type": "dir", "required": True}},
            },
            "infrastructure": {
                "type": "dir",
                "required": True,
                "children": {"scripts": {"type": "dir", "required": True}},
            },
            "workflow": {
                "type": "dir",
                "required": True,
                "children": {"tasks": {"type": "dir", "required": True}},
            },
            "tests": {"type": "dir", "required": True},
            "Makefile": {"type": "file", "required": True},
            ".gitignore": {"type": "file", "required": True},
            "docker-compose.yml": {"type": "file", "required": False},
        }

        # 禁止的文件模式
        self.forbidden_patterns = [
            "*.tmp",
            "*.temp",
            "*_temp.*",
            "*_test.*",
            "*backup*",
            "*_backup.*",
            "*_old.*",
            "Copy of *",
            "utils.py",
            "helpers.py",
            "common.py",
            "test.py",
            "demo.py",
            "example.py",
        ]

    def validate_path(self, path: Path, config: Dict, parent_path: str = "") -> None:
        """验证单个路径"""
        full_path = self.root_path / path
        current_path = f"{parent_path}/{path.name}" if parent_path else str(path)

        if config["type"] == "file":
            if full_path.exists() and full_path.is_file():
                self.passed.append(f"✅ 文件存在: {current_path}")
            elif config["required"]:
                self.errors.append(f"❌ 必需文件缺失: {current_path}")
            else:
                self.warnings.append(f"⚠️  可选文件缺失: {current_path}")

        elif config["type"] == "dir":
            if full_path.exists() and full_path.is_dir():
                self.passed.append(f"✅ 目录存在: {current_path}")

                # 验证子项目
                if "children" in config:
                    for child_name, child_config in config["children"].items():
                        self.validate_path(
                            path / child_name, child_config, current_path
                        )

            elif config["required"]:
                self.errors.append(f"❌ 必需目录缺失: {current_path}")
            else:
                self.warnings.append(f"⚠️  可选目录缺失: {current_path}")

    def check_forbidden_files(self) -> None:
        """检查禁止的文件模式"""
        import fnmatch

        for root, dirs, files in os.walk(self.root_path):
            # 跳过特定目录（增强虚拟环境忽略）
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".mypy_cache", ".pytest_cache"]
                and not str(Path(root) / d).endswith(("site-packages", "/site-packages"))
                and "site-packages" not in str(Path(root) / d)
            ]

            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.root_path)

                # 跳过虚拟环境和第三方包目录
                if any(skip in str(relative_path) for skip in [
                    "site-packages", "/site-packages",
                    "backend/venv", "backend/.venv", "backend/env",
                    ".venv/", "venv/", "env/"
                ]):
                    continue

                for pattern in self.forbidden_patterns:
                    if fnmatch.fnmatch(file, pattern):
                        self.errors.append(
                            f"❌ 禁止的文件模式: {relative_path} (匹配 {pattern})"
                        )

    def validate_file_naming(self) -> None:
        """验证文件命名规范"""
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "node_modules", "__pycache__", ".venv", "venv"]
            ]

            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.root_path)

                # Python文件命名检查
                if file.endswith(".py") and not file.startswith("test_"):
                    if not file.islower() or " " in file:
                        self.warnings.append(
                            f"⚠️  Python文件命名不规范: {relative_path} (应使用snake_case)"
                        )

                # TypeScript/React文件命名检查
                if file.endswith((".ts", ".tsx")):
                    if file.endswith(".tsx") and not file[0].isupper():
                        self.warnings.append(
                            f"⚠️  React组件文件应使用PascalCase: {relative_path}"
                        )

    def generate_report(self) -> Dict:
        """生成验证报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "root_path": str(self.root_path),
            "summary": {
                "total_checks": len(self.passed)
                + len(self.warnings)
                + len(self.errors),
                "passed": len(self.passed),
                "warnings": len(self.warnings),
                "errors": len(self.errors),
                "status": "PASS" if len(self.errors) == 0 else "FAIL",
            },
            "details": {
                "passed": self.passed,
                "warnings": self.warnings,
                "errors": self.errors,
            },
        }

    def run_validation(self) -> bool:
        """运行完整验证"""
        print("🔍 开始项目结构验证...")
        print(f"📁 验证路径: {self.root_path}")
        print("-" * 60)

        # 验证主要结构
        for path_name, config in self.expected_structure.items():
            self.validate_path(Path(path_name), config)

        # 检查禁止文件
        self.check_forbidden_files()

        # 验证文件命名
        self.validate_file_naming()

        # 生成报告
        report = self.generate_report()

        # 输出结果
        print("\n📊 验证结果:")
        print(f"总检查项: {report['summary']['total_checks']}")
        print(f"✅ 通过: {report['summary']['passed']}")
        print(f"⚠️  警告: {report['summary']['warnings']}")
        print(f"❌ 错误: {report['summary']['errors']}")
        print(f"🏆 状态: {report['summary']['status']}")

        if self.errors:
            print("\n❌ 发现的错误:")
            for error in self.errors:
                print(f"  {error}")

        if self.warnings:
            print("\n⚠️  发现的警告:")
            for warning in self.warnings[:10]:  # 限制显示前10个警告
                print(f"  {warning}")
            if len(self.warnings) > 10:
                print(f"  ... 还有 {len(self.warnings) - 10} 个警告")

        # 保存详细报告
        report_path = (
            self.root_path / "infrastructure" / "scripts" / "validation_report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n📋 详细报告已保存到: {report_path}")

        return len(self.errors) == 0


def main():
    """主函数"""
    validator = ProjectStructureValidator()
    success = validator.run_validation()

    if success:
        print("\n🎉 项目结构验证通过！")
        sys.exit(0)
    else:
        print("\n💥 项目结构验证失败，请修复上述错误。")
        sys.exit(1)


if __name__ == "__main__":
    main()
