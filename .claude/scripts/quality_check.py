#!/usr/bin/env python3
"""
质量门控检查脚本 - Reddit Signal Scanner

基于Linus Torvalds的严格代码质量标准，对文件修改进行自动化质检。
在Edit/Write工具执行前通过Claude Code Hooks自动触发。

使用方式:
    python quality_check.py <file_path> [--strict]

返回值:
    0: 检查通过，允许继续操作
    1: 发现严重问题，阻止操作
    2: 警告级问题，允许继续但输出警告
"""

import sys
import json
import subprocess
import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class QualityCheck:
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.issues = []
        self.warnings = []
        
    def check_file(self, file_path: str) -> int:
        """执行文件质量检查"""
        if not os.path.exists(file_path):
            return 0  # 新文件，跳过检查
            
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.py':
            return self._check_python_file(file_path)
        elif file_ext in ['.ts', '.tsx', '.js', '.jsx']:
            return self._check_typescript_file(file_path)
        elif file_ext == '.yml' or file_ext == '.yaml':
            return self._check_yaml_file(file_path)
        else:
            return self._check_generic_file(file_path)
    
    def _check_python_file(self, file_path: str) -> int:
        """Python文件特定检查"""
        print(f"🐍 检查Python文件: {file_path}")
        
        # 语法检查
        if not self._check_python_syntax(file_path):
            self.issues.append(f"语法错误: {file_path}")
            return 1
            
        # 代码风格检查 (flake8)
        flake8_issues = self._run_flake8(file_path)
        if flake8_issues:
            if any('E9' in issue or 'F8' in issue for issue in flake8_issues):
                # 严重语法错误
                self.issues.extend(flake8_issues)
                return 1
            else:
                # 风格问题
                self.warnings.extend(flake8_issues)
        
        # 类型检查 (mypy)
        mypy_issues = self._run_mypy(file_path)  
        if mypy_issues:
            self.warnings.extend(mypy_issues)
            
        # Linus风格检查
        linus_issues = self._check_linus_style(file_path)
        if linus_issues:
            self.warnings.extend(linus_issues)
            
        return 2 if self.warnings else 0
    
    def _check_typescript_file(self, file_path: str) -> int:
        """TypeScript文件检查"""
        print(f"📘 检查TypeScript文件: {file_path}")
        
        # ESLint检查
        eslint_issues = self._run_eslint(file_path)
        if eslint_issues:
            severe_issues = [i for i in eslint_issues if 'error' in i.lower()]
            if severe_issues:
                self.issues.extend(severe_issues)
                return 1
            else:
                self.warnings.extend(eslint_issues)
        
        # TypeScript编译检查
        tsc_issues = self._run_tsc_check(file_path)
        if tsc_issues:
            self.issues.extend(tsc_issues)
            return 1
            
        return 2 if self.warnings else 0
    
    def _check_yaml_file(self, file_path: str) -> int:
        """YAML配置文件检查"""
        print(f"⚙️ 检查YAML文件: {file_path}")
        
        try:
            import yaml
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.issues.append(f"YAML语法错误: {e}")
            return 1
        except Exception as e:
            self.issues.append(f"文件读取错误: {e}")
            return 1
            
        return 0
    
    def _check_generic_file(self, file_path: str) -> int:
        """通用文件检查"""
        print(f"📄 检查通用文件: {file_path}")
        
        # 检查文件大小 (>10MB可能有问题)
        if os.path.getsize(file_path) > 10 * 1024 * 1024:
            self.warnings.append(f"文件过大 (>10MB): {file_path}")
            
        # 检查二进制文件误提交
        if self._is_binary_file(file_path):
            self.warnings.append(f"二进制文件，建议检查是否应该提交: {file_path}")
            
        return 2 if self.warnings else 0
    
    def _check_python_syntax(self, file_path: str) -> bool:
        """检查Python语法"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            return True
        except SyntaxError as e:
            print(f"❌ Python语法错误 ({file_path}:{e.lineno}): {e.msg}")
            return False
        except Exception as e:
            print(f"⚠️ 文件读取问题: {e}")
            return False
    
    def _run_flake8(self, file_path: str) -> List[str]:
        """运行flake8代码风格检查"""
        try:
            result = subprocess.run(
                ['flake8', '--max-line-length=88', '--extend-ignore=E203,W503', file_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # flake8未安装或超时，跳过
        return []
    
    def _run_mypy(self, file_path: str) -> List[str]:
        """运行mypy类型检查"""
        try:
            result = subprocess.run(
                ['mypy', '--ignore-missing-imports', file_path],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # mypy未安装或超时，跳过
        return []
        
    def _run_eslint(self, file_path: str) -> List[str]:
        """运行ESLint检查"""
        try:
            result = subprocess.run(
                ['npx', 'eslint', file_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []
    
    def _run_tsc_check(self, file_path: str) -> List[str]:
        """运行TypeScript编译检查"""
        try:
            result = subprocess.run(
                ['npx', 'tsc', '--noEmit', file_path],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return result.stderr.strip().split('\n') if result.stderr.strip() else []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []
    
    def _check_linus_style(self, file_path: str) -> List[str]:
        """Linus风格检查"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines, 1):
                # 检查缩进深度 (>3层警告)
                indent_level = (len(line) - len(line.lstrip())) // 4
                if indent_level > 3:
                    issues.append(f"行{i}: 缩进过深 (>{3}层), 考虑重构函数")
                
                # 检查行长度 (>120字符警告)
                if len(line.rstrip()) > 120:
                    issues.append(f"行{i}: 行过长 ({len(line.rstrip())}字符)")
                
                # 检查硬编码密钥/密码模式
                if re.search(r'(password|secret|key|token)\s*=\s*["\'][^"\']+["\']', line, re.IGNORECASE):
                    issues.append(f"行{i}: 可能的硬编码密钥，请使用环境变量")
                    
        except Exception:
            pass  # 文件读取问题，跳过风格检查
            
        return issues
    
    def _is_binary_file(self, file_path: str) -> bool:
        """检查是否为二进制文件"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
            return b'\0' in chunk
        except Exception:
            return False
    
    def generate_report(self) -> dict:
        """生成检查报告"""
        return {
            'status': 'fail' if self.issues else ('warn' if self.warnings else 'pass'),
            'issues': self.issues,
            'warnings': self.warnings,
            'summary': self._generate_summary()
        }
    
    def _generate_summary(self) -> str:
        """生成总结"""
        if self.issues:
            return f"❌ 质量检查失败: {len(self.issues)}个严重问题"
        elif self.warnings:
            return f"⚠️ 质量检查通过但有警告: {len(self.warnings)}个建议"
        else:
            return "✅ 质量检查通过"

def main():
    """主函数 - Claude Code Hook入口点"""
    if len(sys.argv) < 2:
        print("用法: python quality_check.py <file_path> [--strict]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    strict_mode = '--strict' in sys.argv
    
    # 检查是否跳过质量检查
    if os.getenv('QUALITY_GATE_SKIP') == '1':
        print("⚠️ 质量检查已跳过 (QUALITY_GATE_SKIP=1)")
        sys.exit(0)
    
    checker = QualityCheck(strict_mode)
    result_code = checker.check_file(file_path)
    
    # 生成报告
    report = checker.generate_report()
    
    # 输出结果
    print(f"\n{report['summary']}")
    
    if report['issues']:
        print("\n❌ 严重问题:")
        for issue in report['issues']:
            print(f"  • {issue}")
            
    if report['warnings']:
        print("\n⚠️ 警告:")
        for warning in report['warnings']:
            print(f"  • {warning}")
    
    # 严格模式下，警告也阻止操作
    if strict_mode and (report['issues'] or report['warnings']):
        result_code = 1
    
    # 记录日志
    if os.getenv('QUALITY_GATE_LOG') == '1':
        log_path = '.claude/logs/quality-gate.log'
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(f"{file_path}: {report['status']} - {report['summary']}\n")
    
    # 如果是Claude Code Hook调用，输出JSON格式
    if os.getenv('CLAUDE_HOOK_MODE') == '1':
        hook_response = {
            'allow': result_code == 0,
            'message': report['summary'],
            'details': report
        }
        print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response)}")
    
    sys.exit(result_code)

if __name__ == '__main__':
    main()