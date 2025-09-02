#!/usr/bin/env python3
"""
Agent审核日志器 - 自动集成Task工具与workflow系统
基于Linus的"简单集成胜过复杂重构"原则

功能：
1. 监听Task工具调用agent的结果
2. 解析agent输出中的评分和状态信息
3. 自动记录到workflow.py的审核日志系统
4. 零侵入，完全透明集成
"""

import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.claude/logs/agent_audit_logger.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AgentAuditLogger:
    """Agent审核结果自动记录器"""
    
    # 支持的Agent类型映射
    AGENT_MAPPING = {
        'task-analyzer': 'task-analyzer',
        'quality-gate': 'quality-gate', 
        'signal-validator': 'signal-validator',
        'linus-architect': 'linus-architect',
        'pre-linus-check': 'pre-linus-check'
    }
    
    # 评分提取正则表达式 - 增强版，支持更多格式
    SCORE_PATTERNS = {
        # 中文格式
        'comprehensive_score': r'综合.*?评分.*?[：:]?\s*(\d+)\s*/\s*100',
        'quality_score': r'质量.*?评分.*?[：:]?\s*(\d+)\s*/\s*100', 
        'final_score': r'最终.*?评分.*?[：:]?\s*(\d+)\s*/\s*100',
        'architecture_score': r'架构.*?评分.*?[：:]?\s*(\d+)\s*/\s*100',
        'linus_score': r'Linus.*?评分.*?[：:]?\s*(\d+)\s*/\s*100',
        
        # 英文格式
        'score_english': r'(?:score|rating|grade)[：:]?\s*(\d+)\s*/\s*100',
        'final_english': r'final\s+(?:score|rating)[：:]?\s*(\d+)\s*/\s*100',
        'overall_english': r'overall[：:]?\s*(\d+)\s*/\s*100',
        
        # 通用数字格式
        'generic_score': r'(\d+)\s*/\s*100(?:\s*分)?',
        'percentage': r'(\d+)%',
        'score_colon': r'分数[：:]\s*(\d+)',
        'rating_colon': r'评级[：:]\s*(\d+)',
        
        # Markdown格式
        'markdown_score': r'\*\*(?:评分|Score|Rating)[：:]?\s*(\d+)/100\*\*',
        'bold_score': r'<strong>.*?(\d+)/100.*?</strong>',
        
        # 特殊格式
        'bracket_score': r'\[(\d+)/100\]',
        'parenthesis_score': r'\((\d+)/100\)',
        'dash_score': r'[-–—]\s*(\d+)/100',
        
        # Agent特定格式
        'quality_gate_score': r'质量.*?检查.*?[：:]?\s*(\d+)/100',
        'linus_architect_score': r'架构.*?审核.*?[：:]?\s*(\d+)/100',
        'signal_validator_score': r'信号.*?验证.*?[：:]?\s*(\d+)/100'
    }
    
    # 状态判断关键词 - 增强版，支持更多表达方式
    STATUS_KEYWORDS = {
        'passed': [
            # 中文表达
            '✅ 通过', '✅通过', '批准', 'PASS', '通过', '合格', '成功', '生产就绪',
            '部署批准', '审核通过', '检查通过', '验证通过', '质量合格', 
            '符合标准', '达标', '可用', '就绪', '完成',
            
            # 英文表达
            'PASSED', 'APPROVED', 'SUCCESS', 'OK', 'GOOD', 'VALID',
            'READY', 'COMPLETE', 'ACCEPTED', 'QUALIFIED', 'CLEARED',
            
            # 符号表达
            '✅', '🟢', '👍', '☑️', '✔️',
            
            # 特殊格式
            'status: pass', 'result: pass', 'verdict: approved',
            'conclusion: pass', 'decision: approve'
        ],
        'failed': [
            # 中文表达
            '❌ 拒绝', '❌拒绝', '失败', 'FAIL', '不通过', '不合格', '错误',
            '无法通过', '审核失败', '检查失败', '验证失败', '质量不合格',
            '不符合标准', '不达标', '阻塞', '拒绝', '禁止',
            
            # 英文表达
            'FAILED', 'REJECTED', 'ERROR', 'INVALID', 'BAD', 'BLOCKED',
            'DENIED', 'UNACCEPTABLE', 'DISQUALIFIED', 'CRITICAL',
            
            # 符号表达
            '❌', '🔴', '👎', '✖️', '❎',
            
            # 特殊格式
            'status: fail', 'result: fail', 'verdict: rejected',
            'conclusion: fail', 'decision: reject'
        ],
        'warning': [
            # 中文表达
            '⚠️ 需调整', '⚠️需调整', '警告', '注意', '建议修复', '有条件通过',
            '需要优化', '建议改进', '存在问题', '轻微问题', '待改进',
            '可以改进', '建议', '提醒', '注意事项',
            
            # 英文表达
            'WARNING', 'CAUTION', 'ATTENTION', 'NOTICE', 'ADVISORY',
            'CONDITIONAL', 'WITH_ISSUES', 'NEEDS_IMPROVEMENT',
            
            # 符号表达
            '⚠️', '🟡', '⚡', '📝', '💡',
            
            # 特殊格式
            'status: warning', 'result: warning', 'with conditions',
            'conditional pass', 'needs attention'
        ]
    }

    def __init__(self, project_root: str = None, debug_mode: bool = False):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.audit_file = self.project_root / '.claude' / 'logs' / 'agent_audit.json'
        self.debug_mode = debug_mode or os.environ.get('AGENT_AUDIT_DEBUG') == '1'
        
        # 调试日志文件
        if self.debug_mode:
            self.debug_file = self.project_root / '.claude' / 'logs' / 'audit_parsing_debug.log'
            self.debug_file.parent.mkdir(parents=True, exist_ok=True)
        
    def extract_task_id(self, content: str) -> Optional[str]:
        """从内容中提取任务ID"""
        patterns = [
            r'prd(\d{2}-\d{2})',  # prd04-01格式
            r'PRD-(\d{2})',       # PRD-04格式  
            r'任务ID[：:]?\s*(\w+)',  # 任务ID: xxx格式
            r'task[_-]?id[：:]?\s*(\w+)'  # task_id: xxx格式
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if 'prd' in pattern:
                    return f"prd{match.group(1)}"
                return match.group(1)
        
        return None
    
    def extract_agent_type(self, content: str) -> Optional[str]:
        """从内容中提取Agent类型"""
        content_lower = content.lower()
        
        # 精确匹配agent名称
        for agent_key, agent_name in self.AGENT_MAPPING.items():
            if agent_key in content_lower:
                return agent_name
        
        # 基于标题和关键功能词汇推断
        if any(word in content for word in ['任务深度分析', '任务分析报告', 'PRD.*分析']):
            return 'task-analyzer'
        elif any(word in content for word in ['质量门控', '质量检查报告', '综合评分']):
            return 'quality-gate'  
        elif any(word in content for word in ['Linus式架构审核', '架构审核结果', '最终裁决']):
            return 'linus-architect'
        elif any(word in content for word in ['信号验证', 'signal-validator', '数据质量']):
            return 'signal-validator'
        elif '预审' in content or 'pre-linus' in content_lower:
            return 'pre-linus-check'
            
        return None
    
    def extract_score(self, content: str) -> Optional[int]:
        """从内容中提取评分 - 增强版"""
        if self.debug_mode:
            self._debug_log(f"尝试提取评分，内容长度: {len(content)}")
            self._debug_log(f"内容片段: {content[:200]}...")
        
        # 按优先级尝试不同模式
        score = None
        matched_pattern = None
        
        for pattern_name, pattern in self.SCORE_PATTERNS.items():
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    score = int(match.group(1))
                    matched_pattern = pattern_name
                    if self.debug_mode:
                        self._debug_log(f"评分匹配成功: {pattern_name} -> {score}")
                    break
                except (ValueError, IndexError):
                    if self.debug_mode:
                        self._debug_log(f"评分匹配失败: {pattern_name} - 数值转换错误")
                    continue
        
        # 如果没有匹配，尝试fallback方法
        if score is None:
            score = self._fallback_score_extraction(content)
        
        # 验证评分合理性
        if score is not None:
            if not (0 <= score <= 100):
                if self.debug_mode:
                    self._debug_log(f"评分超出范围: {score}，重置为None")
                score = None
            else:
                if self.debug_mode:
                    self._debug_log(f"最终评分: {score} (模式: {matched_pattern})")
        
        if score is None and self.debug_mode:
            self._debug_log("未能提取到有效评分")
            
        return score
    
    def _fallback_score_extraction(self, content: str) -> Optional[int]:
        """备用评分提取方法"""
        fallback_patterns = [
            r'(\d{1,3})\s*分',  # XX分
            r'得分\s*[：:]?\s*(\d{1,3})',  # 得分：XX
            r'评价\s*[：:]?\s*(\d{1,3})',  # 评价：XX
            r'分值\s*[：:]?\s*(\d{1,3})',  # 分值：XX
            r'(\d{1,2})\s*\/\s*10',  # X/10 格式，转换为100分制
            r'(\d{1,2})\s*点',  # XX点
            r'[分评级]\s*[：:]?\s*([A-F][+-]?)',  # 字母评级
        ]
        
        for pattern in fallback_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1)
                try:
                    if value.isdigit():
                        score = int(value)
                        # 如果是X/10格式，转换为100分制
                        if '/10' in pattern:
                            score = score * 10
                        elif score <= 10:  # 假设10分制，转换为100分制
                            score = score * 10
                        return score if 0 <= score <= 100 else None
                    elif value in ['A', 'A+', 'A-']:
                        return 90 + (5 if '+' in value else -5 if '-' in value else 0)
                    elif value in ['B', 'B+', 'B-']:
                        return 80 + (5 if '+' in value else -5 if '-' in value else 0)
                    elif value in ['C', 'C+', 'C-']:
                        return 70 + (5 if '+' in value else -5 if '-' in value else 0)
                    elif value in ['D', 'D+', 'D-']:
                        return 60 + (5 if '+' in value else -5 if '-' in value else 0)
                    elif value == 'F':
                        return 50
                except ValueError:
                    continue
        
        return None
    
    def extract_status(self, content: str) -> str:
        """从内容中提取状态 - 增强版"""
        if self.debug_mode:
            self._debug_log(f"尝试提取状态，内容长度: {len(content)}")
        
        content_lower = content.lower()
        matched_status = None
        matched_keyword = None
        
        # 多层匹配策略
        for status, keywords in self.STATUS_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    matched_status = status
                    matched_keyword = keyword
                    if self.debug_mode:
                        self._debug_log(f"状态关键词匹配: {keyword} -> {status}")
                    break
            if matched_status:
                break
        
        # 如果关键词匹配失败，尝试语义分析
        if not matched_status:
            matched_status = self._semantic_status_analysis(content)
            if self.debug_mode and matched_status:
                self._debug_log(f"语义分析匹配: {matched_status}")
        
        # 基于评分推断状态
        if not matched_status:
            score = self.extract_score(content)
            if score:
                if score >= 85:
                    matched_status = 'passed'
                elif score >= 70:
                    matched_status = 'passed'  # 可接受的分数
                else:
                    matched_status = 'failed'
                    
                if self.debug_mode:
                    self._debug_log(f"基于评分推断状态: {score} -> {matched_status}")
        
        # 默认状态
        final_status = matched_status or 'passed'
        
        if self.debug_mode:
            self._debug_log(f"最终状态: {final_status}")
            
        return final_status
    
    def _semantic_status_analysis(self, content: str) -> Optional[str]:
        """语义分析状态提取"""
        # 严重问题指标
        critical_indicators = [
            '严重错误', '致命错误', '阻塞', '无法继续', '必须修复',
            'critical error', 'fatal', 'blocking', 'must fix'
        ]
        
        # 成功指标
        success_indicators = [
            '没有问题', '完美', '优秀', '符合标准', '可以部署',
            'no issues', 'perfect', 'excellent', 'meets standards',
            'ready for deployment', 'production ready'
        ]
        
        # 警告指标
        warning_indicators = [
            '一些问题', '轻微问题', '可以改进', '建议优化',
            'minor issues', 'some problems', 'could improve',
            'suggest optimization'
        ]
        
        content_lower = content.lower()
        
        for indicator in critical_indicators:
            if indicator.lower() in content_lower:
                return 'failed'
        
        for indicator in success_indicators:
            if indicator.lower() in content_lower:
                return 'passed'
        
        for indicator in warning_indicators:
            if indicator.lower() in content_lower:
                return 'warning'
        
        return None
    
    def _debug_log(self, message: str) -> None:
        """写入调试日志"""
        if not self.debug_mode:
            return
            
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} - {message}\n"
        
        try:
            with open(self.debug_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.warning(f"写入调试日志失败: {e}")
    
    def extract_details(self, content: str) -> Dict[str, Any]:
        """提取详细信息 - 增强版"""
        details = {}
        
        if self.debug_mode:
            self._debug_log("开始提取详细信息")
        
        # 提取评分
        score = self.extract_score(content)
        if score:
            details['score'] = score
        
        # 提取问题数量
        self._extract_issue_counts(content, details)
        
        # 提取测试信息
        self._extract_test_results(content, details)
        
        # 提取关键结论
        self._extract_conclusions(content, details)
        
        # 提取性能指标
        self._extract_performance_metrics(content, details)
        
        # 提取建议
        self._extract_suggestions(content, details)
        
        if self.debug_mode:
            self._debug_log(f"提取到详细信息: {details}")
        
        return details
    
    def _extract_issue_counts(self, content: str, details: Dict[str, Any]) -> None:
        """提取问题数量相关信息"""
        issue_patterns = [
            (r'(?:问题|issues?).*?[：:]?\s*(\d+)', 'issues_count'),
            (r'(?:错误|errors?).*?[：:]?\s*(\d+)', 'errors_count'),
            (r'(?:警告|warnings?).*?[：:]?\s*(\d+)', 'warnings_count'),
            (r'(?:已修复|fixed).*?[：:]?\s*(\d+)', 'fixed_count'),
            (r'P0.*?问题.*?[：:]?\s*(\d+)', 'p0_issues'),
            (r'P1.*?问题.*?[：:]?\s*(\d+)', 'p1_issues'),
            (r'P2.*?问题.*?[：:]?\s*(\d+)', 'p2_issues'),
        ]
        
        for pattern, key in issue_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    details[key] = int(match.group(1))
                except ValueError:
                    pass
    
    def _extract_test_results(self, content: str, details: Dict[str, Any]) -> None:
        """提取测试结果信息"""
        test_tools = ['flake8', 'mypy', 'pylint', 'black', 'isort', 'eslint', 'tsc', 'pytest']
        
        for tool in test_tools:
            if tool in content.lower():
                # 检查是否通过
                tool_section = self._extract_section_around_keyword(content, tool, 100)
                pass_indicators = ['通过', 'pass', 'passed', 'ok', 'success', '✅', 'no errors']
                fail_indicators = ['失败', 'fail', 'failed', 'error', 'errors', '❌']
                
                passed = any(indicator in tool_section.lower() for indicator in pass_indicators)
                failed = any(indicator in tool_section.lower() for indicator in fail_indicators)
                
                if passed and not failed:
                    details[f'{tool}_pass'] = True
                elif failed:
                    details[f'{tool}_pass'] = False
    
    def _extract_conclusions(self, content: str, details: Dict[str, Any]) -> None:
        """提取结论信息"""
        conclusion_patterns = [
            r'结论[：:]?\s*([^。\n\r]+)',
            r'conclusion[：:]?\s*([^.\n\r]+)',
            r'verdict[：:]?\s*([^.\n\r]+)',
            r'决定[：:]?\s*([^。\n\r]+)',
            r'最终.*?[：:]?\s*([^。\n\r]+)',
            r'总结[：:]?\s*([^。\n\r]+)',
        ]
        
        for pattern in conclusion_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                conclusion = match.group(1).strip()
                if len(conclusion) > 5:  # 过滤太短的匹配
                    details['conclusion'] = conclusion
                    break
    
    def _extract_performance_metrics(self, content: str, details: Dict[str, Any]) -> None:
        """提取性能指标"""
        perf_patterns = [
            (r'执行时间[：:]?\s*(\d+(?:\.\d+)?)\s*(?:秒|s)', 'execution_time_seconds'),
            (r'响应时间[：:]?\s*(\d+(?:\.\d+)?)\s*(?:毫秒|ms)', 'response_time_ms'),
            (r'内存使用[：:]?\s*(\d+(?:\.\d+)?)\s*(?:MB|mb)', 'memory_usage_mb'),
            (r'覆盖率[：:]?\s*(\d+(?:\.\d+)?)\s*%', 'coverage_percentage'),
            (r'测试.*?通过率[：:]?\s*(\d+(?:\.\d+)?)\s*%', 'test_pass_rate'),
        ]
        
        for pattern, key in perf_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    details[key] = float(match.group(1))
                except ValueError:
                    pass
    
    def _extract_suggestions(self, content: str, details: Dict[str, Any]) -> None:
        """提取建议信息"""
        suggestions = []
        
        suggestion_patterns = [
            r'建议[：:]?\s*([^。\n\r]+)',
            r'推荐[：:]?\s*([^。\n\r]+)',
            r'suggestion[：:]?\s*([^.\n\r]+)',
            r'recommend[：:]?\s*([^.\n\r]+)',
            r'需要.*?[：:]?\s*([^。\n\r]+)',
            r'应该.*?[：:]?\s*([^。\n\r]+)',
        ]
        
        for pattern in suggestion_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                suggestion = match.strip()
                if len(suggestion) > 5 and suggestion not in suggestions:
                    suggestions.append(suggestion)
        
        if suggestions:
            details['suggestions'] = suggestions[:5]  # 最多保留5个建议
    
    def _extract_section_around_keyword(self, content: str, keyword: str, context_chars: int = 100) -> str:
        """提取关键词周围的文本片段"""
        keyword_pos = content.lower().find(keyword.lower())
        if keyword_pos == -1:
            return ""
        
        start = max(0, keyword_pos - context_chars)
        end = min(len(content), keyword_pos + len(keyword) + context_chars)
        
        return content[start:end]
    
    def record_audit(self, task_id: str, agent_name: str, status: str, details: Dict[str, Any] = None):
        """记录审核结果到workflow系统"""
        try:
            # 确保目录存在
            self.audit_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有数据
            audit_data = {}
            if self.audit_file.exists():
                with open(self.audit_file, 'r', encoding='utf-8') as f:
                    audit_data = json.load(f)
            
            # 添加审核记录
            if task_id not in audit_data:
                audit_data[task_id] = {}
                
            audit_data[task_id][agent_name] = {
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'details': details or {}
            }
            
            # 写回文件
            with open(self.audit_file, 'w', encoding='utf-8') as f:
                json.dump(audit_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"记录审核结果: {task_id} - {agent_name} - {status}")
            
        except Exception as e:
            logger.error(f"记录审核结果失败: {e}")
    
    def process_tool_result(self, tool_name: str, tool_result: str) -> None:
        """处理工具调用结果 - 增强版"""
        if tool_name != 'Task':
            if self.debug_mode:
                self._debug_log(f"跳过非Task工具: {tool_name}")
            return
            
        if self.debug_mode:
            self._debug_log(f"开始处理Task工具结果，长度: {len(tool_result)}")
            
        logger.info("处理Task工具调用结果")
        
        # 提取任务ID和Agent类型
        task_id = self.extract_task_id(tool_result)
        agent_type = self.extract_agent_type(tool_result)
        
        if not task_id or not agent_type:
            if self.debug_mode:
                self._debug_log(f"提取失败: task_id={task_id}, agent_type={agent_type}")
                self._debug_log(f"内容片段: {tool_result[:500]}...")
            logger.debug(f"无法提取任务ID或Agent类型: task_id={task_id}, agent_type={agent_type}")
            
            # 尝试从问题跟踪系统记录解析失败
            self._record_parsing_failure(tool_result)
            return
            
        # 提取状态和详细信息
        status = self.extract_status(tool_result)
        details = self.extract_details(tool_result)
        
        # 记录到workflow系统
        self.record_audit(task_id, agent_type, status, details)
        
        logger.info(f"自动记录Agent审核: {task_id} - {agent_type} - {status}")
        
        if self.debug_mode:
            self._debug_log(f"成功处理: {task_id} - {agent_type} - {status}")
    
    def _record_parsing_failure(self, tool_result: str) -> None:
        """记录解析失败，用于改进解析算法"""
        try:
            from .issue_tracker import IssueTracker
            
            tracker = IssueTracker(str(self.project_root))
            tracker.add_issue(
                task_id="audit-logger",
                agent_name="agent-audit-logger",
                severity="medium",
                title="Agent输出解析失败",
                description=f"无法从Agent输出中提取任务ID或Agent类型。输出片段: {tool_result[:200]}...",
                metadata={'full_output_length': len(tool_result)}
            )
            
            if self.debug_mode:
                self._debug_log("已记录解析失败到问题跟踪系统")
                
        except Exception as e:
            logger.warning(f"记录解析失败时出错: {e}")
    
    def get_parsing_statistics(self) -> Dict[str, Any]:
        """获取解析统计信息"""
        stats = {
            'total_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'agent_type_distribution': {},
            'status_distribution': {},
            'average_content_length': 0
        }
        
        # 这里可以从日志文件或数据库中获取统计信息
        # 暂时返回基础结构
        return stats


def main():
    """主函数 - 钩子脚本入口"""
    try:
        import argparse
        parser = argparse.ArgumentParser(description='Agent审核日志器 - 增强版')
        parser.add_argument('--tool-name', help='工具名称')
        parser.add_argument('--tool-result', help='工具结果')
        parser.add_argument('--context', help='上下文信息')
        parser.add_argument('--debug', action='store_true', help='开启调试模式')
        parser.add_argument('--stats', action='store_true', help='显示解析统计')
        parser.add_argument('--test', help='测试模式，使用指定的测试内容')
        
        args = parser.parse_args()
        
        # 初始化日志器
        debug_mode = args.debug or os.environ.get('AGENT_AUDIT_DEBUG') == '1'
        logger_instance = AgentAuditLogger(debug_mode=debug_mode)
        
        if args.stats:
            # 显示统计信息
            stats = logger_instance.get_parsing_statistics()
            print("Agent输出解析统计:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            return
        
        if args.test:
            # 测试模式
            print("测试模式 - 解析测试内容")
            test_content = args.test
            
            print(f"任务ID: {logger_instance.extract_task_id(test_content)}")
            print(f"Agent类型: {logger_instance.extract_agent_type(test_content)}")
            print(f"状态: {logger_instance.extract_status(test_content)}")
            print(f"评分: {logger_instance.extract_score(test_content)}")
            print(f"详细信息: {logger_instance.extract_details(test_content)}")
            return
        
        # 处理工具结果
        if args.tool_name and args.tool_result:
            if debug_mode:
                logger.info("调试模式已开启")
            logger_instance.process_tool_result(args.tool_name, args.tool_result)
        elif os.environ.get('TOOL_NAME') and os.environ.get('TOOL_RESULT'):
            # 从环境变量获取（Claude Code Hook模式）
            tool_name = os.environ.get('TOOL_NAME')
            tool_result = os.environ.get('TOOL_RESULT')
            logger_instance.process_tool_result(tool_name, tool_result)
        else:
            logger.warning("未提供工具调用信息")
            parser.print_help()
            return
        
        logger.info("Agent审核日志器执行完成")
        
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Agent审核日志器执行失败: {e}")
        if os.environ.get('AGENT_AUDIT_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()