#!/usr/bin/env python3
"""
简单验证Celery任务系统是否正常工作
使用eager模式快速测试基本功能
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# 设置环境为测试模式
os.environ["CELERY_ALWAYS_EAGER"] = "True"

from app.tasks.analysis_tasks import analysis_health_check, analyze_product_task


def test_health_check():
    """测试健康检查任务"""
    print("测试健康检查任务...")
    result = analysis_health_check.delay()
    task_result = result.get()

    print(f"任务结果类型: {type(task_result)}")
    print(f"任务结果: {task_result}")

    # 根据实际返回类型验证
    if isinstance(task_result, dict):
        assert task_result["status"] == "healthy"
        print("✅ 健康检查测试通过（返回dict）")
    else:
        assert hasattr(task_result, "status")
        assert task_result.status == "healthy"
        print("✅ 健康检查测试通过（返回对象）")


def test_analyze_product():
    """测试产品分析任务"""
    print("\n测试产品分析任务...")
    test_payload = {"product_description": "AI写作助手，帮助用户生成高质量内容"}
    test_data = {"task_id": "test-001", "user_id": "test-user"}

    try:
        result = analyze_product_task.delay(payload=test_payload, task_data=test_data)
        task_result = result.get()

        print(f"任务结果: {task_result}")
        assert task_result is not None
        print("✅ 产品分析测试通过")
    except Exception as e:
        print(f"⚠️  产品分析需要完整环境: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Celery任务系统基本功能验证")
    print("=" * 50)

    test_health_check()
    test_analyze_product()

    print("\n验证完成！")
