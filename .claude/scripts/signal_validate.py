#!/usr/bin/env python3
"""
信号验证脚本 - Reddit Signal Scanner

验证Reddit数据分析结果的质量和商业信号的可信度。
通过Claude Code Hooks在WebFetch等数据获取后自动触发。

使用方式:
    python signal_validate.py <data_file> [--threshold=0.7]

返回值:
    0: 信号验证通过
    1: 信号质量不足，建议重新分析
    2: 警告级问题，可以使用但需注意限制
"""

import sys
import json
import os
import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import statistics

class SignalValidator:
    def __init__(self, confidence_threshold: float = 0.7):
        self.threshold = confidence_threshold
        self.validation_results = {
            'data_quality': {},
            'signal_strength': {},
            'business_viability': {},
            'risk_assessment': {}
        }
        
    def validate_signal_data(self, data_path: str) -> int:
        """验证信号数据质量"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"❌ 数据读取失败: {e}")
            return 1
        
        print(f"🔍 验证信号数据: {data_path}")
        
        # 数据完整性检查
        completeness_score = self._check_data_completeness(data)
        
        # 数据源可信度评估
        source_credibility = self._evaluate_source_credibility(data)
        
        # 信号强度统计验证
        signal_strength = self._validate_signal_strength(data)
        
        # 商业可行性检查
        business_viability = self._assess_business_viability(data)
        
        # 假阳性检测
        false_positive_risk = self._detect_false_positives(data)
        
        # 计算总体置信度分数
        overall_confidence = self._calculate_confidence_score(
            completeness_score, source_credibility, signal_strength,
            business_viability, false_positive_risk
        )
        
        # 生成验证报告
        return self._generate_validation_result(overall_confidence, data_path)
    
    def _check_data_completeness(self, data: dict) -> float:
        """检查数据完整性"""
        required_fields = ['subreddits', 'posts', 'analysis_date', 'query']
        optional_fields = ['comments', 'user_data', 'sentiment_analysis']
        
        present_required = sum(1 for field in required_fields if field in data and data[field])
        present_optional = sum(1 for field in optional_fields if field in data and data[field])
        
        completeness = (present_required / len(required_fields)) * 0.8 + \
                      (present_optional / len(optional_fields)) * 0.2
        
        self.validation_results['data_quality']['completeness'] = {
            'score': completeness,
            'missing_required': [f for f in required_fields if f not in data or not data[f]],
            'missing_optional': [f for f in optional_fields if f not in data or not data[f]]
        }
        
        return completeness
    
    def _evaluate_source_credibility(self, data: dict) -> float:
        """评估数据源可信度"""
        if 'subreddits' not in data:
            return 0.0
        
        subreddits = data.get('subreddits', [])
        posts = data.get('posts', [])
        
        # 社区多样性评分 (更多样本来源 = 更高可信度)
        diversity_score = min(len(subreddits) / 10, 1.0)  # 目标10个不同社区
        
        # 样本量充足性 (n >= 30为统计显著性基准)
        sample_size = len(posts) if isinstance(posts, list) else 0
        sample_score = min(sample_size / 30, 1.0)
        
        # 时间分布合理性
        time_distribution = self._analyze_time_distribution(posts)
        
        # 用户多样性 (避免少数用户主导)
        user_diversity = self._analyze_user_diversity(posts)
        
        credibility = (diversity_score * 0.3 + sample_score * 0.4 + 
                      time_distribution * 0.2 + user_diversity * 0.1)
        
        self.validation_results['data_quality']['source_credibility'] = {
            'score': credibility,
            'subreddit_count': len(subreddits),
            'sample_size': sample_size,
            'time_distribution': time_distribution,
            'user_diversity': user_diversity
        }
        
        return credibility
    
    def _validate_signal_strength(self, data: dict) -> float:
        """验证信号强度的统计显著性"""
        posts = data.get('posts', [])
        if not posts or not isinstance(posts, list):
            return 0.0
        
        # 提取关键指标
        scores = []
        engagement_rates = []
        sentiment_scores = []
        
        for post in posts:
            if isinstance(post, dict):
                # 标准化分数 (upvotes, comments等)
                upvotes = post.get('upvotes', 0)
                comments = post.get('comment_count', 0)
                if upvotes > 0:
                    scores.append(upvotes)
                    engagement_rate = comments / max(upvotes, 1)
                    engagement_rates.append(engagement_rate)
                
                # 情感分析分数
                sentiment = post.get('sentiment_score', 0.5)
                if isinstance(sentiment, (int, float)):
                    sentiment_scores.append(sentiment)
        
        if not scores:
            return 0.0
        
        # 计算统计指标
        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        
        # 信号集中度检查 (避免极端值主导)
        concentration_ratio = abs(mean_score - median_score) / max(mean_score, 1)
        concentration_score = max(0, 1 - concentration_ratio)
        
        # 变异系数 (标准差/均值, 衡量稳定性)
        cv = std_dev / max(mean_score, 1)
        stability_score = max(0, 1 - cv / 2)  # CV < 2为良好稳定性
        
        # 样本量充足性
        sample_adequacy = min(len(scores) / 50, 1.0)  # 目标50个样本
        
        signal_strength = (concentration_score * 0.4 + stability_score * 0.4 + 
                          sample_adequacy * 0.2)
        
        self.validation_results['signal_strength'] = {
            'score': signal_strength,
            'mean_score': mean_score,
            'median_score': median_score,
            'std_deviation': std_dev,
            'coefficient_variation': cv,
            'sample_size': len(scores),
            'concentration_ratio': concentration_ratio
        }
        
        return signal_strength
    
    def _assess_business_viability(self, data: dict) -> float:
        """评估商业可行性"""
        # 市场规模合理性检查
        market_size = self._estimate_market_size(data)
        
        # 竞争态势分析客观性
        competition_analysis = self._validate_competition_analysis(data)
        
        # 行动建议可操作性
        actionability = self._assess_action_recommendations(data)
        
        viability = (market_size * 0.4 + competition_analysis * 0.3 + 
                    actionability * 0.3)
        
        self.validation_results['business_viability'] = {
            'score': viability,
            'market_size_reasonableness': market_size,
            'competition_objectivity': competition_analysis,
            'recommendation_actionability': actionability
        }
        
        return viability
    
    def _detect_false_positives(self, data: dict) -> float:
        """检测假阳性风险 (返回低风险分数，越高越好)"""
        risk_factors = []
        
        # 季节性/事件性噪音检测
        seasonal_risk = self._detect_seasonal_noise(data)
        risk_factors.append(seasonal_risk)
        
        # 营销推广虚假需求检测
        marketing_noise = self._detect_marketing_noise(data)
        risk_factors.append(marketing_noise)
        
        # 小样本偏差检测
        sample_bias = self._detect_sample_bias(data)
        risk_factors.append(sample_bias)
        
        # 回音室效应检测
        echo_chamber = self._detect_echo_chamber(data)
        risk_factors.append(echo_chamber)
        
        # 风险分数越低越好，这里返回(1 - 平均风险)
        avg_risk = statistics.mean(risk_factors) if risk_factors else 0.5
        low_risk_score = 1 - avg_risk
        
        self.validation_results['risk_assessment'] = {
            'overall_risk': avg_risk,
            'low_risk_score': low_risk_score,
            'seasonal_risk': seasonal_risk,
            'marketing_noise_risk': marketing_noise,
            'sample_bias_risk': sample_bias,
            'echo_chamber_risk': echo_chamber
        }
        
        return low_risk_score
    
    def _analyze_time_distribution(self, posts: list) -> float:
        """分析时间分布合理性"""
        if not posts:
            return 0.5
        
        # 简化实现：检查时间跨度
        timestamps = []
        for post in posts:
            if isinstance(post, dict) and 'created_utc' in post:
                timestamps.append(post['created_utc'])
        
        if len(timestamps) < 2:
            return 0.5
        
        # 时间跨度至少应该覆盖几天
        time_span = max(timestamps) - min(timestamps)
        days_span = time_span / (24 * 3600) if time_span > 0 else 0
        
        # 理想时间跨度 7-30天
        if 7 <= days_span <= 30:
            return 1.0
        elif 3 <= days_span < 7:
            return 0.7
        elif days_span > 30:
            return 0.8  # 时间跨度过长，可能包含过时信息
        else:
            return 0.3  # 时间跨度太短
    
    def _analyze_user_diversity(self, posts: list) -> float:
        """分析用户多样性"""
        if not posts:
            return 0.5
        
        authors = {}
        for post in posts:
            if isinstance(post, dict) and 'author' in post:
                author = post['author']
                authors[author] = authors.get(author, 0) + 1
        
        if not authors:
            return 0.5
        
        total_posts = len(posts)
        unique_authors = len(authors)
        
        # 理想情况：每个作者平均贡献不超过总数的20%
        max_contribution = max(authors.values()) / total_posts
        diversity_score = max(0, 1 - (max_contribution - 0.2) * 2) if max_contribution > 0.2 else 1.0
        
        return diversity_score
    
    def _estimate_market_size(self, data: dict) -> float:
        """估算市场规模合理性"""
        # 简化实现：基于社区规模和活跃度
        subreddits = data.get('subreddits', [])
        if not subreddits:
            return 0.5
        
        # 假设每个subreddit代表一定市场规模
        total_subscribers = sum(sr.get('subscribers', 1000) for sr in subreddits 
                              if isinstance(sr, dict))
        
        # 合理的市场规模范围
        if 10000 <= total_subscribers <= 10000000:  # 1万到1000万
            return 1.0
        elif 1000 <= total_subscribers < 10000:
            return 0.6  # 小众市场
        elif total_subscribers > 10000000:
            return 0.7  # 可能高估了市场
        else:
            return 0.3  # 市场规模过小
    
    def _validate_competition_analysis(self, data: dict) -> float:
        """验证竞争分析客观性"""
        # 简化实现：检查是否有竞品提及
        posts = data.get('posts', [])
        competition_mentions = 0
        total_business_posts = 0
        
        for post in posts:
            if isinstance(post, dict):
                content = str(post.get('title', '')) + ' ' + str(post.get('selftext', ''))
                content_lower = content.lower()
                
                # 识别商业相关帖子
                business_keywords = ['competitor', 'alternative', 'vs', 'compare', 'better than']
                if any(keyword in content_lower for keyword in business_keywords):
                    total_business_posts += 1
                    if any(keyword in content_lower for keyword in ['competitor', 'alternative']):
                        competition_mentions += 1
        
        if total_business_posts == 0:
            return 0.5  # 没有竞争分析信息
        
        competition_ratio = competition_mentions / total_business_posts
        return min(competition_ratio * 2, 1.0)  # 50%以上竞争提及为满分
    
    def _assess_action_recommendations(self, data: dict) -> float:
        """评估行动建议可操作性"""
        # 简化实现：检查是否有具体建议
        recommendations = data.get('recommendations', [])
        if not recommendations:
            return 0.3
        
        actionable_count = 0
        for rec in recommendations:
            if isinstance(rec, str):
                # 检查是否包含具体行动词汇
                action_words = ['implement', 'create', 'build', 'develop', 'launch', 'start']
                if any(word in rec.lower() for word in action_words):
                    actionable_count += 1
        
        if len(recommendations) == 0:
            return 0.3
        
        actionability = actionable_count / len(recommendations)
        return actionability
    
    def _detect_seasonal_noise(self, data: dict) -> float:
        """检测季节性噪音风险"""
        # 简化实现：检查是否在特殊时期
        current_month = datetime.now().month
        
        # 假设11-12月和1月为购物季，可能有季节性偏差
        if current_month in [11, 12, 1]:
            return 0.3  # 轻度风险
        else:
            return 0.1  # 低风险
    
    def _detect_marketing_noise(self, data: dict) -> float:
        """检测营销推广噪音"""
        posts = data.get('posts', [])
        promotional_count = 0
        
        for post in posts:
            if isinstance(post, dict):
                content = str(post.get('title', '')) + ' ' + str(post.get('selftext', ''))
                promo_keywords = ['discount', 'sale', 'promo', 'deal', 'offer', 'coupon']
                if any(keyword in content.lower() for keyword in promo_keywords):
                    promotional_count += 1
        
        if len(posts) == 0:
            return 0.5
        
        promo_ratio = promotional_count / len(posts)
        return min(promo_ratio * 2, 0.8)  # 最高0.8的噪音风险
    
    def _detect_sample_bias(self, data: dict) -> float:
        """检测小样本偏差"""
        posts = data.get('posts', [])
        sample_size = len(posts) if isinstance(posts, list) else 0
        
        if sample_size >= 100:
            return 0.1  # 低偏差风险
        elif sample_size >= 30:
            return 0.3  # 中等风险
        else:
            return 0.7  # 高偏差风险
    
    def _detect_echo_chamber(self, data: dict) -> float:
        """检测回音室效应"""
        subreddits = data.get('subreddits', [])
        subreddit_count = len(subreddits) if isinstance(subreddits, list) else 0
        
        if subreddit_count >= 5:
            return 0.2  # 低回音室风险
        elif subreddit_count >= 3:
            return 0.4  # 中等风险
        else:
            return 0.8  # 高回音室风险
    
    def _calculate_confidence_score(self, completeness: float, credibility: float, 
                                  strength: float, viability: float, 
                                  low_risk: float) -> float:
        """计算总体置信度分数"""
        # 加权平均
        weights = [0.2, 0.25, 0.25, 0.2, 0.1]  # 各维度权重
        scores = [completeness, credibility, strength, viability, low_risk]
        
        confidence = sum(w * s for w, s in zip(weights, scores))
        return confidence
    
    def _generate_validation_result(self, confidence: float, data_path: str) -> int:
        """生成验证结果"""
        print(f"\n📊 信号验证结果 (置信度: {confidence:.2f})")
        
        # 详细分析报告
        quality = self.validation_results['data_quality']
        strength = self.validation_results['signal_strength']
        viability = self.validation_results['business_viability']
        risks = self.validation_results['risk_assessment']
        
        if confidence >= 0.8:
            print("✅ 高置信度信号")
            print(f"🎯 数据完整性: {quality['completeness']['score']:.2f}")
            print(f"🏆 信号强度: {strength['score']:.2f}")
            print(f"💼 商业可行性: {viability['score']:.2f}")
            print(f"🛡️ 低风险评估: {risks['low_risk_score']:.2f}")
            return 0
            
        elif confidence >= self.threshold:
            print("⚠️ 中等置信度信号 - 可使用但需谨慎")
            self._print_improvement_suggestions()
            return 2
            
        else:
            print("❌ 低置信度信号 - 建议重新分析")
            print(f"需要改进的方面:")
            if quality['completeness']['score'] < 0.7:
                print("• 数据完整性不足")
            if strength['score'] < 0.7:
                print("• 信号强度不够")
            if viability['score'] < 0.7:
                print("• 商业可行性存疑")
            if risks['low_risk_score'] < 0.7:
                print("• 假阳性风险较高")
            return 1
    
    def _print_improvement_suggestions(self):
        """打印改进建议"""
        suggestions = []
        
        quality = self.validation_results['data_quality']
        if quality['completeness']['score'] < 0.8:
            suggestions.append("补充缺失的数据字段")
            
        if quality['source_credibility']['score'] < 0.8:
            suggestions.append("增加数据源多样性")
            
        strength = self.validation_results['signal_strength']
        if strength['score'] < 0.8:
            suggestions.append("扩大样本规模")
            
        if suggestions:
            print("💡 改进建议:")
            for suggestion in suggestions:
                print(f"  • {suggestion}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python signal_validate.py <data_file> [--threshold=0.7]")
        sys.exit(1)
    
    data_file = sys.argv[1]
    threshold = 0.7
    
    # 解析阈值参数
    for arg in sys.argv[2:]:
        if arg.startswith('--threshold='):
            try:
                threshold = float(arg.split('=')[1])
            except ValueError:
                print("⚠️ 阈值参数格式错误，使用默认值0.7")
    
    validator = SignalValidator(threshold)
    result = validator.validate_signal_data(data_file)
    
    # Claude Hook响应
    if os.getenv('CLAUDE_HOOK_MODE') == '1':
        hook_response = {
            'validation_passed': result == 0,
            'confidence_score': validator._calculate_confidence_score(
                *[validator.validation_results[k].get('score', 0.5) 
                  for k in ['data_quality', 'signal_strength', 'business_viability', 'risk_assessment']]
            ),
            'recommendations': validator.validation_results
        }
        print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response, indent=2)}")
    
    sys.exit(result)

if __name__ == '__main__':
    main()