"""单元测试示例 - 关键词处理服务

展示单元测试的最佳实践：
1. 完全隔离外部依赖
2. 快速执行（<100ms）
3. 测试单一功能
4. 故障优先策略
"""

import pytest
from typing import Any, Callable, Iterable, Optional, Sequence, cast
from unittest.mock import Mock, patch

from tests.fixtures.base_fixtures import TestIsolation, AssertHelpers, performance_timer
from tests.fixtures.mock_services import TestDataGenerator


# 假设这是我们要测试的服务
class KeywordProcessor:
    """关键词处理服务"""

    def __init__(self, validator: Optional[Callable[[str], bool]] = None) -> None:
        self.validator: Callable[[str], bool] = validator or self._default_validator

    def process_keywords(self, keywords: object) -> list[str]:
        """处理关键词列表"""
        if keywords is None:
            raise TypeError("keywords must be a sequence of strings")

        if isinstance(keywords, str) or not isinstance(keywords, Iterable):
            raise TypeError("keywords must be iterable")

        processed: list[str] = []
        keyword_iter = cast(Iterable[Optional[str]], keywords)
        for keyword in keyword_iter:
            if keyword is None:
                continue
            if not isinstance(keyword, str):
                raise TypeError("each keyword must be a string")
            if self.validator(keyword):
                normalized = keyword.strip().lower()
                if normalized and normalized not in processed:
                    processed.append(normalized)

        if not processed:
            raise ValueError("没有有效的关键词")

        return processed[:10]

    def _default_validator(self, keyword: str) -> bool:
        """默认验证器"""
        cleaned = keyword.strip()
        return 2 <= len(cleaned) <= 100


@TestIsolation.unit_test
class TestKeywordProcessorUnit:
    """关键词处理器单元测试"""
    
    def test_empty_keywords_raises_error(self) -> None:
        """测试空关键词列表 - 故障优先"""
        processor = KeywordProcessor()
        
        with pytest.raises(ValueError) as exc_info:
            processor.process_keywords([])
            
        assert "关键词列表不能为空" in str(exc_info.value)
        
    def test_all_invalid_keywords_raises_error(self) -> None:
        """测试全部无效关键词 - 故障优先"""
        processor = KeywordProcessor()
        invalid_keywords = ["", " ", "a", "x" * 101, None]
        
        with pytest.raises(ValueError) as exc_info:
            processor.process_keywords(invalid_keywords)
            
        assert "没有有效的关键词" in str(exc_info.value)
        
    @pytest.mark.parametrize("invalid_input,error_type", [
        (None, TypeError),
        ("not a list", TypeError),
        (123, TypeError),
        ({}, TypeError),
    ])
    def test_invalid_input_types(self, invalid_input: object, error_type: type[Exception]) -> None:
        """测试无效输入类型 - 边界条件"""
        processor = KeywordProcessor()
        
        with pytest.raises(error_type):
            processor.process_keywords(cast(Any, invalid_input))
            
    def test_keyword_length_boundaries(self) -> None:
        """测试关键词长度边界 - 边界驱动"""
        processor = KeywordProcessor()
        
        # 边界情况
        edge_cases = [
            (["ab"], ["ab"]),  # 最短有效：2字符
            (["a" * 100], ["a" * 100]),  # 最长有效：100字符
            (["a"], []),  # 太短：1字符
            (["a" * 101], []),  # 太长：101字符
        ]
        
        for keywords, expected in edge_cases:
            try:
                result = processor.process_keywords(keywords)
                assert result == expected
            except ValueError:
                assert expected == []  # 预期抛出异常的情况
                
    def test_duplicate_removal(self) -> None:
        """测试重复关键词移除"""
        processor = KeywordProcessor()
        
        keywords = ["Python", "python", "PYTHON", "java", "Java"]
        result = processor.process_keywords(keywords)
        
        assert result == ["python", "java"]
        assert len(result) == 2
        
    def test_whitespace_handling(self) -> None:
        """测试空白字符处理"""
        processor = KeywordProcessor()
        
        keywords = ["  python  ", "\tkeyword\n", "test   "]
        result = processor.process_keywords(keywords)
        
        assert result == ["python", "keyword", "test"]
        
    def test_maximum_keywords_limit(self) -> None:
        """测试最大关键词数量限制"""
        processor = KeywordProcessor()
        
        # 生成15个有效关键词
        keywords = [f"keyword{i}" for i in range(15)]
        result = processor.process_keywords(keywords)
        
        assert len(result) == 10  # 最多返回10个
        assert result == [f"keyword{i}" for i in range(10)]
        
    def test_custom_validator(self) -> None:
        """测试自定义验证器"""
        # Mock验证器
        mock_validator = Mock(side_effect=lambda k: len(k) >= 5)
        processor = KeywordProcessor(validator=mock_validator)
        
        keywords = ["abc", "hello", "world", "py"]
        result = processor.process_keywords(keywords)
        
        # 验证调用次数
        assert mock_validator.call_count == 4
        # 验证结果
        assert result == ["hello", "world"]
        
    def test_special_characters_handling(self) -> None:
        """测试特殊字符处理"""
        processor = KeywordProcessor()
        
        keywords = ["test@example", "keyword#tag", "search?query", "normal"]
        result = processor.process_keywords(keywords)
        
        # 默认验证器应该接受这些特殊字符
        assert len(result) == 4
        
    def test_unicode_keywords(self) -> None:
        """测试Unicode字符支持"""
        processor = KeywordProcessor()
        
        keywords = ["测试", "テスト", "тест", "test"]
        result = processor.process_keywords(keywords)
        
        assert len(result) == 4
        assert all(k in result for k in ["测试", "テスト", "тест", "test"])
        
    def test_performance_requirement(self, performance_timer: Any) -> None:
        """测试性能要求 - 单元测试应该很快"""
        processor = KeywordProcessor()
        keywords = [f"keyword{i}" for i in range(100)]
        
        performance_timer.start()
        result = processor.process_keywords(keywords)
        performance_timer.stop()
        
        # 单元测试应该在100ms内完成
        performance_timer.assert_performance(0.1)
        assert len(result) == 10


@pytest.mark.parametrize("keywords,expected", [
    # 使用TestDataGenerator生成的边界条件数据
    (["python", "fastapi", "react"], ["python", "fastapi", "react"]),
    (["Python", "FastAPI", "React"], ["python", "fastapi", "react"]),
    (["  python  ", "fastapi", "  react  "], ["python", "fastapi", "react"]),
])
def test_keyword_normalization_parametrized(keywords: Sequence[str], expected: Sequence[str]) -> None:
    """参数化测试 - 关键词标准化"""
    processor = KeywordProcessor()
    result = processor.process_keywords(keywords)
    assert result == expected


# ==================== 测试辅助函数 ====================
def test_edge_cases_from_generator() -> None:
    """使用TestDataGenerator生成的边界条件进行测试"""
    processor = KeywordProcessor()
    edge_cases = TestDataGenerator.generate_edge_case_keywords()
    
    for keywords in edge_cases:
        try:
            result = processor.process_keywords(keywords)
            # 验证返回的都是有效关键词
            assert all(isinstance(k, str) and k for k in result)
            assert len(result) <= 10
        except ValueError as e:
            # 某些边界条件预期会失败
            assert "关键词" in str(e)