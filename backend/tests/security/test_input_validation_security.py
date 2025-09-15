"""
输入验证安全测试

目标：
- 邮箱格式拒绝典型注入/XSS 字符串
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import UserRegisterRequest


@pytest.mark.parametrize(
    "email",
    [
        "test@example",  # 无顶级域
        "test@exa mple.com",  # 空格
        "test@example..com",  # 连续点
        "' OR 1=1; --@example.com",  # 注入模式
        "<script>@example.com",  # XSS
        "test@@example.com",  # 双@
    ],
)
def test_register_request_rejects_invalid_emails(email: str):
    with pytest.raises(ValidationError):
        UserRegisterRequest(email=email, password="Aa1!aaaa", confirm_password="Aa1!aaaa")

