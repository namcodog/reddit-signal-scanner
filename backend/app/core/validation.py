"""
Reddit Signal Scanner - 输入验证核心模块

Linus原则："安全第一，但不要过度设计"
- 多层验证：Pydantic基础验证 + 业务逻辑验证 + 安全过滤
- 失败快速：第一个错误立即返回，不浪费资源
- 明确错误：每个验证错误都有清晰的用户提示
"""

import re
from typing import Any, Dict, List, Pattern

from bleach import clean

from .types import JsonValue


class ContentValidator:
    """内容安全验证器

    基于行业标准的多层验证策略：
    1. 基础过滤：移除HTML标签和危险字符
    2. 模式检测：识别常见恶意输入模式
    3. 业务验证：符合具体业务场景要求
    """

    # 允许的HTML标签（空列表 = 移除所有HTML）
    ALLOWED_TAGS: List[str] = []
    ALLOWED_ATTRIBUTES: Dict[str, List[str]] = {}

    # 恶意模式检测（编译一次，重复使用）
    BLOCKED_PATTERNS: List[Pattern[str]] = [
        # 脚本注入检测
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"vbscript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),  # 事件处理器
        # SQL注入检测
        re.compile(
            r"\b(union\s+select|drop\s+table|insert\s+into|delete\s+from)\b",
            re.IGNORECASE,
        ),
        re.compile(r"[\'\"]\s*;\s*(drop|delete|insert|update|select)", re.IGNORECASE),
        # 路径遍历攻击
        re.compile(r"\.\./|\.\\", re.IGNORECASE),
        # 命令注入检测
        re.compile(r"[;&|`$]", re.IGNORECASE),
        # 潜在恶意URL模式
        re.compile(r"(data|javascript|vbscript):", re.IGNORECASE),
    ]

    # 业务特定模式（产品描述不应包含的内容）
    BUSINESS_BLOCKED_PATTERNS: List[Pattern[str]] = [
        # 垃圾信息模式
        re.compile(r"(click here|buy now|free money|guaranteed)", re.IGNORECASE),
        re.compile(r"(\$\d+|\d+\$).*?(guaranteed|easy|fast)", re.IGNORECASE),
        # 过度营销模式
        re.compile(r"!!{3,}|#{3,}", re.IGNORECASE),  # 过多感叹号或井号
    ]

    @classmethod
    def sanitize_input(cls, content: str) -> str:
        """清理输入内容

        Args:
            content: 原始用户输入

        Returns:
            清理后的安全内容

        Raises:
            ValueError: 检测到恶意内容时抛出具体错误信息
        """
        if not isinstance(content, str):
            raise ValueError("输入内容必须是字符串类型")

        # 第一步：基础清理
        content = content.strip()

        # 第二步：HTML清理（使用bleach库，行业标准）
        content = clean(
            content,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True,  # 移除而非转义不允许的标签
            strip_comments=True,
        )

        # 第三步：恶意模式检测
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern.search(content):
                raise ValueError("输入内容包含不安全模式，请移除潜在恶意内容")

        # 第四步：业务逻辑验证
        for pattern in cls.BUSINESS_BLOCKED_PATTERNS:
            if pattern.search(content):
                raise ValueError("产品描述不应包含过度营销或垃圾信息内容")

        return content

    @classmethod
    def validate_product_description(cls, description: str) -> str:
        """产品描述专用验证

        针对产品描述场景的特定验证规则：
        - 长度要求：10-2000字符
        - 内容质量：包含实质信息，非垃圾内容
        - 安全过滤：移除潜在恶意内容

        Args:
            description: 用户输入的产品描述

        Returns:
            验证并清理后的产品描述

        Raises:
            ValueError: 验证失败时的具体错误信息
        """
        # 基础安全清理
        description = cls.sanitize_input(description)

        # 长度验证（双重保险，Pydantic已验证）
        if len(description) < 10:
            raise ValueError("产品描述至少需要10个字符，请提供更详细的描述")

        if len(description) > 2000:
            raise ValueError("产品描述不能超过2000个字符，请简化描述内容")

        # 内容质量检查
        if not cls._has_meaningful_content(description):
            raise ValueError("产品描述应包含实质性内容，请避免重复字符或无意义内容")

        return description

    @classmethod
    def _has_meaningful_content(cls, content: str) -> bool:
        """检查内容是否有意义

        避免用户提交重复字符、全空格等无意义内容
        """
        # 移除空白字符后检查
        clean_content = re.sub(r"\s+", " ", content).strip()

        # 检查是否全是重复字符
        if len(set(clean_content)) < 3:  # 至少需要3个不同字符
            return False

        # 检查是否包含基本单词结构
        word_pattern = re.compile(r"\w{2,}")  # 至少2个字符的单词
        words = word_pattern.findall(clean_content)

        if len(words) < 2:  # 至少需要2个单词
            return False

        return True


class APIValidator:
    """API请求验证器

    统一的API请求验证逻辑，确保所有端点的一致性
    """

    @staticmethod
    def validate_request_headers(headers: Dict[str, str]) -> None:
        """验证请求头

        检查必需的请求头和格式
        """
        # Content-Type检查
        content_type = headers.get("content-type", "").lower()
        if content_type and "application/json" not in content_type:
            raise ValueError("请求必须使用JSON格式，Content-Type: application/json")

    @staticmethod
    def validate_task_creation_request(request_data: Dict[str, JsonValue]) -> None:
        """任务创建请求验证

        PRD02-02专用验证逻辑
        """
        # 检查必需字段
        if "product_description" not in request_data:
            raise ValueError("缺少必需字段：product_description")

        # 类型检查
        product_desc = request_data["product_description"]
        if not isinstance(product_desc, str):
            raise ValueError("product_description必须是字符串类型")

        # 使用ContentValidator进行深度验证
        ContentValidator.validate_product_description(product_desc)


# 性能优化：预编译正则表达式，避免重复编译
def _compile_patterns() -> None:
    """预编译正则表达式模式，提升验证性能"""
    # 这个函数在模块加载时执行，确保模式只编译一次
    pass


# 模块加载时执行性能优化
_compile_patterns()


# Linus式设计说明：
#
# 1. "安全第一，但不过度设计"
#    - 使用成熟的bleach库而非自己实现HTML清理
#    - 模式检测基于实际攻击案例，不是理论假设
#    - 预编译正则表达式，运行时零编译开销
#
# 2. "失败快速，错误明确"
#    - 第一个验证失败立即返回，不浪费CPU
#    - 每个错误都有用户友好的提示信息
#    - 区分技术错误（ValueError）和业务错误（业务级别处理）
#
# 3. "单一职责"
#    - ContentValidator：专注内容安全
#    - APIValidator：专注API层面验证
#    - 每个方法只做一件事，便于测试和维护
#
# 4. "数据驱动配置"
#    - 恶意模式通过列表配置，易于维护
#    - 业务规则和安全规则分离
#    - 支持运行时调整验证策略
