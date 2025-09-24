#!/usr/bin/env python3
"""
MCP工具状态检查和修复脚本
检查所有配置的MCP工具是否正常工作，并提供修复建议
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import time

class MCPToolsChecker:
    def __init__(self):
        self.project_root = Path.cwd()
        self.mcp_config_path = self.project_root / ".claude" / "mcp.json"
        self.env_file = self.project_root / ".env"
        
        # 加载环境变量
        self.load_env_vars()
        
        # 测试结果
        self.results = {
            "working": [],
            "failed": [],
            "warnings": [],
            "suggestions": []
        }
    
    def load_env_vars(self):
        """加载.env文件中的环境变量"""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
    
    def load_mcp_config(self) -> Dict:
        """加载MCP配置文件"""
        if not self.mcp_config_path.exists():
            print(f"❌ MCP配置文件不存在: {self.mcp_config_path}")
            return {}
        
        with open(self.mcp_config_path, 'r') as f:
            return json.load(f)
    
    def test_command_availability(self, command: str) -> bool:
        """测试命令是否可用"""
        try:
            result = subprocess.run(['which', command], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def test_mcp_tool(self, name: str, config: Dict) -> Tuple[bool, str]:
        """测试单个MCP工具"""
        print(f"🔍 测试 {name}...")
        
        command = config.get('command', '')
        args = config.get('args', [])
        env = config.get('env', {})
        enabled = config.get('enabled', True)
        
        if not enabled:
            return True, "已禁用"
        
        # 检查命令是否存在
        if not self.test_command_availability(command):
            return False, f"命令不存在: {command}"
        
        # 检查环境变量
        missing_env = []
        for key, value in env.items():
            if key not in os.environ and not value:
                missing_env.append(key)
        
        if missing_env:
            return False, f"缺少环境变量: {', '.join(missing_env)}"
        
        # 尝试运行工具（简单测试）
        try:
            test_env = os.environ.copy()
            test_env.update(env)
            
            # 对于不同的工具使用不同的测试方法
            if 'tavily-mcp' in str(args):
                # Tavily需要API密钥
                if 'TAVILY_API_KEY' not in test_env:
                    return False, "缺少TAVILY_API_KEY"
                
            elif 'v0-mcp' in str(args):
                # V0需要API密钥
                if 'V0_API_KEY' not in test_env:
                    return False, "缺少V0_API_KEY"
            
            elif 'context7-mcp' in str(args):
                # Context7测试连接
                result = subprocess.run([command] + args + ['--help'], 
                                      capture_output=True, text=True, 
                                      timeout=10, env=test_env)
                if result.returncode != 0:
                    return False, f"工具启动失败: {result.stderr}"
            
            return True, "正常"
            
        except subprocess.TimeoutExpired:
            return False, "测试超时"
        except Exception as e:
            return False, f"测试失败: {str(e)}"
    
    def check_all_tools(self):
        """检查所有MCP工具"""
        print("🚀 开始检查MCP工具状态...\n")
        
        config = self.load_mcp_config()
        if not config or 'mcpServers' not in config:
            print("❌ 无效的MCP配置文件")
            return
        
        servers = config['mcpServers']
        
        for name, server_config in servers.items():
            success, message = self.test_mcp_tool(name, server_config)
            
            if success:
                print(f"✅ {name}: {message}")
                self.results["working"].append(name)
            else:
                print(f"❌ {name}: {message}")
                self.results["failed"].append((name, message))
        
        print(f"\n📊 检查完成:")
        print(f"   ✅ 正常工作: {len(self.results['working'])}")
        print(f"   ❌ 有问题: {len(self.results['failed'])}")
    
    def generate_fix_suggestions(self):
        """生成修复建议"""
        if not self.results["failed"]:
            print("\n🎉 所有MCP工具都正常工作！")
            return
        
        print("\n🔧 修复建议:")
        
        for name, error in self.results["failed"]:
            print(f"\n📌 {name}:")
            
            if "缺少环境变量" in error:
                print(f"   💡 请在.env文件中添加缺少的环境变量")
                
            elif "命令不存在" in error:
                if "npx" in error:
                    print(f"   💡 请安装Node.js和npm: brew install node")
                elif "uvx" in error:
                    print(f"   💡 请安装uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
                    
            elif "TAVILY_API_KEY" in error:
                print(f"   💡 请获取Tavily API密钥: https://tavily.com/")
                
            elif "V0_API_KEY" in error:
                print(f"   💡 请获取V0 API密钥: https://vercel.com/docs/v0/model-api")
    
    def fix_common_issues(self):
        """自动修复常见问题"""
        print("\n🔧 尝试自动修复常见问题...")
        
        # 检查并创建必要的目录
        claude_dir = self.project_root / ".claude"
        if not claude_dir.exists():
            claude_dir.mkdir(parents=True)
            print("✅ 创建.claude目录")
        
        # 检查Node.js和npm
        if not self.test_command_availability('node'):
            print("⚠️  Node.js未安装，请运行: brew install node")
        
        if not self.test_command_availability('npm'):
            print("⚠️  npm未安装，请运行: brew install node")
        
        # 检查uv
        if not self.test_command_availability('uv'):
            print("⚠️  uv未安装，请运行: curl -LsSf https://astral.sh/uv/install.sh | sh")

def main():
    """主函数"""
    checker = MCPToolsChecker()
    
    print("🔍 MCP工具状态检查器")
    print("=" * 50)
    
    # 检查所有工具
    checker.check_all_tools()
    
    # 生成修复建议
    checker.generate_fix_suggestions()
    
    # 尝试自动修复
    checker.fix_common_issues()
    
    print("\n" + "=" * 50)
    print("✨ 检查完成！")

if __name__ == "__main__":
    main()
