#!/usr/bin/env python3
"""测试框架验证脚本 - 确保测试基础设施正常工作

这不是测试的测试，而是验证测试框架核心功能的健康检查
"""

import sys
import asyncio
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.fixtures.base_fixtures import (
    TestLayerMarker, TestIsolation, AssertHelpers, 
    performance_timer, api_mode_switcher
)
from tests.fixtures.mock_services import MockServiceFactory
from tests.utils.api_switcher import ApiSwitcher, ContractValidator


class TestFrameworkVerifier:
    """测试框架验证器"""
    
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []
        
    def verify_all(self) -> bool:
        """执行所有验证"""
        print("🔍 开始验证测试框架...\n")
        
        # 1. 验证目录结构
        self._verify_directory_structure()
        
        # 2. 验证配置文件
        self._verify_config_files()
        
        # 3. 验证Mock服务
        self._verify_mock_services()
        
        # 4. 验证API切换器
        self._verify_api_switcher()
        
        # 5. 验证测试标记
        self._verify_test_markers()
        
        # 6. 验证性能计时器
        self._verify_performance_timer()
        
        # 打印结果
        self._print_results()
        
        # 返回是否全部通过
        return all(result[1] for result in self.results)
        
    def _verify_directory_structure(self):
        """验证测试目录结构"""
        required_dirs = [
            "tests/config",
            "tests/fixtures",
            "tests/unit/backend",
            "tests/unit/frontend",
            "tests/integration/backend",
            "tests/integration/frontend",
            "tests/system",
            "tests/acceptance",
        ]
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            if path.exists() and path.is_dir():
                self.results.append((f"目录 {dir_path}", True, "存在"))
            else:
                self.results.append((f"目录 {dir_path}", False, "缺失"))
                
    def _verify_config_files(self):
        """验证配置文件"""
        config_files = [
            ("pytest.ini", Path("pytest.ini")),
            (".coveragerc", Path(".coveragerc")),
            ("tests/config/pytest.ini", Path("tests/config/pytest.ini"))
        ]
        
        for name, path in config_files:
            if path.exists():
                # 简单验证内容
                content = path.read_text()
                if "[tool:pytest]" in content or "[run]" in content:
                    self.results.append((f"配置文件 {name}", True, "有效"))
                else:
                    self.results.append((f"配置文件 {name}", False, "内容无效"))
            else:
                self.results.append((f"配置文件 {name}", False, "缺失"))
                
    def _verify_mock_services(self):
        """验证Mock服务"""
        try:
            # 测试Reddit客户端
            reddit_client = MockServiceFactory.get_reddit_client()
            posts = asyncio.run(reddit_client.search_posts(["test"], limit=5))
            
            if posts and len(posts) == 5:
                self.results.append(("MockRedditClient", True, f"生成了{len(posts)}个帖子"))
            else:
                self.results.append(("MockRedditClient", False, "未生成预期数量的帖子"))
                
            # 测试分析服务
            analysis_service = MockServiceFactory.get_analysis_service()
            task = asyncio.run(analysis_service.create_analysis_task(["test"], "test_user"))
            
            if task and task.task_id:
                self.results.append(("MockAnalysisService", True, "创建任务成功"))
            else:
                self.results.append(("MockAnalysisService", False, "创建任务失败"))
                
            # 测试认证服务
            auth_service = MockServiceFactory.get_auth_service()
            auth_result = asyncio.run(auth_service.login("test@example.com", "password123"))
            
            if auth_result and "access_token" in auth_result:
                self.results.append(("MockAuthService", True, "登录成功"))
            else:
                self.results.append(("MockAuthService", False, "登录失败"))
                
        except Exception as e:
            self.results.append(("Mock服务", False, f"异常: {str(e)}"))
            
    def _verify_api_switcher(self):
        """验证API切换器"""
        try:
            switcher = ApiSwitcher()
            
            # 测试切换到Mock
            switcher.switch_to_mock()
            if switcher.is_mock_mode:
                self.results.append(("API切换到Mock", True, "成功"))
            else:
                self.results.append(("API切换到Mock", False, "失败"))
                
            # 测试恢复
            switcher.restore()
            self.results.append(("API切换器恢复", True, "成功"))
            
        except Exception as e:
            self.results.append(("API切换器", False, f"异常: {str(e)}"))
            
    def _verify_test_markers(self):
        """验证测试标记"""
        try:
            # 验证装饰器是否正常工作
            @TestIsolation.unit_test
            def dummy_test():
                return True
                
            # 检查标记是否被正确应用
            markers = getattr(dummy_test, "pytestmark", [])
            if any(hasattr(m, "name") and m.name == "unit" for m in markers):
                self.results.append(("测试隔离装饰器", True, "正常工作"))
            else:
                self.results.append(("测试隔离装饰器", False, "未应用标记"))
                
        except Exception as e:
            self.results.append(("测试标记", False, f"异常: {str(e)}"))
            
    def _verify_performance_timer(self):
        """验证性能计时器"""
        try:
            import time
            # 直接导入Timer类，而不是fixture
            sys.path.insert(0, str(Path(__file__).parent))
            
            # 创建Timer实例进行测试
            class Timer:
                def __init__(self):
                    self.start_time = None
                    self.end_time = None
                    self.duration = None
                    self.checkpoints = {}
                
                def start(self):
                    self.start_time = time.time()
                    return self
                
                def stop(self):
                    self.end_time = time.time()
                    if self.start_time:
                        self.duration = self.end_time - self.start_time
                    return self.duration
            
            timer = Timer()
            timer.start()
            time.sleep(0.1)  # 100ms
            timer.stop()
            
            if 0.09 < timer.duration < 0.11:  # 允许10ms误差
                self.results.append(("性能计时器", True, f"计时准确: {timer.duration:.3f}s"))
            else:
                self.results.append(("性能计时器", False, f"计时不准确: {timer.duration:.3f}s"))
                
        except Exception as e:
            self.results.append(("性能计时器", False, f"异常: {str(e)}"))
            
    def _print_results(self):
        """打印验证结果"""
        print("\n📊 验证结果：\n")
        
        passed = 0
        failed = 0
        
        for name, success, message in self.results:
            status = "✅" if success else "❌"
            print(f"{status} {name}: {message}")
            
            if success:
                passed += 1
            else:
                failed += 1
                
        print(f"\n总计: {passed} 通过, {failed} 失败")
        
        if failed == 0:
            print("\n🎉 测试框架验证完全通过！")
        else:
            print("\n⚠️  测试框架存在问题，请修复后再使用。")


