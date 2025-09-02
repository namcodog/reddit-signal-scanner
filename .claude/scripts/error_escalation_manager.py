#!/usr/bin/env python3
"""
错误升级管理器 - 实现3次错误自动升级机制
基于Linus的"第三次调试是最后一次"哲学
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sqlite3
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.claude/logs/error_escalation.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class ErrorEvent:
    """错误事件数据结构"""
    error_signature: str
    error_message: str
    file_path: str
    function_name: str
    timestamp: datetime
    stack_trace: str
    context: Dict[str, str]

@dataclass
class EscalationAction:
    """升级行动数据结构"""
    level: int  # 1=原agent自修复, 2=error-detective, 3=debugger+architect
    agent_type: str
    action_description: str
    timeout_seconds: int
    required_tools: List[str]

class ErrorEscalationManager:
    """错误升级管理器核心类"""
    
    def __init__(self, db_path: str = ".claude/data/error_tracking.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        self.escalation_config = self.load_escalation_config()
    
    def init_database(self):
        """初始化错误跟踪数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 错误事件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_signature TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    file_path TEXT,
                    function_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    stack_trace TEXT,
                    context TEXT,  -- JSON格式
                    resolution_status TEXT DEFAULT 'unresolved',
                    escalation_level INTEGER DEFAULT 0
                )
            ''')
            
            # 升级历史表  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS escalation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_signature TEXT NOT NULL,
                    escalation_level INTEGER NOT NULL,
                    agent_type TEXT NOT NULL,
                    action_taken TEXT,
                    success BOOLEAN,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    execution_time_seconds REAL,
                    notes TEXT
                )
            ''')
            
            # 成功解决方案库
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS solution_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_pattern TEXT NOT NULL,
                    solution_approach TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    avg_resolution_time REAL DEFAULT 0.0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_by_agent TEXT,
                    verification_count INTEGER DEFAULT 0
                )
            ''')
            
            conn.commit()
            logging.info(f"错误跟踪数据库初始化完成: {self.db_path}")
    
    def load_escalation_config(self) -> Dict[int, EscalationAction]:
        """加载升级配置"""
        return {
            1: EscalationAction(
                level=1,
                agent_type="self",
                action_description="原Agent自行修复",
                timeout_seconds=60,
                required_tools=[]
            ),
            2: EscalationAction(
                level=2, 
                agent_type="error-detective",
                action_description="错误侦探深度分析错误模式",
                timeout_seconds=90,
                required_tools=[
                    "mcp__context7__get-library-docs",
                    "mcp__serena__search_for_pattern", 
                    "mcp__sequential-thinking__sequentialthinking",
                    "mcp__tavily-mcp__tavily-search"
                ]
            ),
            3: EscalationAction(
                level=3,
                agent_type="debugger+linus-architect", 
                action_description="专业调试器+架构师强制介入",
                timeout_seconds=180,
                required_tools=[
                    "mcp__context7__get-library-docs",
                    "mcp__serena__find_symbol",
                    "mcp__serena__find_referencing_symbols",
                    "mcp__sequential-thinking__sequentialthinking",
                    "Bash"
                ]
            )
        }
    
    def generate_error_signature(self, error_message: str, file_path: str, 
                                function_name: str) -> str:
        """生成错误唯一签名"""
        # 标准化错误信息，去除变化的部分
        normalized_error = error_message
        
        # 去除行号、临时变量名等变化信息
        import re
        normalized_error = re.sub(r'line \d+', 'line XXX', normalized_error)
        normalized_error = re.sub(r'variable_\d+', 'variable_XXX', normalized_error)
        normalized_error = re.sub(r'temp_\w+', 'temp_XXX', normalized_error)
        
        # 组合签名字符串
        signature_string = f"{file_path}::{function_name}::{normalized_error}"
        
        # 生成MD5签名
        return hashlib.md5(signature_string.encode()).hexdigest()[:12]
    
    def record_error_event(self, error: ErrorEvent) -> int:
        """记录错误事件并返回错误ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO error_events 
                (error_signature, error_message, file_path, function_name, 
                 stack_trace, context, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                error.error_signature,
                error.error_message,
                error.file_path,
                error.function_name,
                error.stack_trace,
                json.dumps(error.context),
                error.timestamp
            ))
            
            error_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"记录错误事件 #{error_id}: {error.error_signature}")
            return error_id
    
    def get_error_occurrence_count(self, error_signature: str, 
                                 time_window_hours: int = 24) -> int:
        """获取错误在指定时间窗口内的发生次数"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM error_events 
                WHERE error_signature = ? AND timestamp > ?
            ''', (error_signature, cutoff_time))
            
            count = cursor.fetchone()[0]
            return count
    
    def should_escalate(self, error_signature: str) -> Optional[EscalationAction]:
        """判断是否需要升级以及升级级别"""
        occurrence_count = self.get_error_occurrence_count(error_signature)
        
        logging.info(f"错误 {error_signature} 在24小时内发生 {occurrence_count} 次")
        
        if occurrence_count >= 3:
            return self.escalation_config[3]  # 第3次：调试器+架构师
        elif occurrence_count >= 2:
            return self.escalation_config[2]  # 第2次：错误侦探
        else:
            return self.escalation_config[1]  # 第1次：原agent自修复
    
    def execute_escalation(self, error_signature: str, escalation: EscalationAction) -> bool:
        """执行错误升级行动"""
        start_time = time.time()
        
        logging.info(f"执行升级行动 Level-{escalation.level}: {escalation.action_description}")
        
        try:
            if escalation.level == 1:
                success = self._handle_self_fix(error_signature)
            elif escalation.level == 2:
                success = self._trigger_error_detective(error_signature)
            elif escalation.level == 3:
                success = self._trigger_debugger_architect(error_signature)
            else:
                logging.error(f"未知的升级级别: {escalation.level}")
                return False
            
            execution_time = time.time() - start_time
            
            # 记录升级历史
            self._record_escalation_history(
                error_signature, 
                escalation, 
                success, 
                execution_time
            )
            
            return success
            
        except Exception as e:
            logging.error(f"升级执行失败: {str(e)}")
            return False
    
    def _handle_self_fix(self, error_signature: str) -> bool:
        """处理自修复 (Level 1)"""
        logging.info("Level 1: 原Agent尝试自修复")
        # 返回允许原agent继续尝试
        return True
    
    def _trigger_error_detective(self, error_signature: str) -> bool:
        """触发错误侦探 (Level 2)"""
        logging.info("Level 2: 触发error-detective Agent")
        
        # 生成error-detective任务
        detective_task = {
            "agent_type": "error-detective",
            "error_signature": error_signature,
            "task_description": "深度分析错误模式，找出根本原因",
            "required_analysis": [
                "错误模式识别",
                "根因分析",
                "上下文线索收集", 
                "解决方案生成"
            ]
        }
        
        # 保存任务到队列文件
        task_file = Path(".claude/tasks/error_detective_queue.json")
        task_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(detective_task, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Error-detective任务已生成: {task_file}")
        return True
    
    def _trigger_debugger_architect(self, error_signature: str) -> bool:
        """触发调试器+架构师 (Level 3)"""
        logging.info("Level 3: 强制触发debugger + linus-architect")
        
        # 生成调试任务
        debug_task = {
            "agent_type": "debugger",
            "error_signature": error_signature,
            "escalation_level": 3,
            "forced_intervention": True,
            "task_description": "系统化调试，彻底解决问题",
            "required_actions": [
                "停止所有修复尝试",
                "保存完整状态",
                "建立调试基线",
                "系统化根因分析",
                "制定彻底解决方案"
            ]
        }
        
        # 生成架构审查任务
        architect_task = {
            "agent_type": "linus-architect",
            "error_signature": error_signature,
            "escalation_trigger": "repeated_failure",
            "task_description": "架构级问题分析",
            "review_scope": [
                "数据结构设计",
                "系统架构合理性",
                "复杂度分析",
                "设计哲学审查"
            ]
        }
        
        # 保存任务
        debug_file = Path(".claude/tasks/debugger_queue.json")
        architect_file = Path(".claude/tasks/architect_review_queue.json")
        
        for task, file_path in [(debug_task, debug_file), (architect_task, architect_file)]:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(task, f, ensure_ascii=False, indent=2)
        
        logging.warning("🚨 第3次错误触发 - 强制停止并深度分析")
        logging.info(f"Debug任务: {debug_file}")  
        logging.info(f"架构审查任务: {architect_file}")
        
        return True
    
    def _record_escalation_history(self, error_signature: str, 
                                 escalation: EscalationAction,
                                 success: bool, execution_time: float):
        """记录升级历史"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO escalation_history
                (error_signature, escalation_level, agent_type, action_taken,
                 success, execution_time_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                error_signature,
                escalation.level,
                escalation.agent_type,
                escalation.action_description,
                success,
                execution_time
            ))
            
            conn.commit()
    
    def process_error(self, error_message: str, file_path: str = "", 
                     function_name: str = "", stack_trace: str = "",
                     context: Dict[str, str] = None) -> Dict[str, any]:
        """处理错误的主入口函数"""
        
        if context is None:
            context = {}
        
        # 生成错误签名
        error_signature = self.generate_error_signature(
            error_message, file_path, function_name
        )
        
        # 创建错误事件
        error_event = ErrorEvent(
            error_signature=error_signature,
            error_message=error_message,
            file_path=file_path,
            function_name=function_name,
            timestamp=datetime.now(),
            stack_trace=stack_trace,
            context=context
        )
        
        # 记录错误事件
        error_id = self.record_error_event(error_event)
        
        # 判断是否需要升级
        escalation = self.should_escalate(error_signature)
        
        # 执行升级行动
        success = self.execute_escalation(error_signature, escalation)
        
        return {
            "error_id": error_id,
            "error_signature": error_signature,
            "escalation_level": escalation.level,
            "escalation_action": escalation.action_description,
            "agent_type": escalation.agent_type,
            "success": success,
            "occurrence_count": self.get_error_occurrence_count(error_signature)
        }
    
    def get_error_statistics(self) -> Dict[str, any]:
        """获取错误统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 总错误数
            cursor.execute("SELECT COUNT(*) FROM error_events")
            total_errors = cursor.fetchone()[0]
            
            # 24小时内错误数
            cutoff_time = datetime.now() - timedelta(hours=24)
            cursor.execute(
                "SELECT COUNT(*) FROM error_events WHERE timestamp > ?", 
                (cutoff_time,)
            )
            recent_errors = cursor.fetchone()[0]
            
            # 升级统计
            cursor.execute("""
                SELECT escalation_level, COUNT(*) as count
                FROM escalation_history 
                WHERE timestamp > ? 
                GROUP BY escalation_level
            """, (cutoff_time,))
            
            escalation_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 成功率统计
            cursor.execute("""
                SELECT escalation_level, 
                       AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
                FROM escalation_history 
                WHERE timestamp > ?
                GROUP BY escalation_level
            """, (cutoff_time,))
            
            success_rates = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_errors": total_errors,
                "recent_errors_24h": recent_errors,
                "escalation_distribution": escalation_stats,
                "success_rates_by_level": success_rates,
                "timestamp": datetime.now().isoformat()
            }


