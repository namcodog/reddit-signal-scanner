#!/usr/bin/env python3
"""
问题状态管理器 - Reddit Signal Scanner

基于Linus Torvalds的"数据结构决定代码复杂度"哲学设计的问题跟踪系统。
核心目标：强制执行"问题发现→修复→验证→继续"的工作流程。

设计原则：
1. 简单的状态机：discovered -> fixing -> fixed -> verified
2. 数据结构优先：问题状态决定工作流程行为
3. 零容忍：有未解决问题必须阻塞后续操作
4. 自愈性：自动检测和修复状态不一致
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.claude/logs/issue_tracker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class IssueStatus(Enum):
    """问题状态枚举 - 清晰的状态机"""
    DISCOVERED = "discovered"    # 刚发现的问题
    FIXING = "fixing"           # 正在修复中
    FIXED = "fixed"             # 已修复，等待验证
    VERIFIED = "verified"       # 已验证修复
    IGNORED = "ignored"         # 被忽略（仅限紧急情况）

class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"    # 阻塞性错误，必须立即修复
    HIGH = "high"           # 高优先级警告
    MEDIUM = "medium"       # 中等优先级建议
    LOW = "low"            # 低优先级提示

@dataclass
class Issue:
    """问题数据结构 - 核心抽象"""
    id: str                    # 问题唯一标识符
    task_id: str              # 关联的任务ID
    agent_name: str           # 发现问题的Agent
    severity: IssueSeverity   # 严重程度
    status: IssueStatus       # 当前状态
    title: str                # 问题标题
    description: str          # 问题描述
    file_path: Optional[str]  # 相关文件路径
    line_number: Optional[int] # 相关行号
    created_at: str           # 创建时间
    updated_at: str           # 更新时间
    fixed_at: Optional[str]   # 修复时间
    verified_at: Optional[str] # 验证时间
    metadata: Dict[str, Any]  # 额外元数据
    
    @classmethod
    def create(cls, task_id: str, agent_name: str, severity: IssueSeverity,
               title: str, description: str, file_path: str = None,
               line_number: int = None, **metadata) -> 'Issue':
        """创建新问题"""
        issue_id = cls._generate_issue_id(task_id, agent_name, title, file_path, line_number)
        now = datetime.now(timezone.utc).isoformat()
        
        return cls(
            id=issue_id,
            task_id=task_id,
            agent_name=agent_name,
            severity=severity,
            status=IssueStatus.DISCOVERED,
            title=title,
            description=description,
            file_path=file_path,
            line_number=line_number,
            created_at=now,
            updated_at=now,
            fixed_at=None,
            verified_at=None,
            metadata=metadata
        )
    
    @staticmethod
    def _generate_issue_id(task_id: str, agent_name: str, title: str,
                          file_path: str = None, line_number: int = None) -> str:
        """生成问题ID - 基于内容哈希，避免重复"""
        content = f"{task_id}:{agent_name}:{title}:{file_path}:{line_number}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def update_status(self, new_status: IssueStatus) -> None:
        """更新问题状态"""
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        
        # 记录状态转换的时间戳
        if new_status == IssueStatus.FIXED:
            self.fixed_at = self.updated_at
        elif new_status == IssueStatus.VERIFIED:
            self.verified_at = self.updated_at
            
        logger.info(f"问题 {self.id} 状态变更: {old_status.value} -> {new_status.value}")
    
    def is_blocking(self) -> bool:
        """判断是否为阻塞性问题"""
        return (self.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH] 
                and self.status not in [IssueStatus.VERIFIED, IssueStatus.IGNORED])
    
    def can_ignore(self) -> bool:
        """判断是否可以被忽略"""
        return self.severity in [IssueSeverity.LOW, IssueSeverity.MEDIUM]

class IssueTracker:
    """问题跟踪器 - 核心状态管理"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.issues_file = self.project_root / '.claude' / 'logs' / 'issues.json'
        
        # 确保目录存在
        self.issues_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载现有问题
        self.issues: Dict[str, Issue] = {}
        self._load_issues()
        
        # 性能缓存
        self._blocking_cache = {}
        self._cache_timestamp = 0
    
    def _load_issues(self) -> None:
        """从文件加载问题列表"""
        if not self.issues_file.exists():
            return
            
        try:
            with open(self.issues_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for issue_data in data.get('issues', []):
                # 将字符串转换回枚举类型
                issue_data['severity'] = IssueSeverity(issue_data['severity'])
                issue_data['status'] = IssueStatus(issue_data['status'])
                
                issue = Issue(**issue_data)
                self.issues[issue.id] = issue
                
            logger.info(f"加载了 {len(self.issues)} 个问题")
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"加载问题文件失败: {e}")
            self.issues = {}
    
    def _save_issues(self) -> None:
        """保存问题到文件"""
        try:
            # 将枚举类型转换为字符串以便JSON序列化
            serializable_issues = []
            for issue in self.issues.values():
                issue_dict = asdict(issue)
                issue_dict['severity'] = issue.severity.value
                issue_dict['status'] = issue.status.value
                serializable_issues.append(issue_dict)
            
            data = {
                'issues': serializable_issues,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'total_count': len(self.issues)
            }
            
            # 原子写入：先写临时文件，再重命名
            temp_file = self.issues_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.rename(self.issues_file)
            
            # 清除缓存
            self._blocking_cache = {}
            
        except Exception as e:
            logger.error(f"保存问题文件失败: {e}")
            raise
    
    def add_issue(self, task_id: str, agent_name: str, severity: str,
                  title: str, description: str, file_path: str = None,
                  line_number: int = None, **metadata) -> Issue:
        """添加新问题"""
        
        # 转换严重程度字符串为枚举
        try:
            severity_enum = IssueSeverity(severity.lower())
        except ValueError:
            severity_enum = IssueSeverity.MEDIUM
            logger.warning(f"未知的严重程度 '{severity}'，使用默认值 MEDIUM")
        
        issue = Issue.create(
            task_id=task_id,
            agent_name=agent_name,
            severity=severity_enum,
            title=title,
            description=description,
            file_path=file_path,
            line_number=line_number,
            **metadata
        )
        
        # 检查是否已存在相同问题
        if issue.id in self.issues:
            existing = self.issues[issue.id]
            logger.info(f"问题 {issue.id} 已存在，更新描述")
            existing.description = description
            existing.updated_at = issue.updated_at
            existing.metadata.update(metadata)
            self._save_issues()
            return existing
        
        self.issues[issue.id] = issue
        self._save_issues()
        
        logger.info(f"添加问题: {issue.id} - {title} [{severity_enum.value}]")
        return issue
    
    def update_issue_status(self, issue_id: str, new_status: str) -> bool:
        """更新问题状态"""
        if issue_id not in self.issues:
            logger.warning(f"问题 {issue_id} 不存在")
            return False
        
        try:
            status_enum = IssueStatus(new_status.lower())
        except ValueError:
            logger.error(f"无效的状态: {new_status}")
            return False
        
        issue = self.issues[issue_id]
        issue.update_status(status_enum)
        self._save_issues()
        
        return True
    
    def get_blocking_issues(self, task_id: str = None) -> List[Issue]:
        """获取阻塞性问题"""
        current_time = time.time()
        cache_key = f"blocking_{task_id}"
        
        # 检查缓存（5秒有效）
        if (cache_key in self._blocking_cache and 
            current_time - self._cache_timestamp < 5):
            return self._blocking_cache[cache_key]
        
        blocking_issues = []
        for issue in self.issues.values():
            if issue.is_blocking():
                if task_id is None or issue.task_id == task_id:
                    blocking_issues.append(issue)
        
        # 按严重程度排序
        blocking_issues.sort(key=lambda x: x.severity.value, reverse=True)
        
        # 更新缓存
        self._blocking_cache[cache_key] = blocking_issues
        self._cache_timestamp = current_time
        
        return blocking_issues
    
    def has_blocking_issues(self, task_id: str = None) -> bool:
        """检查是否有阻塞性问题"""
        return len(self.get_blocking_issues(task_id)) > 0
    
    def get_issues_by_status(self, status: str, task_id: str = None) -> List[Issue]:
        """按状态获取问题"""
        try:
            status_enum = IssueStatus(status.lower())
        except ValueError:
            return []
        
        issues = []
        for issue in self.issues.values():
            if issue.status == status_enum:
                if task_id is None or issue.task_id == task_id:
                    issues.append(issue)
        
        return issues
    
    def get_task_issues(self, task_id: str) -> List[Issue]:
        """获取特定任务的所有问题"""
        return [issue for issue in self.issues.values() if issue.task_id == task_id]
    
    def resolve_issue(self, issue_id: str, force: bool = False) -> bool:
        """解决问题（标记为已验证）"""
        if issue_id not in self.issues:
            return False
        
        issue = self.issues[issue_id]
        
        if not force and issue.status != IssueStatus.FIXED:
            logger.warning(f"问题 {issue_id} 状态为 {issue.status.value}，不能直接解决")
            return False
        
        issue.update_status(IssueStatus.VERIFIED)
        self._save_issues()
        
        return True
    
    def ignore_issue(self, issue_id: str, reason: str = "") -> bool:
        """忽略问题（仅限可忽略的问题）"""
        if issue_id not in self.issues:
            return False
        
        issue = self.issues[issue_id]
        
        if not issue.can_ignore():
            logger.error(f"问题 {issue_id} 严重程度为 {issue.severity.value}，无法忽略")
            return False
        
        issue.update_status(IssueStatus.IGNORED)
        if reason:
            issue.metadata['ignore_reason'] = reason
        
        self._save_issues()
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取问题统计信息"""
        stats = {
            'total': len(self.issues),
            'by_status': {},
            'by_severity': {},
            'blocking_count': 0
        }
        
        for issue in self.issues.values():
            # 按状态统计
            status = issue.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            # 按严重程度统计
            severity = issue.severity.value
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
            
            # 阻塞性问题统计
            if issue.is_blocking():
                stats['blocking_count'] += 1
        
        return stats
    
    def cleanup_resolved_issues(self, days: int = 7) -> int:
        """清理已解决的旧问题"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 3600)
        removed_count = 0
        
        issues_to_remove = []
        for issue in self.issues.values():
            if (issue.status == IssueStatus.VERIFIED and 
                issue.verified_at and 
                datetime.fromisoformat(issue.verified_at.replace('Z', '+00:00')).timestamp() < cutoff_time):
                issues_to_remove.append(issue.id)
        
        for issue_id in issues_to_remove:
            del self.issues[issue_id]
            removed_count += 1
        
        if removed_count > 0:
            self._save_issues()
            logger.info(f"清理了 {removed_count} 个已解决的旧问题")
        
        return removed_count
    
    def export_report(self, task_id: str = None) -> Dict[str, Any]:
        """导出问题报告"""
        issues_to_report = self.get_task_issues(task_id) if task_id else list(self.issues.values())
        
        report = {
            'task_id': task_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': self.get_statistics(),
            'issues': []
        }
        
        for issue in issues_to_report:
            issue_dict = asdict(issue)
            issue_dict['severity'] = issue.severity.value
            issue_dict['status'] = issue.status.value
            report['issues'].append(issue_dict)
        
        return report

