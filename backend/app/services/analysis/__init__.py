"""
分析引擎模块 - Reddit Signal Scanner

包含4步分析流水线的各个步骤实现：
- Step 1: CommunityDiscoveryStep - 智能社区发现
- Step 2: DataCollectionStep - 数据收集 (待实现)
- Step 3: SentimentAnalysisStep - 情感分析 (待实现)
- Step 4: ReportGenerationStep - 报告生成 (待实现)

注意：为避免依赖链爆炸，重量级组件使用延迟导入。
需要时请直接从对应模块导入。
"""

# 延迟导入：避免加载重量级AI依赖
# from .community_discovery_step import CommunityDiscoveryStep

__all__ = []


def get_community_discovery_step():
    """延迟加载社区发现步骤，避免启动时加载AI模型"""
    from .community_discovery_step import CommunityDiscoveryStep

    return CommunityDiscoveryStep
