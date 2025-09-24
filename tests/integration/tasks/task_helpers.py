"""Shared utilities for Celery task-based integration tests."""

from __future__ import annotations

from typing import cast

from celery.app.task import Task as CeleryTask

from tests import tasks as test_tasks


def get_task(name: str) -> CeleryTask:
    """Return a typed Celery task from the shared tests.tasks module."""
    return cast(CeleryTask, getattr(test_tasks, name))
