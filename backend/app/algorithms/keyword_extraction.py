"""
TF-IDF关键词提取器 - 智能社区发现核心组件
基于PRD03-02架构设计，实现高精度关键词提取与产品类型识别
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..core.types import JsonValue

yaml: Optional[ModuleType]
try:
    import yaml as _yaml

    yaml = _yaml
    yaml_available: bool = True
except ImportError:
    yaml = None
    yaml_available = False


# Pydantic响应模型和适配器导入
from ..schemas.responses.algorithm import AlgorithmMetadataResponse

logger = logging.getLogger(__name__)


@dataclass
class ExtractedKeywords:
    """关键词提取结果"""

    primary_keywords: List[str]  # 主要关键词
    product_type: str  # 产品类型
    domain_keywords: List[str]  # 领域特定关键词
    synonyms: List[str]  # 同义词扩展
    confidence: float  # 提取置信度


class KeywordExtractor:
    """
    TF-IDF + 领域词典的智能关键词提取器

    核心功能：
    1. TF-IDF基础关键词提取
    2. 产品类型识别 (SaaS/硬件/服务等)
    3. 领域词汇增强
    4. 同义词扩展
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化关键词提取器

        Args:
            config_path: 配置文件路径，为None时使用默认配置
        """
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words="english",
            ngram_range=(1, 2),  # 支持1-2gram
            min_df=1,  # 最小文档频率
            max_df=0.95,  # 最大文档频率，过滤常见词
            lowercase=True,
            token_pattern=r"[a-zA-Z-]+",  # 保留连字符词汇
            strip_accents="unicode",
        )

        # 加载领域词典和产品类型映射
        self.domain_keywords = self._load_domain_dictionary()
        self.product_type_patterns = self._load_product_type_patterns()
        self.synonym_mapping = self._load_synonym_mapping()

        # TF-IDF训练语料 (预定义常见产品描述模式)
        self._train_tfidf_model()

        logger.info("KeywordExtractor初始化完成")

    def extract_keywords(self, text: str, max_keywords: int = 20) -> ExtractedKeywords:
        """
        提取关键词并识别产品类型

        Args:
            text: 产品描述文本
            max_keywords: 最大关键词数量

        Returns:
            ExtractedKeywords: 包含关键词、产品类型等的结果对象
        """
        # 简化边界检查 - 统一处理为标准化文本
        text = str(text).strip() if text else ""
        if len(text) < 3:  # 最小有效长度
            return self._create_empty_result()

        # 文本预处理
        cleaned_text = self._preprocess_text(text)

        # 1. TF-IDF关键词提取
        tfidf_keywords = self._extract_tfidf_keywords(cleaned_text, max_keywords // 2)

        # 2. 产品类型识别
        product_type = self._identify_product_type(cleaned_text)

        # 3. 领域关键词增强
        domain_keywords = self._extract_domain_keywords(
            cleaned_text, product_type, max_keywords // 4
        )

        # 4. 同义词扩展
        all_base_keywords = list(set(tfidf_keywords + domain_keywords))
        synonyms = self._expand_synonyms(all_base_keywords, max_keywords // 4)

        # 5. 合并去重，保持重要性排序
        primary_keywords = self._merge_and_rank_keywords(
            tfidf_keywords, domain_keywords, max_keywords
        )

        # 6. 计算置信度
        confidence = self._calculate_confidence(
            cleaned_text, primary_keywords, product_type
        )

        result = ExtractedKeywords(
            primary_keywords=primary_keywords,
            product_type=product_type,
            domain_keywords=domain_keywords,
            synonyms=synonyms,
            confidence=confidence,
        )

        logger.debug(
            f"关键词提取完成: {len(primary_keywords)}个主要关键词, "
            f"产品类型: {product_type}, 置信度: {confidence:.2f}"
        )

        return result

    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 移除特殊字符，保留字母、数字、连字符、空格
        cleaned = re.sub(r"[^\w\s-]", " ", text)

        # 规范化空白字符
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned.lower()

    def _extract_tfidf_keywords(self, text: str, max_keywords: int) -> List[str]:
        """使用TF-IDF提取关键词"""
        try:
            # 计算TF-IDF向量
            tfidf_matrix = self.tfidf_vectorizer.transform([text])

            # 获取特征名称
            feature_names = self.tfidf_vectorizer.get_feature_names_out()

            # 获取TF-IDF分数
            scores = tfidf_matrix.toarray()[0]

            # 创建词汇-分数对并排序
            word_scores = [
                (feature_names[i], scores[i])
                for i in range(len(scores))
                if scores[i] > 0
            ]

            # 按分数降序排序
            word_scores.sort(key=lambda x: x[1], reverse=True)

            # 返回top关键词
            return [word for word, score in word_scores[:max_keywords]]

        except Exception as e:
            logger.error(f"TF-IDF关键词提取失败: {e}")
            return []

    def _identify_product_type(self, text: str) -> str:
        """识别产品类型"""
        type_scores = {}

        for product_type, patterns in self.product_type_patterns.items():
            score = 0
            for pattern in patterns:
                # 使用正则表达式匹配
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches
            type_scores[product_type] = score

        # 返回得分最高的产品类型
        if not type_scores or max(type_scores.values()) == 0:
            return "general"

        return max(type_scores, key=lambda x: type_scores[x])

    def _extract_domain_keywords(
        self, text: str, product_type: str, max_keywords: int
    ) -> List[str]:
        """提取领域特定关键词"""
        domain_words = []

        # 获取通用领域词汇
        if "general" in self.domain_keywords:
            domain_words.extend(self.domain_keywords["general"])

        # 获取特定产品类型的词汇
        if product_type in self.domain_keywords:
            domain_words.extend(self.domain_keywords[product_type])

        # 在文本中查找匹配的领域词汇
        found_keywords = []
        text_words = set(text.split())

        for domain_word in domain_words:
            # 完整匹配
            if domain_word in text:
                found_keywords.append(domain_word)
            # 部分匹配 (词汇包含)
            elif any(domain_word in word for word in text_words):
                found_keywords.append(domain_word)

        # 去重并限制数量
        unique_keywords = list(set(found_keywords))
        return unique_keywords[:max_keywords]

    def _expand_synonyms(self, keywords: List[str], max_synonyms: int) -> List[str]:
        """扩展同义词"""
        synonyms = []

        for keyword in keywords:
            if keyword in self.synonym_mapping:
                synonyms.extend(self.synonym_mapping[keyword])

        # 去重并限制数量
        unique_synonyms = list(set(synonyms))
        return unique_synonyms[:max_synonyms]

    def _merge_and_rank_keywords(
        self, tfidf_keywords: List[str], domain_keywords: List[str], max_keywords: int
    ) -> List[str]:
        """合并并排序关键词"""
        # 创建关键词重要性评分
        keyword_scores = {}

        # TF-IDF关键词给予基础分数
        for i, keyword in enumerate(tfidf_keywords):
            keyword_scores[keyword] = 1.0 - (i / len(tfidf_keywords)) * 0.5

        # 领域关键词给予额外加分
        for keyword in domain_keywords:
            if keyword in keyword_scores:
                keyword_scores[keyword] += 0.3  # 领域词汇加分
            else:
                keyword_scores[keyword] = 0.3

        # 按评分排序
        sorted_keywords = sorted(
            keyword_scores.items(), key=lambda x: x[1], reverse=True
        )

        # 返回排序后的关键词
        return [keyword for keyword, score in sorted_keywords[:max_keywords]]

    def _calculate_confidence(
        self, text: str, keywords: List[str], product_type: str
    ) -> float:
        """计算提取置信度"""
        if not keywords:
            return 0.0

        # 基础置信度：关键词在文本中的覆盖率
        text_words = set(text.split())
        keyword_coverage = len(set(keywords) & text_words) / len(keywords)

        # 产品类型识别的置信度加权
        type_confidence = 0.8 if product_type != "general" else 0.6

        # 文本长度加权 (合理长度的文本通常提取更准确)
        length_factor = min(1.0, len(text.split()) / 20)  # 20词左右为佳

        # 综合置信度
        confidence = (
            keyword_coverage * 0.5 + type_confidence * 0.3 + length_factor * 0.2
        )

        return min(1.0, confidence)

    def _train_tfidf_model(self) -> None:
        """训练TF-IDF模型"""
        training_corpus = self._load_training_corpus()

        try:
            self.tfidf_vectorizer.fit(training_corpus)
            logger.debug(
                f"TF-IDF模型训练完成，词汇表大小: " f"{len(self.tfidf_vectorizer.vocabulary_)}"
            )
        except Exception as e:
            logger.error(f"TF-IDF模型训练失败: {e}")

    def _load_training_corpus(self) -> List[str]:
        """从配置文件加载训练语料"""
        training_file = Path("backend/data/training_corpus.yaml")

        try:
            if not yaml_available:
                logger.warning("PyYAML未安装，使用默认语料")
                return self._get_default_corpus()

            with open(training_file, "r", encoding="utf-8") as f:
                assert yaml is not None
                data = yaml.safe_load(f)
                # 确保返回正确的类型
                if isinstance(data, dict) and "training_samples" in data:
                    samples = data["training_samples"]
                    if isinstance(samples, list):
                        return samples
                return self._get_default_corpus()
        except Exception as e:
            logger.warning(f"训练语料文件加载失败: {e}，使用默认语料")
            return self._get_default_corpus()

    def _get_default_corpus(self) -> List[str]:
        """默认训练语料（fallback）"""
        return [
            "ai powered note taking app for researchers and students",
            "social media management platform for businesses",
            "project management software with team collaboration",
            "e-commerce platform for small businesses",
            "mobile app for fitness tracking and health",
        ]

    def _load_domain_dictionary(self) -> Dict[str, List[str]]:
        """加载领域特定词典"""
        return {
            "saas": [
                "software",
                "platform",
                "saas",
                "cloud",
                "api",
                "integration",
                "dashboard",
                "analytics",
                "automation",
                "subscription",
                "enterprise",
                "scalable",
                "workflow",
                "crm",
                "erp",
            ],
            "productivity": [
                "productivity",
                "efficiency",
                "workflow",
                "automation",
                "organize",
                "management",
                "planning",
                "task",
                "project",
                "team",
                "collaboration",
                "remote",
                "workspace",
            ],
            "note_taking": [
                "note",
                "notes",
                "markdown",
                "knowledge",
                "research",
                "writing",
                "documentation",
                "memory",
                "brain",
                "pkm",
                "zettelkasten",
                "obsidian",
                "notion",
                "journal",
            ],
            "ecommerce": [
                "ecommerce",
                "store",
                "shopping",
                "cart",
                "payment",
                "checkout",
                "inventory",
                "products",
                "customers",
                "orders",
                "shipping",
                "marketplace",
                "retail",
            ],
            "mobile_app": [
                "mobile",
                "app",
                "ios",
                "android",
                "smartphone",
                "tablet",
                "native",
                "hybrid",
                "react-native",
                "flutter",
                "push",
                "notifications",
                "offline",
            ],
            "ai_ml": [
                "ai",
                "artificial",
                "intelligence",
                "machine",
                "learning",
                "ml",
                "deep",
                "neural",
                "algorithm",
                "prediction",
                "nlp",
                "computer",
                "vision",
                "automation",
                "smart",
            ],
            "general": [
                "user",
                "users",
                "customer",
                "customers",
                "business",
                "solution",
                "service",
                "tool",
                "tools",
                "feature",
                "features",
                "data",
                "secure",
                "easy",
                "simple",
            ],
        }

    def _load_product_type_patterns(self) -> Dict[str, List[str]]:
        """加载产品类型识别模式"""
        return {
            "saas": [
                r"\bsaas\b",
                r"\bsoftware\b",
                r"\bplatform\b",
                r"\bcloud\b",
                r"\bapi\b",
                r"\bdashboard\b",
            ],
            "mobile_app": [
                r"\bapp\b",
                r"\bmobile\b",
                r"\bios\b",
                r"\bandroid\b",
                r"\bsmartphone\b",
                r"\btablet\b",
            ],
            "ecommerce": [
                r"\becommerce\b",
                r"\be-commerce\b",
                r"\bstore\b",
                r"\bshopping\b",
                r"\bretail\b",
                r"\bmarketplace\b",
            ],
            "hardware": [
                r"\bhardware\b",
                r"\bdevice\b",
                r"\biot\b",
                r"\bsensor\b",
                r"\bembedded\b",
                r"\bphysical\b",
            ],
            "service": [
                r"\bservice\b",
                r"\bconsulting\b",
                r"\bagency\b",
                r"\bprovider\b",
                r"\bsolution\b",
            ],
            "ai_ml": [
                r"\bai\b",
                r"\bartificial intelligence\b",
                r"\bmachine learning\b",
                r"\bml\b",
                r"\bdeep learning\b",
                r"\bneural\b",
            ],
        }

    def _load_synonym_mapping(self) -> Dict[str, List[str]]:
        """加载同义词映射"""
        return {
            "app": ["application", "software", "tool"],
            "platform": ["system", "framework", "solution"],
            "user": ["customer", "client", "member"],
            "business": ["company", "enterprise", "organization"],
            "management": ["administration", "control", "oversight"],
            "automation": ["automatic", "automated", "auto"],
            "analytics": ["analysis", "insights", "metrics", "statistics"],
            "collaboration": ["teamwork", "cooperation", "partnership"],
            "productivity": ["efficiency", "performance", "effectiveness"],
            "mobile": ["smartphone", "tablet", "device"],
            "ai": ["artificial intelligence", "machine learning", "smart"],
            "data": ["information", "records", "database"],
            "secure": ["security", "safe", "protected", "encrypted"],
            "cloud": ["online", "web-based", "internet"],
            "note": ["notes", "memo", "documentation", "record"],
        }

    def _create_empty_result(self) -> ExtractedKeywords:
        """创建空结果对象"""
        return ExtractedKeywords(
            primary_keywords=[],
            product_type="unknown",
            domain_keywords=[],
            synonyms=[],
            confidence=0.0,
        )

    def get_algorithm_metadata(
        self,
    ) -> Union[dict[str, "JsonValue"], AlgorithmMetadataResponse]:
        """获取算法元数据信息 - 支持类型安全响应

        Returns:
            AlgorithmMetadataResponse: 算法元数据的类型安全响应模型

        Note:
            为保持向后兼容，返回类型仍支持Dict[str, Any]，
            但实际返回AlgorithmMetadataResponse实例，可通过适配器转换
        """
        # 创建类型安全的响应模型
        return AlgorithmMetadataResponse(
            algorithm_name="TF-IDF + Domain Dictionary",
            version="1.0.0",
            tfidf_features=(
                len(self.tfidf_vectorizer.vocabulary_)
                if hasattr(self.tfidf_vectorizer, "vocabulary_")
                else 0
            ),
            domain_categories=len(self.domain_keywords),
            product_types=len(self.product_type_patterns),
            synonym_mappings=len(self.synonym_mapping),
        )
