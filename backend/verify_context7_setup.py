#!/usr/bin/env python3
"""
验证Context7设置是否正确
快速检查pytest-celery是否可以正常工作
"""

import sys
import subprocess


def main():
    """运行基本验证"""
    print("🔍 验证Context7设置...")

    # 1. 检查pytest-celery安装
    try:
        import pytest_celery

        print("✅ pytest-celery已安装")
    except ImportError:
        print("❌ pytest-celery未安装，请运行: pip install pytest-celery==1.1.0")
        return 1

    # 2. 检查Redis连接
    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, db=15)
        r.ping()
        print("✅ Redis连接正常")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        print("   请确保Redis正在运行: docker run -d -p 6379:6379 redis:latest")
        return 1

    # 3. 检查测试文件
    import os

    test_file = "tests/test_task_integration.py"
    if os.path.exists(test_file):
        print(f"✅ 测试文件存在: {test_file}")
    else:
        print(f"❌ 测试文件不存在: {test_file}")
        return 1

    # 4. 运行一个简单测试
    print("\n🚀 运行环境就绪测试...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_task_integration.py::TestTaskSystemIntegration::test_celery_environment_ready",
            "-v",
            "-s",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✅ Context7环境测试通过！")
        print("\n可以运行完整测试：")
        print("  pytest tests/test_task_integration.py -v")
    else:
        print("❌ 测试失败")
        print("错误输出：")
        print(result.stderr)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
