from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class JWTPayload(BaseModel):
    sub: str = Field(..., description="user_id")
    tenant: str = Field(..., description="tenant_id")
    exp: int
    iat: int
    permissions: List[str] = Field(default_factory=list)


class UserContext(BaseModel):
    user_id: str
    tenant_id: str
    permissions: List[str] = Field(default_factory=list)
    session_id: str
    expires_at: datetime
