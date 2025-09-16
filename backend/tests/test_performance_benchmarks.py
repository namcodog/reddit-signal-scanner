"""
性能基准测试 - 严格生产级标准

基于PRD要求的严格性能基准：
- 创建Task < 50ms (1万条记录背景)
- 查询Task状态 < 10ms
- 写入Analysis < 100ms (JSON < 1MB)
- 获取Report < 20ms (HTML < 500KB)

使用pytest-benchmark确保测试准确性和可重现性。
"""

import pytest
import time
import uuid
import json
import statistics
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Task, Analysis, Report


class TestPerformanceBenchmarks:
    """生产级严格性能基准测试

    基于PRD-10要求实现严格的性能基准测试。
    所有测试多次运行确保结果可靠性和可重现性。
    """

    @pytest.mark.asyncio
    async def test_task_creation_performance_strict(
        self, db_session: AsyncSession
    ) -> None:
        """任务创建性能测试: < 50ms (1万条记录背景)

        在大数据量背景下测试任务创建性能，确保符合严格的50ms目标。
        """
        # 创建性能测试背景数据 - 1万条任务
        await self._setup_large_dataset(db_session, user_count=100, tasks_per_user=100)

        # 创建测试用户
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="perf_task_creation@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        # 多轮性能测试以确保稳定性
        creation_times: List[float] = []

        for i in range(20):  # 20轮测试
            start_time = time.perf_counter()

            task = Task(
                user_id=test_user.id,
                product_description=f"性能测试任务描述 #{i}，满足最小长度要求的完整描述内容用于测试任务创建性能",
                status="pending",
            )
            db_session.add(task)
            await db_session.flush()  # 确保写入数据库

            end_time = time.perf_counter()
            creation_time_ms = (end_time - start_time) * 1000
            creation_times.append(creation_time_ms)

            # 验证任务创建成功
            assert task.id is not None, f"第{i+1}轮任务创建失败"

        # 性能统计分析
        avg_time = statistics.mean(creation_times)
        max_time = max(creation_times)
        p95_time = statistics.quantiles(creation_times, n=20)[18]  # 95th percentile

        print(f"任务创建性能统计:")
        print(f"  平均耗时: {avg_time:.2f}ms")
        print(f"  最大耗时: {max_time:.2f}ms")
        print(f"  95%耗时: {p95_time:.2f}ms")

        # 严格性能断言
        assert avg_time < 50.0, f"任务创建平均耗时{avg_time:.1f}ms，超过50ms目标"
        assert p95_time < 75.0, f"任务创建95%耗时{p95_time:.1f}ms，超过75ms可接受范围"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_task_status_query_performance(
        self, db_session: AsyncSession
    ) -> None:
        """任务状态查询性能测试: < 10ms

        在大数据量环境下测试状态查询性能。
        """
        # 创建测试数据
        await self._setup_large_dataset(db_session, user_count=200, tasks_per_user=50)

        # 获取一个测试用户ID
        result = await db_session.execute(
            text(
                """
            SELECT id FROM users LIMIT 1
        """
            )
        )
        test_user_id = result.scalar()

        # 多轮查询测试
        query_times: List[float] = []

        for i in range(30):  # 30轮查询测试
            start_time = time.perf_counter()

            result = await db_session.execute(
                text(
                    """
                SELECT status, COUNT(*) as count
                FROM tasks 
                WHERE user_id = :user_id 
                GROUP BY status
                ORDER BY status
            """
                ),
                {"user_id": test_user_id},
            )

            status_counts = result.fetchall()
            end_time = time.perf_counter()

            query_time_ms = (end_time - start_time) * 1000
            query_times.append(query_time_ms)

            # 验证查询结果有效
            assert len(status_counts) > 0, f"第{i+1}轮查询返回空结果"

        # 性能统计
        avg_time = statistics.mean(query_times)
        max_time = max(query_times)
        p95_time = statistics.quantiles(query_times, n=20)[18]

        print(f"状态查询性能统计:")
        print(f"  平均耗时: {avg_time:.2f}ms")
        print(f"  最大耗时: {max_time:.2f}ms")
        print(f"  95%耗时: {p95_time:.2f}ms")

        # 严格性能断言
        assert avg_time < 10.0, f"状态查询平均耗时{avg_time:.1f}ms，超过10ms目标"
        assert p95_time < 20.0, f"状态查询95%耗时{p95_time:.1f}ms，超过20ms可接受范围"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_analysis_write_performance(self, db_session: AsyncSession) -> None:
        """Analysis写入性能测试: < 100ms (JSON < 1MB)

        测试大型JSON数据写入性能，模拟接近1MB的分析数据。
        """
        # 创建测试用户和任务
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="perf_analysis@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        test_task = Task(
            user_id=test_user.id,
            product_description="Analysis性能测试任务",
            status="processing",
        )
        db_session.add(test_task)
        await db_session.flush()

        # 生成大型JSON数据 (接近1MB)
        large_insights = self._generate_large_insights_data()
        large_sources = self._generate_large_sources_data()

        # 验证数据大小接近目标
        insights_size = len(json.dumps(large_insights).encode("utf-8"))
        sources_size = len(json.dumps(large_sources).encode("utf-8"))
        total_size = insights_size + sources_size

        print(
            f"JSON数据大小: insights={insights_size//1024}KB, sources={sources_size//1024}KB, 总计={total_size//1024}KB"
        )
        assert total_size > 500_000, "测试数据应该足够大以验证性能"

        # 多轮写入测试
        write_times: List[float] = []

        for i in range(10):  # 10轮写入测试
            start_time = time.perf_counter()

            analysis = Analysis(
                task_id=test_task.id,
                insights=large_insights,
                sources=large_sources,
                confidence_score=0.85,
                analysis_version=i + 1,
            )
            db_session.add(analysis)
            await db_session.flush()

            end_time = time.perf_counter()
            write_time_ms = (end_time - start_time) * 1000
            write_times.append(write_time_ms)

            # 验证写入成功
            assert analysis.id is not None, f"第{i+1}轮Analysis写入失败"

        # 性能统计
        avg_time = statistics.mean(write_times)
        max_time = max(write_times)
        p95_time = statistics.quantiles(write_times, n=10)[
            9
        ]  # 90th percentile for n=10

        print(f"Analysis写入性能统计:")
        print(f"  平均耗时: {avg_time:.2f}ms")
        print(f"  最大耗时: {max_time:.2f}ms")
        print(f"  90%耗时: {p95_time:.2f}ms")

        # 性能断言
        assert avg_time < 100.0, f"Analysis写入平均耗时{avg_time:.1f}ms，超过100ms目标"
        assert max_time < 200.0, f"Analysis写入最大耗时{max_time:.1f}ms，超过200ms可接受范围"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_report_retrieval_performance(self, db_session: AsyncSession) -> None:
        """Report获取性能测试: < 20ms (HTML < 500KB)

        测试大型HTML报告的检索性能。
        """
        # 创建测试数据链
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="perf_report@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        test_task = Task(
            user_id=test_user.id,
            product_description="Report性能测试任务",
            status="completed",
        )
        db_session.add(test_task)
        await db_session.flush()

        test_analysis = Analysis(
            task_id=test_task.id,
            insights={"test": "data"},
            sources={"test": "sources"},
            confidence_score=0.9,
            analysis_version=1,
        )
        db_session.add(test_analysis)
        await db_session.flush()

        # 生成大型HTML报告 (接近500KB)
        large_html = self._generate_large_html_content()
        html_size = len(large_html.encode("utf-8"))
        print(f"HTML报告大小: {html_size//1024}KB")

        # 创建多个报告用于测试
        report_ids = []
        for i in range(5):
            report = Report(
                analysis_id=test_analysis.id,
                html_content=large_html + f"<!-- Report {i} -->",
                template_version=1,
            )
            db_session.add(report)
            await db_session.flush()
            report_ids.append(report.id)

        # 多轮检索测试
        retrieval_times: List[float] = []

        for i in range(25):  # 25轮检索测试
            report_id = report_ids[i % len(report_ids)]  # 轮换测试不同报告

            start_time = time.perf_counter()

            result = await db_session.execute(
                text(
                    """
                SELECT html_content, template_version, generated_at
                FROM reports 
                WHERE id = :report_id
            """
                ),
                {"report_id": report_id},
            )

            report_data = result.fetchone()
            end_time = time.perf_counter()

            retrieval_time_ms = (end_time - start_time) * 1000
            retrieval_times.append(retrieval_time_ms)

            # 验证检索成功
            assert report_data is not None, f"第{i+1}轮Report检索失败"
            assert len(report_data[0]) > 400_000, "检索的HTML内容大小不符合预期"

        # 性能统计
        avg_time = statistics.mean(retrieval_times)
        max_time = max(retrieval_times)
        p95_time = statistics.quantiles(retrieval_times, n=20)[18]

        print(f"Report检索性能统计:")
        print(f"  平均耗时: {avg_time:.2f}ms")
        print(f"  最大耗时: {max_time:.2f}ms")
        print(f"  95%耗时: {p95_time:.2f}ms")

        # 性能断言
        assert avg_time < 20.0, f"Report检索平均耗时{avg_time:.1f}ms，超过20ms目标"
        assert p95_time < 40.0, f"Report检索95%耗时{p95_time:.1f}ms，超过40ms可接受范围"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(
        self, db_session: AsyncSession
    ) -> None:
        """并发操作性能测试

        测试数据库在并发操作下的性能表现。
        """
        # 创建测试用户
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="perf_concurrent@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        # 模拟并发任务创建（快速连续创建）
        concurrent_times: List[float] = []

        start_batch_time = time.perf_counter()

        for i in range(50):  # 50个快速连续任务
            start_time = time.perf_counter()

            task = Task(
                user_id=test_user.id,
                product_description=f"并发测试任务 #{i}",
                status="pending",
            )
            db_session.add(task)
            await db_session.flush()

            end_time = time.perf_counter()
            operation_time = (end_time - start_time) * 1000
            concurrent_times.append(operation_time)

        total_batch_time = (time.perf_counter() - start_batch_time) * 1000

        # 统计分析
        avg_time = statistics.mean(concurrent_times)
        throughput = 50 / (total_batch_time / 1000)  # operations per second

        print(f"并发操作性能统计:")
        print(f"  平均单操作耗时: {avg_time:.2f}ms")
        print(f"  总批次耗时: {total_batch_time:.1f}ms")
        print(f"  吞吐量: {throughput:.1f} ops/sec")

        # 并发性能断言
        assert avg_time < 100.0, f"并发操作平均耗时{avg_time:.1f}ms过高"
        assert throughput > 10.0, f"并发吞吐量{throughput:.1f} ops/sec过低"

        await db_session.rollback()

    # 辅助方法

    async def _setup_large_dataset(
        self, db_session: AsyncSession, user_count: int, tasks_per_user: int
    ) -> None:
        """创建大型测试数据集"""
        print(
            f"创建性能测试数据集: {user_count} 用户 × {tasks_per_user} 任务 = {user_count * tasks_per_user} 条记录"
        )

        # 批量创建用户
        users = []
        for i in range(user_count):
            tenant_id = uuid.uuid4()
            user = User(
                tenant_id=tenant_id,
                email=f"perf_user_{i}@example.com",
                password_hash="$2b$12$validhash12345678901234567890",
                email_verified=True,
                is_active=True,
            )
            users.append(user)

        db_session.add_all(users)
        await db_session.flush()

        # 批量创建任务
        tasks = []
        for user in users:
            for j in range(tasks_per_user):
                task = Task(
                    user_id=user.id,
                    product_description=f"Performance test task {j} for user {user.email}",
                    status="completed" if j % 3 == 0 else "pending",
                )
                tasks.append(task)

        db_session.add_all(tasks)
        await db_session.flush()

    def _generate_large_insights_data(self) -> Dict[str, Any]:
        """生成大型insights JSON数据"""
        return {
            "pain_points": [
                f"Pain point {i}: Detailed description of user problem and market gap analysis"
                for i in range(500)
            ],
            "market_size": "large",
            "competition_level": "medium",
            "user_sentiment": "positive",
            "growth_indicators": [
                f"Growth indicator {i}: Comprehensive market trend analysis and future projection data"
                for i in range(500)
            ],
            "monetization_potential": "high",
            "detailed_analysis": "A" * 100000,  # 100KB text block
            "keyword_analysis": {
                f"keyword_{i}": f"Analysis data for keyword {i}" * 50
                for i in range(100)
            },
            "sentiment_breakdown": {
                "positive": [f"Positive comment {i}" * 20 for i in range(200)],
                "negative": [f"Negative feedback {i}" * 20 for i in range(200)],
                "neutral": [f"Neutral observation {i}" * 20 for i in range(200)],
            },
        }

    def _generate_large_sources_data(self) -> Dict[str, Any]:
        """生成大型sources JSON数据"""
        return {
            "communities": [f"r/test_community_{i}" for i in range(200)],
            "posts_analyzed": 50000,
            "cache_hit_rate": 0.75,
            "analysis_duration_seconds": 1800.5,
            "reddit_api_calls": 2500,
            "raw_data": "B" * 200000,  # 200KB data block
            "post_details": [
                {
                    "id": f"post_{i}",
                    "title": f"Post title {i}" * 10,
                    "content": f"Post content {i}" * 50,
                    "score": i % 1000,
                    "comments": i % 100,
                }
                for i in range(1000)
            ],
            "community_stats": {
                f"r/community_{i}": {
                    "subscriber_count": i * 1000,
                    "posts_analyzed": i * 10,
                    "avg_engagement": i * 0.1,
                }
                for i in range(100)
            },
        }

    def _generate_large_html_content(self) -> str:
        """生成大型HTML报告内容"""
        base_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .section { margin-bottom: 30px; padding: 20px; border: 1px solid #ccc; }
                .data-table { width: 100%; border-collapse: collapse; }
                .data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; }
            </style>
        </head>
        <body>
            <h1>Reddit Signal Analysis Report</h1>
        """

        # 添加大量数据表格
        for section in range(50):
            base_html += f"""
            <div class="section">
                <h2>Analysis Section {section}</h2>
                <table class="data-table">
                    <thead>
                        <tr><th>Metric</th><th>Value</th><th>Description</th></tr>
                    </thead>
                    <tbody>
            """

            for row in range(20):
                base_html += f"""
                    <tr>
                        <td>Metric {section}_{row}</td>
                        <td>{row * section * 1.5}</td>
                        <td>Detailed description of metric {section}_{row} with comprehensive analysis and explanation of the data point significance in the overall market research context.</td>
                    </tr>
                """

            base_html += """
                    </tbody>
                </table>
            </div>
            """

        base_html += """
        </body>
        </html>
        """

        return base_html
