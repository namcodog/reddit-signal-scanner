#!/usr/bin/env python3
"""
任务编排Agent - Reddit Signal Scanner

智能任务流程管控专家，自动分析依赖关系、处理阻塞任务、动态调整优先级。
基于Linus Torvalds实用主义：让复杂变简单。

使用方式:
    python task_orchestrator.py [--model claude-3-sonnet]
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# 导入Agent基类
from agent_base import AgentBase

class TaskOrchestratorAgent(AgentBase):
    """任务编排Agent - 基于AgentBase的实现"""
    
    def __init__(self):
        super().__init__('task-orchestrator')
    
    def _add_custom_args(self, parser: argparse.ArgumentParser):
        """添加任务编排特定的参数"""
        parser.add_argument('--action', choices=['analyze', 'optimize', 'status'], 
                          default='analyze', help='执行的操作类型')
        parser.add_argument('--todo-data', help='TodoWrite的数据内容')
    
    def execute(self, args: argparse.Namespace) -> int:
        """执行任务编排"""
        start_time = time.time()
        
        try:
            self.logger.info(f"开始任务编排: {args.action}")
            
            if args.action == 'analyze':
                result = self._analyze_dependencies(args.todo_data)
            elif args.action == 'optimize':
                result = self._optimize_workflow()
            elif args.action == 'status':
                result = self._generate_status_report()
            else:
                self.logger.error(f"不支持的操作: {args.action}")
                return 1
            
            # 记录性能指标
            execution_time = time.time() - start_time
            self.report_metrics({
                'execution_time': execution_time,
                'action': args.action,
                'model_used': self.model
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"任务编排失败: {e}")
            return 1
    
    def _analyze_dependencies(self, todo_data: Optional[str]) -> int:
        """分析任务依赖关系"""
        self.logger.info("分析任务依赖关系")
        
        if not todo_data:
            # 从环境变量或文件获取TodoWrite数据
            todo_data = os.environ.get('CLAUDE_TODO_DATA')
        
        if not todo_data:
            self.logger.warning("未找到待分析的任务数据")
            return 0
        
        try:
            todos = json.loads(todo_data) if isinstance(todo_data, str) else todo_data
            
            # 分析任务状态
            pending_tasks = [t for t in todos if t.get('status') == 'pending']
            in_progress_tasks = [t for t in todos if t.get('status') == 'in_progress']
            completed_tasks = [t for t in todos if t.get('status') == 'completed']
            
            # 生成智能分析
            analysis_prompt = f"""
作为任务编排专家，基于Linus的实用主义原则分析以下任务状态：

待处理任务: {len(pending_tasks)}个
进行中任务: {len(in_progress_tasks)}个  
已完成任务: {len(completed_tasks)}个

任务详情:
{json.dumps(todos, indent=2, ensure_ascii=False)}

请分析：
1. 是否存在阻塞和瓶颈？
2. 能否并行执行某些任务？
3. 优先级是否合理？
4. 有什么优化建议？

给出简洁实用的建议。
"""
            
            # 调用AI模型分析
            ai_analysis = self.call_ai_model(analysis_prompt)
            
            print(f"\n🎯 任务编排分析报告:")
            print(f"📊 状态统计: {len(completed_tasks)}已完成 | {len(in_progress_tasks)}进行中 | {len(pending_tasks)}待处理")
            print(f"\n🤖 AI分析建议:")
            print(ai_analysis)
            
            # 检测瓶颈
            if len(in_progress_tasks) > 3:
                print(f"\n⚠️ 发现瓶颈: 同时进行{len(in_progress_tasks)}个任务，建议专注完成当前任务")
                return 2
            
            return 0
            
        except Exception as e:
            self.logger.error(f"依赖分析失败: {e}")
            return 1
    
    def _optimize_workflow(self) -> int:
        """优化工作流程"""
        self.logger.info("优化工作流程")
        
        try:
            # 检查workflow.py状态
            workflow_path = Path("workflow.py")
            if workflow_path.exists():
                # 获取项目状态
                import subprocess
                result = subprocess.run(
                    ["python", "workflow.py", "status"],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    print("\n📈 工作流优化建议:")
                    print(result.stdout)
                    
                    # AI分析工作流状态
                    optimization_prompt = f"""
基于以下工作流状态，提供Linus式的优化建议：

{result.stdout}

重点关注：
1. 并行机会识别
2. 依赖关系简化  
3. 瓶颈消除
4. 资源配置优化

给出3-5条具体可执行的建议。
"""
                    
                    ai_suggestions = self.call_ai_model(optimization_prompt)
                    print(f"\n🚀 AI优化建议:")
                    print(ai_suggestions)
                    
                else:
                    self.logger.warning("无法获取工作流状态")
            else:
                self.logger.warning("workflow.py不存在")
                
            return 0
            
        except Exception as e:
            self.logger.error(f"工作流优化失败: {e}")
            return 1
    
    def _generate_status_report(self) -> int:
        """生成状态报告"""
        self.logger.info("生成状态报告")
        
        try:
            # 收集系统状态信息
            status_info = {
                'timestamp': time.time(),
                'agent_model': self.model,
                'project_status': self._get_project_status(),
                'performance_metrics': self._get_performance_metrics()
            }
            
            print(f"\n📋 任务编排状态报告:")
            print(f"🕐 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🤖 模型: {self.model}")
            print(f"📊 项目状态: {status_info['project_status']}")
            
            # 保存状态报告
            report_file = Path(".claude/logs/task-orchestrator-status.json")
            report_file.parent.mkdir(exist_ok=True)
            
            with open(report_file, 'w') as f:
                json.dump(status_info, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"状态报告已保存: {report_file}")
            return 0
            
        except Exception as e:
            self.logger.error(f"状态报告生成失败: {e}")
            return 1
    
    def _get_project_status(self) -> Dict[str, Any]:
        """获取项目状态"""
        try:
            # 简单的项目状态检查
            status = {
                'workflow_exists': Path("workflow.py").exists(),
                'config_exists': Path("workflow/config.yaml").exists(),
                'agent_config_exists': Path(".claude/agent-config.yaml").exists(),
                'python_files': len(list(Path('.').rglob('*.py'))),
                'typescript_files': len(list(Path('.').rglob('*.ts'))),
            }
            return status
        except Exception:
            return {'status': 'unknown'}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        try:
            metrics_file = Path(".claude/logs/performance/metrics_task-orchestrator.jsonl")
            if metrics_file.exists():
                # 读取最近的指标
                with open(metrics_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        latest = json.loads(lines[-1])
                        return {
                            'last_execution_time': latest.get('execution_time', 0),
                            'total_executions': len(lines)
                        }
            return {'metrics': 'no_data'}
        except Exception:
            return {'metrics': 'error'}

if __name__ == '__main__':
    agent = TaskOrchestratorAgent()
    sys.exit(agent.run())