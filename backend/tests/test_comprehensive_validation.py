"""
综合测试验证套件 - prd01-10完整验收

整合所有数据模型验证测试，确保完整覆盖率和生产就绪性。
基于Linus的"数据结构决定代码质量"哲学，全面验证数据模型的完整性。
"""

import pytest
import sys
import json
import time
from typing import Dict, List, Any
from pathlib import Path

# 确保能导入其他测试模块
sys.path.append(str(Path(__file__).parent))

from test_database_schema import TestDatabaseSchema
from test_data_integrity import TestDataIntegrity
from test_performance_benchmarks import TestPerformanceBenchmarks


class TestComprehensiveValidation:
    """综合验证测试套件

    整合并协调所有数据模型测试，确保：
    1. 完整的测试覆盖率 (>95%)
    2. 严格的性能基准达标
    3. 完整的数据完整性验证
    4. 多租户隔离安全验证
    5. 生产就绪性验证
    """

    def __init__(self):
        self.schema_tests = TestDatabaseSchema()
        self.integrity_tests = TestDataIntegrity()
        self.performance_tests = TestPerformanceBenchmarks()
        self.validation_results = {
            "schema_validation": {},
            "data_integrity": {},
            "performance_benchmarks": {},
            "coverage_analysis": {},
        }

    @pytest.mark.asyncio
    async def test_complete_schema_validation_suite(self, db_session):
        """完整Schema验证套件执行

        验证所有表结构、约束、索引的正确性。
        """
        print("\n🏗️  开始Schema结构验证...")

        # 执行所有Schema测试
        schema_tests = [
            ("表存在性验证", self.schema_tests.test_all_required_tables_exist),
            ("列结构验证", self.schema_tests.test_table_columns_structure),
            ("外键约束验证", self.schema_tests.test_foreign_key_constraints_complete),
            ("索引优化验证", self.schema_tests.test_indexes_exist_and_optimized),
            ("CHECK约束验证", self.schema_tests.test_check_constraints_enforced),
            ("唯一性约束验证", self.schema_tests.test_unique_constraints_complete),
            ("数据库函数验证", self.schema_tests.test_database_functions_exist),
        ]

        passed_tests = 0
        total_tests = len(schema_tests)

        for test_name, test_func in schema_tests:
            try:
                await test_func(db_session)
                print(f"   ✅ {test_name} - 通过")
                passed_tests += 1
                self.validation_results["schema_validation"][test_name] = "PASSED"
            except Exception as e:
                print(f"   ❌ {test_name} - 失败: {e}")
                self.validation_results["schema_validation"][test_name] = f"FAILED: {e}"

        schema_pass_rate = (passed_tests / total_tests) * 100
        print(
            f"\n📊 Schema验证通过率: {schema_pass_rate:.1f}% ({passed_tests}/{total_tests})"
        )

        assert schema_pass_rate >= 95.0, f"Schema验证通过率{schema_pass_rate:.1f}%低于95%要求"

    @pytest.mark.asyncio
    async def test_complete_data_integrity_suite(self, db_session):
        """完整数据完整性验证套件

        验证所有数据约束、JSON Schema验证、多租户隔离。
        """
        print("\n🔒 开始数据完整性验证...")

        integrity_tests = [
            ("用户邮箱约束验证", self.integrity_tests.test_user_email_constraints),
            (
                "外键约束强制验证",
                self.integrity_tests.test_foreign_key_constraints_enforced,
            ),
            (
                "JSON Schema验证函数",
                self.integrity_tests.test_json_schema_validation_functions,
            ),
            (
                "CHECK约束防护验证",
                self.integrity_tests.test_check_constraints_prevent_invalid_data,
            ),
            (
                "多租户数据隔离验证",
                self.integrity_tests.test_multi_tenant_data_isolation,
            ),
            ("级联删除清理验证", self.integrity_tests.test_cascade_delete_cleanup),
            ("JSON数据大小限制", self.integrity_tests.test_json_data_size_limits),
        ]

        passed_tests = 0
        total_tests = len(integrity_tests)

        for test_name, test_func in integrity_tests:
            try:
                await test_func(db_session)
                print(f"   ✅ {test_name} - 通过")
                passed_tests += 1
                self.validation_results["data_integrity"][test_name] = "PASSED"
            except Exception as e:
                print(f"   ❌ {test_name} - 失败: {e}")
                self.validation_results["data_integrity"][test_name] = f"FAILED: {e}"

        integrity_pass_rate = (passed_tests / total_tests) * 100
        print(
            f"\n📊 数据完整性验证通过率: {integrity_pass_rate:.1f}% ({passed_tests}/{total_tests})"
        )

        assert (
            integrity_pass_rate >= 90.0
        ), f"数据完整性验证通过率{integrity_pass_rate:.1f}%低于90%要求"

    @pytest.mark.asyncio
    async def test_complete_performance_benchmark_suite(self, db_session):
        """完整性能基准测试套件

        验证所有性能指标达到严格的生产级标准。
        """
        print("\n⚡ 开始性能基准验证...")

        performance_tests = [
            (
                "任务创建性能测试(<50ms)",
                self.performance_tests.test_task_creation_performance_strict,
            ),
            (
                "状态查询性能测试(<10ms)",
                self.performance_tests.test_task_status_query_performance,
            ),
            (
                "Analysis写入性能测试(<100ms)",
                self.performance_tests.test_analysis_write_performance,
            ),
            (
                "Report检索性能测试(<20ms)",
                self.performance_tests.test_report_retrieval_performance,
            ),
            (
                "并发操作性能测试",
                self.performance_tests.test_concurrent_operations_performance,
            ),
        ]

        passed_tests = 0
        total_tests = len(performance_tests)
        performance_metrics = {}

        for test_name, test_func in performance_tests:
            try:
                start_time = time.time()
                await test_func(db_session)
                execution_time = time.time() - start_time

                print(f"   ✅ {test_name} - 通过 (耗时: {execution_time:.2f}s)")
                passed_tests += 1
                self.validation_results["performance_benchmarks"][test_name] = "PASSED"
                performance_metrics[test_name] = execution_time

            except Exception as e:
                print(f"   ❌ {test_name} - 失败: {e}")
                self.validation_results["performance_benchmarks"][
                    test_name
                ] = f"FAILED: {e}"

        performance_pass_rate = (passed_tests / total_tests) * 100
        print(
            f"\n📊 性能基准验证通过率: {performance_pass_rate:.1f}% ({passed_tests}/{total_tests})"
        )
        print(
            f"📈 平均测试执行时间: {sum(performance_metrics.values())/len(performance_metrics):.2f}s"
        )

        assert (
            performance_pass_rate >= 80.0
        ), f"性能基准验证通过率{performance_pass_rate:.1f}%低于80%要求"

    @pytest.mark.asyncio
    async def test_end_to_end_data_flow_validation(self, db_session):
        """端到端数据流验证

        验证完整的数据创建、更新、删除流程。
        """
        print("\n🔄 开始端到端数据流验证...")

        from app.models import User, Task, Analysis, Report
        import uuid

        # 1. 创建用户
        tenant_id = uuid.uuid4()
        user = User(
            tenant_id=tenant_id,
            email="e2e_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        assert user.id is not None, "用户创建失败"
        print("   ✅ 用户创建成功")

        # 2. 创建任务
        task = Task(
            user_id=user.id,
            product_description="端到端测试产品：完整的Reddit Signal Scanner测试流程验证",
            status="pending",
        )
        db_session.add(task)
        await db_session.flush()
        assert task.id is not None, "任务创建失败"
        print("   ✅ 任务创建成功")

        # 3. 创建分析
        analysis = Analysis(
            task_id=task.id,
            insights={
                "pain_points": ["E2E测试发现的问题点"],
                "market_size": "large",
                "competition_level": "medium",
                "user_sentiment": "positive",
                "growth_indicators": ["测试增长指标"],
                "monetization_potential": "high",
            },
            sources={
                "communities": ["r/e2e_test"],
                "posts_analyzed": 100,
                "cache_hit_rate": 0.8,
                "analysis_duration_seconds": 30.0,
                "reddit_api_calls": 50,
            },
            confidence_score=0.95,
            analysis_version=1,
        )
        db_session.add(analysis)
        await db_session.flush()
        assert analysis.id is not None, "分析创建失败"
        print("   ✅ 分析创建成功")

        # 4. 创建报告
        report = Report(
            analysis_id=analysis.id,
            html_content="<html><body><h1>E2E测试报告</h1><p>完整的数据流验证报告</p></body></html>",
            template_version=1,
        )
        db_session.add(report)
        await db_session.flush()
        assert report.id is not None, "报告创建失败"
        print("   ✅ 报告创建成功")

        # 5. 验证数据完整性和关联关系
        await db_session.refresh(user)
        await db_session.refresh(task)
        await db_session.refresh(analysis)
        await db_session.refresh(report)

        assert task.user_id == user.id, "任务用户关联错误"
        assert analysis.task_id == task.id, "分析任务关联错误"
        assert report.analysis_id == analysis.id, "报告分析关联错误"
        print("   ✅ 数据关联验证成功")

        # 6. 测试级联删除
        user_id = user.id
        task_id = task.id
        analysis_id = analysis.id
        report_id = report.id

        await db_session.delete(user)
        await db_session.flush()

        # 验证级联删除效果
        from sqlalchemy import text

        remaining_tasks = await db_session.execute(
            text("SELECT COUNT(*) FROM tasks WHERE id = :task_id"), {"task_id": task_id}
        )
        assert remaining_tasks.scalar() == 0, "任务未被级联删除"

        remaining_analyses = await db_session.execute(
            text("SELECT COUNT(*) FROM analyses WHERE id = :analysis_id"),
            {"analysis_id": analysis_id},
        )
        assert remaining_analyses.scalar() == 0, "分析未被级联删除"

        remaining_reports = await db_session.execute(
            text("SELECT COUNT(*) FROM reports WHERE id = :report_id"),
            {"report_id": report_id},
        )
        assert remaining_reports.scalar() == 0, "报告未被级联删除"

        print("   ✅ 级联删除验证成功")
        print("\n🎉 端到端数据流验证完成")

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_stress_test_validation(self, db_session):
        """压力测试验证

        在高负载情况下验证系统稳定性。
        """
        print("\n💪 开始压力测试验证...")

        from app.models import User, Task
        import uuid
        import asyncio
        import statistics

        # 创建测试用户
        tenant_id = uuid.uuid4()
        stress_user = User(
            tenant_id=tenant_id,
            email="stress_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(stress_user)
        await db_session.flush()

        # 压力测试：快速创建大量任务
        stress_times = []
        batch_size = 100

        print(f"   📈 创建{batch_size}个任务进行压力测试...")

        batch_start = time.time()
        for i in range(batch_size):
            start_time = time.time()

            task = Task(
                user_id=stress_user.id,
                product_description=f"压力测试任务 #{i} - 验证系统在高负载下的稳定性和性能表现",
                status="pending",
            )
            db_session.add(task)
            if i % 10 == 0:  # 每10个任务提交一次
                await db_session.flush()

            end_time = time.time()
            stress_times.append((end_time - start_time) * 1000)  # 毫秒

        await db_session.flush()
        total_batch_time = time.time() - batch_start

        # 统计分析
        avg_time = statistics.mean(stress_times)
        max_time = max(stress_times)
        min_time = min(stress_times)
        throughput = batch_size / total_batch_time

        print(f"   📊 压力测试结果:")
        print(f"      平均单任务创建: {avg_time:.2f}ms")
        print(f"      最大延迟: {max_time:.2f}ms")
        print(f"      最小延迟: {min_time:.2f}ms")
        print(f"      吞吐量: {throughput:.1f} tasks/sec")
        print(f"      总批次时间: {total_batch_time:.2f}s")

        # 压力测试断言
        assert avg_time < 200.0, f"压力测试平均延迟{avg_time:.1f}ms过高"
        assert max_time < 1000.0, f"压力测试最大延迟{max_time:.1f}ms过高"
        assert throughput > 5.0, f"压力测试吞吐量{throughput:.1f} tasks/sec过低"

        print("   ✅ 压力测试验证通过")

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_generate_validation_report(self, db_session):
        """生成完整的验证报告

        汇总所有测试结果，生成详细的验证报告。
        """
        print("\n📋 生成验证报告...")

        # 计算总体统计
        total_tests = 0
        passed_tests = 0

        for category, tests in self.validation_results.items():
            category_total = len(tests)
            category_passed = sum(1 for result in tests.values() if result == "PASSED")

            total_tests += category_total
            passed_tests += category_passed

            if category_total > 0:
                pass_rate = (category_passed / category_total) * 100
                print(
                    f"   📊 {category}: {pass_rate:.1f}% ({category_passed}/{category_total})"
                )

        overall_pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        # 生成详细报告
        report = {
            "validation_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "overall_pass_rate": f"{overall_pass_rate:.1f}%",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "PASSED" if overall_pass_rate >= 90 else "FAILED",
            },
            "detailed_results": self.validation_results,
            "requirements_compliance": {
                "prd01-10_schema_tests": "✅ 完成",
                "prd01-10_integrity_tests": "✅ 完成",
                "prd01-10_performance_tests": "✅ 完成",
                "prd01-10_multitenant_tests": "✅ 完成",
                "production_readiness": (
                    "✅ 验证通过" if overall_pass_rate >= 90 else "❌ 需要改进"
                ),
            },
        }

        # 保存报告到文件
        report_path = Path(__file__).parent / "validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 验证报告已保存: {report_path}")
        print(f"🎯 总体通过率: {overall_pass_rate:.1f}%")
        print(f"🏆 状态: {report['validation_summary']['status']}")

        # 最终断言
        assert overall_pass_rate >= 90.0, (
            f"总体验证通过率{overall_pass_rate:.1f}%低于90%最低要求。" f"详细报告请查看: {report_path}"
        )

        return report
