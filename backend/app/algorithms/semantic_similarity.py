"""
语义相似度计算引擎 - 智能社区发现核心组件
基于sentence-transformers实现高效的语义相似度计算与缓存优化
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import numpy as np
from numpy.typing import NDArray

from ..core.types import JsonValue

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer

# 模块级别的全局变量定义
try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
    SentenceTransformer: Optional[type[_SentenceTransformer]] = _SentenceTransformer
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
import aiofiles
import aiofiles.os
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """相似度计算结果"""

    query_text: str
    similarities: NDArray[np.float64]
    computation_time: float
    cache_hit: bool
    model_info: Dict[str, str]


class SemanticSimilarityEngine:
    """
    高效的语义相似度计算引擎

    核心功能：
    1. 使用sentence-transformers进行语义向量编码
    2. 预计算社区向量缓存，避免重复计算
    3. 批量矩阵运算，比循环快10-100倍
    4. 异步文件操作，提升I/O性能
    """

    # 模型配置
    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384维，平衡速度和精度
    VECTOR_DIM = 384

    # 缓存配置
    CACHE_DIR = "data/vectors"
    COMMUNITY_VECTORS_FILE = "community_vectors.npy"
    COMMUNITY_METADATA_FILE = "community_metadata.json"

    # 类型注解
    model: Optional[Any]  # SentenceTransformer or None
    community_vectors: Optional[NDArray[np.float64]]
    community_metadata: Optional[dict[str, JsonValue]]

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
        enable_cache: bool = True,
    ):
        """
        初始化语义相似度引擎

        Args:
            model_name: 使用的sentence-transformer模型名称
            cache_dir: 向量缓存目录
            enable_cache: 是否启用向量缓存
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.cache_dir = Path(cache_dir or self.CACHE_DIR)
        self.enable_cache = enable_cache

        # 初始化模型
        self.model = None
        self.community_vectors = None
        self.community_metadata = None

        # 性能统计
        self.stats = {"computations": 0, "cache_hits": 0, "avg_computation_time": 0.0}

        logger.info(
            f"SemanticSimilarityEngine初始化: model={self.model_name}, "
            f"cache_enabled={self.enable_cache}"
        )

    async def initialize(self) -> None:
        """异步初始化引擎"""
        start_time = time.time()

        # 创建缓存目录
        if self.enable_cache:
            await aiofiles.os.makedirs(self.cache_dir, exist_ok=True)

        # 加载sentence-transformer模型
        await self._load_model()

        # 加载预计算向量
        if self.enable_cache:
            await self._load_cached_vectors()

        init_time = time.time() - start_time
        logger.info(f"SemanticSimilarityEngine初始化完成，耗时: {init_time:.2f}秒")

    async def _load_model(self) -> None:
        """加载sentence-transformer模型"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers不可用，使用Mock模型")
            self.model = None
            return

        if SentenceTransformer is None:
            logger.error("SentenceTransformer类不可用")
            self.model = None
            return

        try:
            # 在子线程中加载模型，避免阻塞主线程
            loop = asyncio.get_event_loop()
            loaded_model = await loop.run_in_executor(
                None, SentenceTransformer, self.model_name
            )
            self.model = loaded_model
            logger.info(f"模型加载完成: {self.model_name}")
            return
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self.model = None
            return

    async def _load_cached_vectors(self) -> None:
        """加载预计算的社区向量"""
        vectors_path = self.cache_dir / self.COMMUNITY_VECTORS_FILE
        metadata_path = self.cache_dir / self.COMMUNITY_METADATA_FILE

        # Early return pattern - 文件不存在时直接返回
        if not (vectors_path.exists() and metadata_path.exists()):
            logger.warning("预计算向量文件不存在，需要先运行预计算")
            return

        try:
            # 异步加载向量
            loaded_vectors = await asyncio.get_event_loop().run_in_executor(
                None, np.load, str(vectors_path)
            )
            self.community_vectors = loaded_vectors

            # 异步加载元数据
            async with aiofiles.open(metadata_path, "r", encoding="utf-8") as f:
                content = await f.read()
                self.community_metadata = json.loads(content)

            # np.load()成功返回后，community_vectors不会是None
            # mypy: community_vectors 可能是 None 的联合类型，这里显式收敛
            vecs = self.community_vectors
            count = int(len(vecs)) if isinstance(vecs, np.ndarray) else 0
            logger.info(f"预计算向量加载完成: {count}个社区向量")
            return

        except Exception as e:
            logger.error(f"向量缓存加载失败: {e}")
            self.community_vectors = None
            self.community_metadata = None
            return

    async def compute_similarity_batch(
        self, query_text: str, target_texts: Optional[List[str]] = None
    ) -> SimilarityResult:
        """
        批量计算语义相似度

        Args:
            query_text: 查询文本
            target_texts: 目标文本列表，为None时使用预计算向量

        Returns:
            SimilarityResult: 相似度计算结果
        """
        if not self.model:
            raise RuntimeError("模型未初始化，请先调用initialize()")

        start_time = time.time()
        cache_hit = False

        # 如果使用预计算向量
        if target_texts is None:
            if self.community_vectors is None:
                raise RuntimeError("预计算向量未加载，请提供target_texts或运行预计算")

            similarities = await self._compute_with_cached_vectors(query_text)
            cache_hit = True

        else:
            # 实时计算相似度
            similarities = await self._compute_realtime_similarities(
                query_text, target_texts
            )

        computation_time = time.time() - start_time

        # 更新统计信息
        self._update_stats(computation_time, cache_hit)

        return SimilarityResult(
            query_text=query_text,
            similarities=similarities,
            computation_time=computation_time,
            cache_hit=cache_hit,
            model_info={
                "model_name": self.model_name,
                "vector_dim": str(self.VECTOR_DIM),
            },
        )

    async def _compute_with_cached_vectors(
        self, query_text: str
    ) -> NDArray[np.float64]:
        """使用预计算向量计算相似度"""
        if self.model is None:
            raise RuntimeError("模型未加载")

        assert self.model is not None
        model = self.model  # 局部变量避免lambda中的类型推断问题
        # 编码查询文本
        query_vector = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.encode([query_text], convert_to_numpy=True)
        )

        # 批量计算余弦相似度 - 矩阵运算，高效
        similarities = await asyncio.get_event_loop().run_in_executor(
            None, lambda: cosine_similarity(query_vector, self.community_vectors)[0]
        )

        return np.asarray(similarities, dtype=np.float64)

    async def _compute_realtime_similarities(
        self, query_text: str, target_texts: List[str]
    ) -> NDArray[np.float64]:
        """实时计算相似度"""
        if self.model is None:
            raise RuntimeError("模型未加载")

        assert self.model is not None
        model = self.model  # 局部变量避免lambda中的类型推断问题
        # 批量编码所有文本
        all_texts = [query_text] + target_texts

        vectors = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.encode(all_texts, convert_to_numpy=True)
        )

        # 分离查询向量和目标向量
        query_vector = vectors[0:1]
        target_vectors = vectors[1:]

        # 计算相似度
        similarities = await asyncio.get_event_loop().run_in_executor(
            None, lambda: cosine_similarity(query_vector, target_vectors)[0]
        )

        return np.asarray(similarities, dtype=np.float64)

    async def precompute_community_vectors(
        self, communities: list[dict[str, JsonValue]], text_field: str = "combined_text"
    ) -> Optional[NDArray[np.float64]]:
        """
        预计算社区向量并缓存

        Args:
            communities: 社区数据列表
            text_field: 用于向量计算的文本字段名
        """
        if not self.model:
            raise RuntimeError("模型未初始化，请先调用initialize()")

        if not self.enable_cache:
            logger.warning("缓存功能已禁用，跳过预计算")
            return None

        start_time = time.time()

        # 提取文本
        texts = []
        metadata = []

        for i, community in enumerate(communities):
            if text_field in community:
                texts.append(community[text_field])
            else:
                # 如果没有combined_text，组合描述和标签
                # 统一将可变类型转换为字符串，确保类型安全
                tags_val = community.get("tags", [])
                if isinstance(tags_val, list):
                    tags_joined = " ".join(str(t) for t in tags_val)
                else:
                    tags_joined = str(tags_val)
                desc = str(community.get("description", ""))
                combined = f"{desc} {tags_joined}"
                texts.append(combined.strip())

            # 保存元数据
            metadata.append(
                {
                    "index": i,
                    "id": community.get("id", f"community_{i}"),
                    "name": community.get("name", ""),
                    "description": str(community.get("description", ""))[:100],  # 截断长描述
                }
            )

        logger.info(f"开始预计算 {len(texts)} 个社区向量...")

        assert self.model is not None
        model = self.model  # 局部变量避免lambda中的类型推断问题
        # 批量编码向量
        vectors = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: model.encode(texts, convert_to_numpy=True, show_progress_bar=True),
        )

        # 保存向量到文件
        vectors_path = self.cache_dir / self.COMMUNITY_VECTORS_FILE
        await asyncio.get_event_loop().run_in_executor(
            None, np.save, str(vectors_path), vectors
        )

        # 保存元数据
        metadata_path = self.cache_dir / self.COMMUNITY_METADATA_FILE
        metadata_content = {
            "total_communities": len(communities),
            "vector_dim": vectors.shape[1],
            "model_name": self.model_name,
            "created_at": time.time(),
            "communities": metadata,
        }

        async with aiofiles.open(metadata_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(metadata_content, indent=2, ensure_ascii=False))

        # 更新内存中的缓存
        self.community_vectors = vectors
        self.community_metadata = metadata_content

        computation_time = time.time() - start_time
        logger.info(
            f"预计算完成: {len(vectors)}个向量，"
            f"维度: {vectors.shape[1]}，耗时: {computation_time:.2f}秒"
        )

        return np.asarray(vectors, dtype=np.float64)

    def get_top_similar_indices(
        self, similarities: Any, top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """
        获取相似度最高的K个索引

        Args:
            similarities: 相似度数组
            top_k: 返回的数量

        Returns:
            List[Tuple[int, float]]: (索引, 相似度分数) 的列表
        """
        # 获取排序后的索引
        sorted_indices = np.argsort(similarities)[::-1]

        # 返回top-k结果
        return [(int(idx), float(similarities[idx])) for idx in sorted_indices[:top_k]]

    def _update_stats(self, computation_time: float, cache_hit: bool) -> None:
        """更新性能统计"""
        self.stats["computations"] += 1
        if cache_hit:
            self.stats["cache_hits"] += 1

        # 计算平均计算时间
        total_computations = self.stats["computations"]
        current_avg = self.stats["avg_computation_time"]
        self.stats["avg_computation_time"] = (
            current_avg * (total_computations - 1) + computation_time
        ) / total_computations

    def get_performance_stats(self) -> dict[str, JsonValue]:
        """获取性能统计信息"""
        cache_hit_rate = 0.0
        if self.stats["computations"] > 0:
            cache_hit_rate = self.stats["cache_hits"] / self.stats["computations"]

        return {
            "total_computations": self.stats["computations"],
            "cache_hits": self.stats["cache_hits"],
            "cache_hit_rate": cache_hit_rate,
            "avg_computation_time": self.stats["avg_computation_time"],
            "model_name": self.model_name,
            "cached_vectors": (
                len(self.community_vectors) if self.community_vectors is not None else 0
            ),
        }

    async def health_check(self) -> Dict[str, Union[bool, str, float, Tuple[int, ...]]]:
        """系统健康检查"""
        health_status: Dict[str, Union[bool, str, float, Tuple[int, ...]]] = {
            "model_loaded": self.model is not None,
            "cache_enabled": self.enable_cache,
            "vectors_cached": self.community_vectors is not None,
            "cache_dir_exists": self.cache_dir.exists() if self.enable_cache else False,
        }

        # 简单的推理测试
        if self.model:
            try:
                assert self.model is not None
                model = self.model  # 局部变量避免lambda中的类型推断问题
                start_time = time.time()
                test_vector = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: model.encode(["test sentence"], convert_to_numpy=True),
                )
                inference_time = time.time() - start_time

                health_status.update(
                    {
                        "inference_test": True,
                        "inference_time": inference_time,
                        "vector_shape": tuple(test_vector.shape),
                    }
                )
            except Exception as e:
                health_status.update({"inference_test": False, "error": str(e)})

        return health_status

    def get_algorithm_metadata(self) -> dict[str, JsonValue]:
        """获取算法元数据"""
        return {
            "algorithm_name": "Semantic Similarity with Sentence Transformers",
            "version": "1.0.0",
            "model_name": self.model_name,
            "vector_dimension": self.VECTOR_DIM,
            "similarity_metric": "cosine_similarity",
            "cache_enabled": self.enable_cache,
            "performance_stats": self.get_performance_stats(),
        }
