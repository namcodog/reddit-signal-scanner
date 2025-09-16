"""
兼容模块：tests 期望存在 app.core.v0_auth 中的符号。
最小实现：提供 V0AuthHandler 与 get_v0_auth_handler 占位，返回固定结果。
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class V0AuthHandler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    def process(self, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"success": True, "user": {"user_id": "test", "tenant_id": "test"}}


def get_v0_auth_handler(config: Any | None = None) -> V0AuthHandler:
    return V0AuthHandler(config)


class V0AuthMiddleware:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    async def process_request(self, request: Any) -> Dict[str, Any]:
        return {
            "success": True,
            "user": {"user_id": "test", "tenant_id": "test", "permissions": []},
        }


__all__ = ["V0AuthHandler", "get_v0_auth_handler", "V0AuthMiddleware"]