def main():
    """主函数 - 用于测试和命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="错误升级管理器")
    parser.add_argument('action', choices=['test', 'stats', 'process'], 
                       help='执行的操作')
    parser.add_argument('--error-message', help='错误信息')
    parser.add_argument('--file-path', help='文件路径') 
    parser.add_argument('--function-name', help='函数名称')
    
    args = parser.parse_args()
    
    manager = ErrorEscalationManager()
    
    if args.action == 'test':
        # 测试错误升级
        test_error = {
            "error_message": "TypeError: 'NoneType' object is not subscriptable",
            "file_path": "backend/app/services/reddit_scanner.py",
            "function_name": "process_post_data"
        }
        
        print("🧪 测试错误升级机制...")
        
        # 模拟3次相同错误
        for i in range(3):
            print(f"\n--- 第 {i+1} 次错误 ---")
            result = manager.process_error(**test_error)
            
            print(f"错误签名: {result['error_signature']}")
            print(f"升级级别: {result['escalation_level']}")
            print(f"处理Agent: {result['agent_type']}")
            print(f"升级行动: {result['escalation_action']}")
            print(f"累计发生次数: {result['occurrence_count']}")
            
            time.sleep(1)  # 模拟时间间隔
    
    elif args.action == 'stats':
        # 显示统计信息
        stats = manager.get_error_statistics()
        print("\n📊 错误升级统计报告")
        print("=" * 50)
        print(f"总错误数: {stats['total_errors']}")
        print(f"24小时内错误数: {stats['recent_errors_24h']}")
        print(f"升级分布: {stats['escalation_distribution']}")
        print(f"成功率: {stats['success_rates_by_level']}")
    
    elif args.action == 'process':
        # 处理具体错误
        if not args.error_message:
            print("❌ 处理错误需要提供 --error-message 参数")
            return
        
        result = manager.process_error(
            error_message=args.error_message,
            file_path=args.file_path or "",
            function_name=args.function_name or ""
        )
        
        print(f"✅ 错误处理完成: {result}")


if __name__ == "__main__":
    main()