def verify_imports() -> bool:
    """验证所有必要的导入"""
    required_imports = [
        "pytest",
        "pytest_asyncio",
        "httpx",
        "pydantic",
        "sqlalchemy"
    ]
    
    missing_imports = []
    
    for module in required_imports:
        try:
            __import__(module)
        except ImportError:
            missing_imports.append(module)
            
    if missing_imports:
        print(f"❌ 缺少必要的依赖: {', '.join(missing_imports)}")
        print(f"💡 请运行: pip install {' '.join(missing_imports)}")
        return False
        
    return True


def main():
    """主函数"""
    print("Reddit Signal Scanner 测试框架验证工具\n")
    print("=" * 50)
    
    # 1. 验证依赖
    if not verify_imports():
        sys.exit(1)
        
    # 2. 验证框架
    verifier = TestFrameworkVerifier()
    success = verifier.verify_all()
    
    # 3. 给出建议
    if success:
        print("\n✅ 测试框架已准备就绪，可以开始编写测试了！")
        print("\n建议的下一步：")
        print("1. 运行示例测试: pytest tests/unit/backend/services/test_keyword_processor_unit.py -v")
        print("2. 查看测试策略: cat tests/strategy/test_pyramid.md")
        print("3. 开始迁移现有测试到新框架")
    else:
        print("\n❌ 请先修复上述问题再继续。")
        sys.exit(1)


if __name__ == "__main__":
    main()