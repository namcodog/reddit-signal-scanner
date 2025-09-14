"""
Reddit Signal Scanner - 输入验证模块

安全输入验证，防止注入攻击和数据污染
基于Linus设计原则：简洁、安全、可靠
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set


class ValidationError(Exception):
    """输入验证异常"""

    pass


class CommunityNameFormat(Enum):
    """社区名称格式枚举"""

    WITH_PREFIX = "with_r_prefix"  # r/community
    WITHOUT_PREFIX = "without_prefix"  # community


@dataclass
class ValidationConfig:
    """验证配置"""

    max_community_name_length: int = 50
    max_communities_count: int = 100
    allowed_chars_pattern: str = r"^[a-zA-Z0-9_]+$"
    blocked_names: Set[str] = field(
        default_factory=lambda: {
            "admin",
            "api",
            "www",
            "mail",
            "root",
            "test",
            "null",
            "undefined",
            "deleted",
            "removed",
        }
    )


class RedditInputValidator:
    """Reddit输入验证器

    提供安全的输入验证，防止：
    - 路径遍历攻击
    - SQL注入
    - XSS攻击
    - 恶意社区名称
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()

    def validate_community_name(
        self,
        community: str,
        format_type: CommunityNameFormat = CommunityNameFormat.WITH_PREFIX,
    ) -> str:
        """验证并标准化社区名称

        Args:
            community: 社区名称
            format_type: 期望的格式类型

        Returns:
            str: 标准化后的社区名称

        Raises:
            ValidationError: 验证失败
        """
        if not community or not isinstance(community, str):
            raise ValidationError("社区名称不能为空")

        # 移除空白字符
        clean_community = community.strip()

        if not clean_community:
            raise ValidationError("社区名称不能为空白")

        # 长度检查
        if len(clean_community) > self.config.max_community_name_length:
            raise ValidationError(
                f"社区名称过长，最大长度: {self.config.max_community_name_length}"
            )

        # 格式处理
        if clean_community.startswith("r/"):
            base_name = clean_community[2:]
        else:
            base_name = clean_community

        # 基础名称验证
        if not base_name:
            raise ValidationError("社区名称不能仅为'r/'")

        # 字符检查 - 防止路径遍历
        if not re.match(self.config.allowed_chars_pattern, base_name):
            raise ValidationError("社区名称包含非法字符，只允许字母、数字和下划线")

        # 特殊字符检查 - 防止注入
        dangerous_patterns = [
            "..",  # 路径遍历
            "/",  # 路径分隔符
            "\\",  # Windows路径分隔符
            ";",  # 命令分隔符
            "|",  # 管道符
            "&",  # 命令连接符
            "$",  # 变量替换
            "`",  # 命令替换
            "<",  # 重定向
            ">",  # 重定向
            "*",  # 通配符
            "?",  # 通配符
        ]

        for pattern in dangerous_patterns:
            if pattern in base_name:
                raise ValidationError(f"社区名称包含危险字符: {pattern}")

        # 保留名称检查
        if base_name.lower() in self.config.blocked_names:
            raise ValidationError(f"社区名称 '{base_name}' 是保留名称")

        # 格式化输出
        if format_type == CommunityNameFormat.WITH_PREFIX:
            return f"r/{base_name.lower()}"
        else:
            return base_name.lower()

    def validate_community_list(
        self, communities: List[str], allow_duplicates: bool = False
    ) -> List[str]:
        """验证社区列表

        Args:
            communities: 社区列表
            allow_duplicates: 是否允许重复

        Returns:
            List[str]: 验证后的社区列表

        Raises:
            ValidationError: 验证失败
        """
        if not communities:
            raise ValidationError("社区列表不能为空")

        if not isinstance(communities, list):
            raise ValidationError("社区列表必须是list类型")

        if len(communities) > self.config.max_communities_count:
            raise ValidationError(f"社区数量超限，最大允许: {self.config.max_communities_count}")

        validated_communities = []
        seen_communities = set()

        for i, community in enumerate(communities):
            try:
                validated_name = self.validate_community_name(community)

                # 重复检查
                if not allow_duplicates:
                    if validated_name in seen_communities:
                        continue  # 跳过重复项
                    seen_communities.add(validated_name)

                validated_communities.append(validated_name)

            except ValidationError as e:
                raise ValidationError(f"第 {i+1} 个社区名称验证失败: {str(e)}")

        if not validated_communities:
            raise ValidationError("没有有效的社区名称")

        return validated_communities

    def validate_post_content(self, content: str, max_length: int = 10000) -> str:
        """验证帖子内容

        Args:
            content: 帖子内容
            max_length: 最大长度

        Returns:
            str: 清洗后的内容

        Raises:
            ValidationError: 验证失败
        """
        if not isinstance(content, str):
            raise ValidationError("内容必须是字符串类型")

        # 长度检查
        if len(content) > max_length:
            raise ValidationError(f"内容过长，最大长度: {max_length}")

        # 移除危险HTML标签
        dangerous_tags = [
            "<script",
            "</script>",
            "<iframe",
            "</iframe>",
            "<object",
            "</object>",
            "<embed",
            "</embed>",
            "javascript:",
            "vbscript:",
            "data:text/html",
        ]

        clean_content = content
        for tag in dangerous_tags:
            if tag.lower() in clean_content.lower():
                raise ValidationError(f"内容包含危险标签: {tag}")

        return clean_content.strip()

    def validate_numeric_range(
        self, value: int, min_value: int, max_value: int, field_name: str = "数值"
    ) -> int:
        """验证数值范围

        Args:
            value: 待验证的值
            min_value: 最小值
            max_value: 最大值
            field_name: 字段名称

        Returns:
            int: 验证后的值

        Raises:
            ValidationError: 验证失败
        """
        if not isinstance(value, int):
            raise ValidationError(f"{field_name}必须是整数")

        if value < min_value or value > max_value:
            raise ValidationError(f"{field_name}必须在 {min_value} - {max_value} 范围内")

        return value

    def sanitize_search_query(self, query: str) -> str:
        """清洗搜索查询字符串

        Args:
            query: 搜索查询

        Returns:
            str: 清洗后的查询
        """
        if not query or not isinstance(query, str):
            return ""

        # 移除控制字符
        clean_query = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", query)

        # 限制长度
        clean_query = clean_query[:200]

        # 移除多余空白
        clean_query = re.sub(r"\s+", " ", clean_query).strip()

        return clean_query


# 全局验证器实例
default_validator = RedditInputValidator()


def validate_community_name(community: str) -> str:
    """便捷函数：验证社区名称"""
    return default_validator.validate_community_name(community)


def validate_community_list(communities: List[str]) -> List[str]:
    """便捷函数：验证社区列表"""
    return default_validator.validate_community_list(communities)


def validate_post_content(content: str) -> str:
    """便捷函数：验证帖子内容"""
    return default_validator.validate_post_content(content)
