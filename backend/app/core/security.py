"""
安全工具模块 - 密码哈希、验证和安全工具函数

Linus原则：
- 使用成熟的库，不要重新发明密码学
- 简单的接口，隐藏复杂的实现
- 安全默认值，但允许配置
- 性能和安全的平衡
"""

import hashlib
import hmac
import importlib
import secrets
from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Protocol,
    Tuple,
    Union,
    cast,
    runtime_checkable,
)


@runtime_checkable
class _CryptContextProto(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, hashed: str) -> bool:
        ...

    def needs_update(self, hashed: str) -> bool:
        ...


# 延迟导入第三方依赖：在类型检查期不要求 stubs
if TYPE_CHECKING:
    from passlib.context import CryptContext as _CryptContext  # pragma: no cover
else:  # 运行时分支
    _CryptContext = Any

from .config import get_settings

# ===== 密码哈希配置 =====

# 密码上下文 - 动态加载，配合 Protocol 约束调用面
_ctx_cls = cast(Any, importlib.import_module("passlib.context").CryptContext)
pwd_context: _CryptContextProto = _ctx_cls(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12
)


def hash_password(password: str) -> str:
    """
    哈希密码

    Args:
        password: 明文密码

    Returns:
        BCrypt哈希后的密码
    """
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        密码是否匹配
    """
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except Exception:
        # 哈希格式错误或其他异常
        return False


def need_password_rehash(hashed_password: str) -> bool:
    """
    检查密码是否需要重新哈希

    当BCrypt轮次配置改变时，旧密码需要重新哈希

    Args:
        hashed_password: 哈希后的密码

    Returns:
        是否需要重新哈希
    """
    try:
        return bool(pwd_context.needs_update(hashed_password))
    except Exception:
        # 哈希格式无法识别，需要重新哈希
        return True


# ===== 随机值生成 =====


def generate_random_string(length: int = 32) -> str:
    """
    生成加密安全的随机字符串

    Args:
        length: 字符串长度

    Returns:
        URL安全的随机字符串
    """
    return secrets.token_urlsafe(length)


def generate_random_bytes(length: int = 32) -> bytes:
    """
    生成加密安全的随机字节

    Args:
        length: 字节长度

    Returns:
        随机字节
    """
    return secrets.token_bytes(length)


def generate_secure_token(length: int = 32) -> str:
    """
    生成安全令牌（用于重置密码、邮件验证等）

    Args:
        length: 令牌长度

    Returns:
        安全令牌字符串
    """
    return secrets.token_urlsafe(length)


# ===== HMAC签名和验证 =====


def create_hmac_signature(
    data: Union[str, bytes], secret_key: Optional[str] = None, algorithm: str = "sha256"
) -> str:
    """
    创建HMAC签名

    Args:
        data: 要签名的数据
        secret_key: 密钥（默认使用JWT密钥）
        algorithm: 哈希算法

    Returns:
        十六进制签名字符串
    """
    if secret_key is None:
        secret_key = get_settings().jwt_secret_key

    if isinstance(data, str):
        data = data.encode("utf-8")

    signature = hmac.new(secret_key.encode("utf-8"), data, getattr(hashlib, algorithm))

    return signature.hexdigest()


def verify_hmac_signature(
    data: Union[str, bytes],
    signature: str,
    secret_key: Optional[str] = None,
    algorithm: str = "sha256",
) -> bool:
    """
    验证HMAC签名

    Args:
        data: 原始数据
        signature: 签名
        secret_key: 密钥（默认使用JWT密钥）
        algorithm: 哈希算法

    Returns:
        签名是否有效
    """
    try:
        expected_signature = create_hmac_signature(data, secret_key, algorithm)
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False


# ===== 时间安全验证 =====


def create_timestamped_signature(
    data: str, max_age_seconds: int = 3600, secret_key: Optional[str] = None
) -> str:
    """
    创建带时间戳的签名

    用于邮件验证链接、重置密码链接等有时效性的场景

    Args:
        data: 要签名的数据
        max_age_seconds: 最大有效时间（秒）
        secret_key: 签名密钥

    Returns:
        包含时间戳的签名数据
    """
    timestamp = int(datetime.utcnow().timestamp())
    payload = f"{data}.{timestamp}.{max_age_seconds}"
    signature = create_hmac_signature(payload, secret_key)

    return f"{payload}.{signature}"


def verify_timestamped_signature(
    signed_data: str, secret_key: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    验证带时间戳的签名

    Args:
        signed_data: 带签名的数据
        secret_key: 签名密钥

    Returns:
        (是否有效, 原始数据)
    """
    try:
        parts = signed_data.split(".")
        if len(parts) != 4:
            return False, None

        data, timestamp_str, max_age_str, signature = parts
        timestamp = int(timestamp_str)
        max_age = int(max_age_str)

        # 检查时间是否过期
        current_time = int(datetime.utcnow().timestamp())
        if current_time - timestamp > max_age:
            return False, None

        # 验证签名
        payload = f"{data}.{timestamp}.{max_age}"
        if not verify_hmac_signature(payload, signature, secret_key):
            return False, None

        return True, data

    except (ValueError, IndexError):
        return False, None


# ===== 安全比较 =====


def constant_time_compare(a: str, b: str) -> bool:
    """
    常时间字符串比较，防止时序攻击

    Args:
        a: 字符串A
        b: 字符串B

    Returns:
        字符串是否相等
    """
    return hmac.compare_digest(a, b)


# ===== 密码强度验证 =====


