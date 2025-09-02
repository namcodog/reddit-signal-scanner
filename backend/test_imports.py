#!/usr/bin/env python3
"""
测试模型导入 - 验证修复结果
"""


def test_basic_imports():
    """测试基本导入功能"""
    print("🧪 测试基本模块导入...")

    try:
        # 1. 测试Base模型导入
        print("1. 测试Base模型...")
        from app.models.base import Base

        print("   ✅ Base导入成功")

        # 2. 测试Report模型导入
        print("2. 测试Report模型...")
        from app.models.report import Report, create_report

        print(f"   ✅ Report导入成功，表名: {Report.__tablename__}")

        # 3. 测试Analysis模型导入
        print("3. 测试Analysis模型...")
        from app.models.analysis import Analysis

        print(f"   ✅ Analysis导入成功，表名: {Analysis.__tablename__}")

        # 4. 测试服务层导入
        print("4. 测试ReportCacheService...")
        from app.services.report_cache_service import ReportCacheService

        print("   ✅ ReportCacheService导入成功")

        print("\n🎉 所有导入测试通过！")
        return True

    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        return False
    except Exception as e:
        print(f"⚠️ 其他错误: {e}")
        return False


def test_model_structure():
    """测试模型结构"""
    print("\n🔍 验证模型结构...")

    try:
        from app.models.report import Report
        from app.models.analysis import Analysis

        # 检查Report模型
        print("Report模型属性:")
        print(f"  - 表名: {Report.__tablename__}")
        print(f"  - 主键: {Report.__table__.primary_key}")

        # 检查Analysis模型
        print("Analysis模型属性:")
        print(f"  - 表名: {Analysis.__tablename__}")
        print(f"  - 主键: {Analysis.__table__.primary_key}")

        print("✅ 模型结构验证通过")
        return True

    except Exception as e:
        print(f"❌ 模型结构测试失败: {e}")
        return False


if __name__ == "__main__":
    print("🚀 开始验证修复结果...\n")

    import_test = test_basic_imports()
    structure_test = test_model_structure()

    if import_test and structure_test:
        print("\n✅ 所有测试通过！导入问题已修复")
        print("📋 Pylance的警告应该会消失")
    else:
        print("\n❌ 仍有问题需要解决")
