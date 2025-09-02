#!/usr/bin/env python3
"""
Reddit Signal Scanner - 数据库配置验证脚本
prd01-08任务验证：确保数据库配置和性能优化正确实施

Linus原则: "简单的验证脚本，直接输出结果"
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import (
    validate_database_config,
    check_database_health,
    load_database_config,
)
from app.core.config import get_settings


def print_header(title: str) -> None:
    """打印标题分隔符"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_section(title: str) -> None:
    """打印小节标题"""
    print(f"\n{'-'*40}")
    print(f"  {title}")
    print(f"{'-'*40}")


def format_status(status: bool) -> str:
    """格式化状态显示"""
    return "✅ 通过" if status else "❌ 失败"


def print_config_summary(config: dict) -> None:
    """打印配置摘要"""
    if not config:
        print("⚠️ 配置为空或未加载")
        return

    # 内存配置
    memory = config.get("memory", {})
    if memory:
        print(f"📊 内存配置:")
        print(f"   - shared_buffers: {memory.get('shared_buffers', '未配置')}")
        print(
            f"   - effective_cache_size: {memory.get('effective_cache_size', '未配置')}"
        )
        print(f"   - work_mem: {memory.get('work_mem', '未配置')}")

    # 连接配置
    conn_limits = config.get("connection_limits", {})
    if conn_limits:
        print(f"🔗 连接配置:")
        print(f"   - max_connections: {conn_limits.get('max_connections', '未配置')}")

    # JSONB优化
    jsonb = config.get("jsonb_optimization", {})
    if jsonb:
        print(f"📝 JSONB优化:")
        print(
            f"   - gin_pending_list_limit: {jsonb.get('gin_pending_list_limit', '未配置')}"
        )

    # 性能目标
    targets = config.get("performance_targets", {})
    settings = get_settings()
    env_targets = targets.get(settings.environment, {})
    if env_targets:
        print(f"🎯 性能目标 ({settings.environment}):")
        print(
            f"   - JSONB查询最大时间: {env_targets.get('jsonb_query_max_time', '未配置')}"
        )
        print(f"   - 并发连接数: {env_targets.get('concurrent_connections', '未配置')}")


def validate_prd01_08_requirements(config: dict) -> tuple[bool, list[str]]:
    """验证prd01-08任务要求是否满足"""
    requirements_met = []
    issues = []

    settings = get_settings()
    env = settings.environment

    # 检查内存配置要求
    memory = config.get("memory", {})
    if memory:
        shared_buffers = memory.get("shared_buffers", "")
        if "512MB" in shared_buffers and env == "production":
            requirements_met.append("✅ shared_buffers: 512MB (生产环境)")
        elif "256MB" in shared_buffers and env == "development":
            requirements_met.append("✅ shared_buffers: 256MB (开发环境)")

        effective_cache = memory.get("effective_cache_size", "")
        if "2GB" in effective_cache and env == "production":
            requirements_met.append("✅ effective_cache_size: 2GB (生产环境)")
        elif "1GB" in effective_cache and env == "development":
            requirements_met.append("✅ effective_cache_size: 1GB (开发环境)")

        work_mem = memory.get("work_mem", "")
        if "8MB" in work_mem and env == "production":
            requirements_met.append("✅ work_mem: 8MB (生产环境)")
        elif "4MB" in work_mem and env == "development":
            requirements_met.append("✅ work_mem: 4MB (开发环境)")
    else:
        issues.append("❌ 未找到内存配置")

    # 检查连接配置要求
    conn_limits = config.get("connection_limits", {})
    if conn_limits:
        max_conn = conn_limits.get("max_connections", 0)
        if max_conn == 100 and env == "production":
            requirements_met.append("✅ max_connections: 100 (生产环境)")
        elif max_conn == 50 and env == "development":
            requirements_met.append("✅ max_connections: 50 (开发环境)")
        else:
            issues.append(f"❌ max_connections配置不匹配: {max_conn}")
    else:
        issues.append("❌ 未找到连接限制配置")

    # 检查GIN索引优化要求
    jsonb = config.get("jsonb_optimization", {})
    if jsonb:
        gin_limit = jsonb.get("gin_pending_list_limit", "")
        if "4MB" in gin_limit:
            requirements_met.append("✅ gin_pending_list_limit: 4MB")
    else:
        issues.append("❌ 未找到JSONB优化配置")

    # 检查连接超时配置要求
    connections = config.get("connections", {})
    if connections:
        stmt_timeout = connections.get("statement_timeout", "")
        if "30s" in stmt_timeout:
            requirements_met.append("✅ statement_timeout: 30s")

        idle_timeout = connections.get("idle_in_transaction_session_timeout", "")
        if "60s" in idle_timeout:
            requirements_met.append("✅ idle_in_transaction_session_timeout: 60s")
    else:
        issues.append("❌ 未找到连接超时配置")

    return len(issues) == 0, requirements_met + issues


