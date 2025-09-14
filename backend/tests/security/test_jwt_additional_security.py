"""
附加JWT安全测试覆盖

补强点：
- alg=none 拒绝
- iss/aud 不匹配拒绝
- kid 头部不影响验证通过
- RS256 令牌在未配置RSA公钥时不得被接受（避免算法混淆）
"""

import base64
import json
import time
import uuid

import jwt
import pytest
from jwt.exceptions import InvalidTokenError

from app.core.jwt_handler import JWTHandler


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _make_none_alg_token(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}
    h = _b64u(json.dumps(header, separators=(",", ":")).encode())
    p = _b64u(json.dumps(payload, separators=(",", ":")).encode())
    # None 算法：空签名段
    return f"{h}.{p}."


class TestAdditionalJWTSecurity:
    def setup_method(self) -> None:
        self.handler = JWTHandler()

    def test_reject_none_algorithm_tokens(self):
        now = int(time.time())
        payload = {
            "user_id": "u-1",
            "tenant_id": "t-1",
            "email": "u@test.com",
            "permissions": [],
            "token_type": "access",
            "exp": now + 3600,
            "iat": now,
            "iss": "reddit-scanner",
            "aud": "api",
            "jti": str(uuid.uuid4()),
        }

        token = _make_none_alg_token(payload)
        with pytest.raises(Exception):  # InvalidAlgorithmError/InvalidTokenError
            self.handler.verify_token(token)

    def test_audience_issuer_mismatch_rejected(self):
        now = int(time.time())
        bad_iss = {
            "user_id": "u-1",
            "tenant_id": "t-1",
            "email": "u@test.com",
            "permissions": [],
            "token_type": "access",
            "exp": now + 3600,
            "iat": now,
            "iss": "wrong-issuer",
            "aud": "api",
            "jti": str(uuid.uuid4()),
        }
        bad_aud = {**bad_iss, "iss": "reddit-scanner", "aud": "wrong-aud"}

        hs_key = self.handler.keys.hmac_key
        t1 = jwt.encode(bad_iss, hs_key, algorithm="HS256")
        t2 = jwt.encode(bad_aud, hs_key, algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            self.handler.verify_token(t1)
        with pytest.raises(InvalidTokenError):
            self.handler.verify_token(t2)

    def test_kid_header_does_not_affect_hs256_verification(self):
        now = int(time.time())
        payload = {
            "user_id": "u-1",
            "tenant_id": "t-1",
            "email": "u@test.com",
            "permissions": ["read"],
            "token_type": "access",
            "exp": now + 3600,
            "iat": now,
            "iss": "reddit-scanner",
            "aud": "api",
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(
            payload, self.handler.keys.hmac_key, algorithm="HS256", headers={"kid": "bogus"}
        )
        verified = self.handler.verify_token(token)
        assert verified.user_id == "u-1"
        assert verified.tenant_id == "t-1"

    def test_rs256_token_not_accepted_without_configured_public_key(self):
        # 生成与应用无关的一对RSA密钥，签发RS256 token
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        now = int(time.time())
        payload = {
            "user_id": "u-1",
            "tenant_id": "t-1",
            "email": "u@test.com",
            "permissions": [],
            "token_type": "access",
            "exp": now + 3600,
            "iat": now,
            "iss": "reddit-scanner",
            "aud": "api",
            "jti": str(uuid.uuid4()),
        }
        rs_token = jwt.encode(payload, private_pem, algorithm="RS256")

        # 应用未配置对应公钥时，应拒绝该token
        with pytest.raises(Exception):
            self.handler.verify_token(rs_token)

