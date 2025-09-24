#!/usr/bin/env python3
"""Environment health check helper for Reddit Signal Scanner integration.

This script reads the canonical environment matrix (`integration/environments.yaml`),
performs lightweight validations on connection strings, and optionally pings API
health endpoints. It is designed to be fast (sub-10s) so it can be wired into the
`make env-check` target or run ad-hoc before 联调 sessions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlparse

import httpx
import yaml
from pydantic import BaseModel, Field, AnyUrl, ValidationError, model_validator
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_CONFIG_PATH = REPO_ROOT / "integration" / "environments.yaml"


class EndpointConfig(BaseModel):
    """Single health endpoint definition."""

    path: str
    expected_status: int = Field(ge=100, le=599)

    @model_validator(mode="after")
    def _validate_path(self) -> "EndpointConfig":
        if not self.path.startswith("/"):
            msg = f"health endpoint path must start with '/', got: {self.path}"
            raise ValueError(msg)
        return self


class CeleryConfig(BaseModel):
    """Celery connection configuration."""

    broker_url: str
    result_backend: str

    @model_validator(mode="after")
    def _validate_urls(self) -> "CeleryConfig":
        for label, value in ("broker_url", self.broker_url), ("result_backend", self.result_backend):
            if "://" not in value:
                msg = f"Celery {label} is not a valid URL: {value}"
                raise ValueError(msg)
        return self


class DocsInfo(BaseModel):
    """Documentation pointers for an environment."""

    env_file: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EnvironmentConfig(BaseModel):
    """Environment-level configuration record."""

    api_base: AnyUrl
    database_url: str
    redis_url: str
    celery: CeleryConfig
    docs: DocsInfo
    tls_required: bool = False
    custom_health_endpoints: list[EndpointConfig] = Field(default_factory=list)
    custom_headers: Mapping[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_database_and_redis(self) -> "EnvironmentConfig":
        if "://" not in self.database_url:
            msg = f"database_url must contain a scheme: {self.database_url}"
            raise ValueError(msg)
        if "://" not in self.redis_url:
            msg = f"redis_url must contain a scheme: {self.redis_url}"
            raise ValueError(msg)
        return self


class DefaultConfig(BaseModel):
    """Defaults shared across environments."""

    health_endpoints: list[EndpointConfig]
    timeout_seconds: float = Field(default=5.0, gt=0.0)
    headers: Mapping[str, str] = Field(default_factory=dict)


class EnvironmentMatrix(BaseModel):
    """Root YAML mapping."""

    version: str
    updated_at: date
    maintainer: str
    defaults: DefaultConfig
    environments: Mapping[str, EnvironmentConfig]


@dataclass(slots=True)
class EndpointStatus:
    """Runtime status for a single endpoint check."""

    path: str
    expected_status: int
    actual_status: int | None
    ok: bool
    error: str | None = None


@dataclass(slots=True)
class ConnectionValidation:
    """Validation result for connection strings."""

    target: str
    ok: bool
    error: str | None = None


@dataclass(slots=True)
class EnvironmentReport:
    """Aggregated report for an environment."""

    name: str
    api_base: str
    endpoint_results: list[EndpointStatus] = field(default_factory=list)
    connections: list[ConnectionValidation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dict without `asdict` recursion quirks."""
        return {
            "name": self.name,
            "api_base": self.api_base,
            "endpoint_results": [asdict(item) for item in self.endpoint_results],
            "connections": [asdict(item) for item in self.connections],
        }


async def _check_endpoint(
    client: httpx.AsyncClient,
    api_base: str,
    endpoint: EndpointConfig,
) -> EndpointStatus:
    url = f"{api_base.rstrip('/')}{endpoint.path}"
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        return EndpointStatus(
            path=endpoint.path,
            expected_status=endpoint.expected_status,
            actual_status=None,
            ok=False,
            error=str(exc),
        )
    return EndpointStatus(
        path=endpoint.path,
        expected_status=endpoint.expected_status,
        actual_status=response.status_code,
        ok=response.status_code == endpoint.expected_status,
        error=None if response.status_code == endpoint.expected_status else response.text[:200],
    )


def _validate_database_url(url: str) -> ConnectionValidation:
    try:
        parsed = make_url(url)
    except Exception as exc:  # noqa: BLE001 - surface error message to user
        return ConnectionValidation(target="database", ok=False, error=str(exc))
    if parsed.host in (None, ""):
        return ConnectionValidation(target="database", ok=False, error="missing host in database URL")
    return ConnectionValidation(target="database", ok=True)


