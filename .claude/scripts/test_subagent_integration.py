#!/usr/bin/env python3
"""
SubAgent系统集成测试
验证PreCodeValidator、TypeEnforcer、DesignReviewer与现有工具的协同工作
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import json

# 添加项目根目录到path
sys.path.append(str(Path(__file__).parent.parent.parent))

class SubAgentIntegrationTest:
    """SubAgent系统集成测试"""
    
    def __init__(self):
        self.test_results = {}
        self.temp_files = []
        
    def cleanup(self):
        """清理测试文件"""
        for file_path in self.temp_files:
            try:
                os.remove(file_path)
            except:
                pass
    
    def create_test_file(self, content: str, suffix: str = ".py") -> str:
        """创建临时测试文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            self.temp_files.append(f.name)
            return f.name
    
    def test_quality_gate_integration(self) -> Dict[str, Any]:
        """测试quality_gate与SubAgent协同"""
        print("🔄 测试Quality Gate与SubAgent集成...")
        
        # 测试代码：故意包含type:ignore来触发TypeEnforcer
        bad_code = '''
def bad_function(data):  # 缺少类型注解
    result = data.get("key")  # type: ignore  # 类型逃避
    return result

def another_bad(x: Any) -> Any:  # 滥用Any
    pass
'''
        
        good_code = '''
from typing import Dict, Optional, Any

def good_function(data: Dict[str, Any]) -> Optional[str]:
    """完整类型注解的函数"""
    result = data.get("key")
    return str(result) if result is not None else None
'''
        
        # 创建测试文件
        bad_file = self.create_test_file(bad_code)
        good_file = self.create_test_file(good_code)
        
        # 测试quality_gate对不良代码的检测
        quality_gate_path = Path(__file__).parent.parent.parent / "backend/scripts/quality_gate.py"
        if quality_gate_path.exists():
            # 测试不良代码
            result_bad = subprocess.run([
                "python", str(quality_gate_path), "--files", bad_file
            ], capture_output=True, text=True)
            
            # 测试良好代码  
            result_good = subprocess.run([
                "python", str(quality_gate_path), "--files", good_file
            ], capture_output=True, text=True)
            
            return {
                "quality_gate_available": True,
                "bad_code_blocked": result_bad.returncode != 0,
                "good_code_passed": result_good.returncode == 0,
                "bad_output": result_bad.stdout,
                "good_output": result_good.stdout
            }
        else:
            return {"quality_gate_available": False}
    
    def test_subagent_file_structure(self) -> Dict[str, Any]:
        """测试SubAgent配置文件结构"""
        print("📁 测试SubAgent文件结构...")
        
        agents_dir = Path(__file__).parent.parent / "agents"
        
        required_agents = [
            "pre-code-validator.md",
            "type-enforcer.md", 
            "design-reviewer.md"
        ]
        
        results = {}
        for agent_file in required_agents:
            agent_path = agents_dir / agent_file
            if agent_path.exists():
                # 检查文件格式是否正确
                with open(agent_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 检查YAML前端
                has_yaml_header = content.startswith('---')
                has_name_field = 'name:' in content[:500]
                has_description_field = 'description:' in content[:500]
                has_tools_field = 'tools:' in content[:500]
                
                results[agent_file] = {
                    "exists": True,
                    "has_yaml_header": has_yaml_header,
                    "has_name": has_name_field,
                    "has_description": has_description_field,
                    "has_tools": has_tools_field,
                    "valid_format": all([has_yaml_header, has_name_field, 
                                       has_description_field, has_tools_field])
                }
            else:
                results[agent_file] = {"exists": False}
        
        return results
    
    def test_workflow_integration(self) -> Dict[str, Any]:
        """测试SubAgent与workflow.py集成"""
        print("🔄 测试Workflow集成...")
        
        workflow_path = Path(__file__).parent.parent.parent / "workflow.py"
        if workflow_path.exists():
            # 测试workflow status命令
            result = subprocess.run([
                "python", str(workflow_path), "status"
            ], capture_output=True, text=True, cwd=str(workflow_path.parent))
            
            return {
                "workflow_available": True,
                "status_works": result.returncode == 0,
                "output": result.stdout[:500] if result.stdout else result.stderr[:500]
            }
        else:
            return {"workflow_available": False}
    
    def test_mypy_strict_mode(self) -> Dict[str, Any]:
        """测试MyPy严格模式检查"""
        print("🔍 测试MyPy严格模式...")
        
        # 测试代码：各种类型问题
        test_cases = {
            "missing_types": '''
def missing_types_function(data):
    return data.get("key")
''',
            "type_ignore": '''
def type_ignore_function(data: dict) -> str:
    result = data.get("key")  # type: ignore
    return result
''',
            "any_abuse": '''
from typing import Any
def any_abuse_function(data: Any) -> Any:
    return data
''',
            "good_types": '''
from typing import Dict, Optional
def good_function(data: Dict[str, str]) -> Optional[str]:
    return data.get("key")
'''
        }
        
        results = {}
        for test_name, code in test_cases.items():
            test_file = self.create_test_file(code)
            
            # 运行mypy --strict检查
            result = subprocess.run([
                "python", "-m", "mypy", "--strict", test_file
            ], capture_output=True, text=True)
            
            results[test_name] = {
                "exit_code": result.returncode,
                "has_errors": result.returncode != 0,
                "error_count": len([line for line in result.stdout.split('\n') 
                                 if ' error:' in line]),
                "output": result.stdout[:200]
            }
        
        return results
    
    def test_agent_coordination(self) -> Dict[str, Any]:
        """测试Agent协调机制"""
        print("🤝 测试Agent协调机制...")
        
        # 检查是否存在agent_coordinator脚本
        coordinator_path = Path(__file__).parent / "agent_coordinator.py"
        
        if coordinator_path.exists():
            # 测试coordinator状态
            result = subprocess.run([
                "python", str(coordinator_path), "--action", "status"
            ], capture_output=True, text=True)
            
            return {
                "coordinator_available": True,
                "status_works": result.returncode == 0,
                "output": result.stdout[:300]
            }
        else:
            return {
                "coordinator_available": False,
                "note": "Agent协调器可能需要单独实现"
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        print("🧪 开始SubAgent系统集成测试...")
        print("=" * 60)
        
        try:
            self.test_results = {
                "quality_gate": self.test_quality_gate_integration(),
                "subagent_files": self.test_subagent_file_structure(), 
                "workflow": self.test_workflow_integration(),
                "mypy_strict": self.test_mypy_strict_mode(),
                "agent_coordination": self.test_agent_coordination()
            }
            
            # 生成测试报告
            self.generate_integration_report()
            
            return self.test_results
        
        finally:
            self.cleanup()
    
    def generate_integration_report(self):
        """生成集成测试报告"""
        print("\n" + "=" * 60)
        print("📊 SubAgent系统集成测试报告")
        print("=" * 60)
        
        # 1. SubAgent文件结构检查
        print("\n1. 📁 SubAgent文件结构:")
        for agent, status in self.test_results["subagent_files"].items():
            if status["exists"]:
                if status.get("valid_format", False):
                    print(f"   ✅ {agent}: 配置正确")
                else:
                    print(f"   ⚠️  {agent}: 配置格式有问题")
            else:
                print(f"   ❌ {agent}: 文件缺失")
        
        # 2. Quality Gate集成
        print("\n2. 🔍 Quality Gate集成:")
        qg = self.test_results["quality_gate"]
        if qg.get("quality_gate_available"):
            if qg.get("bad_code_blocked") and qg.get("good_code_passed"):
                print("   ✅ 质量门控正常工作，能正确识别类型问题")
            else:
                print("   ⚠️  质量门控可能存在问题")
        else:
            print("   ❌ Quality Gate不可用")
        
        # 3. MyPy严格模式
        print("\n3. 🔍 MyPy严格模式检查:")
        mypy = self.test_results["mypy_strict"]
        problem_cases = [case for case, result in mypy.items() 
                        if case != "good_types" and not result["has_errors"]]
        if not problem_cases and mypy.get("good_types", {}).get("has_errors", True):
            print("   ✅ MyPy严格模式正常工作")
        else:
            print("   ⚠️  MyPy严格模式可能配置有问题")
            for case in problem_cases:
                print(f"      - {case}应该有错误但没有检测到")
        
        # 4. 工作流集成
        print("\n4. 🔄 Workflow集成:")
        wf = self.test_results["workflow"]
        if wf.get("workflow_available") and wf.get("status_works"):
            print("   ✅ Workflow系统可用")
        else:
            print("   ⚠️  Workflow系统可能有问题")
        
        # 5. Agent协调
        print("\n5. 🤝 Agent协调:")
        coord = self.test_results["agent_coordination"]
        if coord.get("coordinator_available"):
            print("   ✅ Agent协调器可用")
        else:
            print("   ⚠️  Agent协调器需要进一步实现")
        
        # 总结
        print("\n" + "=" * 60)
        
        # 计算通过率
        all_checks = []
        
        # SubAgent文件检查
        subagent_valid = all(
            status.get("valid_format", False) if status.get("exists") else False
            for status in self.test_results["subagent_files"].values()
        )
        all_checks.append(subagent_valid)
        
        # Quality Gate检查
        qg_valid = (qg.get("quality_gate_available", False) and 
                   qg.get("bad_code_blocked", False) and 
                   qg.get("good_code_passed", False))
        all_checks.append(qg_valid)
        
        # MyPy检查
        mypy_valid = (len(problem_cases) == 0 and 
                     not mypy.get("good_types", {}).get("has_errors", True))
        all_checks.append(mypy_valid)
        
        # Workflow检查
        wf_valid = (wf.get("workflow_available", False) and 
                   wf.get("status_works", False))
        all_checks.append(wf_valid)
        
        passed_count = sum(all_checks)
        total_count = len(all_checks)
        pass_rate = (passed_count / total_count) * 100
        
        if pass_rate >= 75:
            print(f"✅ 集成测试通过率: {pass_rate:.1f}% ({passed_count}/{total_count})")
            print("🎯 SubAgent系统基本准备就绪，可以投入使用")
        else:
            print(f"⚠️  集成测试通过率: {pass_rate:.1f}% ({passed_count}/{total_count})")
            print("🔧 需要修复一些集成问题才能完全投入使用")
        
        print("=" * 60)


def main():
    """主函数"""
    tester = SubAgentIntegrationTest()
    results = tester.run_all_tests()
    
    # 保存测试结果
    results_file = Path(__file__).parent / "subagent_integration_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 测试结果已保存到: {results_file}")


if __name__ == "__main__":
    main()