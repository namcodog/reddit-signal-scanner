"""Regression tests ensuring report-related modules import cleanly."""

from __future__ import annotations

from typing import Any, Mapping, Sequence, cast

import pytest

pytestmark = pytest.mark.integration


def test_report_modules_importable() -> None:
    from backend.app.models.base import Base as BaseModel
    from backend.app.models.report import Report, ReportCreateRequest, create_report
    from backend.app.services.report_cache_service import ReportCacheService

    assert hasattr(BaseModel, "metadata")
    assert Report.__tablename__ == "reports"
    assert callable(create_report)
    assert hasattr(ReportCacheService, "get_report")

    schema_fields = _schema_field_names(ReportCreateRequest)
    assert {"analysis_id", "html_content", "status"}.issubset(schema_fields)


def test_report_model_structure() -> None:
    from backend.app.models.report import Report

    required_attrs: Sequence[str] = (
        "id",
        "analysis_id",
        "html_content",
        "status",
        "created_at",
    )
    for name in required_attrs:
        assert hasattr(Report, name)


def _schema_field_names(model: Any) -> Sequence[str]:
    raw_fields: Mapping[str, Any]
    if hasattr(model, "model_fields"):
        raw_fields = cast(Mapping[str, Any], getattr(model, "model_fields"))
    else:
        raw_fields = cast(Mapping[str, Any], getattr(model, "__fields__"))
    return tuple(raw_fields.keys())
