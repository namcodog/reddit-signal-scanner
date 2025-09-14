"""
兼容性适配器 - 支持从Dict[str, Any]到Pydantic模型的平滑过渡

基于FastAPI最佳实践的渐进式重构策略：
1. 保持向后兼容性
2. 支持Union类型注解
3. 使用jsonable_encoder确保序列化兼容性
4. 提供类型安全的转换函数
"""

from typing import Any, Callable, Dict, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ...core.types import JsonValue

# 泛型类型变量
T = TypeVar("T", bound=BaseModel)


def ensure_pydantic_model(
    data: Union[dict[str, JsonValue], BaseModel], model_class: Type[T]
) -> T:
    """
    确保数据是Pydantic模型实例

    Args:
        data: 原始数据（可能是dict或已经是Pydantic模型）
        model_class: 目标Pydantic模型类

    Returns:
        Pydantic模型实例
    """
    if isinstance(data, BaseModel):
        # 如果已经是Pydantic模型，检查类型是否匹配
        if isinstance(data, model_class):
            return data
        else:
            # 类型不匹配，转换为dict后重新创建
            return model_class(**data.model_dump())
    elif isinstance(data, dict):
        # 从dict创建Pydantic模型
        return model_class(**data)
    else:
        raise TypeError(f"Expected dict or BaseModel, got {type(data)}")


def ensure_json_serializable(
    data: Union[dict[str, JsonValue], BaseModel],
) -> dict[str, JsonValue]:
    """
    确保数据可以JSON序列化

    Args:
        data: 原始数据（dict或Pydantic模型）

    Returns:
        JSON兼容的字典
    """
    if isinstance(data, BaseModel):
        # 使用FastAPI的jsonable_encoder确保兼容性
        result = jsonable_encoder(data)
        # 确保返回dict类型，符合FastAPI最佳实践
        return result if isinstance(result, dict) else {"data": result}
    elif isinstance(data, dict):
        # 对于dict，也使用jsonable_encoder处理可能的复杂对象
        result = jsonable_encoder(data)
        return result if isinstance(result, dict) else {"data": result}
    else:
        raise TypeError(f"Expected dict or BaseModel, got {type(data)}")


def create_backward_compatible_response(
    data: Union[dict[str, JsonValue], BaseModel], prefer_dict: bool = False
) -> Union[dict[str, JsonValue], BaseModel]:
    """
    创建向后兼容的响应

    Args:
        data: 原始数据
        prefer_dict: 是否优先返回dict格式（用于过渡期）

    Returns:
        根据prefer_dict参数返回dict或BaseModel
    """
    if prefer_dict:
        return ensure_json_serializable(data)
    else:
        return data


# FastAPI最佳实践：简单明确的类型转换函数
# 移除复杂的装饰器，采用直接函数调用模式


# 类型联合定义 - 用于过渡期的类型注解
ResponseType = Union[dict[str, JsonValue], BaseModel]


class TransitionResponse:
    """过渡期响应包装器 - 同时支持dict和Pydantic模型"""

    def __init__(self, data: ResponseType) -> None:
        self.data = data

    def as_dict(self) -> dict[str, JsonValue]:
        """返回dict格式"""
        return ensure_json_serializable(self.data)

    def as_model(self, model_class: Type[T]) -> T:
        """返回Pydantic模型格式"""
        return ensure_pydantic_model(self.data, model_class)

    def to_fastapi_response(self) -> dict[str, JsonValue]:
        """返回适合FastAPI的响应格式"""
        return self.as_dict()


# 常用适配器函数
def adapt_error_statistics(data: ResponseType) -> BaseModel:
    """错误统计数据适配器"""
    from ..responses.error import ErrorStatisticsResponse

    return TransitionResponse(data).as_model(ErrorStatisticsResponse)


def adapt_crawler_task(data: ResponseType) -> BaseModel:
    """爬虫任务数据适配器"""
    from ..responses.task import CrawlerTaskResponse

    return TransitionResponse(data).as_model(CrawlerTaskResponse)


def adapt_auth_context(data: ResponseType) -> BaseModel:
    """认证上下文数据适配器"""
    from ..responses.auth import UnifiedAuthContextResponse

    return TransitionResponse(data).as_model(UnifiedAuthContextResponse)


def adapt_algorithm_metadata(data: ResponseType) -> BaseModel:
    """算法元数据适配器"""
    from ..responses.algorithm import AlgorithmMetadataResponse

    return TransitionResponse(data).as_model(AlgorithmMetadataResponse)
