#!/usr/bin/env python3
"""
Reddit Signal Scanner - 工作流管理工具
基于 Linus Torvalds 设计哲学：数据结构优先、简单胜过聪明

用法:
    python workflow.py status      # 查看项目状态
    python workflow.py context <task_id>  # 获取任务上下文
    python workflow.py complete <task_id> # 标记任务完成

设计原则:
- 这是个状态机，不是项目管理工具
- 只需要知道当前状态和下一步
- 数据结构决定代码复杂度
- 故障自愈优于手动修复
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Task:
    """任务数据结构 - 核心抽象"""
    id: str
    name: str
    desc: str
    size: str  # S/M/L
    deps: List[str]  # 依赖的任务ID
    files: List[str]  # 相关文件路径
    context: str  # 任务上下文描述
    prd: str  # 所属PRD
    
    def is_ready(self, completed_tasks: Set[str]) -> bool:
        """检查任务是否可以开始（所有依赖已完成）"""
        return all(dep in completed_tasks for dep in self.deps)


class WorkflowManager:
    """工作流管理器 - Linus式极简设计"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.workflow_dir = self.project_root / "workflow"
        self.tasks_dir = self.workflow_dir / "tasks"
        self.state_file = self.workflow_dir / "state.yaml"
        
        # 确保目录存在
        self.workflow_dir.mkdir(exist_ok=True)
        self.tasks_dir.mkdir(exist_ok=True)
        
        # 加载任务和状态
        self.tasks: Dict[str, Task] = {}
        self.state: Dict[str, Any] = {}
        self._load_all_tasks()
        self._load_state()
    
    def _load_all_tasks(self):
        """从YAML文件加载所有任务定义"""
        for yaml_file in self.tasks_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    prd_name = yaml_file.stem
                    
                    for task_data in data.get('tasks', []):
                        task = Task(
                            id=task_data['id'],
                            name=task_data['name'],
                            desc=task_data['desc'],
                            size=task_data.get('size', 'M'),
                            deps=task_data.get('deps', []),
                            files=task_data.get('files', []),
                            context=task_data.get('context', ''),
                            prd=prd_name
                        )
                        self.tasks[task.id] = task
            except Exception as e:
                print(f"⚠️ 加载任务文件 {yaml_file} 失败: {e}")
    
    def _load_state(self):
        """加载项目状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️ 状态文件损坏，尝试恢复: {e}")
                self._auto_repair_state()
        else:
            # 初始化状态文件
            self.state = {
                'completed': [],
                'in_progress': None,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            self._save_state()
    
    def _save_state(self):
        """保存状态到文件"""
        backup_file = self.state_file.with_suffix('.yaml.backup')
        
        # 创建备份
        if self.state_file.exists():
            self.state_file.rename(backup_file)
        
        self.state['last_updated'] = datetime.now().isoformat()
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.state, f, allow_unicode=True, indent=2, default_flow_style=False)
        except Exception as e:
            print(f"❌ 保存状态失败: {e}")
            # 恢复备份
            if backup_file.exists():
                backup_file.rename(self.state_file)
            raise
    
    def _auto_repair_state(self):
        """自动修复损坏的状态文件"""
        print("🔧 尝试自动修复状态文件...")
        
        # 1. 尝试从备份恢复
        backup_file = self.state_file.with_suffix('.yaml.backup')
        if backup_file.exists():
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.state = yaml.safe_load(f) or {}
                print("✅ 从备份文件恢复成功")
                return
            except:
                pass
        
        # 2. 重新初始化状态
        print("🔄 重新初始化状态文件...")
        self.state = {
            'completed': [],
            'in_progress': None,
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'auto_repaired': True
        }
        self._save_state()
        print("✅ 状态文件重新初始化完成")
    
    def get_completed_tasks(self) -> Set[str]:
        """获取已完成的任务集合"""
        return set(self.state.get('completed', []))
    
    def get_ready_tasks(self) -> List[Task]:
        """获取所有可以开始的任务（依赖已满足）"""
        completed = self.get_completed_tasks()
        ready_tasks = []
        
        for task in self.tasks.values():
            if task.id not in completed and task.is_ready(completed):
                ready_tasks.append(task)
        
        # 按PRD顺序和依赖深度排序
        return sorted(ready_tasks, key=lambda t: (t.prd, len(t.deps)))
    
    def get_blocked_tasks(self) -> List[Task]:
        """获取被阻塞的任务"""
        completed = self.get_completed_tasks()
        blocked_tasks = []
        
        for task in self.tasks.values():
            if task.id not in completed and not task.is_ready(completed):
                blocked_tasks.append(task)
        
        return blocked_tasks
    
    def status(self):
        """显示项目整体状态"""
        completed = self.get_completed_tasks()
        ready_tasks = self.get_ready_tasks()
        blocked_tasks = self.get_blocked_tasks()
        in_progress = self.state.get('in_progress')
        
        total_tasks = len(self.tasks)
        completed_count = len(completed)
        progress = (completed_count / total_tasks * 100) if total_tasks > 0 else 0
        
        print(f"\n📊 Reddit Signal Scanner - 项目状态")
        print(f"=" * 50)
        print(f"✅ 已完成: {completed_count}/{total_tasks} 任务 ({progress:.1f}%)")
        
        if in_progress:
            task = self.tasks.get(in_progress)
            if task:
                print(f"🔄 进行中: {in_progress} ({task.name})")
        
        print(f"📋 可开始: {len(ready_tasks)} 个任务")
        if ready_tasks:
            print("   下一个任务:")
            for task in ready_tasks[:3]:  # 只显示前3个
                print(f"     • {task.id}: {task.name} [{task.size}]")
            if len(ready_tasks) > 3:
                print(f"     ... 还有 {len(ready_tasks)-3} 个任务")
        
        print(f"⏸️ 被阻塞: {len(blocked_tasks)} 个任务等待依赖")
        
        # 显示按PRD分组的进度
        print(f"\n📋 PRD完成度:")
        prd_stats = {}
        for task in self.tasks.values():
            prd = task.prd
            if prd not in prd_stats:
                prd_stats[prd] = {'total': 0, 'completed': 0}
            prd_stats[prd]['total'] += 1
            if task.id in completed:
                prd_stats[prd]['completed'] += 1
        
        for prd, stats in sorted(prd_stats.items()):
            pct = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            status_icon = "✅" if pct == 100 else "🔄" if pct > 0 else "⏸️"
            print(f"   {status_icon} {prd.upper()}: {stats['completed']}/{stats['total']} ({pct:.0f}%)")
        
        print(f"\n⏰ 最后更新: {self.state.get('last_updated', 'Unknown')}")
    
    def context(self, task_id: str):
        """获取任务的上下文信息"""
        if task_id not in self.tasks:
            print(f"❌ 任务 {task_id} 不存在")
            return
        
        task = self.tasks[task_id]
        completed = self.get_completed_tasks()
        
        print(f"\n🎯 任务上下文: {task_id}")
        print(f"=" * 50)
        print(f"📝 名称: {task.name}")
        print(f"📖 描述: {task.desc}")
        print(f"📏 大小: {task.size} ({'小' if task.size=='S' else '中' if task.size=='M' else '大'}任务)")
        print(f"📋 所属PRD: {task.prd.upper()}")
        
        # 依赖检查
        if task.deps:
            print(f"\n🔗 依赖关系:")
            all_deps_met = True
            for dep in task.deps:
                status = "✅" if dep in completed else "❌"
                dep_task = self.tasks.get(dep, None)
                dep_name = dep_task.name if dep_task else "未知任务"
                print(f"     {status} {dep}: {dep_name}")
                if dep not in completed:
                    all_deps_met = False
            
            if not all_deps_met:
                print(f"\n⚠️  任务被阻塞 - 请先完成上述依赖任务")
                return
        else:
            print(f"\n🎯 无依赖 - 可立即开始")
        
        # 相关文件
        if task.files:
            print(f"\n📁 相关文件:")
            for file_path in task.files:
                full_path = self.project_root / file_path
                exists = "✅" if full_path.exists() else "📝"
                print(f"     {exists} {file_path}")
        
        # 任务上下文
        if task.context:
            print(f"\n📋 任务上下文:")
            print(f"{task.context}")
        
        print(f"\n🚀 准备就绪 - 可以开始此任务")
    
    def complete(self, task_id: str, verify: bool = True):
        """标记任务完成"""
        if task_id not in self.tasks:
            print(f"❌ 任务 {task_id} 不存在")
            return
        
        completed = self.get_completed_tasks()
        
        if task_id in completed:
            print(f"ℹ️ 任务 {task_id} 已经完成")
            return
        
        task = self.tasks[task_id]
        
        # 检查依赖
        if not task.is_ready(completed):
            missing_deps = [dep for dep in task.deps if dep not in completed]
            print(f"❌ 无法完成 {task_id} - 缺少依赖: {missing_deps}")
            return
        
        # 简单验证（检查相关文件是否存在）
        if verify and task.files:
            missing_files = []
            for file_path in task.files:
                full_path = self.project_root / file_path
                if not full_path.exists():
                    missing_files.append(file_path)
            
            if missing_files:
                print(f"⚠️ 验证失败 - 缺少文件: {missing_files}")
                response = input("是否强制完成？(y/N): ")
                if response.lower() != 'y':
                    return
        
        # 标记完成
        completed.add(task_id)
        self.state['completed'] = list(completed)
        self.state['in_progress'] = None
        self._save_state()
        
        print(f"✅ 任务 {task_id} ({task.name}) 已完成")
        
        # 检查解锁的新任务
        new_ready = self.get_ready_tasks()
        unlocked = [t for t in new_ready if all(dep == task_id or dep in completed for dep in t.deps)]
        
        if unlocked:
            print(f"🔓 解锁新任务:")
            for task in unlocked:
                print(f"     • {task.id}: {task.name}")
        
        # 显示进度
        total = len(self.tasks)
        progress = len(completed) / total * 100
        print(f"📊 整体进度: {len(completed)}/{total} ({progress:.1f}%)")
    
    def reset(self, all_state: bool = False, task_id: str = None):
        """重置状态"""
        if all_state:
            response = input("⚠️ 确认重置所有任务状态？这将清除所有进度 (y/N): ")
            if response.lower() == 'y':
                self.state = {
                    'completed': [],
                    'in_progress': None,
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'reset_reason': 'User requested full reset'
                }
                self._save_state()
                print("✅ 所有状态已重置")
            else:
                print("❌ 重置操作已取消")
        
        elif task_id:
            if task_id not in self.tasks:
                print(f"❌ 任务 {task_id} 不存在")
                return
            
            completed = set(self.state.get('completed', []))
            if task_id in completed:
                completed.remove(task_id)
                self.state['completed'] = list(completed)
                
                # 如果这是进行中的任务，也清除
                if self.state.get('in_progress') == task_id:
                    self.state['in_progress'] = None
                
                self._save_state()
                print(f"✅ 任务 {task_id} 状态已重置")
                
                # 检查这会解锁哪些新任务
                newly_blocked = []
                for task in self.tasks.values():
                    if task_id in task.deps and task.is_ready(completed):
                        newly_blocked.append(task.id)
                
                if newly_blocked:
                    print(f"⚠️ 重置此任务会阻塞以下任务: {', '.join(newly_blocked)}")
            else:
                print(f"ℹ️ 任务 {task_id} 未完成，无需重置")
        else:
            print("❌ 请指定 --all 或 --task <task_id>")
    
    def verify_integrity(self, auto_fix: bool = False):
        """验证状态文件完整性"""
        issues = []
        
        print("🔍 验证状态文件完整性...")
        
        # 检查1: 状态文件格式
        required_fields = ['completed', 'created_at', 'last_updated']
        for field in required_fields:
            if field not in self.state:
                issues.append(f"缺少必需字段: {field}")
        
        # 检查2: 完成的任务ID有效性
        completed = self.state.get('completed', [])
        invalid_tasks = [tid for tid in completed if tid not in self.tasks]
        if invalid_tasks:
            issues.append(f"无效的已完成任务: {invalid_tasks}")
        
        # 检查3: 依赖关系一致性
        dependency_violations = []
        for task_id in completed:
            task = self.tasks.get(task_id)
            if task:
                for dep in task.deps:
                    if dep not in completed:
                        dependency_violations.append(f"{task_id} 已完成但依赖 {dep} 未完成")
        
        if dependency_violations:
            issues.append(f"依赖关系违反: {dependency_violations}")
        
        # 检查4: 进行中任务的有效性
        in_progress = self.state.get('in_progress')
        if in_progress and in_progress not in self.tasks:
            issues.append(f"无效的进行中任务: {in_progress}")
        
        if not issues:
            print("✅ 状态文件完整性验证通过")
            return True
        
        print(f"⚠️ 发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        if auto_fix:
            print("\n🔧 尝试自动修复...")
            
            # 修复无效的已完成任务
            if invalid_tasks:
                self.state['completed'] = [tid for tid in completed if tid in self.tasks]
                print(f"   ✅ 移除无效任务: {invalid_tasks}")
            
            # 修复无效的进行中任务
            if in_progress and in_progress not in self.tasks:
                self.state['in_progress'] = None
                print(f"   ✅ 清除无效的进行中任务: {in_progress}")
            
            # 修复缺失的必需字段
            if 'completed' not in self.state:
                self.state['completed'] = []
                print(f"   ✅ 添加缺失字段: completed")
            
            if 'created_at' not in self.state:
                self.state['created_at'] = datetime.now().isoformat()
                print(f"   ✅ 添加缺失字段: created_at")
            
            if 'last_updated' not in self.state:
                self.state['last_updated'] = datetime.now().isoformat()
                print(f"   ✅ 添加缺失字段: last_updated")
            
            # 保存修复后的状态
            self._save_state()
            print("🎉 自动修复完成")
            return self.verify_integrity(auto_fix=False)  # 重新验证
        
        return False
    
    def list_tasks(self, ready_only: bool = False, completed_only: bool = False, prd_filter: str = None):
        """列出任务"""
        tasks_to_show = list(self.tasks.values())
        
        # 应用过滤器
        if prd_filter:
            tasks_to_show = [t for t in tasks_to_show if t.prd.lower() == prd_filter.lower()]
            if not tasks_to_show:
                print(f"❌ 没有找到PRD '{prd_filter}' 的任务")
                return
        
        completed = self.get_completed_tasks()
        
        if ready_only:
            tasks_to_show = [t for t in tasks_to_show if t.is_ready(completed) and t.id not in completed]
            title = "📋 可开始的任务"
        elif completed_only:
            tasks_to_show = [t for t in tasks_to_show if t.id in completed]
            title = "✅ 已完成的任务"
        else:
            title = "📋 所有任务"
        
        if not tasks_to_show:
            print(f"{title}: 无")
            return
        
        print(f"\n{title} ({len(tasks_to_show)} 个):")
        print("=" * 60)
        
        # 按PRD分组
        by_prd = {}
        for task in tasks_to_show:
            if task.prd not in by_prd:
                by_prd[task.prd] = []
            by_prd[task.prd].append(task)
        
        for prd, tasks in sorted(by_prd.items()):
            print(f"\n📁 {prd.upper()}:")
            for task in sorted(tasks, key=lambda t: t.id):
                status_icon = "✅" if task.id in completed else "📋"
                ready_status = "🚀" if task.is_ready(completed) and task.id not in completed else ""
                print(f"   {status_icon} {task.id}: {task.name} [{task.size}] {ready_status}")
                if task.desc and len(task.desc) < 80:
                    print(f"      📝 {task.desc}")
    
    def get_stats(self):
        """获取统计信息"""
        completed = self.get_completed_tasks()
        ready = self.get_ready_tasks()
        blocked = self.get_blocked_tasks()
        
        return {
            'total_tasks': len(self.tasks),
            'completed_tasks': len(completed),
            'ready_tasks': len(ready),
            'blocked_tasks': len(blocked),
            'completion_rate': len(completed) / len(self.tasks) * 100 if self.tasks else 0
        }


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="Reddit Signal Scanner 工作流管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # status 命令
    subparsers.add_parser('status', help='显示项目状态')
    
    # context 命令  
    context_parser = subparsers.add_parser('context', help='获取任务上下文')
    context_parser.add_argument('task_id', help='任务ID')
    
    # complete 命令
    complete_parser = subparsers.add_parser('complete', help='标记任务完成')
    complete_parser.add_argument('task_id', help='任务ID')
    complete_parser.add_argument('--verify', action='store_true', default=True, help='验证任务完成')
    complete_parser.add_argument('--no-verify', dest='verify', action='store_false', help='跳过验证')
    
    # reset 命令
    reset_parser = subparsers.add_parser('reset', help='重置状态或特定任务')
    reset_parser.add_argument('--all', action='store_true', help='重置所有状态')
    reset_parser.add_argument('--task', help='重置特定任务状态')
    
    # verify 命令
    verify_parser = subparsers.add_parser('verify', help='验证状态文件完整性')
    verify_parser.add_argument('--fix', action='store_true', help='自动修复发现的问题')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出任务')
    list_parser.add_argument('--ready', action='store_true', help='只显示可开始的任务')
    list_parser.add_argument('--completed', action='store_true', help='只显示已完成的任务')
    list_parser.add_argument('--prd', help='按PRD过滤任务')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = WorkflowManager()
        
        if args.command == 'status':
            manager.status()
        elif args.command == 'context':
            manager.context(args.task_id)
        elif args.command == 'complete':
            manager.complete(args.task_id, verify=args.verify)
        elif args.command == 'reset':
            manager.reset(all_state=args.all, task_id=args.task)
        elif args.command == 'verify':
            manager.verify_integrity(auto_fix=args.fix)
        elif args.command == 'list':
            manager.list_tasks(ready_only=args.ready, completed_only=args.completed, prd_filter=args.prd)
    
    except KeyboardInterrupt:
        print("\n\n👋 操作已取消")
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()