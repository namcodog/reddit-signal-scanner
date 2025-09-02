#!/usr/bin/env python3
"""
质量门控检查脚本 - Reddit Signal Scanner

基于Linus Torvalds的严格代码质量标准，对文件修改进行自动化质检。
在Edit/Write工具执行前通过Claude Code Hooks自动触发。

使用方式:
    python quality_check.py <file_path> [--model claude-3-haiku] [--strict]

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
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 导入Agent基类
from agent_base import AgentBase

class QualityGateAgent(AgentBase):
    """质量门控Agent - 基于AgentBase的实现，集成问题跟踪系统"""
    
    def __init__(self):
        super().__init__('quality-gate')
        self.checker = QualityCheck()
        
        # 集成问题跟踪器
        try:
            from .issue_tracker import IssueTracker
            self.issue_tracker = IssueTracker()
        except ImportError:
            self.logger.warning("无法导入问题跟踪器，将跳过问题记录功能")
            self.issue_tracker = None
    
    def _add_custom_args(self, parser: argparse.ArgumentParser):
        """添加质量检查特定的参数"""
        parser.add_argument('file_path', nargs='?', help='要检查的文件路径')
        parser.add_argument('--all', action='store_true', help='检查所有文件')
    
    def execute(self, args: argparse.Namespace) -> int:
        """执行质量检查"""
        start_time = time.time()
        
        # 设置严格模式
        self.checker.strict_mode = args.strict
        
        try:
            if args.all:
                # 检查所有相关文件
                result = self._check_all_files()
            elif args.file_path:
                # 检查指定文件
                result = self.checker.check_file(args.file_path)
            else:
                # 从环境变量获取文件路径 (Hook模式)
                file_path = os.environ.get('CLAUDE_TOOL_FILE_PATH')
                if file_path:
                    result = self.checker.check_file(file_path)
                else:
                    self.logger.error("未指定要检查的文件")
                    return 1
            
            # 记录性能指标
            execution_time = time.time() - start_time
            self.report_metrics({
                'execution_time': execution_time,
                'files_checked': 1 if args.file_path else 0,
                'issues_found': len(self.checker.issues),
                'warnings_found': len(self.checker.warnings)
            })
            
            # 输出结果
            self._output_results()
            
            return result
            
        except Exception as e:
            self.logger.error(f"质量检查失败: {e}")
            return 1
    
    def _check_all_files(self) -> int:
        """检查所有项目文件"""
        files_to_check = []
        
        # Python文件
        files_to_check.extend(Path('.').rglob('*.py'))
        # TypeScript文件  
        files_to_check.extend(Path('.').rglob('*.ts'))
        files_to_check.extend(Path('.').rglob('*.tsx'))
        # YAML配置文件
        files_to_check.extend(Path('.').rglob('*.yaml'))
        files_to_check.extend(Path('.').rglob('*.yml'))
        
        # 过滤掉不需要检查的文件
        excludes = ['.git', 'node_modules', '__pycache__', '.venv', 'venv']
        files_to_check = [
            f for f in files_to_check 
            if not any(exclude in str(f) for exclude in excludes)
        ]
        
        self.logger.info(f"检查 {len(files_to_check)} 个文件")
        
        overall_result = 0
        for file_path in files_to_check:
            result = self.checker.check_file(str(file_path))
            if result > overall_result:
                overall_result = result
                
        return overall_result
    
    def _output_results(self):
        """输出检查结果"""
        if self.checker.issues:
            print("\n❌ 发现严重问题:")
            for issue in self.checker.issues:
                print(f"  • {issue}")
                
        if self.checker.warnings:
            print("\n⚠️ 发现警告:")
            for warning in self.checker.warnings:
                print(f"  • {warning}")
                
        if not self.checker.issues and not self.checker.warnings:
            print("✅ 质量检查通过")

class QualityCheck:
    """质量检查器 - 集成问题跟踪和强制修复循环"""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.issues = []
        self.warnings = []
        self.current_task_id = None  # 当前检查的任务ID
        self.require_fix_verification = True  # 是否要求修复验证
        
        # 集成问题跟踪器
        try:
            from .issue_tracker import IssueTracker
            self.issue_tracker = IssueTracker()
        except ImportError:
            print("⚠️ 无法导入问题跟踪器")
            self.issue_tracker = None
        
    def check_file(self, file_path: str, task_id: str = None) -> int:
        """执行文件质量检查 - 增强版，集成问题跟踪"""
        if not os.path.exists(file_path):
            return 0  # 新文件，跳过检查
        
        self.current_task_id = task_id or self._extract_task_id_from_path(file_path)
        
        print(f"🔍 开始质量检查: {file_path}")
        if self.current_task_id:
            print(f"📋 关联任务: {self.current_task_id}")
        
        # 检查是否有未解决的问题
        if self.require_fix_verification and self.issue_tracker and self.current_task_id:
            blocking_issues = self.issue_tracker.get_blocking_issues(self.current_task_id)
            if blocking_issues:
                return self._handle_existing_issues(file_path, blocking_issues)
        
        # 执行具体的文件类型检查
        file_ext = Path(file_path).suffix.lower()
        result_code = 0
        
        if file_ext == '.py':
            result_code = self._check_python_file(file_path)
        elif file_ext in ['.ts', '.tsx', '.js', '.jsx']:
            result_code = self._check_typescript_file(file_path)
        elif file_ext == '.yml' or file_ext == '.yaml':
            result_code = self._check_yaml_file(file_path)
        else:
            result_code = self._check_generic_file(file_path)
        
        # 记录新发现的问题
        if result_code > 0:
            self._record_issues_to_tracker(file_path)
        
        return result_code
    
    def _extract_task_id_from_path(self, file_path: str) -> str:
        """从文件路径或环境变量中提取任务ID"""
        # 尝试从环境变量获取
        task_id = os.environ.get('CURRENT_TASK_ID')
        if task_id:
            return task_id
        
        # 尝试从文件路径推断
        path_parts = Path(file_path).parts
        for part in path_parts:
            if part.startswith('prd') and '-' in part:
                return part
        
        # 默认返回通用任务ID
        return "quality-check"
    
    def _handle_existing_issues(self, file_path: str, blocking_issues: list) -> int:
        """处理已存在的阻塞性问题"""
        print(f"🔴 发现 {len(blocking_issues)} 个阻塞性问题需要先解决:")
        
        for issue in blocking_issues:
            status_icon = "🔥" if issue.severity.value == "critical" else "⚠️"
            print(f"  {status_icon} [{issue.severity.value.upper()}] {issue.title}")
            print(f"      文件: {issue.file_path}")
            if issue.line_number:
                print(f"      行号: {issue.line_number}")
            print(f"      描述: {issue.description}")
            print()
        
        print("⛔ 质量检查被阻塞 - 请先修复上述问题")
        print("💡 修复后可以重新运行质量检查")
        print("🔧 或使用 python issue_tracker.py update <issue_id> fixed 来标记问题已修复")
        
        return 1  # 返回错误码，阻塞操作
    
    def _record_issues_to_tracker(self, file_path: str) -> None:
        """将发现的问题记录到跟踪系统"""
        if not self.issue_tracker or not self.current_task_id:
            return
        
        # 记录严重问题
        for issue in self.issues:
            self.issue_tracker.add_issue(
                task_id=self.current_task_id,
                agent_name="quality-gate",
                severity="high",  # 严重问题
                title=f"质量检查失败: {issue}",
                description=issue,
                file_path=file_path,
                metadata={'check_type': 'quality_gate', 'auto_generated': True}
            )
        
        # 记录警告
        for warning in self.warnings:
            self.issue_tracker.add_issue(
                task_id=self.current_task_id,
                agent_name="quality-gate", 
                severity="medium",  # 警告级别
                title=f"质量建议: {warning}",
                description=warning,
                file_path=file_path,
                metadata={'check_type': 'quality_gate', 'auto_generated': True}
            )
    
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
    
    def verify_fixes(self, file_path: str, task_id: str = None) -> int:
        """验证问题修复 - 重新检查文件并更新问题状态"""
        if not self.issue_tracker:
            print("⚠️ 问题跟踪器不可用，跳过修复验证")
            return self.check_file(file_path, task_id)
        
        task_id = task_id or self.current_task_id or self._extract_task_id_from_path(file_path)
        
        print(f"🔄 验证修复: {file_path}")
        print(f"📋 任务ID: {task_id}")
        
        # 获取该任务的所有问题
        old_issues = self.issue_tracker.get_task_issues(task_id)
        old_blocking_count = len([i for i in old_issues if i.is_blocking()])
        
        print(f"📊 修复前: {old_blocking_count} 个阻塞性问题")
        
        # 临时禁用修复验证，避免递归
        old_require_fix = self.require_fix_verification
        self.require_fix_verification = False
        
        try:
            # 重新检查文件
            result_code = self.check_file(file_path, task_id)
            
            # 检查修复效果
            new_issues = self.issue_tracker.get_task_issues(task_id)
            new_blocking_count = len([i for i in new_issues if i.is_blocking()])
            
            print(f"📊 修复后: {new_blocking_count} 个阻塞性问题")
            
            if new_blocking_count < old_blocking_count:
                fixed_count = old_blocking_count - new_blocking_count
                print(f"✅ 修复了 {fixed_count} 个问题")
                
                # 标记已修复的问题
                self._mark_fixed_issues(old_issues, new_issues)
                
            elif new_blocking_count == 0:
                print("🎉 所有阻塞性问题已解决!")
                
                # 标记所有旧问题为已验证
                for issue in old_issues:
                    if issue.is_blocking():
                        self.issue_tracker.resolve_issue(issue.id, force=True)
                        
            else:
                print("⚠️ 仍有问题需要解决")
            
            return result_code
            
        finally:
            # 恢复修复验证设置
            self.require_fix_verification = old_require_fix
    
    def _mark_fixed_issues(self, old_issues: list, new_issues: list) -> None:
        """标记已修复的问题"""
        old_issue_keys = {self._issue_key(i) for i in old_issues if i.is_blocking()}
        new_issue_keys = {self._issue_key(i) for i in new_issues if i.is_blocking()}
        
        fixed_keys = old_issue_keys - new_issue_keys
        
        for issue in old_issues:
            if issue.is_blocking() and self._issue_key(issue) in fixed_keys:
                self.issue_tracker.update_issue_status(issue.id, 'verified')
                print(f"  ✅ 问题已修复: {issue.title}")
    
    def _issue_key(self, issue) -> str:
        """生成问题的唯一键，用于比较"""
        return f"{issue.file_path}:{issue.line_number}:{issue.title}"
    
    def force_continue(self, file_path: str, task_id: str = None, reason: str = "") -> int:
        """强制跳过阻塞性问题（紧急情况使用）"""
        if not self.issue_tracker:
            return 0
        
        task_id = task_id or self.current_task_id or self._extract_task_id_from_path(file_path)
        blocking_issues = self.issue_tracker.get_blocking_issues(task_id)
        
        if not blocking_issues:
            print("✅ 无阻塞性问题")
            return 0
        
        print(f"⚠️ 强制跳过 {len(blocking_issues)} 个阻塞性问题")
        if reason:
            print(f"原因: {reason}")
        
        ignored_count = 0
        for issue in blocking_issues:
            if issue.can_ignore():
                self.issue_tracker.ignore_issue(issue.id, reason or "用户强制跳过")
                ignored_count += 1
            else:
                print(f"❌ 无法忽略严重问题: {issue.title}")
        
        print(f"✅ 忽略了 {ignored_count} 个问题")
        return 0 if ignored_count == len(blocking_issues) else 1
    
    def generate_report(self) -> dict:
        """生成检查报告"""
        report = {
            'status': 'fail' if self.issues else ('warn' if self.warnings else 'pass'),
            'issues': self.issues,
            'warnings': self.warnings,
            'summary': self._generate_summary(),
            'task_id': self.current_task_id
        }
        
        # 添加问题跟踪信息
        if self.issue_tracker and self.current_task_id:
            blocking_issues = self.issue_tracker.get_blocking_issues(self.current_task_id)
            report['blocking_issues_count'] = len(blocking_issues)
            report['has_blocking_issues'] = len(blocking_issues) > 0
        
        return report
    
    def _generate_summary(self) -> str:
        """生成总结"""
        if self.issues:
            return f"❌ 质量检查失败: {len(self.issues)}个严重问题"
        elif self.warnings:
            return f"⚠️ 质量检查通过但有警告: {len(self.warnings)}个建议"
        else:
            return "✅ 质量检查通过"

def main():
    """主函数 - 支持多种操作模式的入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description='质量门控系统 - 增强版')
    parser.add_argument('file_path', nargs='?', help='要检查的文件路径')
    parser.add_argument('--strict', action='store_true', help='严格模式')
    parser.add_argument('--task-id', help='关联的任务ID')
    
    # Agent协调器传递的额外参数
    parser.add_argument('--task-content', help='任务内容')
    parser.add_argument('--task-type', help='任务类型')
    parser.add_argument('--priority', help='优先级')
    parser.add_argument('--involves-code', action='store_true', help='涉及代码')
    parser.add_argument('--involves-data', action='store_true', help='涉及数据')
    parser.add_argument('--involves-architecture', action='store_true', help='涉及架构')
    parser.add_argument('--has-errors', action='store_true', help='有错误')
    parser.add_argument('--error-type', help='错误类型')
    
    # 操作模式
    parser.add_argument('--verify-fixes', action='store_true', help='验证问题修复')
    parser.add_argument('--force-continue', action='store_true', help='强制跳过阻塞性问题')
    parser.add_argument('--reason', help='强制继续的原因')
    parser.add_argument('--check-blocking', action='store_true', help='只检查是否有阻塞性问题')
    
    # 兼容性参数
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('-'):
        # 兼容旧的调用方式
        args = parser.parse_args()
    elif len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    else:
        args = parser.parse_args()
    
    # 检查是否跳过质量检查
    if os.getenv('QUALITY_GATE_SKIP') == '1':
        print("⚠️ 质量检查已跳过 (QUALITY_GATE_SKIP=1)")
        sys.exit(0)
    
    # 初始化检查器
    checker = QualityCheck(strict_mode=args.strict)
    
    if not args.file_path:
        print("❌ 请指定要检查的文件路径")
        parser.print_help()
        sys.exit(1)
    
    result_code = 0
    
    try:
        if args.verify_fixes:
            # 验证修复模式
            print("🔄 验证修复模式")
            result_code = checker.verify_fixes(args.file_path, args.task_id)
            
        elif args.force_continue:
            # 强制继续模式
            print("⚠️ 强制继续模式")
            result_code = checker.force_continue(args.file_path, args.task_id, args.reason)
            if result_code == 0:
                # 强制跳过后继续正常检查
                result_code = checker.check_file(args.file_path, args.task_id)
                
        elif args.check_blocking:
            # 只检查阻塞性问题
            print("🔍 检查阻塞性问题")
            if checker.issue_tracker:
                task_id = args.task_id or checker._extract_task_id_from_path(args.file_path)
                blocking_issues = checker.issue_tracker.get_blocking_issues(task_id)
                if blocking_issues:
                    print(f"🔴 发现 {len(blocking_issues)} 个阻塞性问题")
                    result_code = 1
                else:
                    print("✅ 无阻塞性问题")
                    result_code = 0
            else:
                print("⚠️ 问题跟踪器不可用")
                result_code = 0
        else:
            # 标准检查模式
            result_code = checker.check_file(args.file_path, args.task_id)
        
        # 生成并显示报告
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
        
        # 显示问题跟踪信息
        if report.get('has_blocking_issues'):
            print(f"\n🔴 有 {report.get('blocking_issues_count', 0)} 个阻塞性问题需要解决")
            print("💡 使用 --verify-fixes 验证修复效果")
            print("🔧 使用 --force-continue 强制跳过（不推荐）")
        
        # 严格模式下，警告也阻止操作
        if args.strict and (report['issues'] or report['warnings']):
            result_code = 1
        
        # 记录日志
        if os.getenv('QUALITY_GATE_LOG') == '1':
            log_path = '.claude/logs/quality-gate.log'
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a') as f:
                timestamp = datetime.now().isoformat()
                f.write(f"{timestamp} - {args.file_path}: {report['status']} - {report['summary']}\n")
        
        # 如果是Claude Code Hook调用，输出JSON格式
        if os.getenv('CLAUDE_HOOK_MODE') == '1':
            hook_response = {
                'allow': result_code == 0,
                'message': report['summary'],
                'details': report,
                'blocking_issues': report.get('has_blocking_issues', False)
            }
            print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response)}")
        
        # 为Agent协调器输出JSON结果（最后一行）
        elif args.task_id:
            agent_result = {
                'agent': 'quality-gate',
                'status': 'completed' if result_code == 0 else 'failed',
                'task_id': args.task_id,
                'quality_result': {
                    'result_code': result_code,
                    'status': report['status'],
                    'issues_count': len(report.get('issues', [])),
                    'warnings_count': len(report.get('warnings', [])),
                    'has_blocking_issues': report.get('has_blocking_issues', False)
                },
                'suggestions': [
                    report['summary'],
                    f"发现 {len(report.get('issues', []))} 个问题",
                    f"发现 {len(report.get('warnings', []))} 个警告"
                ][:3],
                'execution_time': report.get('duration', 0.0)
            }
            print(json.dumps(agent_result, ensure_ascii=False))
    
    except KeyboardInterrupt:
        print("\n\n👋 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 质量检查执行失败: {e}")
        if os.getenv('QUALITY_GATE_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    sys.exit(result_code)

if __name__ == '__main__':
    # 使用新的Agent系统
    agent = QualityGateAgent()
    sys.exit(agent.run())