def _validate_redis_url(url: str, label: str) -> ConnectionValidation:
    parsed = urlparse(url)
    if not parsed.scheme:
        return ConnectionValidation(target=label, ok=False, error="missing scheme")
    if parsed.scheme not in {"redis", "rediss"}:
        return ConnectionValidation(target=label, ok=False, error=f"unsupported scheme: {parsed.scheme}")
    if parsed.hostname in (None, ""):
        return ConnectionValidation(target=label, ok=False, error="missing hostname")
    return ConnectionValidation(target=label, ok=True)


async def check_environment(
    name: str,
    config: EnvironmentConfig,
    defaults: DefaultConfig,
) -> EnvironmentReport:
    """Run validations and return a structured report."""

    merged_headers: dict[str, str] = {**defaults.headers, **dict(config.custom_headers)}
    endpoints: list[EndpointConfig] = [*defaults.health_endpoints, *config.custom_health_endpoints]

    report = EnvironmentReport(name=name, api_base=str(config.api_base))

    connections: list[ConnectionValidation] = [
        _validate_database_url(config.database_url),
        _validate_redis_url(config.redis_url, "redis"),
        _validate_redis_url(config.celery.broker_url, "celery_broker"),
        _validate_redis_url(config.celery.result_backend, "celery_result"),
    ]
    report.connections.extend(connections)

    if not endpoints:
        return report

    verify_tls = config.tls_required
    timeout = httpx.Timeout(defaults.timeout_seconds)
    async with httpx.AsyncClient(headers=merged_headers, timeout=timeout, verify=verify_tls) as client:
        tasks = [_check_endpoint(client, str(config.api_base), endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
        report.endpoint_results.extend(results)

    return report


def load_matrix(config_path: Path) -> EnvironmentMatrix:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    try:
        return EnvironmentMatrix.model_validate(raw)
    except ValidationError as exc:  # noqa: BLE001
        print("❌ 配置文件解析失败:", file=sys.stderr)
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


def format_report(report: EnvironmentReport) -> str:
    lines: list[str] = []
    lines.append(f"🌐 环境：{report.name} ({report.api_base})")
    for conn in report.connections:
        status_icon = "✅" if conn.ok else "❌"
        detail = "" if conn.error is None else f" - {conn.error}"
        lines.append(f"  {status_icon} {conn.target}: {detail or 'ok'}")
    if not report.endpoint_results:
        lines.append("  ⚠️ 未配置健康检查端点")
        return "\n".join(lines)
    for endpoint in report.endpoint_results:
        status_icon = "✅" if endpoint.ok else "❌"
        actual = endpoint.actual_status if endpoint.actual_status is not None else "--"
        detail = "" if endpoint.error is None else f" - {endpoint.error}"
        lines.append(
            f"  {status_icon} GET {endpoint.path} -> {actual} (期待 {endpoint.expected_status}){detail}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perform environment health checks.")
    parser.add_argument(
        "--env",
        default="local",
        help="environment key to inspect, or 'all' for every environment",
    )
    parser.add_argument(
        "--config",
        default=str(ENV_CONFIG_PATH),
        help="path to environments.yaml (defaults to repo integration/environments.yaml)",
    )
    parser.add_argument(
        "--output",
        help="optional path to dump JSON report",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available environments and exit",
    )
    return parser.parse_args()


def list_environments(matrix: EnvironmentMatrix) -> None:
    env_names = ", ".join(matrix.environments.keys())
    print(f"🔎 可用环境：{env_names}")


def select_environments(matrix: EnvironmentMatrix, env_flag: str) -> Sequence[tuple[str, EnvironmentConfig]]:
    if env_flag == "all":
        return list(matrix.environments.items())
    if env_flag not in matrix.environments:
        available = ", ".join(matrix.environments.keys())
        raise SystemExit(f"未知环境 '{env_flag}'，可选值：{available}")
    return [(env_flag, matrix.environments[env_flag])]


async def run() -> None:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"配置文件不存在: {config_path}")

    matrix = load_matrix(config_path)

    if args.list:
        list_environments(matrix)
        return

    selected = select_environments(matrix, args.env)

    reports: list[EnvironmentReport] = []
    for name, config in selected:
        report = await check_environment(name, config, matrix.defaults)
        reports.append(report)
        print(format_report(report))

    if args.output is None:
        return

    output_path = Path(args.output)
    payload = {
        "generated_at": date.today().isoformat(),
        "environments": [report.as_dict() for report in reports],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 报告已写入 {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("⚠️ 健康检查被中断", file=sys.stderr)
        raise SystemExit(130) from None
