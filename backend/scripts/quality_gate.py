#!/usr/bin/env python3
"""
Reddit Signal Scanner - Linus风格质量门控系统

Linus原则:
- "品味无法教授，但可以通过严格的标准培养"
- 严格但公平：语法错误零容忍，风格问题给建议
- 自动化执行：无需人工判断，系统自动决策
- 持续改进：每次提交都检查，防止质量倒退
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import json

# 质量标准配置
QUALITY_STANDARDS = {
    "mypy_errors": 0,  # MyPy错误零容忍
    "flake8_errors": 0,  # 语法错误零容忍
    "flake8_warnings": 10,  # 风格警告可适度容忍
    "line_length": 88,  # Black标准
    "min_score": 85,  # 最低综合得分
}

# 核心文件路径
CORE_FILES = [
    "app/main.py",
    "app/core/database.py",
    "app/api/v1/endpoints/stream.py",
    "app/api/v1/router.py",
    "app/api/middleware.py",
    "app/api/models.py",
]


class QualityGate:
    """Linus风格的质量门控器"""

    def __init__(self):
        self.results = {}
        self.total_score = 0
        self.issues = []
        self.warnings = []

    def run_mypy_check(self, files: List[str]) -> Dict[str, Any]:
        """运行MyPy类型检查 - 零错误容忍"""
        print("🔍 运行MyPy类型检查...")

        cmd = [
            "python",
            "-m",
            "mypy",
            *files,
            "--ignore-missing-imports",
            "--show-error-codes",
            "--no-error-summary",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        error_count = len(
            [line for line in result.stdout.split("\n") if " error:" in line]
        )

        return {
            "exit_code": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "error_count": error_count,
            "score": 100 if error_count == 0 else max(0, 100 - error_count * 5),
        }

    def run_flake8_check(self, files: List[str]) -> Dict[str, Any]:
        """运行Flake8风格检查 - 分层处理错误和警告"""
        print("🎨 运行Flake8风格检查...")

        cmd = [
            "python",
            "-m",
            "flake8",
            *files,
            "--max-line-length=88",
            "--extend-ignore=E203,W503",
            "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # 分类错误和警告
        errors = [line for line in lines if any(code in line for code in ["E", "F"])]
        warnings = [
            line for line in lines if any(code in line for code in ["W", "C", "N"])
        ]

        error_count = len(errors)
        warning_count = len(warnings)

        # 计算得分：错误扣重分，警告扣轻分
        score = 100
        score -= error_count * 10  # 每个错误扣10分
        score -= warning_count * 2  # 每个警告扣2分
        score = max(0, score)

        return {
            "exit_code": result.returncode,
            "output": result.stdout,
            "error_count": error_count,
            "warning_count": warning_count,
            "errors": errors,
            "warnings": warnings,
            "score": score,
        }

    def run_black_check(self, files: List[str]) -> Dict[str, Any]:
        """运行Black格式检查"""
        print("⚫ 运行Black格式检查...")

        cmd = ["python", "-m", "black", "--check", "--diff"] + files
        result = subprocess.run(cmd, capture_output=True, text=True)

        needs_formatting = result.returncode != 0

        return {
            "exit_code": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "needs_formatting": needs_formatting,
            "score": 100 if not needs_formatting else 80,
        }

    def run_security_check(self, files: List[str]) -> Dict[str, Any]:
        """运行基础安全检查"""
        print("🛡️ 运行安全检查...")

        security_issues = []
        score = 100

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 检查硬编码敏感信息
                sensitive_patterns = [
                    'password="',
                    'api_key="',
                    'secret="',
                    'token="',
                    "AWS_ACCESS_KEY",
                    'DATABASE_URL="postgresql://',
                ]

                for pattern in sensitive_patterns:
                    if pattern in content:
                        security_issues.append(
                            f"{file_path}: 发现疑似硬编码敏感信息: {pattern}"
                        )
                        score -= 20

            except Exception as e:
                security_issues.append(f"{file_path}: 文件读取失败: {e}")

        return {
            "security_issues": security_issues,
            "score": max(0, score),
            "passed": len(security_issues) == 0,
        }

    def check_files(self, files: List[str] = None) -> Dict[str, Any]:
        """执行完整的质量检查"""
        if files is None:
            # 检查所有存在的核心文件
            files = []
            for file_path in CORE_FILES:
                if Path(file_path).exists():
                    files.append(file_path)

            if not files:
                return {
                    "success": False,
                    "message": "未找到要检查的文件",
                    "total_score": 0,
                }

        print(f"🎯 开始质量检查 - 文件数量: {len(files)}")
        print(f"📁 检查文件: {', '.join(files)}")

        # 运行各项检查
        self.results = {
            "mypy": self.run_mypy_check(files),
            "flake8": self.run_flake8_check(files),
            "black": self.run_black_check(files),
            "security": self.run_security_check(files),
        }

        # 计算综合得分
        weights = {"mypy": 0.4, "flake8": 0.3, "black": 0.2, "security": 0.1}
        self.total_score = sum(
            self.results[check]["score"] * weights[check] for check in weights.keys()
        )

        # 判断是否通过质量门控
        success = self.evaluate_quality_gate()

        return {
            "success": success,
            "total_score": round(self.total_score, 1),
            "results": self.results,
            "issues": self.issues,
            "warnings": self.warnings,
            "files_checked": files,
            "timestamp": datetime.now().isoformat(),
        }

    def evaluate_quality_gate(self) -> bool:
        """Linus风格的质量评估"""
        success = True

        # MyPy错误：零容忍
        if self.results["mypy"]["error_count"] > QUALITY_STANDARDS["mypy_errors"]:
            self.issues.append(
                f"❌ MyPy错误: {self.results['mypy']['error_count']}个 (标准: 0)"
            )
            success = False

        # Flake8错误：零容忍
        if self.results["flake8"]["error_count"] > QUALITY_STANDARDS["flake8_errors"]:
            self.issues.append(
                f"❌ Flake8错误: {self.results['flake8']['error_count']}个 (标准: 0)"
            )
            success = False

        # Flake8警告：适度容忍
        if (
            self.results["flake8"]["warning_count"]
            > QUALITY_STANDARDS["flake8_warnings"]
        ):
            self.warnings.append(
                f"⚠️ Flake8警告: {self.results['flake8']['warning_count']}个 (建议: ≤{QUALITY_STANDARDS['flake8_warnings']})"
            )

        # Black格式：严格要求
        if self.results["black"]["needs_formatting"]:
            self.issues.append("❌ 代码格式不符合Black标准")
            success = False

        # 安全检查：严格要求
        if not self.results["security"]["passed"]:
            self.issues.append(
                f"❌ 安全检查失败: {len(self.results['security']['security_issues'])}个问题"
            )
            success = False

        # 综合得分：最低标准
        if self.total_score < QUALITY_STANDARDS["min_score"]:
            self.issues.append(
                f"❌ 综合得分过低: {self.total_score:.1f} (标准: ≥{QUALITY_STANDARDS['min_score']})"
            )
            success = False

        return success

    def generate_report(self, result: Dict[str, Any]) -> str:
        """生成Linus风格的质量报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("🏛️ Reddit Signal Scanner - 质量门控报告")
        lines.append("=" * 60)
        lines.append(f"📊 综合得分: {result['total_score']:.1f}/100")
        lines.append(f"📁 检查文件: {len(result['files_checked'])}个")
        lines.append(f"⏰ 检查时间: {result['timestamp']}")
        lines.append("")

        # 各项检查结果
        lines.append("📋 详细结果:")
        lines.append(
            f"  🔍 MyPy类型检查: {result['results']['mypy']['score']:.1f}/100 "
            f"({result['results']['mypy']['error_count']}个错误)"
        )
        lines.append(
            f"  🎨 Flake8风格检查: {result['results']['flake8']['score']:.1f}/100 "
            f"({result['results']['flake8']['error_count']}个错误, "
            f"{result['results']['flake8']['warning_count']}个警告)"
        )
        lines.append(
            f"  ⚫ Black格式检查: {result['results']['black']['score']:.1f}/100 "
            f"({'通过' if not result['results']['black']['needs_formatting'] else '需要格式化'})"
        )
        lines.append(
            f"  🛡️ 安全检查: {result['results']['security']['score']:.1f}/100 "
            f"({'通过' if result['results']['security']['passed'] else '发现问题'})"
        )
        lines.append("")

        # 严重问题
        if result["issues"]:
            lines.append("🚨 严重问题 (必须修复):")
            for issue in result["issues"]:
                lines.append(f"  {issue}")
            lines.append("")

        # 警告信息
        if result["warnings"]:
            lines.append("⚠️ 警告信息 (建议修复):")
            for warning in result["warnings"]:
                lines.append(f"  {warning}")
            lines.append("")

        # 最终判断
        if result["success"]:
            lines.append("✅ 质量门控: 通过")
            lines.append("👏 代码质量达到Linus标准，可以提交！")
        else:
            lines.append("❌ 质量门控: 未通过")
            lines.append("🔧 请修复上述问题后重新检查")

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Reddit Signal Scanner 质量门控系统")
    parser.add_argument("--files", nargs="*", help="要检查的文件列表")
    parser.add_argument("--all-files", action="store_true", help="检查所有核心文件")
    parser.add_argument("--json", action="store_true", help="输出JSON格式结果")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")

    args = parser.parse_args()

    gate = QualityGate()

    # 确定要检查的文件
    files_to_check = None
    if args.files:
        files_to_check = args.files
    elif args.all_files:
        files_to_check = None  # 使用默认的核心文件列表
    else:
        # 默认检查核心文件
        files_to_check = None

    # 运行质量检查
    result = gate.check_files(files_to_check)

    # 自动修复选项
    if args.fix and not result["success"]:
        print("🔧 尝试自动修复问题...")

        # 自动运行Black格式化
        if result["results"]["black"]["needs_formatting"]:
            print("📝 运行Black自动格式化...")
            subprocess.run(["python", "-m", "black"] + result["files_checked"])

        # 自动运行isort排序导入
        print("📦 运行isort排序导入...")
        subprocess.run(["python", "-m", "isort"] + result["files_checked"])

        print("✨ 自动修复完成，请重新运行质量检查")

    # 输出结果
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(gate.generate_report(result))

    # 设置退出码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
