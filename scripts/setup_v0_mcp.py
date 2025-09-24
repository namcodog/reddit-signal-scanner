#!/usr/bin/env python3
"""
v0-mcp工具安装和配置脚本
自动安装和配置v0-mcp工具，包括API密钥设置
"""

import json
import subprocess
import sys
import os
from pathlib import Path
import tempfile
import shutil

class V0MCPSetup:
    def __init__(self):
        self.project_root = Path.cwd()
        self.mcp_config_path = self.project_root / ".claude" / "mcp.json"
        self.env_file = self.project_root / ".env"

    def check_prerequisites(self) -> bool:
        """检查前置条件"""
        print("🔍 检查前置条件...")

        # 检查Node.js
        try:
            result = subprocess.run(['node', '--version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ Node.js: {result.stdout.strip()}")
            else:
                print("❌ Node.js未安装")
                return False
        except:
            print("❌ Node.js未安装")
            return False

        # 检查npm
        try:
            result = subprocess.run(['npm', '--version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ npm: {result.stdout.strip()}")
            else:
                print("❌ npm未安装")
                return False
        except:
            print("❌ npm未安装")
            return False

        return True

    def install_v0_mcp(self) -> bool:
        """安装v0-mcp包"""
        print("\n📦 安装v0-mcp...")

        try:
            # 测试v0-mcp是否可用
            result = subprocess.run(['npx', '-y', 'v0-mcp@latest', '--help'],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                print("✅ v0-mcp安装成功")
                return True
            else:
                print(f"❌ v0-mcp安装失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("❌ v0-mcp安装超时")
            return False
        except Exception as e:
            print(f"❌ v0-mcp安装失败: {str(e)}")
            return False

    def setup_api_key(self) -> str:
        """设置API密钥"""
        print("\n🔑 配置V0 API密钥...")

        # 检查环境变量中是否已有密钥
        api_key = os.environ.get('V0_API_KEY')
        if api_key:
            print("✅ 在环境变量中找到V0_API_KEY")
            return api_key

        # 检查.env文件中是否有密钥
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('V0_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        if api_key:
                            print("✅ 在.env文件中找到V0_API_KEY")
                            return api_key

        print("⚠️  未找到V0_API_KEY")
        print("📝 请按以下步骤获取API密钥:")
        print("   1. 访问 https://vercel.com/docs/v0/model-api")
        print("   2. 登录您的Vercel账户")
        print("   3. 生成新的API密钥")
        print("   4. 将密钥添加到.env文件中: V0_API_KEY=your_key_here")

        return ""

    def update_mcp_config(self, api_key: str) -> bool:
        """更新MCP配置"""
        print("\n⚙️  更新MCP配置...")

        # 确保.claude目录存在
        claude_dir = self.mcp_config_path.parent
        claude_dir.mkdir(parents=True, exist_ok=True)

        # 加载现有配置或创建新配置
        if self.mcp_config_path.exists():
            with open(self.mcp_config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {"mcpServers": {}}

        # 获取npx路径
        try:
            result = subprocess.run(['which', 'npx'],
                                  capture_output=True, text=True, timeout=5)
            npx_path = result.stdout.strip() if result.returncode == 0 else "/usr/local/bin/npx"
        except:
            npx_path = "/usr/local/bin/npx"

        # 添加或更新v0-mcp配置
        v0_config = {
            "command": npx_path,
            "args": ["-y", "v0-mcp@latest"],
            "env": {
                "V0_API_KEY": api_key
            } if api_key else {},
            "enabled": True,
            "timeout": 300
        }

        config["mcpServers"]["v0-mcp"] = v0_config

        # 保存配置
        try:
            with open(self.mcp_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print("✅ MCP配置已更新")
            return True
        except Exception as e:
            print(f"❌ 更新MCP配置失败: {str(e)}")
            return False

    def test_v0_mcp(self) -> bool:
        """测试v0-mcp工具"""
        print("\n🧪 测试v0-mcp工具...")

        api_key = os.environ.get('V0_API_KEY')
        if not api_key:
            print("⚠️  无API密钥，跳过功能测试")
            return True

        try:
            # 设置环境变量
            test_env = os.environ.copy()
            test_env['V0_API_KEY'] = api_key

            # 运行简单测试
            result = subprocess.run(['npx', '-y', 'v0-mcp@latest'],
                                  input='{"method": "tools/list", "params": {}}\n',
                                  capture_output=True, text=True,
                                  timeout=30, env=test_env)

            if "v0_generate_ui" in result.stdout:
                print("✅ v0-mcp工具测试成功")
                return True
            else:
                print("⚠️  v0-mcp工具响应异常")
                return False

        except subprocess.TimeoutExpired:
            print("⚠️  v0-mcp工具测试超时")
            return False
        except Exception as e:
            print(f"⚠️  v0-mcp工具测试失败: {str(e)}")
            return False

    def show_usage_examples(self):
        """显示使用示例"""
        print("\n📚 v0-mcp使用示例:")
        print("=" * 50)

        examples = [
            "创建登录表单: '使用v0生成一个现代的登录表单，包含邮箱和密码字段'",
            "生成仪表板: '创建一个带有侧边栏和图表的管理仪表板'",
            "图片转代码: '将这个设计图转换为React组件: [图片URL]'",
            "迭代改进: '改进之前的组件，添加响应式设计'"
        ]

        for i, example in enumerate(examples, 1):
            print(f"{i}. {example}")

        print("\n🔧 可用工具:")
        tools = [
            "v0_generate_ui - 从文本描述生成UI组件",
            "v0_generate_from_image - 从图像生成UI组件",
            "v0_chat_complete - 对话式UI开发",
            "v0_setup_check - 验证API连接"
        ]

        for tool in tools:
            print(f"   • {tool}")

def main():
    """主函数"""
    setup = V0MCPSetup()

    print("🚀 v0-mcp安装和配置工具")
    print("=" * 50)

    # 检查前置条件
    if not setup.check_prerequisites():
        print("\n❌ 前置条件检查失败，请先安装Node.js和npm")
        print("   安装命令: brew install node")
        sys.exit(1)

    # 安装v0-mcp
    if not setup.install_v0_mcp():
        print("\n❌ v0-mcp安装失败")
        sys.exit(1)

    # 设置API密钥
    api_key = setup.setup_api_key()

    # 更新MCP配置
    if not setup.update_mcp_config(api_key):
        print("\n❌ MCP配置更新失败")
        sys.exit(1)

    # 测试工具
    setup.test_v0_mcp()

    # 显示使用示例
    setup.show_usage_examples()

    print("\n" + "=" * 50)
    print("✨ v0-mcp配置完成！")

    if not api_key:
        print("\n⚠️  提醒: 请添加V0_API_KEY到.env文件以启用完整功能")

if __name__ == "__main__":
    main()
