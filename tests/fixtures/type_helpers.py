"""Shared type-checking helpers for tests.

These helpers keep mypy satisfied while we interact with SQLAlchemy models
that expose InstrumentedAttribute proxies at runtime. Using them avoids
copying the same `cast` patterns across multiple test modules.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, TypeVar

from backend.app.models.analysis import Analysis
from backend.app.models.task import FailureCategory, TaskStatus

T = TypeVar("T")


def ensure_uuid(value: Any) -> "uuid.UUID":  # type: ignore[name-defined]
    """Assert that the value is a UUID and return it."""
    import uuid

    if not isinstance(value, uuid.UUID):
        raise AssertionError(f"Expected UUID, got {type(value)!r}")
    return value


def ensure_task_status(value: Any) -> TaskStatus:
    if not isinstance(value, TaskStatus):
        raise AssertionError(f"Expected TaskStatus, got {type(value)!r}")
    return value


def ensure_decimal(value: Any) -> Decimal:
    if not isinstance(value, Decimal):
        raise AssertionError(f"Expected Decimal, got {type(value)!r}")
    return value


def ensure_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise AssertionError(f"Expected datetime, got {type(value)!r}")
    return value


def ensure_optional_datetime(value: Any) -> Optional[datetime]:
    if value is not None and not isinstance(value, datetime):
        raise AssertionError(f"Expected Optional[datetime], got {type(value)!r}")
    return value


def ensure_optional_failure_category(value: Any) -> Optional[FailureCategory]:
    if value is not None and not isinstance(value, FailureCategory):
        raise AssertionError(f"Expected Optional[FailureCategory], got {type(value)!r}")
    return value


def ensure_optional_analysis(value: Any) -> Optional[Analysis]:
    if value is not None and not isinstance(value, Analysis):
        raise AssertionError(f"Expected Optional[Analysis], got {type(value)!r}")
    return value
