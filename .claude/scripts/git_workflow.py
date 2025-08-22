#!/usr/bin/env python3
"""
Git工作流脚本 - Reddit Signal Scanner

确保版本控制质量、分支策略执行和代码历史清晰。
通过Claude Code Hooks在git操作前后自动触发。

使用方式:
    python git_workflow.py [--pre-commit|--pre-push|--post-merge] [--commit-msg="message"]

返回值:
    0: Git工作流检查通过
    1: 发现严重问题，阻止操作
    2: 警告级问题，允许继续
"""

import sys
import os
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class GitWorkflowManager:
    def __init__(self):
        self.project_root = Path.cwd()
        self.git_dir = self.project_root / '.git'
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'workflow_status': '',
            'branch_analysis': {},
            'commit_analysis': {},
            'security_scan': {},
            'issues': [],
            'warnings': [],
            'suggestions': []
        }
        
        # Reddit Signal Scanner项目的Git策略
        self.branch_strategy = {
            'main': {'protected': True, 'desc': '生产就绪代码'},
            'develop': {'protected': False, 'desc': '开发主分支'},
            'feature/*': {'pattern': True, 'desc': '功能开发分支'},
            'hotfix/*': {'pattern': True, 'desc': '紧急修复分支'},
            'release/*': {'pattern': True, 'desc': '发布准备分支'}
        }
        
        # 提交信息规范
        self.commit_types = {
            'feat': '新功能',
            'fix': 'Bug修复', 
            'docs': '文档更新',
            'style': '代码格式化',
            'refactor': '重构代码',
            'test': '测试相关',
            'chore': '构建工具等',
            'perf': '性能优化',
            'ci': 'CI/CD相关'
        }
    
    def run_pre_commit_checks(self) -> int:
        """提交前检查"""
        print("🔍 Git提交前检查...")
        
        overall_status = 0
        
        # 1. 检查提交信息
        commit_msg_status = self._validate_commit_message()
        overall_status = max(overall_status, commit_msg_status)
        
        # 2. 扫描敏感信息
        security_status = self._scan_staged_files_for_secrets()
        overall_status = max(overall_status, security_status)
        
        # 3. 检查文件大小
        file_size_status = self._check_file_sizes()
        overall_status = max(overall_status, file_size_status)
        
        # 4. 验证分支策略
        branch_status = self._validate_current_branch()
        overall_status = max(overall_status, branch_status)
        
        self.results['workflow_status'] = 'pre_commit_completed'
        return overall_status
    
    def run_pre_push_checks(self) -> int:
        """推送前检查"""
        print("🚀 Git推送前检查...")
        
        overall_status = 0
        
        # 1. 检查分支同步状态
        sync_status = self._check_remote_sync()
        overall_status = max(overall_status, sync_status)
        
        # 2. 分析提交历史质量
        history_status = self._analyze_commit_history()
        overall_status = max(overall_status, history_status)
        
        # 3. 检查合并冲突
        conflict_status = self._check_merge_conflicts()
        overall_status = max(overall_status, conflict_status)
        
        self.results['workflow_status'] = 'pre_push_completed'
        return overall_status
    
    def run_post_merge_cleanup(self) -> int:
        """合并后清理"""
        print("🧹 Git合并后清理...")
        
        # 1. 清理已合并的分支
        self._suggest_branch_cleanup()
        
        # 2. 更新版本标签
        self._suggest_version_tagging()
        
        # 3. 更新项目文档
        self._check_documentation_updates()
        
        self.results['workflow_status'] = 'post_merge_completed'
        return 0
    
    def _validate_commit_message(self, commit_message: Optional[str] = None) -> int:
        """验证提交信息格式"""
        if not commit_message:
            # 获取最新的提交信息
            try:
                result = subprocess.run(
                    ['git', 'log', '-1', '--pretty=format:%s'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    commit_message = result.stdout.strip()
                else:
                    return 0  # 无法获取提交信息，跳过检查
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return 0
        
        if not commit_message:
            return 0
        
        # 检查提交信息格式
        # 格式: type(scope): description
        pattern = r'^(feat|fix|docs|style|refactor|test|chore|perf|ci)(\(.+\))?: .{1,50}'
        
        if not re.match(pattern, commit_message):
            self.results['issues'].append(
                f"提交信息格式错误: '{commit_message}'"
            )
            self.results['suggestions'].append(
                "正确格式: type(scope): description\n"
                "示例: feat(api): 添加Reddit信号验证端点"
            )
            return 1
        
        # 检查描述质量
        commit_type = commit_message.split(':')[0]
        description = commit_message.split(':', 1)[1].strip()
        
        if len(description) < 5:
            self.results['warnings'].append("提交描述过于简短，建议更详细说明")
            return 2
        
        if description.lower() in ['bug fix', 'fix bug', 'update', 'change']:
            self.results['warnings'].append("提交描述过于模糊，建议说明具体改动")
            return 2
        
        self.results['commit_analysis']['message_quality'] = 'good'
        return 0
    
    def _scan_staged_files_for_secrets(self) -> int:
        """扫描暂存文件中的敏感信息"""
        try:
            # 获取暂存的文件
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return 0  # 无暂存文件
            
            staged_files = result.stdout.strip().split('\n')
            if not staged_files or staged_files == ['']:
                return 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        security_issues = []
        
        for file_path in staged_files:
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查各种敏感信息模式
                secret_patterns = [
                    (r'password\s*[=:]\s*["\'][^"\']{6,}["\']', 'hardcoded password'),
                    (r'api[_\-]?key\s*[=:]\s*["\'][^"\']{10,}["\']', 'API key'),
                    (r'secret\s*[=:]\s*["\'][^"\']{10,}["\']', 'secret token'),
                    (r'token\s*[=:]\s*["\'][^"\']{15,}["\']', 'access token'),
                    (r'-----BEGIN.*PRIVATE KEY-----', 'private key'),
                    (r'sk-[a-zA-Z0-9]{32,}', 'OpenAI secret key'),
                    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub personal access token'),
                    (r'postgresql://[^:]+:[^@]+@', 'database connection string'),
                    (r'mongodb://[^:]+:[^@]+@', 'MongoDB connection string')
                ]
                
                for pattern, desc in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        security_issues.append(f"{file_path}: 检测到{desc}")
                
                # 检查可疑的配置文件内容
                if file_path.endswith(('.env', '.ini', '.conf')):
                    if 'localhost' not in content and any(
                        keyword in content.lower() 
                        for keyword in ['password=', 'secret=', 'key=']
                    ):
                        security_issues.append(f"{file_path}: 配置文件可能包含敏感信息")
                
            except Exception:
                continue  # 跳过无法读取的文件
        
        if security_issues:
            self.results['issues'].extend(security_issues)
            self.results['security_scan']['secrets_found'] = len(security_issues)
            return 1
        
        self.results['security_scan']['secrets_found'] = 0
        return 0
    
    def _check_file_sizes(self) -> int:
        """检查文件大小，防止大文件误提交"""
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                return 0
            
            staged_files = result.stdout.strip().split('\n')
            if not staged_files or staged_files == ['']:
                return 0
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        large_files = []
        very_large_files = []
        
        for file_path in staged_files:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                # 1MB = 1024*1024 bytes
                if file_size > 10 * 1024 * 1024:  # >10MB
                    very_large_files.append((file_path, file_size))
                elif file_size > 1024 * 1024:  # >1MB
                    large_files.append((file_path, file_size))
        
        if very_large_files:
            for file_path, size in very_large_files:
                self.results['issues'].append(
                    f"文件过大: {file_path} ({size / 1024 / 1024:.1f}MB)"
                )
            self.results['suggestions'].append(
                "建议使用Git LFS处理大文件，或将其添加到.gitignore"
            )
            return 1
        
        if large_files:
            for file_path, size in large_files:
                self.results['warnings'].append(
                    f"文件较大: {file_path} ({size / 1024 / 1024:.1f}MB)"
                )
            return 2
        
        return 0
    
    def _validate_current_branch(self) -> int:
        """验证当前分支策略"""
        try:
            # 获取当前分支
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                return 0
            
            current_branch = result.stdout.strip()
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        if not current_branch:
            return 0
        
        # 检查分支命名规范
        valid_branch = False
        
        # 检查保护分支
        if current_branch in ['main', 'master']:
            self.results['warnings'].append(
                f"直接在{current_branch}分支提交，建议使用feature分支"
            )
            return 2
        
        # 检查分支命名模式
        valid_patterns = [
            r'^develop$',
            r'^feature/.+',
            r'^fix/.+', 
            r'^hotfix/.+',
            r'^release/.+',
            r'^chore/.+'
        ]
        
        for pattern in valid_patterns:
            if re.match(pattern, current_branch):
                valid_branch = True
                break
        
        if not valid_branch:
            self.results['warnings'].append(
                f"分支名'{current_branch}'不符合规范，建议格式: type/description"
            )
            self.results['suggestions'].append(
                "推荐分支名格式:\n"
                "- feature/new-feature-name\n"
                "- fix/bug-description\n" 
                "- hotfix/urgent-fix"
            )
            return 2
        
        self.results['branch_analysis']['current_branch'] = current_branch
        self.results['branch_analysis']['valid_naming'] = True
        return 0
    
    def _check_remote_sync(self) -> int:
        """检查与远程的同步状态"""
        try:
            # 获取当前分支
            current_branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True, text=True, timeout=5
            )
            
            if current_branch_result.returncode != 0:
                return 0
            
            current_branch = current_branch_result.stdout.strip()
            
            # 检查是否有远程分支
            remote_check = subprocess.run(
                ['git', 'ls-remote', '--heads', 'origin', current_branch],
                capture_output=True, text=True, timeout=10
            )
            
            if remote_check.returncode != 0 or not remote_check.stdout.strip():
                # 没有远程分支，这是新分支
                self.results['warnings'].append(
                    f"分支'{current_branch}'没有对应的远程分支"
                )
                return 2
            
            # 检查本地与远程的差异
            ahead_behind_result = subprocess.run(
                ['git', 'rev-list', '--left-right', '--count', f'origin/{current_branch}...HEAD'],
                capture_output=True, text=True, timeout=5
            )
            
            if ahead_behind_result.returncode == 0:
                behind, ahead = map(int, ahead_behind_result.stdout.strip().split())
                
                if behind > 0:
                    self.results['warnings'].append(
                        f"本地分支落后远程{behind}个提交，建议先pull"
                    )
                    return 2
                
                if ahead > 10:
                    self.results['warnings'].append(
                        f"本地分支领先远程{ahead}个提交，考虑分批推送"
                    )
                    return 2
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        return 0
    
    def _analyze_commit_history(self) -> int:
        """分析提交历史质量"""
        try:
            # 获取最近10个提交
            result = subprocess.run(
                ['git', 'log', '--oneline', '-10'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return 0
            
            commits = result.stdout.strip().split('\n')
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        if not commits or commits == ['']:
            return 0
        
        # 分析提交模式
        small_commits = 0
        fix_commits = 0
        wip_commits = 0
        
        for commit_line in commits:
            if not commit_line.strip():
                continue
                
            # 提取提交信息（去掉hash）
            commit_msg = ' '.join(commit_line.split()[1:])
            
            # 检查小提交（可能需要squash）
            if any(keyword in commit_msg.lower() for keyword in 
                   ['typo', 'oops', 'minor', 'small']):
                small_commits += 1
            
            # 检查修复提交
            if commit_msg.lower().startswith('fix'):
                fix_commits += 1
            
            # 检查WIP提交
            if any(keyword in commit_msg.lower() for keyword in 
                   ['wip', 'work in progress', 'tmp', 'temp']):
                wip_commits += 1
        
        status = 0
        
        if wip_commits > 2:
            self.results['warnings'].append(
                f"发现{wip_commits}个WIP提交，合并前建议squash"
            )
            status = max(status, 2)
        
        if small_commits > 3:
            self.results['warnings'].append(
                f"发现{small_commits}个小修补提交，考虑合并"
            )
            status = max(status, 2)
        
        if fix_commits > len(commits) * 0.5:
            self.results['warnings'].append(
                "修复提交过多，可能代码质量需要改进"
            )
            status = max(status, 2)
        
        self.results['commit_analysis']['history_quality'] = {
            'total_commits': len(commits),
            'small_commits': small_commits,
            'fix_commits': fix_commits,
            'wip_commits': wip_commits
        }
        
        return status
    
    def _check_merge_conflicts(self) -> int:
        """检查合并冲突"""
        try:
            # 检查是否有未解决的合并
            merge_head_path = self.git_dir / 'MERGE_HEAD'
            if merge_head_path.exists():
                self.results['issues'].append("存在未完成的合并，请先解决")
                return 1
            
            # 检查工作目录状态
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, timeout=5
            )
            
            if status_result.returncode != 0:
                return 0
            
            status_lines = status_result.stdout.strip().split('\n')
            conflict_files = []
            
            for line in status_lines:
                if line.startswith('UU '):  # 未解决的冲突
                    conflict_files.append(line[3:])
            
            if conflict_files:
                self.results['issues'].append(
                    f"存在冲突文件: {', '.join(conflict_files)}"
                )
                return 1
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        
        return 0
    
    def _suggest_branch_cleanup(self):
        """建议分支清理"""
        try:
            # 获取已合并的分支
            result = subprocess.run(
                ['git', 'branch', '--merged'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                return
            
            merged_branches = [
                branch.strip().replace('* ', '') 
                for branch in result.stdout.strip().split('\n')
                if branch.strip() and not branch.strip().replace('* ', '') in ['main', 'master', 'develop']
            ]
            
            if merged_branches:
                self.results['suggestions'].append(
                    f"以下分支已合并，可以删除: {', '.join(merged_branches)}"
                )
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    def _suggest_version_tagging(self):
        """建议版本标签"""
        try:
            # 检查最新标签
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                # 没有标签，建议创建初始版本
                self.results['suggestions'].append(
                    "建议创建初始版本标签: git tag v0.1.0"
                )
                return
            
            last_tag = result.stdout.strip()
            
            # 检查自上次标签以来的提交
            commits_since_tag = subprocess.run(
                ['git', 'log', f'{last_tag}..HEAD', '--oneline'],
                capture_output=True, text=True, timeout=5
            )
            
            if commits_since_tag.returncode == 0 and commits_since_tag.stdout.strip():
                commit_count = len(commits_since_tag.stdout.strip().split('\n'))
                
                # 分析提交类型
                commit_content = commits_since_tag.stdout
                has_features = 'feat' in commit_content
                has_breaking = 'BREAKING' in commit_content
                
                if has_breaking:
                    self.results['suggestions'].append("建议创建主版本标签（有破坏性变更）")
                elif has_features:
                    self.results['suggestions'].append("建议创建次版本标签（有新功能）")
                elif commit_count > 5:
                    self.results['suggestions'].append("建议创建补丁版本标签（有多个修复）")
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    def _check_documentation_updates(self):
        """检查文档更新需要"""
        # 检查是否有API相关的变更
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD~1..HEAD'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                return
            
            changed_files = result.stdout.strip().split('\n')
            
            api_changes = [f for f in changed_files if 'api' in f.lower() or f.endswith('.py')]
            config_changes = [f for f in changed_files if 'config' in f or f.endswith('.yml')]
            
            if api_changes:
                self.results['suggestions'].append(
                    "API文件有变更，考虑更新API文档"
                )
            
            if config_changes:
                self.results['suggestions'].append(
                    "配置文件有变更，检查是否需要更新部署文档"
                )
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    def generate_workflow_report(self) -> str:
        """生成Git工作流报告"""
        report = []
        
        # 标题和时间戳
        report.append("🔄 Git工作流检查报告")
        report.append("=" * 40)
        
        # 整体状态
        status = self.results['workflow_status']
        if self.results['issues']:
            report.append("❌ 工作流状态: 需要修复")
        elif self.results['warnings']:
            report.append("⚠️ 工作流状态: 有警告")
        else:
            report.append("✅ 工作流状态: 良好")
        
        report.append("")
        
        # 严重问题
        if self.results['issues']:
            report.append("🔴 需要修复的问题:")
            for i, issue in enumerate(self.results['issues'], 1):
                report.append(f"  {i}. {issue}")
            report.append("")
        
        # 警告
        if self.results['warnings']:
            report.append("🟡 警告信息:")
            for i, warning in enumerate(self.results['warnings'], 1):
                report.append(f"  {i}. {warning}")
            report.append("")
        
        # 分支分析
        branch_info = self.results.get('branch_analysis', {})
        if branch_info:
            current_branch = branch_info.get('current_branch', 'unknown')
            report.append(f"🌿 当前分支: {current_branch}")
            
            if branch_info.get('valid_naming'):
                report.append("✅ 分支命名符合规范")
            else:
                report.append("⚠️ 分支命名建议改进")
            report.append("")
        
        # 提交分析
        commit_info = self.results.get('commit_analysis', {})
        if commit_info:
            msg_quality = commit_info.get('message_quality', 'unknown')
            report.append(f"📝 提交信息质量: {msg_quality}")
            
            history = commit_info.get('history_quality', {})
            if history:
                report.append(f"📊 最近提交分析:")
                report.append(f"   总提交数: {history.get('total_commits', 0)}")
                report.append(f"   修复提交: {history.get('fix_commits', 0)}")
                report.append(f"   WIP提交: {history.get('wip_commits', 0)}")
            report.append("")
        
        # 安全扫描
        security = self.results.get('security_scan', {})
        if 'secrets_found' in security:
            secrets_count = security['secrets_found']
            if secrets_count == 0:
                report.append("🛡️ 安全扫描: 未发现敏感信息")
            else:
                report.append(f"🚨 安全扫描: 发现{secrets_count}个敏感信息")
            report.append("")
        
        # 建议
        if self.results['suggestions']:
            report.append("💡 改进建议:")
            for i, suggestion in enumerate(self.results['suggestions'], 1):
                # 处理多行建议
                suggestion_lines = suggestion.split('\n')
                report.append(f"  {i}. {suggestion_lines[0]}")
                for line in suggestion_lines[1:]:
                    if line.strip():
                        report.append(f"     {line}")
            report.append("")
        
        # Git工作流提示
        report.append("🎯 Git最佳实践提醒:")
        report.append("  • 保持提交原子性，每个提交只做一件事")
        report.append("  • 编写清晰的提交信息，解释'为什么'而不是'做什么'")
        report.append("  • 定期整理提交历史，保持项目历史清晰")
        report.append("  • 合并前进行code review，确保代码质量")
        
        return "\n".join(report)
    
    def get_status_code(self) -> int:
        """获取状态码"""
        if self.results.get('issues'):
            return 1  # 严重问题
        elif self.results.get('warnings'):
            return 2  # 警告
        else:
            return 0  # 正常

def main():
    """主函数"""
    workflow_manager = GitWorkflowManager()
    
    # 解析命令行参数
    pre_commit = '--pre-commit' in sys.argv
    pre_push = '--pre-push' in sys.argv
    post_merge = '--post-merge' in sys.argv
    
    commit_message = None
    for arg in sys.argv:
        if arg.startswith('--commit-msg='):
            commit_message = arg.split('=', 1)[1]
    
    # 执行相应检查
    try:
        if pre_commit:
            status_code = workflow_manager.run_pre_commit_checks()
        elif pre_push:
            status_code = workflow_manager.run_pre_push_checks()
        elif post_merge:
            status_code = workflow_manager.run_post_merge_cleanup()
        else:
            # 默认执行提交前检查
            status_code = workflow_manager.run_pre_commit_checks()
        
        # 生成报告
        report = workflow_manager.generate_workflow_report()
        print(report)
        
        # Claude Hook响应
        if os.getenv('CLAUDE_HOOK_MODE') == '1':
            hook_response = {
                'git_workflow_status': 'pass' if status_code == 0 else ('warning' if status_code == 2 else 'fail'),
                'allow_operation': status_code != 1,
                'workflow_results': workflow_manager.results
            }
            print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response, indent=2)}")
        
        sys.exit(status_code)
        
    except Exception as e:
        print(f"❌ Git工作流检查执行失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()