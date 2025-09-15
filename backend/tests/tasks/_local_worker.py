"""
本地Celery Worker测试夹具（Context7兼容最小实现）

目的：
- 在Docker镜像构建失败（pytest-celery vendor镜像）时提供可靠的本地worker回退路径
- 仍然使用真实的Redis broker/backend，保留异步语义
"""
from __future__ import annotations

import os
import pytest
from celery.contrib.testing.worker import start_worker


@pytest.fixture(scope="session")
def celery_app_instance():
    # 复用项目的统一Celery应用配置
    from app.core.celery_app import get_celery_app

    app = get_celery_app()

    # 允许在CI/本地通过环境变量覆盖broker/backend
    broker_url = os.getenv("CELERY_BROKER_URL")
    result_backend = os.getenv("CELERY_RESULT_BACKEND")
    if broker_url:
        app.conf.broker_url = broker_url
    if result_backend:
        app.conf.result_backend = result_backend

    # 确保异步执行
    app.conf.task_always_eager = False
    return app


@pytest.fixture(scope="function")
def local_celery_worker(celery_app_instance):
    # 使用Celery官方testing工具启动本地worker，避免Docker依赖
    with start_worker(
        celery_app_instance,
        concurrency=1,
        logfile="-",
        loglevel="INFO",
        perform_ping_check=False,
    ) as worker:
        yield worker
