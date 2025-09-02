#!/usr/bin/env python3
"""
智能错误路由器 - 替代复杂的3次升级机制
基于Linus的"理解错误优于计数错误"哲学

功能：
1. 智能错误分类 - 基于错误内容和上下文分类
2. 最佳Agent选择 - 根据错误类型选择最合适的处理Agent
3. 解决方案推荐 - 基于历史成功案例推荐解决方案
4. 简化的升级策略 - 去掉计数逻辑，改为智能判断
"""

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.claude/logs/intelligent_error_router.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class ErrorContext:
    """错误上下文信息"""
    error_message: str
    error_type: str  # syntax, runtime, logic, integration, performance
    severity: str   # low, medium, high, critical
    source_file: Optional[str] = None
    function_name: Optional[str] = None
    stack_trace: Optional[str] = None
    previous_attempts: List[str] = None
    
    def __post_init__(self):
        if self.previous_attempts is None:
            self.previous_attempts = []

@dataclass
class RoutingDecision:
    """路由决策结果"""
    recommended_agent: str
    confidence: float  # 0.0-1.0
    reasoning: str
    alternative_agents: List[str]
    estimated_complexity: str  # simple, moderate, complex
    recommended_timeout: int  # 秒

class IntelligentErrorRouter:
    """智能错误路由器"""
    
    # 错误模式匹配规则
    ERROR_PATTERNS = {
        'syntax': [
            r'SyntaxError', r'IndentationError', r'TabError',
            r'语法错误', r'缩进错误', r'unexpected token'
        ],
        'import': [
            r'ImportError', r'ModuleNotFoundError', r'No module named',
            r'导入错误', r'模块未找到', r'cannot import'
        ],
        'type': [
            r'TypeError', r'AttributeError', r'NameError',
            r'类型错误', r'属性错误', r'名称错误'
        ],
        'value': [
            r'ValueError', r'KeyError', r'IndexError',
            r'值错误', r'键错误', r'索引错误'
        ],
        'runtime': [
            r'RuntimeError', r'SystemError', r'MemoryError',
            r'运行时错误', r'系统错误', r'内存错误'
        ],
        'network': [
            r'ConnectionError', r'TimeoutError', r'HTTPError',
            r'网络错误', r'连接超时', r'HTTP错误'
        ],
        'database': [
            r'DatabaseError', r'IntegrityError', r'OperationalError',
            r'数据库错误', r'完整性错误', r'操作错误'
        ],
        'permission': [
            r'PermissionError', r'FileNotFoundError', r'OSError',
            r'权限错误', r'文件未找到', r'系统错误'
        ]
    }
    
    # Agent专业领域映射
    AGENT_SPECIALTIES = {
        'quality-gate': {
            'specialties': ['syntax', 'type', 'import', 'style'],
            'confidence_boost': 0.8,
            'typical_timeout': 180,
            'description': '代码质量检查专家，擅长语法、类型、导入错误'
        },
        'error-detective': {
            'specialties': ['runtime', 'logic', 'integration'],
            'confidence_boost': 0.9,
            'typical_timeout': 600,
            'description': '错误侦探，擅长运行时错误和逻辑问题分析'
        },
        'debugger': {
            'specialties': ['complex', 'critical', 'system'],
            'confidence_boost': 0.95,
            'typical_timeout': 900,
            'description': '专业调试器，处理复杂和关键错误'
        },
        'linus-architect': {
            'specialties': ['architecture', 'design', 'performance'],
            'confidence_boost': 0.7,
            'typical_timeout': 450,
            'description': '架构专家，处理设计和性能问题'
        },
        'signal-validator': {
            'specialties': ['data', 'network', 'api'],
            'confidence_boost': 0.8,
            'typical_timeout': 240,
            'description': '信号验证专家，处理数据和网络问题'
        },
        'config-sync': {
            'specialties': ['config', 'permission', 'environment'],
            'confidence_boost': 0.6,
            'typical_timeout': 120,
            'description': '配置专家，处理环境和权限问题'
        }
    }
    
    def __init__(self):
        self.logger = logging.getLogger('IntelligentErrorRouter')
        self.routing_history: List[Dict] = []
        self.success_patterns: Dict[str, List[str]] = {}
        self.load_success_patterns()
    
    def classify_error(self, error_message: str, context: Dict[str, Any] = None) -> ErrorContext:
        """智能错误分类"""
        self.logger.info("开始错误分类分析")
        
        # 1. 识别错误类型
        error_type = self._identify_error_type(error_message)
        
        # 2. 评估严重程度
        severity = self._assess_severity(error_message, context)
        
        # 3. 提取上下文信息
        source_file = context.get('file_path') if context else None
        function_name = context.get('function_name') if context else None
        stack_trace = context.get('stack_trace') if context else None
        
        return ErrorContext(
            error_message=error_message,
            error_type=error_type,
            severity=severity,
            source_file=source_file,
            function_name=function_name,
            stack_trace=stack_trace
        )
    
    def route_to_best_agent(self, error_context: ErrorContext) -> RoutingDecision:
        """路由到最佳Agent"""
        self.logger.info(f"为{error_context.error_type}错误选择最佳Agent")
        
        # 1. 计算每个Agent的适合度分数
        agent_scores = self._calculate_agent_scores(error_context)
        
        # 2. 选择最佳Agent
        best_agent = max(agent_scores.items(), key=lambda x: x[1])
        recommended_agent, confidence = best_agent
        
        # 3. 获取备选Agent
        alternative_agents = sorted(
            [agent for agent, score in agent_scores.items() if agent != recommended_agent],
            key=lambda x: agent_scores[x],
            reverse=True
        )[:2]  # 取前2个备选
        
        # 4. 评估复杂度和超时时间
        complexity = self._assess_complexity(error_context)
        timeout = self._estimate_timeout(recommended_agent, complexity)
        
        # 5. 生成推理说明
        reasoning = self._generate_reasoning(error_context, recommended_agent, confidence)
        
        return RoutingDecision(
            recommended_agent=recommended_agent,
            confidence=confidence,
            reasoning=reasoning,
            alternative_agents=alternative_agents,
            estimated_complexity=complexity,
            recommended_timeout=timeout
        )
    
    def suggest_resolution_strategy(self, error_context: ErrorContext, 
                                  routing_decision: RoutingDecision) -> Dict[str, Any]:
        """建议解决策略"""
        self.logger.info("生成解决策略建议")
        
        # 1. 查找类似的成功案例
        similar_cases = self._find_similar_success_cases(error_context)
        
        # 2. 生成具体建议
        strategy = {
            'primary_approach': self._get_primary_approach(error_context, routing_decision),
            'specific_steps': self._generate_specific_steps(error_context),
            'fallback_options': self._get_fallback_options(routing_decision),
            'similar_success_cases': similar_cases,
            'estimated_effort': self._estimate_effort(error_context),
            'success_probability': self._estimate_success_probability(error_context, routing_decision)
        }
        
        return strategy
    
    def execute_intelligent_routing(self, error_message: str, 
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行智能路由 - 主入口函数"""
        start_time = time.time()
        
        try:
            self.logger.info("开始智能错误路由")
            
            # 1. 错误分类
            error_context = self.classify_error(error_message, context)
            
            # 2. Agent路由
            routing_decision = self.route_to_best_agent(error_context)
            
            # 3. 策略建议
            resolution_strategy = self.suggest_resolution_strategy(error_context, routing_decision)
            
            # 4. 生成最终结果
            result = {
                'error_analysis': asdict(error_context),
                'routing_decision': asdict(routing_decision),
                'resolution_strategy': resolution_strategy,
                'routing_time': time.time() - start_time,
                'timestamp': time.time()
            }
            
            # 5. 记录路由历史
            self._record_routing_history(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"智能路由失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'routing_time': time.time() - start_time
            }
    
    # === 私有方法 ===
    
    def _identify_error_type(self, error_message: str) -> str:
        """识别错误类型"""
        error_message_lower = error_message.lower()
        
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern.lower(), error_message_lower):
                    return error_type
        
        # 默认分类
        if 'error' in error_message_lower or '错误' in error_message_lower:
            return 'runtime'
        else:
            return 'unknown'
    
    def _assess_severity(self, error_message: str, context: Dict[str, Any] = None) -> str:
        """评估错误严重程度"""
        critical_keywords = ['critical', '关键', 'fatal', '致命', 'crash', '崩溃']
        high_keywords = ['error', '错误', 'exception', '异常', 'failed', '失败']
        medium_keywords = ['warning', '警告', 'deprecated', '废弃']
        
        error_lower = error_message.lower()
        
        if any(keyword in error_lower for keyword in critical_keywords):
            return 'critical'
        elif any(keyword in error_lower for keyword in high_keywords):
            return 'high'
        elif any(keyword in error_lower for keyword in medium_keywords):
            return 'medium'
        else:
            return 'low'
    
    def _calculate_agent_scores(self, error_context: ErrorContext) -> Dict[str, float]:
        """计算Agent适合度分数"""
        scores = {}
        
        for agent_name, config in self.AGENT_SPECIALTIES.items():
            base_score = 0.3  # 基础分数
            
            # 专业领域匹配
            if error_context.error_type in config['specialties']:
                base_score += config['confidence_boost']
            
            # 严重程度匹配
            if error_context.severity == 'critical' and agent_name == 'debugger':
                base_score += 0.2
            elif error_context.severity == 'high' and agent_name == 'error-detective':
                base_score += 0.15
            elif error_context.severity in ['low', 'medium'] and agent_name == 'quality-gate':
                base_score += 0.1
            
            # 历史成功率调整
            historical_bonus = self._get_historical_success_bonus(agent_name, error_context.error_type)
            base_score += historical_bonus
            
            scores[agent_name] = min(base_score, 1.0)  # 限制在1.0以内
        
        return scores
    
    def _assess_complexity(self, error_context: ErrorContext) -> str:
        """评估错误复杂度"""
        if error_context.severity == 'critical':
            return 'complex'
        elif error_context.error_type in ['syntax', 'import', 'type']:
            return 'simple'
        elif error_context.error_type in ['runtime', 'network', 'database']:
            return 'moderate'
        else:
            return 'moderate'
    
    def _estimate_timeout(self, agent_name: str, complexity: str) -> int:
        """估算超时时间"""
        base_timeout = self.AGENT_SPECIALTIES[agent_name]['typical_timeout']
        
        multipliers = {
            'simple': 0.8,
            'moderate': 1.0,
            'complex': 1.5
        }
        
        return int(base_timeout * multipliers.get(complexity, 1.0))
    
    def _generate_reasoning(self, error_context: ErrorContext, agent_name: str, confidence: float) -> str:
        """生成推理说明"""
        agent_desc = self.AGENT_SPECIALTIES[agent_name]['description']
        
        reasoning = f"选择{agent_name}处理{error_context.error_type}类型的{error_context.severity}级错误。"
        reasoning += f"该Agent是{agent_desc}，"
        reasoning += f"对此类错误的处理信心度为{confidence:.1%}。"
        
        if error_context.severity == 'critical':
            reasoning += "由于错误级别为关键，建议立即处理。"
        
        return reasoning
    
    def _get_primary_approach(self, error_context: ErrorContext, routing_decision: RoutingDecision) -> str:
        """获取主要解决方法"""
        approaches = {
            'syntax': '检查语法错误，验证代码格式和缩进',
            'import': '验证模块导入路径，检查依赖安装',
            'type': '检查数据类型匹配，验证变量定义',
            'value': '验证输入值范围，检查数据有效性',
            'runtime': '分析执行环境，检查运行时条件',
            'network': '验证网络连接，检查API端点状态',
            'database': '检查数据库连接，验证查询语句',
            'permission': '验证文件权限，检查目录访问权限'
        }
        
        return approaches.get(error_context.error_type, '进行系统性错误分析和调试')
    
    def _generate_specific_steps(self, error_context: ErrorContext) -> List[str]:
        """生成具体步骤"""
        steps_map = {
            'syntax': [
                '使用代码检查工具验证语法',
                '检查括号、引号匹配',
                '验证缩进一致性'
            ],
            'import': [
                '检查模块安装状态',
                '验证导入路径正确性',
                '确认Python环境配置'
            ],
            'runtime': [
                '分析错误堆栈跟踪',
                '检查相关变量状态',
                '验证执行环境条件'
            ]
        }
        
        return steps_map.get(error_context.error_type, ['进行系统性错误分析'])
    
    def _get_fallback_options(self, routing_decision: RoutingDecision) -> List[str]:
        """获取备用选项"""
        fallback = []
        
        for alt_agent in routing_decision.alternative_agents:
            desc = self.AGENT_SPECIALTIES[alt_agent]['description']
            fallback.append(f"如果{routing_decision.recommended_agent}无法解决，尝试{alt_agent}: {desc}")
        
        fallback.append("最后选项：人工分析和调试")
        
        return fallback
    
    def _find_similar_success_cases(self, error_context: ErrorContext) -> List[str]:
        """查找类似的成功案例"""
        # 这里可以集成历史成功案例数据库
        # 目前返回模拟数据
        return [
            f"类似的{error_context.error_type}错误在95%的情况下可以通过代码检查解决",
            f"{error_context.severity}级错误通常需要15-30分钟处理时间"
        ]
    
    def _estimate_effort(self, error_context: ErrorContext) -> str:
        """估算解决工作量"""
        effort_map = {
            ('simple', 'low'): '5-15分钟',
            ('simple', 'medium'): '15-30分钟',
            ('moderate', 'high'): '30-60分钟',
            ('complex', 'critical'): '1-3小时'
        }
        
        complexity = self._assess_complexity(error_context)
        key = (complexity, error_context.severity)
        
        return effort_map.get(key, '30-60分钟')
    
    def _estimate_success_probability(self, error_context: ErrorContext, 
                                    routing_decision: RoutingDecision) -> float:
        """估算成功概率"""
        base_probability = 0.7  # 基础成功率
        
        # 根据Agent信心度调整
        base_probability += routing_decision.confidence * 0.2
        
        # 根据错误类型调整
        type_multipliers = {
            'syntax': 0.95,
            'import': 0.9,
            'type': 0.85,
            'runtime': 0.75,
            'network': 0.7,
            'database': 0.65
        }
        
        multiplier = type_multipliers.get(error_context.error_type, 0.8)
        return min(base_probability * multiplier, 0.95)
    
    def _get_historical_success_bonus(self, agent_name: str, error_type: str) -> float:
        """获取历史成功率加成"""
        # 模拟历史数据，实际实现时从数据库读取
        historical_data = {
            ('quality-gate', 'syntax'): 0.1,
            ('error-detective', 'runtime'): 0.15,
            ('debugger', 'complex'): 0.2
        }
        
        return historical_data.get((agent_name, error_type), 0.0)
    
    def _record_routing_history(self, result: Dict[str, Any]):
        """记录路由历史"""
        self.routing_history.append(result)
        
        # 保存到文件
        history_file = Path('.claude/logs/routing_history.jsonl')
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    def load_success_patterns(self):
        """加载成功模式（从历史数据）"""
        # 实际实现时从数据库或文件加载
        self.success_patterns = {
            'syntax': ['代码格式化', '语法检查工具'],
            'import': ['依赖安装', '路径修正'],
            'runtime': ['环境检查', '变量验证']
        }

def main():
    """主函数 - 支持命令行调用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='智能错误路由器')
    parser.add_argument('--error-message', help='错误消息')
    parser.add_argument('--context-file', help='上下文信息JSON文件')
    parser.add_argument('--action', choices=['route', 'stats'], default='route')
    
    args = parser.parse_args()
    
    router = IntelligentErrorRouter()
    
    if args.action == 'route':
        if args.error_message:
            # 加载上下文
            context = {}
            if args.context_file and Path(args.context_file).exists():
                with open(args.context_file, 'r', encoding='utf-8') as f:
                    context = json.load(f)
            
            # 执行路由
            result = router.execute_intelligent_routing(args.error_message, context)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("请提供错误消息: --error-message 'your error message'")
    
    elif args.action == 'stats':
        print(f"路由历史记录: {len(router.routing_history)}条")
        if router.routing_history:
            latest = router.routing_history[-1]
            print(f"最近路由: {latest['routing_decision']['recommended_agent']}")

if __name__ == '__main__':
    main()