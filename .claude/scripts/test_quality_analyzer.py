#!/usr/bin/env python3
"""
PRD01-10 数据模型验收测试 - 测试质量分析器
基于Linus Torvalds严格标准设计的测试代码质量分析工具

作者: Claude AI
版本: v1.0
创建日期: 2025-01-24

功能:
1. 测试代码复杂度分析
2. 测试覆盖率质量评估
3. 测试可维护性评分
4. 测试可靠性分析
5. Linus级别品味评估
"""

import ast
import os
import sys
import json
import statistics
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestQualityMetrics:
    """测试质量指标数据类"""
    coverage_score: float
    complexity_score: float  
    reliability_score: float
    maintainability_score: float
    linus_taste_score: float
    overall_score: float
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典格式"""
        return {
            'coverage_score': self.coverage_score,
            'complexity_score': self.complexity_score,
            'reliability_score': self.reliability_score, 
            'maintainability_score': self.maintainability_score,
            'linus_taste_score': self.linus_taste_score,
            'overall_score': self.overall_score
        }


class TestQualityAnalyzer:
    """测试质量分析器 - 基于Linus Torvalds的严格标准"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_dir = self.project_root / "backend"
        self.test_dir = self.backend_dir / "tests"
        
        # Linus级别的质量阈值
        self.quality_thresholds = {
            'min_coverage': 95.0,
            'max_complexity': 10,
            'max_nesting_depth': 3,
            'min_docstring_coverage': 90.0,
            'max_function_length': 50
        }
    
    def analyze_test_suite(self) -> TestQualityMetrics:
        """分析测试套件质量 - 返回综合质量评分"""
        print("🔍 开始分析测试套件质量...")
        
        # 计算各项质量指标
        coverage_score = self._calculate_coverage_score()
        complexity_score = self._calculate_complexity_score()
        reliability_score = self._calculate_reliability_score()
        maintainability_score = self._calculate_maintainability_score()
        linus_taste_score = self._calculate_linus_taste_score()
        
        # 计算综合评分 (加权平均)
        weights = {
            'coverage': 0.25,
            'complexity': 0.20,
            'reliability': 0.20, 
            'maintainability': 0.20,
            'linus_taste': 0.15
        }
        
        overall_score = (
            coverage_score * weights['coverage'] +
            complexity_score * weights['complexity'] +
            reliability_score * weights['reliability'] +
            maintainability_score * weights['maintainability'] +
            linus_taste_score * weights['linus_taste']
        )
        
        return TestQualityMetrics(
            coverage_score=coverage_score,
            complexity_score=complexity_score,
            reliability_score=reliability_score,
            maintainability_score=maintainability_score, 
            linus_taste_score=linus_taste_score,
            overall_score=overall_score
        )
    
    def _calculate_coverage_score(self) -> float:
        """计算测试覆盖率评分"""
        print("📊 分析测试覆盖率...")
        
        try:
            # 运行pytest获取覆盖率数据
            cmd = [
                sys.executable, '-m', 'pytest', 
                '--cov=app', '--cov-report=json',
                '--cov-report=term-missing',
                str(self.test_dir)
            ]
            
            result = subprocess.run(
                cmd, 
                cwd=self.backend_dir,
                capture_output=True, 
                text=True
            )
            
            # 查找coverage.json文件
            coverage_file = self.backend_dir / 'coverage.json'
            if not coverage_file.exists():
                print("⚠️ 未找到coverage.json文件，使用默认评分")
                return 0.0
                
            with open(coverage_file, 'r') as f:
                coverage_data = json.load(f)
            
            # 计算各种覆盖率指标
            line_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
            branch_coverage = coverage_data.get('totals', {}).get('percent_covered_display', 0)
            
            # 根据覆盖率计算评分
            if line_coverage >= self.quality_thresholds['min_coverage']:
                score = 100.0
            elif line_coverage >= 90:
                score = 80.0 + (line_coverage - 90) * 4  # 90-95% -> 80-100分
            elif line_coverage >= 80:
                score = 60.0 + (line_coverage - 80) * 2  # 80-90% -> 60-80分
            else:
                score = line_coverage * 0.75  # <80% -> 按比例计算
            
            print(f"   行覆盖率: {line_coverage:.1f}%")
            print(f"   覆盖率评分: {score:.1f}/100")
            
            return score
            
        except Exception as e:
            print(f"❌ 覆盖率分析失败: {e}")
            return 0.0
    
    def _calculate_complexity_score(self) -> float:
        """计算测试代码复杂度评分"""
        print("🧠 分析代码复杂度...")
        
        complexity_scores = []
        nesting_violations = 0
        function_length_violations = 0
        
        for test_file in self.test_dir.rglob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        # 计算圈复杂度
                        complexity = self._calculate_cyclomatic_complexity(node)
                        complexity_scores.append(complexity)
                        
                        # 检查嵌套深度 (Linus的3层规则)
                        nesting_depth = self._calculate_nesting_depth(node)
                        if nesting_depth > self.quality_thresholds['max_nesting_depth']:
                            nesting_violations += 1
                        
                        # 检查函数长度
                        function_length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                        if function_length > self.quality_thresholds['max_function_length']:
                            function_length_violations += 1
                            
            except Exception as e:
                print(f"   警告: 分析 {test_file} 时出错: {e}")
                continue
        
        if not complexity_scores:
            print("   未找到测试函数")
            return 0.0
        
        # 计算复杂度评分
        avg_complexity = statistics.mean(complexity_scores)
        max_complexity = max(complexity_scores)
        
        # 基础复杂度评分
        if avg_complexity <= 5:
            complexity_score = 100.0
        elif avg_complexity <= self.quality_thresholds['max_complexity']:
            complexity_score = 100.0 - (avg_complexity - 5) * 10  # 5-10 -> 100-50分
        else:
            complexity_score = max(0, 50.0 - (avg_complexity - 10) * 5)  # >10 -> <50分
        
        # Linus规则违反惩罚
        nesting_penalty = nesting_violations * 10  # 每个违反扣10分
        length_penalty = function_length_violations * 5   # 每个违反扣5分
        
        final_score = max(0, complexity_score - nesting_penalty - length_penalty)
        
        print(f"   平均圈复杂度: {avg_complexity:.1f}")
        print(f"   最大圈复杂度: {max_complexity}")
        print(f"   嵌套深度违反: {nesting_violations} 个")
        print(f"   函数长度违反: {function_length_violations} 个")
        print(f"   复杂度评分: {final_score:.1f}/100")
        
        return final_score
    
    def _calculate_reliability_score(self) -> float:
        """计算测试可靠性评分"""
        print("🔧 分析测试可靠性...")
        
        try:
            # 运行测试多次检查稳定性
            stable_runs = 0
            total_runs = 3
            
            for i in range(total_runs):
                cmd = [
                    sys.executable, '-m', 'pytest',
                    str(self.test_dir),
                    '--tb=no', '-q'
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=self.backend_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    stable_runs += 1
            
            # 计算稳定性评分
            stability_ratio = stable_runs / total_runs
            
            # 检查测试隔离性 (通过fixture使用分析)
            isolation_score = self._analyze_test_isolation()
            
            # 综合可靠性评分
            reliability_score = (stability_ratio * 70 + isolation_score * 0.3) * 100
            
            print(f"   稳定性: {stable_runs}/{total_runs} 次成功")
            print(f"   隔离性评分: {isolation_score:.1f}")
            print(f"   可靠性评分: {reliability_score:.1f}/100")
            
            return reliability_score
            
        except Exception as e:
            print(f"❌ 可靠性分析失败: {e}")
            return 0.0
    
    def _calculate_maintainability_score(self) -> float:
        """计算测试可维护性评分"""
        print("🔧 分析测试可维护性...")
        
        docstring_coverage = 0
        total_functions = 0
        duplicate_code_score = 100.0
        naming_score = 100.0
        
        for test_file in self.test_dir.rglob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        total_functions += 1
                        
                        # 检查文档字符串
                        if ast.get_docstring(node):
                            docstring_coverage += 1
                        
                        # 检查命名规范
                        if not self._is_good_test_name(node.name):
                            naming_score -= 2
                            
            except Exception as e:
                print(f"   警告: 分析 {test_file} 时出错: {e}")
                continue
        
        # 计算文档覆盖率评分
        if total_functions > 0:
            docstring_ratio = docstring_coverage / total_functions * 100
        else:
            docstring_ratio = 0
        
        # 综合可维护性评分
        maintainability_score = (
            (docstring_ratio * 0.4) +
            (duplicate_code_score * 0.3) +
            (max(0, naming_score) * 0.3)
        )
        
        print(f"   文档覆盖率: {docstring_ratio:.1f}%")
        print(f"   命名规范评分: {max(0, naming_score):.1f}/100")
        print(f"   可维护性评分: {maintainability_score:.1f}/100")
        
        return maintainability_score
    
    def _calculate_linus_taste_score(self) -> float:
        """计算Linus级别品味评分 - 消除特殊情况的程度"""
        print("👨‍💻 评估Linus级别代码品味...")
        
        taste_violations = 0
        total_functions = 0
        
        taste_patterns = {
            'excessive_if_else': 0,      # 过多if-else分支
            'hardcoded_values': 0,       # 硬编码值
            'magic_numbers': 0,          # 魔法数字
            'unclear_assertions': 0,     # 不清晰的断言
            'data_structure_issues': 0   # 数据结构设计问题
        }
        
        for test_file in self.test_dir.rglob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        total_functions += 1
                        
                        # 检查各种品味问题
                        violations = self._analyze_taste_violations(node, content)
                        for key, count in violations.items():
                            taste_patterns[key] += count
                            taste_violations += count
                            
            except Exception as e:
                print(f"   警告: 分析 {test_file} 时出错: {e}")
                continue
        
        # 计算品味评分
        if total_functions == 0:
            taste_score = 0.0
        else:
            # 每个函数平均违反数
            violations_per_function = taste_violations / total_functions
            
            # Linus标准: 0违反=100分, 每个违反扣10分
            taste_score = max(0, 100 - violations_per_function * 10)
        
        print(f"   总违反数: {taste_violations}")
        print(f"   平均每函数违反: {violations_per_function:.1f}")
        for pattern, count in taste_patterns.items():
            if count > 0:
                print(f"   - {pattern}: {count}")
        print(f"   Linus品味评分: {taste_score:.1f}/100")
        
        return taste_score
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """计算函数的圈复杂度"""
        complexity = 1  # 基础复杂度
        
        for child in ast.walk(node):
            # 每个决策点增加复杂度
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try,
                                ast.ExceptHandler, ast.With, ast.Assert)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _calculate_nesting_depth(self, node: ast.FunctionDef) -> int:
        """计算函数的最大嵌套深度"""
        def get_depth(n, current_depth=0):
            max_depth = current_depth
            
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                    child_depth = get_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = get_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)
            
            return max_depth
        
        return get_depth(node)
    
    def _analyze_test_isolation(self) -> float:
        """分析测试隔离性 - 检查fixture使用和数据清理"""
        fixture_usage = 0
        total_test_functions = 0
        
        # 检查conftest.py是否存在
        conftest_exists = (self.test_dir / "conftest.py").exists()
        
        for test_file in self.test_dir.rglob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 简单检查fixture使用模式
                if '@pytest.fixture' in content or 'fixture' in content:
                    fixture_usage += 1
                    
                # 计算测试函数数量
                total_test_functions += content.count('def test_')
                    
            except Exception:
                continue
        
        # 计算隔离性评分
        isolation_score = 0.0
        
        if conftest_exists:
            isolation_score += 30
            
        if total_test_functions > 0:
            fixture_ratio = fixture_usage / len(list(self.test_dir.rglob("test_*.py")))
            isolation_score += fixture_ratio * 70
        
        return min(100.0, isolation_score)
    
    def _is_good_test_name(self, name: str) -> bool:
        """检查测试函数命名是否符合规范"""
        # 良好的测试命名应该描述: what_when_then 或 test_behavior_condition_result
        parts = name.replace('test_', '').split('_')
        return len(parts) >= 3  # 至少3个部分描述测试
    
    def _analyze_taste_violations(self, node: ast.FunctionDef, content: str) -> Dict[str, int]:
        """分析单个函数的品味违反情况"""
        violations = {
            'excessive_if_else': 0,
            'hardcoded_values': 0, 
            'magic_numbers': 0,
            'unclear_assertions': 0,
            'data_structure_issues': 0
        }
        
        # 检查过多的if-else分支
        if_count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                if_count += 1
        
        if if_count > 3:  # Linus风格: 消除过多分支
            violations['excessive_if_else'] += 1
        
        # 检查硬编码字符串和数字
        for child in ast.walk(node):
            if isinstance(child, ast.Str) and len(child.s) > 10:
                violations['hardcoded_values'] += 1
            elif isinstance(child, ast.Num) and child.n not in [0, 1, -1]:
                violations['magic_numbers'] += 1
        
        # 检查断言质量 (简化检查)
        assert_count = content.count('assert')
        assertTrue_count = content.count('assertTrue(')
        
        if assertTrue_count / max(1, assert_count) > 0.3:  # 超过30%使用assertTrue
            violations['unclear_assertions'] += 1
        
        return violations


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PRD01-10 测试质量分析器')
    parser.add_argument('--project-root', default='.',
                       help='项目根目录路径')
    parser.add_argument('--min-score', type=float, default=90.0,
                       help='最低质量评分阈值')
    parser.add_argument('--output', '-o', 
                       help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 初始化分析器
    analyzer = TestQualityAnalyzer(args.project_root)
    
    print("🚀 PRD01-10 数据模型验收测试 - 测试质量分析器")
    print("基于Linus Torvalds严格标准")
    print("=" * 60)
    
    # 执行分析
    metrics = analyzer.analyze_test_suite()
    
    # 生成报告
    print("\n📊 质量分析结果")
    print("-" * 40)
    print(f"测试覆盖率评分:   {metrics.coverage_score:.1f}/100")
    print(f"代码复杂度评分:   {metrics.complexity_score:.1f}/100") 
    print(f"测试可靠性评分:   {metrics.reliability_score:.1f}/100")
    print(f"可维护性评分:     {metrics.maintainability_score:.1f}/100")
    print(f"Linus品味评分:    {metrics.linus_taste_score:.1f}/100")
    print("-" * 40)
    print(f"综合质量评分:     {metrics.overall_score:.1f}/100")
    
    # 质量等级评定
    if metrics.overall_score >= 90:
        grade = "A+ (Linus级别)"
        color = "🟢"
    elif metrics.overall_score >= 85:
        grade = "A (优秀)"
        color = "🟢"
    elif metrics.overall_score >= 80:
        grade = "B+ (良好)"
        color = "🟡"
    elif metrics.overall_score >= 70:
        grade = "B (合格)"
        color = "🟡"
    else:
        grade = "C (需要改进)"
        color = "🔴"
    
    print(f"\n{color} 质量等级: {grade}")
    
    # 输出报告到文件
    if args.output:
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics.to_dict(),
            'grade': grade,
            'passed': metrics.overall_score >= args.min_score
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 报告已保存到: {args.output}")
    
    # 检查是否达到最低标准
    if metrics.overall_score < args.min_score:
        print(f"\n❌ 质量评分 {metrics.overall_score:.1f} 未达到最低标准 {args.min_score}")
        print("建议改进:")
        
        if metrics.coverage_score < 90:
            print(f"  • 提高测试覆盖率 (当前: {metrics.coverage_score:.1f}%)")
        if metrics.complexity_score < 90:
            print(f"  • 降低代码复杂度 (当前评分: {metrics.complexity_score:.1f})")
        if metrics.linus_taste_score < 90:
            print(f"  • 改善代码品味，消除特殊情况 (当前评分: {metrics.linus_taste_score:.1f})")
        
        sys.exit(1)
    else:
        print(f"\n✅ 质量评分达标，符合生产环境标准")
        sys.exit(0)


if __name__ == '__main__':
    main()