def check_password_strength(password: str) -> Tuple[bool, list[str]]:
    """
    检查密码强度

    Args:
        password: 待检查的密码

    Returns:
        (是否符合要求, 错误信息列表)
    """
    errors = []

    # 长度检查
    if len(password) < 8:
        errors.append("密码长度至少8位")

    if len(password) > 128:
        errors.append("密码长度不能超过128位")

    # 字符类型检查
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if not has_upper:
        errors.append("密码必须包含大写字母")

    if not has_lower:
        errors.append("密码必须包含小写字母")

    if not has_digit:
        errors.append("密码必须包含数字")

    # 弱密码检查
    weak_passwords = [
        "123456",
        "password",
        "123456789",
        "12345678",
        "12345",
        "1234567",
        "qwerty",
        "abc123",
        "Password",
        "password123",
        "admin",
        "letmein",
    ]

    if password.lower() in [wp.lower() for wp in weak_passwords]:
        errors.append("密码过于简单，请使用更复杂的密码")

    return len(errors) == 0, errors


# ===== 安全工具函数 =====


def mask_email(email: str) -> str:
    """
    遮罩邮箱地址，用于日志记录

    Args:
        email: 邮箱地址

    Returns:
        遮罩后的邮箱 (user***@exam***.com)
    """
    try:
        username, domain = email.split("@")

        # 用户名遮罩
        if len(username) <= 3:
            masked_username = username[0] + "*" * (len(username) - 1)
        else:
            masked_username = username[:2] + "*" * (len(username) - 2)

        # 域名遮罩
        domain_parts = domain.split(".")
        if len(domain_parts) >= 2:
            masked_domain = domain_parts[0][:2] + "*" * max(0, len(domain_parts[0]) - 2)
            if len(domain_parts) > 1:
                masked_domain += "." + ".".join(domain_parts[1:])
        else:
            masked_domain = domain[:2] + "*" * max(0, len(domain) - 2)

        return f"{masked_username}@{masked_domain}"

    except ValueError:
        # 邮箱格式错误
        return "***@***.***"


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除危险字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    import re

    # 移除路径分隔符和特殊字符
    sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)

    # 移除控制字符
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", sanitized)

    # 限制长度
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        max_name_length = 250 - len(ext)
        sanitized = name[:max_name_length] + ("." + ext if ext else "")

    # 确保不是Windows保留名
    reserved_names = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]

    name_upper = sanitized.upper().split(".")[0]
    if name_upper in reserved_names:
        sanitized = f"_{sanitized}"

    return sanitized or "unnamed_file"


# ===== 速率限制工具 =====


class SimpleRateLimiter:
    """
    简单的内存速率限制器
    生产环境建议使用Redis实现
    """

    def __init__(self) -> None:
        self._attempts: dict[str, list[tuple[datetime, int]]] = {}
        self._cleanup_interval = 3600  # 1小时清理一次
        self._last_cleanup = datetime.utcnow()

    def is_allowed(
        self, key: str, max_attempts: int = 5, window_seconds: int = 300
    ) -> bool:
        """
        检查是否允许操作

        Args:
            key: 限制键（如IP地址、用户ID）
            max_attempts: 最大尝试次数
            window_seconds: 时间窗口（秒）

        Returns:
            是否允许操作
        """
        now = datetime.utcnow()

        # 定期清理过期数据
        if (now - self._last_cleanup).total_seconds() > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

        # 获取或创建尝试记录
        if key not in self._attempts:
            self._attempts[key] = []

        attempts = self._attempts[key]

        # 移除过期的尝试记录
        cutoff_time = now - timedelta(seconds=window_seconds)
        attempts[:] = [
            (timestamp, count)
            for timestamp, count in attempts
            if timestamp > cutoff_time
        ]

        # 计算当前窗口内的尝试次数
        total_attempts = sum(count for _, count in attempts)

        if total_attempts >= max_attempts:
            return False

        # 记录本次尝试
        attempts.append((now, 1))
        return True

    def _cleanup_expired(self) -> None:
        """清理过期的尝试记录"""
        now = datetime.utcnow()
        cutoff_time = now - timedelta(seconds=3600)  # 保留1小时内的记录

        for key in list(self._attempts.keys()):
            attempts = self._attempts[key]
            attempts[:] = [
                (timestamp, count)
                for timestamp, count in attempts
                if timestamp > cutoff_time
            ]

            if not attempts:
                del self._attempts[key]


# 全局速率限制器实例
rate_limiter = SimpleRateLimiter()


# ===== 便捷函数 =====


def create_password_reset_token(user_id: str, max_age_hours: int = 1) -> str:
    """创建密码重置令牌"""
    return create_timestamped_signature(
        data=f"password_reset:{user_id}", max_age_seconds=max_age_hours * 3600
    )


def verify_password_reset_token(token: str) -> Tuple[bool, Optional[str]]:
    """验证密码重置令牌"""
    is_valid, data = verify_timestamped_signature(token)

    if is_valid and data and data.startswith("password_reset:"):
        user_id = data.split(":", 1)[1]
        return True, user_id

    return False, None


def create_email_verification_token(email: str, max_age_hours: int = 24) -> str:
    """创建邮箱验证令牌"""
    return create_timestamped_signature(
        data=f"email_verify:{email}", max_age_seconds=max_age_hours * 3600
    )


def verify_email_verification_token(token: str) -> Tuple[bool, Optional[str]]:
    """验证邮箱验证令牌"""
    is_valid, data = verify_timestamped_signature(token)

    if is_valid and data and data.startswith("email_verify:"):
        email = data.split(":", 1)[1]
        return True, email

    return False, None
