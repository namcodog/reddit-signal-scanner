#!/usr/bin/env python3
"""
Agent系统健康诊断脚本 - Reddit Signal Scanner

快速诊断和修复Agent系统常见问题的工具脚本。

使用方式:
    python3 .claude/scripts/agent_doctor.py [--fix] [--verbose]

功能:
    --fix: 自动修复发现的问题
    --verbose: 详细输出诊断信息
"""

import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

class AgentDoctor:
    def __init__(self, auto_fix: bool = False, verbose: bool = False):
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.project_root = Path.cwd()
        self.claude_dir = self.project_root / '.claude'
        
        self.issues = []
        self.fixes_applied = []
        self.warnings = []
        
    def diagnose_system(self) -> bool:
        """全面诊断Agent系统健康状况"""
        print("🔍 Agent系统健康诊断开始...")
        
        all_healthy = True
        
        # 1. 检查目录结构
        if not self._check_directory_structure():
            all_healthy = False
            
        # 2. 检查配置文件
        if not self._check_configuration_files():
            all_healthy = False
            
        # 3. 检查脚本文件
        if not self._check_script_files():
            all_healthy = False
            
        # 4. 检查依赖安装
        if not self._check_dependencies():
            all_healthy = False
            
        # 5. 检查权限设置
        if not self._check_permissions():
            all_healthy = False
            
        # 6. 功能性测试
        if not self._run_functional_tests():
            all_healthy = False
            
        return all_healthy
    
    def _check_directory_structure(self) -> bool:
        """检查目录结构"""
        if self.verbose:
            print("📁 检查目录结构...")
            
        required_dirs = [
            self.claude_dir,
            self.claude_dir / 'agents',
            self.claude_dir / 'scripts',
            self.claude_dir / 'logs'
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing_dirs.append(str(dir_path))
                if self.auto_fix:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.fixes_applied.append(f"创建目录: {dir_path}")
        
        if missing_dirs and not self.auto_fix:
            self.issues.append(f"缺少目录: {', '.join(missing_dirs)}")
            return False
            
        return True
    
    def _check_configuration_files(self) -> bool:
        """检查配置文件"""
        if self.verbose:
            print("⚙️ 检查配置文件...")
            
        settings_file = self.claude_dir / 'settings.json'
        
        if not settings_file.exists():
            self.issues.append("缺少settings.json配置文件")
            if self.auto_fix:
                self._create_default_settings()
                self.fixes_applied.append("创建默认settings.json")
            return False
        
        # 验证JSON格式
        try:
            with open(settings_file, 'r') as f:
                config = json.load(f)
                
            # 检查必需的Hook配置
            required_hooks = ['PreToolUse', 'PostToolUse', 'Stop']
            for hook in required_hooks:
                if hook not in config:
                    self.warnings.append(f"settings.json缺少{hook}配置")
                    
        except json.JSONDecodeError as e:
            self.issues.append(f"settings.json格式错误: {e}")
            return False
            
        return True
    
    def _check_script_files(self) -> bool:
        """检查脚本文件"""
        if self.verbose:
            print("📜 检查脚本文件...")
            
        required_scripts = [
            'quality_check.py',
            'signal_validate.py', 
            'perf_metrics.py',
            'config_sync.py',
            'linus_architect.py',
            'git_workflow.py'
        ]
        
        scripts_dir = self.claude_dir / 'scripts'
        missing_scripts = []
        
        for script_name in required_scripts:
            script_path = scripts_dir / script_name
            if not script_path.exists():
                missing_scripts.append(script_name)
            else:
                # 检查脚本语法
                try:
                    subprocess.run([
                        'python3', '-m', 'py_compile', str(script_path)
                    ], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    self.issues.append(f"脚本语法错误: {script_name}")
        
        if missing_scripts:
            self.issues.append(f"缺少脚本文件: {', '.join(missing_scripts)}")
            return False
            
        return True
    
    def _check_dependencies(self) -> bool:
        """检查Python依赖"""
        if self.verbose:
            print("📦 检查Python依赖...")
            
        required_packages = ['psutil', 'pyyaml', 'requests']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.issues.append(f"缺少Python包: {', '.join(missing_packages)}")
            if self.auto_fix:
                try:
                    subprocess.run([
                        'pip', 'install'] + missing_packages, check=True
                    )
                    self.fixes_applied.append(f"安装依赖: {', '.join(missing_packages)}")
                except subprocess.CalledProcessError as e:
                    self.issues.append(f"自动安装依赖失败: {e}")
                    return False
            else:
                return False
                
        return True
    
    def _check_permissions(self) -> bool:
        """检查文件权限"""
        if self.verbose:
            print("🔒 检查文件权限...")
            
        scripts_dir = self.claude_dir / 'scripts'
        permission_issues = []
        
        for script_file in scripts_dir.glob('*.py'):
            if not os.access(script_file, os.X_OK):
                permission_issues.append(str(script_file))
                if self.auto_fix:
                    script_file.chmod(0o755)
                    self.fixes_applied.append(f"修复权限: {script_file.name}")
        
        if permission_issues and not self.auto_fix:
            self.issues.append(f"脚本无执行权限: {', '.join(permission_issues)}")
            return False
            
        return True
    
    def _run_functional_tests(self) -> bool:
        """运行功能性测试"""
        if self.verbose:
            print("🧪 运行功能性测试...")
            
        test_results = []
        scripts_dir = self.claude_dir / 'scripts'
        
        # 测试质量检查脚本
        quality_script = scripts_dir / 'quality_check.py'
        if quality_script.exists():
            try:
                result = subprocess.run([
                    'python3', str(quality_script), str(quality_script)
                ], capture_output=True, timeout=10)
                test_results.append(('quality_check', result.returncode == 0))
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                test_results.append(('quality_check', False))
        
        # 测试性能监控脚本
        perf_script = scripts_dir / 'perf_metrics.py'
        if perf_script.exists():
            try:
                result = subprocess.run([
                    'python3', str(perf_script), '--system-check'
                ], capture_output=True, timeout=15)
                # 性能脚本可能返回警告(2)，这是正常的
                test_results.append(('perf_metrics', result.returncode in [0, 2]))
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                test_results.append(('perf_metrics', False))
        
        # 分析测试结果
        failed_tests = [name for name, success in test_results if not success]
        if failed_tests:
            self.warnings.append(f"功能测试失败: {', '.join(failed_tests)}")
        
        return len(failed_tests) == 0
    
    def _create_default_settings(self):
        """创建默认settings.json"""
        default_settings = {
            "PreToolUse": [
                {
                    "script": "$CLAUDE_PROJECT_DIR/.claude/scripts/quality_check.py",
                    "matchers": [
                        {"tool": "Edit"},
                        {"tool": "Write"},
                        {"tool": "MultiEdit"}
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "script": "$CLAUDE_PROJECT_DIR/.claude/scripts/perf_metrics.py",
                    "matchers": [
                        {"tool": "WebFetch"},
                        {"tool": "Bash"}
                    ]
                }
            ],
            "Stop": [
                {
                    "script": "$CLAUDE_PROJECT_DIR/.claude/scripts/config_sync.py"
                }
            ]
        }
        
        settings_file = self.claude_dir / 'settings.json'
        with open(settings_file, 'w') as f:
            json.dump(default_settings, f, indent=2)
    
    def generate_report(self) -> str:
        """生成诊断报告"""
        report = []
        
        # 标题
        report.append("🏥 Agent系统健康诊断报告")
        report.append("=" * 50)
        
        # 总体状态
        if not self.issues:
            report.append("✅ 系统状态: 健康")
        else:
            report.append("❌ 系统状态: 需要修复")
        
        report.append("")
        
        # 严重问题
        if self.issues:
            report.append("🔴 需要修复的问题:")
            for i, issue in enumerate(self.issues, 1):
                report.append(f"  {i}. {issue}")
            report.append("")
        
        # 警告
        if self.warnings:
            report.append("🟡 警告信息:")
            for i, warning in enumerate(self.warnings, 1):
                report.append(f"  {i}. {warning}")
            report.append("")
        
        # 自动修复记录
        if self.fixes_applied:
            report.append("🔧 已自动修复:")
            for i, fix in enumerate(self.fixes_applied, 1):
                report.append(f"  {i}. {fix}")
            report.append("")
        
        # 建议操作
        if self.issues and not self.auto_fix:
            report.append("💡 建议操作:")
            report.append("  1. 运行 'python3 .claude/scripts/agent_doctor.py --fix' 自动修复")
            report.append("  2. 手动安装缺失的依赖: pip install psutil pyyaml requests")
            report.append("  3. 检查文件权限: chmod +x .claude/scripts/*.py")
            report.append("")
        
        # 系统信息
        report.append("📋 系统信息:")
        report.append(f"  项目根目录: {self.project_root}")
        report.append(f"  Claude目录: {self.claude_dir}")
        report.append(f"  Python版本: {sys.version.split()[0]}")
        
        return "\n".join(report)

def main():
    """主函数"""
    auto_fix = '--fix' in sys.argv
    verbose = '--verbose' in sys.argv
    
    doctor = AgentDoctor(auto_fix=auto_fix, verbose=verbose)
    
    print("🩺 Agent系统诊断工具")
    print("-" * 30)
    
    # 运行诊断
    is_healthy = doctor.diagnose_system()
    
    # 生成并打印报告
    report = doctor.generate_report()
    print(report)
    
    # 返回状态码
    if is_healthy and not doctor.warnings:
        sys.exit(0)  # 完全健康
    elif is_healthy:
        sys.exit(2)  # 有警告但可运行
    else:
        sys.exit(1)  # 有严重问题

if __name__ == '__main__':
    main()