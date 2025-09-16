"""
智能社区发现分析步骤 - PRD03-02核心实现
Step 1: 智能社区发现算法集成到分析引擎
基于TF-IDF + 语义相似度 + 多维度评分的精准社区推荐
"""

import asyncio
import logging
import time
from typing import Any, List, Mapping, Optional
from app.core.types import StepInfo

from app.core.analyzer_config import StepConfig
from app.core.step_base import BaseAnalysisStep
from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus

from ..community_discovery import (
    CommunityDiscoveryService,
    DiscoveryRequest,
    DiscoveryResponse,
)

logger = logging.getLogger(__name__)


class CommunityDiscoveryStep(BaseAnalysisStep):
    """
    智能社区发现分析步骤 - 4步分析流水线的Step 1

    核心功能：
    1. 基于产品描述的关键词提取和产品类型识别
    2. 语义相似度计算匹配最相关社区
    3. 多维度评分 (相似度40% + 活跃度30% + 质量30%)
    4. 动态数量决策 (根据缓存命中率决定10/20/30个社区)
    5. 多样性控制确保社区类别分布合理

    输出数据：
    - communities: 排序后的推荐社区列表
    - algorithm_metadata: 算法执行元数据
    - processing_stats: 性能统计信息
    """

    def __init__(self, config: StepConfig) -> None:
        """初始化社区发现步骤"""
        super().__init__(config)

        # 社区发现服务实例
        self.discovery_service: Optional[CommunityDiscoveryService] = None

        # 步骤特定配置
        self.step_config = {
            "default_max_communities": 20,
            "fallback_communities": 10,
            "quality_threshold": 0.1,
            "enable_diversity": True,
        }

        logger.info(f"CommunityDiscoveryStep初始化完成: {self.name}")

    async def _initialize_service_if_needed(self) -> None:
        """延迟初始化社区发现服务"""
        if self.discovery_service is None:
            try:
                self.logger.info("初始化CommunityDiscoveryService...")
                self.discovery_service = CommunityDiscoveryService()
                await self.discovery_service.initialize()
                self.logger.info("CommunityDiscoveryService初始化成功")
            except (RuntimeError, ValueError, TypeError) as e:
                self.logger.error(f"社区发现服务初始化失败: {e}")
                raise

    def validate_input(self, data: PipelineData) -> bool:
        """
        输入验证 - 检查是否具备执行社区发现的条件

        Args:
            data: 流水线数据

        Returns:
            bool: 是否可以执行
        """
        # 通用验证
        if not self.validate_common_input(data):
            return False

        # 特定验证
        product_description = data.product_description.strip()
        if len(product_description) < 10:
            self.add_error(data, "产品描述过短，至少需要10个字符")
            return False

        if len(product_description) > 2000:
            self.add_warning(data, "产品描述过长，将截取前2000个字符处理")
            data.product_description = product_description[:2000]

        self.logger.debug(f"输入验证通过，产品描述长度: {len(product_description)}")
        return True

    async def _process_step(self, data: PipelineData) -> PipelineResult:
        """
        执行智能社区发现核心逻辑

        Args:
            data: 流水线数据

        Returns:
            PipelineResult: 包含发现的社区数据
        """
        step_start_time = time.time()

        try:
            # 1. 初始化服务
            await self._initialize_service_if_needed()

            # 2. 构建发现请求
            discovery_request = self._build_discovery_request(data)

            # 3. 执行社区发现
            self.logger.info(
                f"开始执行社区发现: {discovery_request.product_description[:50]}..."
            )

            # mypy: self.discovery_service 已在上方初始化，但类型仍为 Optional；此处做一次局部收敛
            service = self.discovery_service
            assert service is not None
            discovery_response = await self._execute_with_timeout(
                service.discover_communities(discovery_request),
                timeout=self.config.max_duration - 5,  # 留5秒缓冲时间
            )

            # 4. 验证和处理结果
            processed_result = await self._process_discovery_response(
                discovery_response, data
            )

            # 5. 构建步骤结果
            result_data = {
                "communities": processed_result["communities"],
                "total_found": processed_result["total_found"],
                "algorithm_metadata": processed_result["algorithm_metadata"],
                "processing_stats": processed_result["processing_stats"],
                "confidence_score": self._calculate_step_confidence(processed_result),
                "recommendations": self._generate_recommendations(processed_result),
            }

            step_duration = time.time() - step_start_time
            self.log_performance(
                "community_discovery_complete",
                step_duration,
                communities_found=result_data["total_found"],
                confidence=result_data["confidence_score"],
            )

            success_result = self.create_success_result(result_data)

            # 添加成功消息到流水线
            communities_count = result_data["total_found"]
            self.logger.info(f"社区发现成功完成: 找到{communities_count}个相关社区")

            return success_result

        except asyncio.TimeoutError:
            error_msg = f"社区发现步骤超时 (>{self.config.max_duration}s)"
            self.add_error(data, error_msg)
            return self._create_error_result(error_msg, StepStatus.TIMEOUT)

        except (ValueError, RuntimeError, TypeError) as e:
            error_msg = f"社区发现执行异常: {str(e)}"
            self.add_error(data, error_msg)
            self.logger.error(error_msg, exc_info=True)
            return self._create_error_result(error_msg, StepStatus.FAILED)

    def _build_discovery_request(self, data: PipelineData) -> DiscoveryRequest:
        """构建社区发现请求"""

        # 获取用户配置的社区数量（来自 PipelineData.analysis_config）
        max_communities = None
        if (
            getattr(data, "analysis_config", None)
            and data.analysis_config.max_communities
        ):
            max_communities = data.analysis_config.max_communities

        # 构建请求
        request = DiscoveryRequest(
            product_description=data.product_description,
            target_keywords=(
                data.analysis_config.target_keywords
                if data.analysis_config.target_keywords
                else None
            ),
            max_results=max_communities,
            enable_cache=getattr(data.analysis_config, "enable_cache", True),
            filters=None,  # 后续版本支持
        )

        self.logger.debug(f"构建发现请求: max_results={request.max_results}")
        return request

    async def _process_discovery_response(
        self, response: DiscoveryResponse, data: PipelineData
    ) -> Mapping[str, Any]:
        """处理和验证发现响应"""

        # 基础验证
        if not response.communities:
            self.add_warning(data, "未找到相关社区，可能需要调整产品描述")
            return {
                "communities": [],
                "total_found": 0,
                "algorithm_metadata": response.algorithm_metadata,
                "processing_stats": response.processing_stats,
            }

        # 质量过滤
        high_quality_communities = []
        for community in response.communities:
            relevance_score = community.get("relevance_score", {})
            final_score = relevance_score.get("final_score", 0.0)

            if final_score >= self.step_config["quality_threshold"]:
                high_quality_communities.append(community)
            else:
                self.logger.debug(
                    f"过滤低质量社区: {community.get('name')} " f"(分数: {final_score:.3f})"
                )

        # 记录过滤统计
        original_count = len(response.communities)
        filtered_count = len(high_quality_communities)

        if filtered_count < original_count:
            self.logger.info(
                f"质量过滤: {original_count} → {filtered_count} "
                f"(阈值: {self.step_config['quality_threshold']})"
            )

        # 如果过滤后社区太少，降低阈值
        if filtered_count < 5 and original_count > 5:
            self.add_warning(
                data,
                f"高质量社区数量较少({filtered_count}个)，" f"建议优化产品描述以获得更精准的结果",
            )
            high_quality_communities = response.communities[:10]  # 取前10个

        return {
            "communities": high_quality_communities,
            "total_found": len(high_quality_communities),
            "algorithm_metadata": response.algorithm_metadata,
            "processing_stats": response.processing_stats,
            "filtering_stats": {
                "original_count": original_count,
                "filtered_count": filtered_count,
                "quality_threshold": self.step_config["quality_threshold"],
            },
        }

    def _calculate_step_confidence(self, processed_result: Mapping[str, Any]) -> float:
        """计算步骤置信度"""
        communities_count = processed_result["total_found"]

        if communities_count == 0:
            return 0.0

        # 基础置信度：基于找到的社区数量
        count_confidence: float = min(1.0, communities_count / 15)  # 15个社区为满分

        # 算法置信度：基于关键词提取和产品类型识别的置信度
        algorithm_meta = processed_result.get("algorithm_metadata", {})
        extracted_info = algorithm_meta.get("extracted_info", {})
        keyword_confidence: float = float(extracted_info.get("confidence", 0.5))

        # 质量置信度：基于平均评分
        avg_score: float = 0.0
        if communities_count > 0:
            total_score = sum(
                community.get("relevance_score", {}).get("final_score", 0.0)
                for community in processed_result["communities"]
            )
            avg_score = total_score / communities_count

        # 综合置信度
        final_confidence: float = (
            count_confidence * 0.4 + keyword_confidence * 0.3 + avg_score * 0.3
        )

        return float(min(1.0, final_confidence))

    def _generate_recommendations(
        self, processed_result: Mapping[str, Any]
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        communities_count = processed_result["total_found"]
        algorithm_meta = processed_result.get("algorithm_metadata", {})

        # 基于社区数量的建议
        if communities_count == 0:
            recommendations.append("未找到相关社区，建议：1) 简化产品描述；2) 使用更通用的关键词")
        elif communities_count < 5:
            recommendations.append("相关社区较少，建议补充产品的应用场景和目标用户信息")
        elif communities_count > 25:
            recommendations.append("找到较多社区，建议细化产品描述以获得更精准的推荐")

        # 基于产品类型的建议
        extracted_info = algorithm_meta.get("extracted_info", {})
        product_type = extracted_info.get("product_type", "unknown")

        if product_type == "general":
            recommendations.append("产品类型识别不够明确，建议明确说明产品属于SaaS、移动应用还是硬件产品")

        # 基于置信度的建议
        confidence = extracted_info.get("confidence", 0.5)
        if confidence < 0.6:
            recommendations.append("关键词提取置信度较低，建议使用更具体和专业的产品描述")

        return recommendations

    def _validate_result(self, result: PipelineResult, data: PipelineData) -> bool:
        """验证步骤结果"""
        if not super()._validate_result(result, data):
            return False

        # 社区发现特定验证
        result_data = result.data

        # 检查必需字段
        required_fields = [
            "communities",
            "total_found",
            "algorithm_metadata",
            "confidence_score",
        ]
        for field in required_fields:
            if field not in result_data:
                self.logger.error(f"缺失必需字段: {field}")
                return False

        # 检查数据类型
        if not isinstance(result_data["communities"], list):
            self.logger.error("communities字段必须是列表类型")
            return False

        if not isinstance(result_data["total_found"], int):
            self.logger.error("total_found字段必须是整数类型")
            return False

        # 检查数据一致性
        communities_list = result_data["communities"]
        total_count = result_data["total_found"]

        if len(communities_list) != total_count:
            self.logger.error(f"社区列表长度({len(communities_list)})与总数({total_count})不匹配")
            return False

        self.logger.debug("结果验证通过")
        return True

    async def health_check(self) -> Mapping[str, Any]:
        """健康检查"""
        health_status = {
            "step_name": self.name,
            "service_initialized": self.discovery_service is not None,
        }

        if self.discovery_service:
            try:
                service_health = await self.discovery_service.health_check()
                health_status.update(
                    {
                        "service_health": service_health,
                        "ready": service_health.get("service_initialized", False),
                    }
                )
            except (RuntimeError, ValueError, TypeError) as e:
                health_status.update(
                    {"service_health": {"error": str(e)}, "ready": False}
                )
        else:
            health_status["ready"] = False

        return health_status

    def get_step_info(self) -> StepInfo:
        """获取步骤信息"""
        # 仅返回基础 StepInfo（与父类签名一致），扩展信息另行暴露
        return super().get_step_info()
