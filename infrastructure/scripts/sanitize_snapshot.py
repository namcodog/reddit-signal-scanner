#!/usr/bin/env python3
"""Sanitize production snapshots into mock-friendly payloads.

Features:
- Supports JSON arrays and JSON Lines files.
- Masks common PII fields (usernames, emails, IPs, tokens) with deterministic hashes.
- Allows down-sampling via `--sample-rate` for lightweight fixtures.

Sample usage::

    python infrastructure/scripts/sanitize_snapshot.py \
        --input prod_dump.json --output sanitized.json --sample-rate 0.2 --pretty
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = dict[str, "JsonValue"]
JsonArray: TypeAlias = list["JsonValue"]
JsonValue: TypeAlias = JsonPrimitive | JsonObject | JsonArray

SENSITIVE_NAME_KEYS: frozenset[str] = frozenset(
    {
        "user",
        "username",
        "user_name",
        "userId",
        "user_id",
        "author",
        "account",
        "email",
        "ip",
        "ip_address",
        "session",
    }
)
SENSITIVE_SUBSTRINGS: tuple[str, ...] = ("token", "secret", "password", "credential", "api_key")


@dataclass(slots=True)
class SanitizeStats:
    """Simple counter for reporting."""

    records_seen: int = 0
    records_kept: int = 0
    fields_masked: int = 0
    fields_scrubbed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "records_seen": self.records_seen,
            "records_kept": self.records_kept,
            "fields_masked": self.fields_masked,
            "fields_scrubbed": self.fields_scrubbed,
        }


class AliasFactory:
    """Deterministic alias builder based on SHA-256."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def user_alias(self, raw: str) -> str:
        if raw not in self._cache:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
            self._cache[raw] = f"user_{digest}"
        return self._cache[raw]

    def email_alias(self, raw: str) -> str:
        if raw not in self._cache:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
            self._cache[raw] = f"anon+{digest}@example.com"
        return self._cache[raw]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize production snapshots into safe mock data.")
    parser.add_argument("--input", required=True, help="Path to the raw JSON / JSONL file")
    parser.add_argument("--output", required=True, help="Destination path for sanitized data")
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=1.0,
        help="Float in (0,1] to down-sample the dataset deterministically",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Write JSON with indentation (only applies to array output)",
    )
    return parser.parse_args()


def _load_records(path: Path) -> list[JsonObject]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback to JSON Lines
        records: list[JsonObject] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parsed_line = json.loads(line)
            if not isinstance(parsed_line, dict):
                raise ValueError("JSONL 模式要求每行是一个对象")
            records.append(parsed_line)
        return records
    if not isinstance(parsed, list):
        raise ValueError("输入 JSON 顶层必须是数组或 JSON Lines")
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("数组元素必须是对象")
    return parsed


def _should_remove_key(key: str) -> bool:
    lowered = key.lower()
    return any(substr in lowered for substr in SENSITIVE_SUBSTRINGS)


def _is_sensitive_name(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_NAME_KEYS


def _sanitize_scalar(key: str, value: JsonPrimitive, alias_factory: AliasFactory, stats: SanitizeStats) -> JsonPrimitive:
    if value is None:
        return value
    if isinstance(value, str):
        if key.lower() == "email":
            stats.fields_masked += 1
            return alias_factory.email_alias(value)
        if _is_sensitive_name(key):
            stats.fields_masked += 1
            return alias_factory.user_alias(value)
        if key.lower() in {"ip", "ip_address"}:
            stats.fields_masked += 1
            return "0.0.0.0"
    return value


def _sanitize_value(key: str, value: JsonValue, alias_factory: AliasFactory, stats: SanitizeStats) -> JsonValue:
    if _should_remove_key(key):
        stats.fields_scrubbed += 1
        return "REDACTED"
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v, alias_factory, stats) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, item, alias_factory, stats) for item in value]
    return _sanitize_scalar(key, value, alias_factory, stats)


def sanitize_records(records: Iterable[JsonObject], sample_rate: float) -> tuple[list[JsonObject], SanitizeStats]:
    stats = SanitizeStats()
    alias_factory = AliasFactory()
    rng = random.Random(42)
    sanitized: list[JsonObject] = []

    for record in records:
        stats.records_seen += 1
        if sample_rate < 1.0 and rng.random() > sample_rate:
            continue
        sanitized_record: JsonObject = {
            key: _sanitize_value(key, value, alias_factory, stats) for key, value in record.items()
        }
        sanitized.append(sanitized_record)
        stats.records_kept += 1

    return sanitized, stats


def write_output(path: Path, records: list[JsonObject], pretty: bool) -> None:
    indent = 2 if pretty else None
    path.write_text(json.dumps(records, ensure_ascii=False, indent=indent), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not 0 < args.sample_rate <= 1:
        raise SystemExit("--sample-rate 必须在 (0, 1] 区间内")

    try:
        records = _load_records(input_path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 无法读取输入文件: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    sanitized, stats = sanitize_records(records, args.sample_rate)

    try:
        write_output(output_path, sanitized, args.pretty)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 写入输出文件失败: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("✨ 脱敏完成！")
    print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