def main():
    """命令行工具入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='问题状态管理器')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出问题')
    list_parser.add_argument('--task', help='任务ID过滤')
    list_parser.add_argument('--status', help='状态过滤')
    list_parser.add_argument('--blocking', action='store_true', help='只显示阻塞性问题')
    
    # add 命令
    add_parser = subparsers.add_parser('add', help='添加问题')
    add_parser.add_argument('task_id', help='任务ID')
    add_parser.add_argument('agent_name', help='Agent名称')
    add_parser.add_argument('severity', choices=['critical', 'high', 'medium', 'low'], help='严重程度')
    add_parser.add_argument('title', help='问题标题')
    add_parser.add_argument('description', help='问题描述')
    add_parser.add_argument('--file', help='相关文件路径')
    add_parser.add_argument('--line', type=int, help='相关行号')
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='更新问题状态')
    update_parser.add_argument('issue_id', help='问题ID')
    update_parser.add_argument('status', choices=['discovered', 'fixing', 'fixed', 'verified', 'ignored'], help='新状态')
    
    # check 命令
    check_parser = subparsers.add_parser('check', help='检查阻塞性问题')
    check_parser.add_argument('--task', help='任务ID')
    
    # stats 命令
    subparsers.add_parser('stats', help='显示统计信息')
    
    # cleanup 命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理已解决的问题')
    cleanup_parser.add_argument('--days', type=int, default=7, help='保留天数')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tracker = IssueTracker()
    
    if args.command == 'list':
        issues = list(tracker.issues.values())
        
        if args.task:
            issues = [i for i in issues if i.task_id == args.task]
        
        if args.status:
            issues = [i for i in issues if i.status.value == args.status]
            
        if args.blocking:
            issues = [i for i in issues if i.is_blocking()]
        
        print(f"问题列表 ({len(issues)} 个):")
        for issue in issues:
            status_icon = "🔴" if issue.is_blocking() else "🟡" if issue.status == IssueStatus.FIXING else "🟢"
            print(f"{status_icon} {issue.id}: {issue.title} [{issue.severity.value}] [{issue.status.value}]")
            if issue.file_path:
                print(f"   📁 {issue.file_path}:{issue.line_number or '?'}")
    
    elif args.command == 'add':
        issue = tracker.add_issue(
            task_id=args.task_id,
            agent_name=args.agent_name,
            severity=args.severity,
            title=args.title,
            description=args.description,
            file_path=args.file,
            line_number=args.line
        )
        print(f"✅ 添加问题: {issue.id}")
    
    elif args.command == 'update':
        if tracker.update_issue_status(args.issue_id, args.status):
            print(f"✅ 更新问题状态: {args.issue_id} -> {args.status}")
        else:
            print(f"❌ 更新失败")
    
    elif args.command == 'check':
        blocking_issues = tracker.get_blocking_issues(args.task)
        if blocking_issues:
            print(f"🔴 发现 {len(blocking_issues)} 个阻塞性问题:")
            for issue in blocking_issues:
                print(f"  • {issue.id}: {issue.title} [{issue.severity.value}]")
            return 1  # 退出码1表示有阻塞性问题
        else:
            print("✅ 无阻塞性问题")
            return 0
    
    elif args.command == 'stats':
        stats = tracker.get_statistics()
        print("📊 问题统计:")
        print(f"  总计: {stats['total']}")
        print(f"  阻塞性: {stats['blocking_count']}")
        print(f"  按状态:")
        for status, count in stats['by_status'].items():
            print(f"    {status}: {count}")
        print(f"  按严重程度:")
        for severity, count in stats['by_severity'].items():
            print(f"    {severity}: {count}")
    
    elif args.command == 'cleanup':
        removed = tracker.cleanup_resolved_issues(args.days)
        print(f"🧹 清理了 {removed} 个已解决的问题")

if __name__ == '__main__':
    main()