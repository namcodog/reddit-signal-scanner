#!/usr/bin/env python3
"""
PRD01-10 数据模型验收测试执行脚本

执行完整的数据模型验证测试套件，生成详细的验证报告。
基于Linus的"理解优于实现"哲学，确保数据模型的完整验证。
"""

import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any


class PRD0110ValidationRunner:
    """PRD01-10验证测试执行器"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_results = {}
        self.start_time = time.time()

    def run_schema_tests(self) -> Dict[str, Any]:
        """执行数据库Schema验证测试"""
        print("🏗️  执行数据库Schema验证测试...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/test_database_schema.py",
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=schema_test_results.json",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )

            success = result.returncode == 0
            print(
                f"   {'✅' if success else '❌'} Schema测试 - {'通过' if success else '失败'}"
            )

            return {
                "status": "PASSED" if success else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": time.time() - self.start_time,
            }

        except subprocess.TimeoutExpired:
            print("   ⏱️ Schema测试超时")
            return {"status": "TIMEOUT", "error": "测试超时"}
        except Exception as e:
            print(f"   💥 Schema测试执行异常: {e}")
            return {"status": "ERROR", "error": str(e)}

    def run_integrity_tests(self) -> Dict[str, Any]:
        """执行数据完整性验证测试"""
        print("🔒 执行数据完整性验证测试...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/test_data_integrity.py",
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=integrity_test_results.json",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
            )

            success = result.returncode == 0
            print(
                f"   {'✅' if success else '❌'} 完整性测试 - {'通过' if success else '失败'}"
            )

            return {
                "status": "PASSED" if success else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": time.time() - self.start_time,
            }

        except subprocess.TimeoutExpired:
            print("   ⏱️ 完整性测试超时")
            return {"status": "TIMEOUT", "error": "测试超时"}
        except Exception as e:
            print(f"   💥 完整性测试执行异常: {e}")
            return {"status": "ERROR", "error": str(e)}

    def run_performance_tests(self) -> Dict[str, Any]:
        """执行性能基准测试"""
        print("⚡ 执行性能基准验证测试...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/test_performance_benchmarks.py",
            "-v",
            "--tb=short",
            "-s",  # -s显示print输出
            "--json-report",
            "--json-report-file=performance_test_results.json",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1200,  # 20分钟超时（性能测试可能较慢）
            )

            success = result.returncode == 0
            print(
                f"   {'✅' if success else '❌'} 性能测试 - {'通过' if success else '失败'}"
            )

            return {
                "status": "PASSED" if success else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": time.time() - self.start_time,
            }

        except subprocess.TimeoutExpired:
            print("   ⏱️ 性能测试超时")
            return {"status": "TIMEOUT", "error": "测试超时"}
        except Exception as e:
            print(f"   💥 性能测试执行异常: {e}")
            return {"status": "ERROR", "error": str(e)}

    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """执行综合验证测试"""
        print("🔄 执行综合验证测试...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/test_comprehensive_validation.py",
            "-v",
            "--tb=short",
            "-s",
            "--json-report",
            "--json-report-file=comprehensive_test_results.json",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1800,  # 30分钟超时
            )

            success = result.returncode == 0
            print(
                f"   {'✅' if success else '❌'} 综合测试 - {'通过' if success else '失败'}"
            )

            return {
                "status": "PASSED" if success else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": time.time() - self.start_time,
            }

        except subprocess.TimeoutExpired:
            print("   ⏱️ 综合测试超时")
            return {"status": "TIMEOUT", "error": "测试超时"}
        except Exception as e:
            print(f"   💥 综合测试执行异常: {e}")
            return {"status": "ERROR", "error": str(e)}

    def run_coverage_analysis(self) -> Dict[str, Any]:
        """执行测试覆盖率分析"""
        print("📊 执行测试覆盖率分析...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=app",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=json:coverage.json",
            "--cov-fail-under=85",
            "-q",  # 安静模式，只显示覆盖率
        ]

        try:
            result = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True, text=True, timeout=600
            )

            # 读取覆盖率JSON报告
            coverage_file = self.project_root / "coverage.json"
            coverage_data = {}

            if coverage_file.exists():
                with open(coverage_file, "r") as f:
                    coverage_data = json.load(f)

            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
            success = result.returncode == 0 and total_coverage >= 85

            print(f"   📈 测试覆盖率: {total_coverage:.1f}%")
            print(
                f"   {'✅' if success else '❌'} 覆盖率分析 - {'达标' if success else '不达标'}"
            )

            return {
                "status": "PASSED" if success else "FAILED",
                "coverage_percentage": total_coverage,
                "coverage_data": coverage_data,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except Exception as e:
            print(f"   💥 覆盖率分析异常: {e}")
            return {"status": "ERROR", "error": str(e)}

    def generate_final_report(self) -> Dict[str, Any]:
        """生成最终验证报告"""
        print("\n📋 生成最终验证报告...")

        total_time = time.time() - self.start_time

        # 计算总体结果
        test_categories = ["schema", "integrity", "performance", "comprehensive"]
        passed_categories = sum(
            1
            for cat in test_categories
            if self.test_results.get(cat, {}).get("status") == "PASSED"
        )

        overall_success = passed_categories == len(test_categories)
        coverage_success = (
            self.test_results.get("coverage", {}).get("status") == "PASSED"
        )

        final_status = "PASSED" if (overall_success and coverage_success) else "FAILED"

        report = {
            "prd01_10_validation_summary": {
                "status": final_status,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_execution_time": f"{total_time:.2f} seconds",
                "categories_passed": f"{passed_categories}/{len(test_categories)}",
                "overall_pass_rate": f"{(passed_categories/len(test_categories)*100):.1f}%",
            },
            "test_results": self.test_results,
            "requirements_compliance": {
                "prd01_10_schema_validation": (
                    "✅"
                    if self.test_results.get("schema", {}).get("status") == "PASSED"
                    else "❌"
                ),
                "prd01_10_integrity_validation": (
                    "✅"
                    if self.test_results.get("integrity", {}).get("status") == "PASSED"
                    else "❌"
                ),
                "prd01_10_performance_validation": (
                    "✅"
                    if self.test_results.get("performance", {}).get("status")
                    == "PASSED"
                    else "❌"
                ),
                "prd01_10_comprehensive_validation": (
                    "✅"
                    if self.test_results.get("comprehensive", {}).get("status")
                    == "PASSED"
                    else "❌"
                ),
                "test_coverage_requirement": "✅" if coverage_success else "❌",
            },
            "next_steps": self._generate_next_steps(),
        }

        # 保存报告
        report_file = self.project_root / "PRD01_10_VALIDATION_REPORT.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 打印总结
        print(f"\n🎯 PRD01-10验证总结:")
        print(f"   状态: {final_status}")
        print(f"   执行时间: {total_time:.2f}秒")
        print(f"   通过率: {(passed_categories/len(test_categories)*100):.1f}%")
        print(
            f"   覆盖率: {self.test_results.get('coverage', {}).get('coverage_percentage', 0):.1f}%"
        )
        print(f"   详细报告: {report_file}")

        return report

    def _generate_next_steps(self) -> List[str]:
        """生成下一步行动建议"""
        next_steps = []

        if self.test_results.get("schema", {}).get("status") != "PASSED":
            next_steps.append("修复数据库Schema结构问题")

        if self.test_results.get("integrity", {}).get("status") != "PASSED":
            next_steps.append("解决数据完整性约束问题")

        if self.test_results.get("performance", {}).get("status") != "PASSED":
            next_steps.append("优化数据库性能，满足基准要求")

        if self.test_results.get("coverage", {}).get("status") != "PASSED":
            next_steps.append("提高测试覆盖率至85%以上")

        if not next_steps:
            next_steps.append("✅ 所有验证通过，可以进行生产部署")

        return next_steps

    def run_all_validations(self) -> Dict[str, Any]:
        """执行完整的PRD01-10验证流程"""
        print("🚀 开始PRD01-10数据模型验收测试")
        print("=" * 60)

        # 执行所有测试类别
        self.test_results["schema"] = self.run_schema_tests()
        self.test_results["integrity"] = self.run_integrity_tests()
        self.test_results["performance"] = self.run_performance_tests()
        self.test_results["comprehensive"] = self.run_comprehensive_tests()
        self.test_results["coverage"] = self.run_coverage_analysis()

        # 生成最终报告
        final_report = self.generate_final_report()

        print("\n" + "=" * 60)
        print("🎉 PRD01-10验证完成!")

        return final_report


def main():
    """主执行函数"""
    runner = PRD0110ValidationRunner()

    try:
        final_report = runner.run_all_validations()

        # 根据结果设置退出代码
        if final_report["prd01_10_validation_summary"]["status"] == "PASSED":
            print("\n✅ 所有验证通过 - PRD01-10任务完成!")
            sys.exit(0)
        else:
            print("\n❌ 验证失败 - 需要修复问题后重新测试")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试执行")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 测试执行异常: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
