"""
修复后的Reddit信号提取器验证测试

使用正确的数据模型字段
"""

import sys
import os
from datetime import datetime
from typing import List

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.analysis.signal_extractor import RedditSignalExtractor, UnifiedSignalDetector
from app.models.signal_pattern import SignalPattern, SignalType, RedditPost, DEFAULT_SIGNAL_PATTERNS
from app.models.analysis_pipeline import PipelineData, AnalysisConfig


def create_correct_reddit_post(post_id: str, title: str, content: str, subreddit: str = "test") -> RedditPost:
    """使用正确的字段创建RedditPost"""
    return RedditPost(
        id=post_id,
        title=title,
        content=content,
        subreddit=subreddit,
        score=10,
        comment_count=5,
        created_at=datetime.utcnow(),
    )


def test_correct_signal_extraction():
    """测试修复后的信号提取"""
    print("🧪 测试修复后的信号提取...")
    
    # 创建正确的测试数据
    test_posts = [
        create_correct_reddit_post("post1", "Pain Point", "This app is broken and sucks terribly"),
        create_correct_reddit_post("post2", "Competitor", "Much better than Slack for team communication"),
        create_correct_reddit_post("post3", "Opportunity", "Really need a feature for batch processing"),
    ]
    
    # 使用默认信号模式
    detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)
    
    try:
        # 执行信号提取
        signals = detector.extract_signals(test_posts)
        
        print(f"✅ 成功提取 {len(signals)} 个信号")
        
        # 验证信号结构
        for i, signal in enumerate(signals):
            print(f"\n信号 {i+1}:")
            print(f"  - 类型: {signal.signal_type.value}")
            print(f"  - 内容: {signal.content[:50]}...")
            print(f"  - 匹配关键词: {signal.matched_keywords}")
            print(f"  - 置信度: {signal.confidence:.3f}")
            print(f"  - 情感分数: {signal.sentiment_score:.3f}")
            print(f"  - 来源帖子ID: {signal.source_post_id}")
            print(f"  - 子版块: {signal.subreddit}")
            print(f"  - 上下文元数据: {list(signal.context_metadata.keys())}")
            
            # 验证必需字段
            assert hasattr(signal, 'signal_type')
            assert hasattr(signal, 'matched_keywords')
            assert hasattr(signal, 'source_post_id')
            assert hasattr(signal, 'context_metadata')
            assert isinstance(signal.matched_keywords, list)
        
        print("✅ 所有信号字段验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 信号提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_extractor_integration():
    """测试与PipelineData的集成"""
    print("\n🧪 测试与PipelineData集成...")
    
    try:
        # 创建正确的测试数据
        config = AnalysisConfig(product_description="Test product for signal extraction")
        data = PipelineData(
            product_description="Test product for signal extraction",
            target_keywords=["test"],
            analysis_config=config,
            pipeline_id="test-pipeline",
            total_steps=4,
        )
        
        # 模拟数据收集步骤的输出
        test_posts = [
            create_correct_reddit_post("integration1", "Integration Test", "This tool is broken and frustrating"),
            create_correct_reddit_post("integration2", "Competitor Test", "Better than existing solutions"),
        ]
        
        data.step_results["data_collection"] = {
            "reddit_posts": test_posts,
            "total_posts": len(test_posts),
        }
        
        # 测试信号提取器
        extractor = RedditSignalExtractor()
        
        # 注意：这是async方法，需要运行在async环境中
        import asyncio
        result = asyncio.run(extractor.execute(data))
        
        print(f"✅ 集成测试成功: {result.success}")
        
        if result.success:
            print(f"  - 处理帖子数: {result.data['total_processed']}")
            print(f"  - 提取信号数: {result.data['total_signals']}")
            print(f"  - 信号统计: {result.data['statistics']}")
            
            # 验证信号结构
            signals = result.data['signals']
            if signals:
                first_signal = signals[0]
                print(f"  - 第一个信号: {first_signal['signal_type']} - {first_signal['content'][:30]}...")
                
                # 验证字段名正确性
                expected_fields = ['signal_type', 'matched_keywords', 'source_post_id', 'context_metadata']
                for field in expected_fields:
                    assert field in first_signal, f"缺少字段: {field}"
                
                print("✅ 信号字段完整性验证通过")
        
        return result.success
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_model_compatibility():
    """测试数据模型兼容性"""
    print("\n🧪 测试数据模型兼容性...")
    
    try:
        # 测试RedditPost创建
        post = create_correct_reddit_post("compat1", "Compatibility Test", "Test content")
        print(f"✅ RedditPost创建成功: {post.id}")
        print(f"  - 字段验证: id={post.id}, title={post.title}, subreddit={post.subreddit}")
        
        # 测试Signal与实际模式创建
        from app.models.signal_pattern import Signal, SignalType
        
        signal = Signal(
            signal_type=SignalType.PAIN_POINT,
            content="Test signal content",
            matched_keywords=["test", "broken"],
            sentiment_score=-0.5,
            confidence=0.8,
            source_post_id="test123",
            subreddit="testsubreddit",
        )
        
        print(f"✅ Signal创建成功: {signal.signal_type.value}")
        print(f"  - 字段验证: matched_keywords={signal.matched_keywords}")
        print(f"  - 字段验证: source_post_id={signal.source_post_id}")
        print(f"  - 字段验证: context_metadata={signal.context_metadata}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据模型兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有修复验证测试"""
    print("🚀 开始修复后的验证测试")
    print("=" * 50)
    
    try:
        results = []
        
        # 测试1: 数据模型兼容性
        results.append(test_data_model_compatibility())
        
        # 测试2: 信号提取核心逻辑
        results.append(test_correct_signal_extraction())
        
        # 测试3: 集成测试
        results.append(test_signal_extractor_integration())
        
        success_count = sum(results)
        total_count = len(results)
        
        print("\n" + "=" * 50)
        if success_count == total_count:
            print("🎉 所有测试通过！数据结构问题已修复")
            print("\n✅ 修复确认:")
            print("  - Signal字段: matched_keywords, source_post_id, context_metadata 正确")
            print("  - RedditPost字段: id, title, content, subreddit, created_at 正确") 
            print("  - 集成测试: 与PipelineData完全兼容")
            print("  - 实际运行: 代码确实能够工作")
            return True
        else:
            print(f"❌ {total_count - success_count}/{total_count} 个测试失败")
            return False
            
    except Exception as e:
        print(f"\n💥 测试执行错误: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)