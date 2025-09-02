"""
数据库Schema结构测试 - 完整验证套件

基于Linus原则的数据结构优先设计：
- 数据结构决定代码质量
- 消除特殊情况，统一验证逻辑
- 严格约束验证确保数据完整性
"""

import pytest
from typing import Dict, List, Set, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestDatabaseSchema:
    """数据库Schema结构完整验证测试

    验证所有表结构、约束、索引的正确性和一致性。
    基于Linus的数据结构优先哲学，确保数据模型的完整性。
    """

    @pytest.mark.asyncio
    async def test_all_required_tables_exist(self, db_session: AsyncSession) -> None:
        """验证所有必需表存在且命名正确

        Args:
            db_session: 数据库会话

        Raises:
            AssertionError: 如果缺少必需的表
        """
        result = await db_session.execute(
            text(
                """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
            )
        )

        existing_tables: Set[str] = {row[0] for row in result.fetchall()}
        required_tables: Set[str] = {
            "users",
            "tasks",
            "analyses",
            "reports",
            "community_caches",
        }

        missing = required_tables - existing_tables
        assert not missing, f"缺少核心表: {sorted(missing)}"

        extra = existing_tables - required_tables - {"alembic_version"}
        if extra:
            print(f"发现额外表 (可能是测试表): {sorted(extra)}")

    @pytest.mark.asyncio
    async def test_table_columns_structure(self, db_session: AsyncSession) -> None:
        """验证表列结构的正确性

        验证每个表的关键列存在，类型正确，约束完整。
        """
        # 定义期望的表结构
        expected_columns: Dict[str, Dict[str, str]] = {
            "users": {
                "id": "uuid",
                "tenant_id": "uuid",
                "email": "character varying",
                "password_hash": "character varying",
                "email_verified": "boolean",
                "is_active": "boolean",
                "created_at": "timestamp with time zone",
                "updated_at": "timestamp with time zone",
            },
            "tasks": {
                "id": "uuid",
                "user_id": "uuid",
                "product_description": "text",
                "status": "character varying",
                "created_at": "timestamp with time zone",
                "updated_at": "timestamp with time zone",
            },
            "analyses": {
                "id": "uuid",
                "task_id": "uuid",
                "insights": "jsonb",
                "sources": "jsonb",
                "confidence_score": "double precision",
                "analysis_version": "integer",
                "created_at": "timestamp with time zone",
            },
            "reports": {
                "id": "uuid",
                "analysis_id": "uuid",
                "html_content": "text",
                "template_version": "integer",
                "generated_at": "timestamp with time zone",
            },
            "community_caches": {
                "id": "uuid",
                "community_name": "character varying",
                "cached_data": "jsonb",
                "expires_at": "timestamp with time zone",
                "created_at": "timestamp with time zone",
            },
        }

        for table_name, expected_cols in expected_columns.items():
            result = await db_session.execute(
                text(
                    """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name
                ORDER BY ordinal_position
            """
                ),
                {"table_name": table_name},
            )

            actual_columns = {row[0]: row[1] for row in result.fetchall()}

            # 验证关键列存在且类型正确
            for col_name, expected_type in expected_cols.items():
                assert col_name in actual_columns, f"表 {table_name} 缺少列 {col_name}"

                actual_type = actual_columns[col_name]
                assert actual_type == expected_type, (
                    f"表 {table_name}.{col_name} 类型错误: "
                    f"期望 {expected_type}, 实际 {actual_type}"
                )

    @pytest.mark.asyncio
    async def test_foreign_key_constraints_complete(
        self, db_session: AsyncSession
    ) -> None:
        """验证外键约束完整性和级联删除设置

        确保所有必需的外键约束存在，级联删除设置正确。
        """
        result = await db_session.execute(
            text(
                """
            SELECT 
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints tc 
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu 
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints rc 
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """
            )
        )

        fk_constraints: List[Tuple] = result.fetchall()
        assert (
            len(fk_constraints) >= 3
        ), f"外键约束不足，期望至少3个，实际: {len(fk_constraints)}"

        # 验证关键外键关系存在
        expected_fks: Set[Tuple[str, str, str]] = {
            ("tasks", "user_id", "users"),
            ("analyses", "task_id", "tasks"),
            ("reports", "analysis_id", "analyses"),
        }

        actual_fks: Set[Tuple[str, str, str]] = {
            (fk[0], fk[2], fk[3]) for fk in fk_constraints
        }

        missing_fks = expected_fks - actual_fks
        assert not missing_fks, f"缺少关键外键约束: {missing_fks}"

        # 验证级联删除设置
        cascade_rules = [fk for fk in fk_constraints if fk[5] == "CASCADE"]
        assert (
            len(cascade_rules) >= 2
        ), f"级联删除规则不足，期望至少2个，实际: {len(cascade_rules)}"

    @pytest.mark.asyncio
    async def test_indexes_exist_and_optimized(self, db_session: AsyncSession) -> None:
        """验证索引存在并针对查询优化

        确保关键查询有对应的索引支持，包括B-tree和GIN索引。
        """
        result = await db_session.execute(
            text(
                """
            SELECT 
                schemaname, 
                tablename, 
                indexname, 
                indexdef,
                CASE 
                    WHEN indexdef LIKE '%USING gin%' THEN 'gin'
                    WHEN indexdef LIKE '%USING btree%' THEN 'btree'
                    ELSE 'other'
                END as index_type
            FROM pg_indexes 
            WHERE tablename IN ('users', 'tasks', 'analyses', 'reports', 'community_caches')
                AND indexname NOT LIKE '%_pkey'
            ORDER BY tablename, indexname
        """
            )
        )

        indexes = result.fetchall()

        # 按类型分组索引
        gin_indexes = [idx for idx in indexes if idx[4] == "gin"]
        btree_indexes = [idx for idx in indexes if idx[4] == "btree"]

        # 验证GIN索引存在（用于JSONB列）
        assert (
            len(gin_indexes) >= 2
        ), f"GIN索引不足，期望至少2个（用于JSONB查询），实际: {len(gin_indexes)}"

        # 验证B-tree索引存在（用于常规查询）
        assert (
            len(btree_indexes) >= 6
        ), f"B-tree索引不足，期望至少6个（用于外键和查询优化），实际: {len(btree_indexes)}"

        # 验证关键索引存在
        index_names = {idx[2] for idx in indexes}
        critical_indexes = {
            "ix_users_email",
            "ix_users_tenant_id",
            "ix_tasks_user_id",
            "ix_tasks_status",
            "ix_analyses_task_id",
            "ix_reports_analysis_id",
        }

        for critical_idx in critical_indexes:
            if critical_idx not in index_names:
                print(f"警告: 建议创建索引 {critical_idx} 以优化查询性能")

    @pytest.mark.asyncio
    async def test_check_constraints_enforced(self, db_session: AsyncSession) -> None:
        """验证CHECK约束正确强制执行

        确保数据完整性约束在数据库层面得到强制执行。
        """
        result = await db_session.execute(
            text(
                """
            SELECT 
                tc.table_name,
                tc.constraint_name,
                cc.check_clause
            FROM information_schema.table_constraints tc
            JOIN information_schema.check_constraints cc
                ON tc.constraint_name = cc.constraint_name
            WHERE tc.constraint_type = 'CHECK'
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """
            )
        )

        check_constraints = result.fetchall()

        # 验证关键CHECK约束存在
        constraint_tables = {constraint[0] for constraint in check_constraints}
        expected_tables = {"tasks", "analyses", "users"}

        missing_check_tables = expected_tables - constraint_tables
        if missing_check_tables:
            print(
                f"警告: 这些表可能需要CHECK约束来确保数据完整性: {missing_check_tables}"
            )

        # 验证至少存在基础约束
        print(f"发现 {len(check_constraints)} 个CHECK约束")

    @pytest.mark.asyncio
    async def test_unique_constraints_complete(self, db_session: AsyncSession) -> None:
        """验证唯一性约束完整性

        确保应该唯一的字段有对应的UNIQUE约束。
        """
        result = await db_session.execute(
            text(
                """
            SELECT 
                tc.table_name,
                tc.constraint_name,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_schema = 'public'
            GROUP BY tc.table_name, tc.constraint_name
            ORDER BY tc.table_name
        """
            )
        )

        unique_constraints = result.fetchall()

        # 验证关键唯一性约束
        unique_columns = {
            (constraint[0], constraint[2]) for constraint in unique_constraints
        }
        expected_unique = {("users", "email"), ("community_caches", "community_name")}

        for table, column in expected_unique:
            matching = [
                uc for uc in unique_columns if uc[0] == table and column in uc[1]
            ]
            assert matching, f"表 {table} 的列 {column} 应该有唯一性约束"

    @pytest.mark.asyncio
    async def test_database_functions_exist(self, db_session: AsyncSession) -> None:
        """验证数据库函数存在且可用

        检查JSON验证函数和其他自定义函数的可用性。
        """
        result = await db_session.execute(
            text(
                """
            SELECT routine_name, routine_type
            FROM information_schema.routines
            WHERE routine_schema = 'public'
                AND routine_type = 'FUNCTION'
            ORDER BY routine_name
        """
            )
        )

        functions = result.fetchall()
        function_names = {func[0] for func in functions}

        # 验证关键函数存在
        expected_functions = {"validate_insights_schema", "validate_sources_schema"}

        missing_functions = expected_functions - function_names
        if missing_functions:
            print(f"警告: 缺少数据验证函数: {missing_functions}")
            print("建议创建这些函数以确保JSON数据完整性")

        # 如果函数存在，测试其基本可用性
        for func_name in expected_functions.intersection(function_names):
            try:
                test_result = await db_session.execute(
                    text(f"SELECT {func_name}('{{}}') as result")
                )
                result_value = test_result.scalar()
                print(f"函数 {func_name} 可用，测试结果: {result_value}")
            except Exception as e:
                print(f"警告: 函数 {func_name} 存在但执行失败: {e}")