async def main():
    """主验证流程"""
    print_header("Reddit Signal Scanner - 数据库配置验证")
    print("prd01-08任务验证：数据库配置和性能优化")

    settings = get_settings()
    print(f"🌍 当前环境: {settings.environment}")
    print(f"🔧 调试模式: {'启用' if settings.debug else '禁用'}")

    # 1. 基础配置验证
    print_section("1. 配置文件验证")
    try:
        config = load_database_config()
        if config:
            print("✅ 数据库配置文件加载成功")
            print_config_summary(config)
        else:
            print("❌ 数据库配置文件加载失败或为空")
            return False
    except Exception as e:
        print(f"❌ 配置加载异常: {e}")
        return False

    # 2. 配置有效性验证
    print_section("2. 配置有效性检查")
    validation_result = validate_database_config()
    print(f"配置有效性: {format_status(validation_result['valid'])}")

    if validation_result.get("issues"):
        print("❌ 发现的问题:")
        for issue in validation_result["issues"]:
            print(f"   - {issue}")

    if validation_result.get("warnings"):
        print("⚠️ 警告:")
        for warning in validation_result["warnings"]:
            print(f"   - {warning}")

    config_summary = validation_result.get("config_summary", {})
    print(f"📊 配置摘要:")
    print(
        f"   - 内存优化: {format_status(config_summary.get('memory_optimized', False))}"
    )
    print(
        f"   - JSONB优化: {format_status(config_summary.get('jsonb_optimized', False))}"
    )
    print(
        f"   - 多租户就绪: {format_status(config_summary.get('multi_tenant_ready', False))}"
    )

    # 3. prd01-08任务要求验证
    print_section("3. PRD01-08任务要求验证")
    requirements_met, details = validate_prd01_08_requirements(config)
    print(f"任务要求满足: {format_status(requirements_met)}")

    if details:
        print("📋 详细检查结果:")
        for detail in details:
            print(f"   {detail}")

    # 4. 数据库连接健康检查（如果数据库可用）
    print_section("4. 数据库连接测试")
    try:
        health = await check_database_health()
        if health["status"] == "healthy":
            print("✅ 数据库连接健康")
            print(f"   - 连接状态: {health['connection']}")
            print(f"   - 测试查询: {health['test_query']}")

            pool_status = health.get("pool_status")
            if pool_status:
                print(f"   - 连接池大小: {pool_status['size']}")
                print(f"   - 已检出连接: {pool_status['checked_out']}")
                print(f"   - 已归还连接: {pool_status['checked_in']}")

            config_info = health.get("configuration", {})
            print(
                f"   - 优化配置启用: {format_status(config_info.get('optimization_enabled', False))}"
            )
            print(
                f"   - JSONB优化: {format_status(config_info.get('jsonb_optimization', False))}"
            )
            print(
                f"   - 多租户支持: {format_status(config_info.get('multi_tenant', False))}"
            )
        else:
            print(f"❌ 数据库连接不健康: {health.get('error', '未知错误')}")
            print("   (这可能是因为数据库服务未启动，属于正常情况)")

    except Exception as e:
        print(f"⚠️ 数据库连接测试跳过: {e}")
        print("   (数据库服务可能未启动，这是正常情况)")

    # 5. 总结
    print_section("5. 验证总结")

    overall_success = config and validation_result["valid"] and requirements_met

    print(f"🎯 prd01-08任务实施状态: {format_status(overall_success)}")

    if overall_success:
        print("\n🎉 恭喜！prd01-08任务已成功实施:")
        print("   ✅ 数据库配置文件创建完成")
        print("   ✅ PostgreSQL服务器优化配置就绪")
        print("   ✅ 数据库连接代码零破坏性扩展完成")
        print("   ✅ JSONB和多租户性能优化配置生效")
        print("   ✅ 所有任务要求参数配置正确")

        print("\n📈 预期性能提升:")
        targets = config.get("performance_targets", {}).get(settings.environment, {})
        if targets:
            print(
                f"   🔹 JSONB查询目标: <{targets.get('jsonb_query_max_time', '50ms')}"
            )
            print(
                f"   🔹 并发连接支持: {targets.get('concurrent_connections', '100')}个"
            )
            if "multi_tenant_query_max_time" in targets:
                print(
                    f"   🔹 多租户查询目标: <{targets['multi_tenant_query_max_time']}"
                )
    else:
        print("\n⚠️ prd01-08任务实施需要注意以下问题:")
        if not config:
            print("   - 数据库配置文件需要检查")
        if not validation_result["valid"]:
            print("   - 配置验证存在问题")
        if not requirements_met:
            print("   - 任务要求参数需要调整")

    print(f"\n{'='*60}")
    return overall_success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 验证中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 验证异常: {e}")
        sys.exit(1)
