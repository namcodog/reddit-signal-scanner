#!/usr/bin/env python3
"""
Agent基础类 - Reddit Signal Scanner

为所有Agent提供统一的模型配置、参数解析和执行框架。
基于Linus Torvalds的简洁原则：统一接口，消除重复。

使用方式:
    class MyAgent(AgentBase):
        def execute(self, **kwargs):
            # 具体实现
            pass
"""

import sys
import argparse
import yaml
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

class AgentBase(ABC):
    """Agent基础类，提供统一的配置和执行框架"""
    
    def __init__(self, name: str):
        self.name = name
        self.model = None
        self.config = {}
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """设置日志记录"""
        logger = logging.getLogger(f"agent.{self.name}")
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
            
        logger.setLevel(logging.INFO)
        
        # 控制台输出
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            f'[{self.name}] %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 文件输出
        log_dir = Path(".claude/logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / f"{self.name}.log")
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """解析命令行参数"""
        parser = argparse.ArgumentParser(
            description=f"{self.name} Agent - Reddit Signal Scanner"
        )
        
        # 标准参数
        parser.add_argument(
            '--model', 
            default='claude-3-haiku',
            help='要使用的AI模型 (default: claude-3-haiku)'
        )
        parser.add_argument(
            '--config',
            type=str,
            help='Agent配置文件路径'
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='启用严格模式'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='启用调试模式'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            help='执行超时时间(秒)'
        )
        
        # Agent特定参数
        self._add_custom_args(parser)
        
        return parser.parse_args(args)
    
    def _add_custom_args(self, parser: argparse.ArgumentParser):
        """子类可以重写此方法添加自定义参数"""
        pass
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载Agent配置"""
        if not config_path:
            # 默认配置文件路径
            config_path = Path(".claude/agent-config.yaml")
        else:
            config_path = Path(config_path)
            
        if not config_path.exists():
            self.logger.warning(f"配置文件不存在: {config_path}")
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f) or {}
                
            # 获取此Agent的特定配置
            agent_config = full_config.get('agents', {}).get(self.name, {})
            defaults = full_config.get('defaults', {})
            
            # 合并默认配置和Agent特定配置
            config = {**defaults, **agent_config}
            
            self.logger.info(f"已加载配置: {len(config)}个参数")
            return config
            
        except Exception as e:
            self.logger.error(f"配置文件加载失败: {e}")
            return {}
    
    def get_model_config(self) -> Dict[str, Any]:
        """获取模型配置"""
        model_configs = {
            'claude-3-haiku': {
                'max_tokens': 4096,
                'temperature': 0.1,
                'cost_per_token': 0.00025,  # 示例价格
                'speed': 'fast'
            },
            'claude-3-sonnet': {
                'max_tokens': 4096,
                'temperature': 0.1,
                'cost_per_token': 0.003,
                'speed': 'medium'
            },
            'claude-3-opus': {
                'max_tokens': 4096,
                'temperature': 0.1,
                'cost_per_token': 0.015,
                'speed': 'slow'
            }
        }
        
        return model_configs.get(self.model, model_configs['claude-3-haiku'])
    
    def call_ai_model(self, prompt: str, context: Optional[str] = None) -> str:
        """调用AI模型（模拟实现）"""
        model_config = self.get_model_config()
        
        self.logger.info(f"使用模型: {self.model}")
        self.logger.debug(f"提示词长度: {len(prompt)}字符")
        
        # 这里应该实际调用AI模型
        # 目前返回模拟响应
        return f"[{self.model}] AI分析结果：已处理提示词（{len(prompt)}字符）"
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """主执行方法"""
        try:
            # 解析参数
            parsed_args = self.parse_args(args)
            
            # 设置调试模式
            if parsed_args.debug:
                self.logger.setLevel(logging.DEBUG)
                
            # 设置模型
            self.model = parsed_args.model
            
            # 加载配置
            self.config = self.load_config(parsed_args.config)
            
            # 从配置中覆盖模型设置
            if 'model' in self.config:
                self.model = self.config['model']
                self.logger.info(f"从配置文件设置模型: {self.model}")
            
            # 记录执行开始
            self.logger.info(f"开始执行 Agent: {self.name}")
            self.logger.debug(f"参数: {vars(parsed_args)}")
            
            # 执行具体逻辑
            result = self.execute(parsed_args)
            
            # 记录执行结果
            if result == 0:
                self.logger.info("执行成功")
            elif result == 1:
                self.logger.error("执行失败")
            else:
                self.logger.warning("执行完成但有警告")
                
            return result
            
        except KeyboardInterrupt:
            self.logger.info("用户中断执行")
            return 1
        except Exception as e:
            self.logger.error(f"执行过程中发生错误: {e}")
            if hasattr(self, 'logger') and self.logger.level == logging.DEBUG:
                import traceback
                self.logger.debug(traceback.format_exc())
            return 1
    
    @abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """
        具体的Agent执行逻辑，子类必须实现
        
        Args:
            args: 解析后的命令行参数
            
        Returns:
            int: 退出码 (0=成功, 1=失败, 2=警告)
        """
        pass
    
    def validate_environment(self) -> bool:
        """验证运行环境"""
        try:
            # 检查必要的目录
            required_dirs = ['.claude', '.claude/logs', '.claude/scripts']
            for dir_path in required_dirs:
                Path(dir_path).mkdir(exist_ok=True)
                
            # 检查Python版本
            if sys.version_info < (3, 7):
                self.logger.error("需要Python 3.7+")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"环境验证失败: {e}")
            return False
    
    def report_metrics(self, metrics: Dict[str, Any]):
        """报告执行指标"""
        try:
            metrics_file = Path(".claude/logs/performance") / f"metrics_{self.name}.jsonl"
            metrics_file.parent.mkdir(exist_ok=True)
            
            import time
            metric_record = {
                'timestamp': time.time(),
                'agent': self.name,
                'model': self.model,
                **metrics
            }
            
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(metric_record) + '\n')
                
        except Exception as e:
            self.logger.warning(f"指标记录失败: {e}")

# 工具函数
def create_agent_script(agent_name: str, agent_class_name: str):
    """为特定Agent创建独立的执行脚本"""
    script_content = f'''#!/usr/bin/env python3
"""
{agent_name} Agent - Reddit Signal Scanner
基于AgentBase的具体实现
"""

import sys
import os
from pathlib import Path

# 添加scripts目录到Python路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from agent_base import AgentBase

# 这里导入具体的Agent实现
# from {agent_name}_impl import {agent_class_name}

class {agent_class_name}(AgentBase):
    def __init__(self):
        super().__init__('{agent_name}')
    
    def execute(self, args):
        # TODO: 实现具体的Agent逻辑
        self.logger.info(f"执行 {agent_name} Agent")
        return 0

if __name__ == '__main__':
    agent = {agent_class_name}()
    sys.exit(agent.run())
'''
    return script_content

if __name__ == '__main__':
    # 示例用法
    class ExampleAgent(AgentBase):
        def __init__(self):
            super().__init__('example')
            
        def execute(self, args):
            self.logger.info("示例Agent执行")
            return 0
    
    agent = ExampleAgent()
    sys.exit(agent.run())