"""
分析步骤抽象基类 - Reddit Signal Scanner
定义所有分析步骤的统一接口和基础行为

基于Linus设计原则：
- 统一接口消除特殊情况
- 简洁的抽象，只定义必要的行为
- 子类专注业务逻辑，基类处理通用逻辑
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, cast

from ..models.analysis_pipeline import (
    PipelineData,
    PipelineResult,
    StepResultValue,
    StepStatus,
)
from .analyzer_config import StepConfig
from .types import JsonValue, StepInfo


class AnalysisStep(ABC):
    """
    分析步骤抽象基类 - 所有步骤的统一接口

    设计原则：
    - 每个步骤都是独立的处理单元
    - 统一的输入输出格式（PipelineData → PipelineResult）
    - 内置超时控制、错误处理、性能监控
    - 子类只需实现核心的 _process_step 方法
    """

    def __init__(self, config: StepConfig) -> None:
        self.config = config
        self.name = self.__class__.__name__.replace("Step", "").lower()
        self.logger = logging.getLogger(f"analysis.{self.name}")

        # 性能追踪
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    async def process(self, data: PipelineData) -> PipelineResult:
        """
        处理数据 - 主入口方法

        统一处理流程：
        1. 输入验证
        2. 超时控制
        3. 核心处理逻辑
        4. 结果验证
        5. 性能记录
        """
        self._start_time = time.time()

        try:
            # 1. 输入验证
            if not self.validate_input(data):
                return self._create_error_result("输入验证失败")

            self.logger.info(f"开始执行步骤: {self.name}")

            # 2. 超时控制
            try:
                result = await asyncio.wait_for(
                    self._process_step(data), timeout=self.config.max_duration
                )
            except asyncio.TimeoutError:
                return self._create_error_result(
                    f"步骤超时 (>{self.config.max_duration}s)",
                    status=StepStatus.TIMEOUT,
                )

            # 3. 结果验证
            if not self._validate_result(result, data):
                return self._create_error_result("输出验证失败")

            # 4. 记录性能
            duration = time.time() - self._start_time
            result.duration = duration
            result.metadata.update(
                {
                    "step_name": self.name,
                    "config_version": self.config.step_name,
                    "execution_time": duration,
                }
            )

            self.logger.info(
                f"步骤 {self.name} 执行完成，耗时: {duration:.2f}s，" f"成功: {result.success}"
            )

            return result

        except Exception as e:
            self.logger.error(f"步骤 {self.name} 执行异常: {str(e)}", exc_info=True)
            return self._create_error_result(f"执行异常: {str(e)}")

    @abstractmethod
    async def _process_step(self, data: PipelineData) -> PipelineResult:
        """
        核心处理逻辑 - 子类必须实现

        Args:
            data: 流水线数据

        Returns:
            PipelineResult: 处理结果
        """
        pass

    @abstractmethod
    def validate_input(self, data: PipelineData) -> bool:
        """
        输入验证 - 子类必须实现

        Args:
            data: 流水线数据

        Returns:
            bool: 输入是否有效
        """
        pass

    def _validate_result(self, result: PipelineResult, data: PipelineData) -> bool:
        """
        结果验证 - 基类实现，子类可覆盖

        Args:
            result: 步骤结果
            data: 输入数据

        Returns:
            bool: 结果是否有效
        """
        # 基础验证（类型由签名保证，此处不再做运行时类型检查）
        if result.step_name != self.name:
            self.logger.error(f"步骤名不匹配: 期望{self.name}, 实际{result.step_name}")
            return False

        return True

    def _create_error_result(
        self, error_message: str, status: StepStatus = StepStatus.FAILED
    ) -> PipelineResult:
        """
        创建错误结果

        Args:
            error_message: 错误消息
            status: 错误状态

        Returns:
            PipelineResult: 错误结果
        """
        duration = 0.0
        if self._start_time:
            duration = time.time() - self._start_time

        return PipelineResult(
            step_name=self.name,
            duration=duration,
            data={},
            success=False,
            status=status,
            error_message=error_message,
            metadata={
                "step_name": self.name,
                "error_time": time.time(),
                "config_version": self.config.step_name,
            },
        )

    def get_expected_duration(self) -> float:
        """预期耗时（秒）"""
        return self.config.max_duration

    def get_step_info(self) -> StepInfo:
        """获取步骤信息"""
        return {
            "name": self.name,
            "class_": self.__class__.__name__,
            "expected_duration": float(self.get_expected_duration()),
            "config": {
                "max_duration": float(self.config.max_duration),
                "step_name": self.config.step_name,
            },
        }


class BaseAnalysisStep(AnalysisStep):
    """
    基础分析步骤 - 提供常用的辅助方法

    继承此类可以获得：
    - 数据访问辅助方法
    - 结果构建辅助方法
    - 错误处理辅助方法
    - 性能监控辅助方法
    """

    def get_previous_result(
        self, data: PipelineData, step_name: str
    ) -> Optional[Dict[str, StepResultValue]]:
        """安全获取前序步骤结果"""
        return data.get_step_result(step_name)

    def create_success_result(
        self, result_data: Dict[str, StepResultValue]
    ) -> PipelineResult:
        """创建成功结果"""
        return PipelineResult(
            step_name=self.name,
            duration=0.0,  # 将在process方法中更新
            data=cast(Dict[str, JsonValue], result_data),
            success=True,
            status=StepStatus.COMPLETED,
        )

    def add_warning(self, data: PipelineData, warning: str) -> None:
        """添加警告到流水线数据"""
        data.add_warning(warning, self.name)
        self.logger.warning(warning)

    def add_error(self, data: PipelineData, error: str) -> None:
        """添加错误到流水线数据"""
        data.add_error(error, self.name)
        self.logger.error(error)

    def log_performance(
        self, operation: str, duration: float, **metrics: Union[str, int, float]
    ) -> None:
        """记录性能指标"""
        self.logger.info(f"性能指标 - {operation}: {duration:.3f}s, " f"指标: {metrics}")

    def validate_common_input(self, data: PipelineData) -> bool:
        """通用输入验证"""
        if not data.product_description.strip():
            self.logger.error("产品描述为空")
            return False

        if not data.is_healthy():
            self.logger.error(f"流水线状态异常，错误: {data.errors}")
            return False

        return True

    async def _execute_with_timeout(
        self, coro: Any, timeout: Optional[float] = None
    ) -> Any:
        """执行协程并处理超时"""
        if timeout is None:
            timeout = self.config.max_duration / 2  # 给步骤留一半时间

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning(f"子操作超时 (>{timeout}s)")
            raise

    def _calculate_confidence(self, data_quality: float, result_count: int) -> float:
        """计算置信度评分"""
        if result_count == 0:
            return 0.0

        # 基础置信度基于数据质量
        base_confidence = max(0.0, min(1.0, data_quality))

        # 结果数量调整
        count_factor = min(1.0, result_count / 10)  # 10个结果为满分

        return base_confidence * count_factor


# 便捷的装饰器
def step_performance_monitor(func: Any) -> Any:
    """步骤性能监控装饰器"""

    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            duration = time.time() - start_time
            self.log_performance(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"{func.__name__} 执行失败，耗时: {duration:.3f}s，错误: {e}")
            raise

    return wrapper


# 兼容导出：某些测试从 step_base 导入 StepResult
# 将 StepResult 作为 PipelineResult 的别名导出，避免大范围改测
StepResult = PipelineResult
