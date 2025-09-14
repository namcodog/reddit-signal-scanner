"""
占位维护任务模块：提供基本任务以满足 Celery include 导入。
"""
from ..core.celery_app import get_celery_app
from typing import Any, Callable, TypeVar, cast

celery_app = get_celery_app()


TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def _typed_task(*args: Any, **kwargs: Any) -> Callable[[TFunc], TFunc]:
    """轻量的类型化装饰器包装，避免未类型化装饰器污染签名。"""
    decorator = celery_app.task(*args, **kwargs)

    def wrapper(func: TFunc) -> TFunc:
        return cast(TFunc, decorator(func))

    return wrapper


@_typed_task(name="app.tasks.maintenance.cache_maintenance")
def cache_maintenance() -> str:
    return "ok"
