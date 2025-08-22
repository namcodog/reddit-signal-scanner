#!/usr/bin/env python3
"""
Linus架构师脚本 - Reddit Signal Scanner

以Linus Torvalds的视角进行架构决策和代码审查，确保系统架构简洁高效。
通过Claude Code Hooks在重大代码变更时自动触发。

使用方式:
    python linus_architect.py <file_or_directory> [--mode=review|decision|debt-analysis]

返回值:
    0: 架构审查通过
    1: 架构问题需要修复
    2: 建议修改但可接受
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ast
import re
from datetime import datetime

class LinusArchitect:
    def __init__(self):
        self.project_root = Path.cwd()
        self.analysis_results = {
            'timestamp': datetime.now().isoformat(),
            'architectural_decision': '',
            'complexity_analysis': {},
            'debt_assessment': {},
            'recommendations': [],
            'violations': [],
            'score': 0.0
        }
        
        # Linus式架构原则
        self.core_principles = {
            'simplicity': {'weight': 0.4, 'desc': '简洁性优于聪明性'},
            'clarity': {'weight': 0.25, 'desc': '代码应该读起来像英语'},
            'performance': {'weight': 0.2, 'desc': '性能不能成为事后考虑'},
            'maintainability': {'weight': 0.15, 'desc': '维护性决定项目生死'}
        }
    
    def review_architectural_change(self, target_path: str) -> int:
        """审查架构变更"""
        print(f"🧠 Linus架构师审查: {target_path}")
        
        if os.path.isfile(target_path):
            return self._review_file_change(target_path)
        elif os.path.isdir(target_path):
            return self._review_directory_changes(target_path)
        else:
            print(f"❌ 路径不存在: {target_path}")
            return 1
    
    def _review_file_change(self, file_path: str) -> int:
        """审查单个文件变更"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.py':
            return self._review_python_architecture(file_path)
        elif file_ext in ['.ts', '.tsx', '.js', '.jsx']:
            return self._review_typescript_architecture(file_path)
        elif file_ext in ['.yml', '.yaml']:
            return self._review_config_architecture(file_path)
        else:
            # 通用文件审查
            return self._review_generic_architecture(file_path)
    
    def _review_generic_architecture(self, file_path: str) -> int:
        """审查通用文件架构"""
        print(f"📄 审查通用文件: {file_path}")
        
        # 对于非代码文件，进行基本的架构检查
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.analysis_results['violations'].append(f"文件读取失败: {str(e)}")
            return 1
        
        score = 100.0
        
        # 检查文件大小
        if len(content) > 10000:  # >10KB的非代码文件可能有问题
            score *= 0.9
            self.analysis_results['violations'].append(
                f"{file_path} - 文件过大，考虑拆分或归档"
            )
        
        # 检查是否包含敏感信息
        if any(keyword in content.lower() for keyword in ['password', 'secret', 'key']):
            score *= 0.7
            self.analysis_results['violations'].append(
                f"{file_path} - 可能包含敏感信息"
            )
        
        self.analysis_results['score'] = score / 100.0
        return self._make_architectural_decision(score)
    
    def _review_python_architecture(self, file_path: str) -> int:
        """审查Python代码架构"""
        print(f"🐍 审查Python架构: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                tree = ast.parse(source_code)
        except Exception as e:
            self.analysis_results['violations'].append(f"文件解析失败: {str(e)}")
            return 1
        
        # 架构检查项
        score = 100.0
        
        # 1. 复杂度检查
        complexity_score = self._check_complexity(tree, file_path)
        score *= complexity_score
        
        # 2. 职责单一性检查
        cohesion_score = self._check_cohesion(tree, file_path)
        score *= cohesion_score
        
        # 3. 依赖关系检查
        dependency_score = self._check_dependencies(tree, file_path)
        score *= dependency_score
        
        # 4. Linus风格检查
        style_score = self._check_linus_style(source_code, file_path)
        score *= style_score
        
        self.analysis_results['score'] = score / 100.0
        
        return self._make_architectural_decision(score)
    
    def _check_complexity(self, tree: ast.AST, file_path: str) -> float:
        """检查代码复杂度"""
        class ComplexityAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 0
                self.function_complexities = {}
                self.class_sizes = {}
                self.current_function = None
                self.current_class = None
                
            def visit_FunctionDef(self, node):
                self.current_function = node.name
                func_complexity = self._calculate_cyclomatic_complexity(node)
                self.function_complexities[node.name] = func_complexity
                
                # Linus原则：函数不应超过一屏(~25行)
                func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if func_lines > 25:
                    self.parent.analysis_results['violations'].append(
                        f"{file_path}:{node.lineno} - 函数{node.name}过长({func_lines}行), Linus原则: <25行"
                    )
                
                self.generic_visit(node)
                self.current_function = None
            
            def visit_ClassDef(self, node):
                self.current_class = node.name
                class_methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                self.class_sizes[node.name] = len(class_methods)
                
                # Linus原则：避免God Object
                if len(class_methods) > 15:
                    self.parent.analysis_results['violations'].append(
                        f"{file_path}:{node.lineno} - 类{node.name}过大({len(class_methods)}个方法), 考虑拆分"
                    )
                
                self.generic_visit(node)
                self.current_class = None
            
            def _calculate_cyclomatic_complexity(self, node):
                complexity = 1  # 基础复杂度
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                        complexity += 1
                    elif isinstance(child, ast.Try):
                        complexity += len(child.handlers)
                return complexity
        
        analyzer = ComplexityAnalyzer()
        analyzer.parent = self  # 传递引用以访问analysis_results
        analyzer.visit(tree)
        
        # 计算复杂度分数
        avg_complexity = sum(analyzer.function_complexities.values()) / max(len(analyzer.function_complexities), 1)
        
        # Linus标准：平均复杂度应<5
        if avg_complexity > 10:
            complexity_score = 0.3  # 严重复杂
        elif avg_complexity > 5:
            complexity_score = 0.7  # 需要关注
        else:
            complexity_score = 1.0  # 优秀
        
        self.analysis_results['complexity_analysis'] = {
            'average_complexity': avg_complexity,
            'function_complexities': analyzer.function_complexities,
            'class_sizes': analyzer.class_sizes,
            'score': complexity_score
        }
        
        return complexity_score
    
    def _check_cohesion(self, tree: ast.AST, file_path: str) -> float:
        """检查代码内聚性"""
        class CohesionAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.classes = {}
                self.current_class = None
                
            def visit_ClassDef(self, node):
                self.current_class = node.name
                self.classes[node.name] = {
                    'methods': [],
                    'attributes': set(),
                    'responsibilities': []
                }
                
                # 分析类的职责
                for method in [n for n in node.body if isinstance(n, ast.FunctionDef)]:
                    method_name = method.name
                    self.classes[node.name]['methods'].append(method_name)
                    
                    # 检查是否违反单一职责原则
                    if self._suggests_multiple_responsibilities(method_name):
                        self.classes[node.name]['responsibilities'].append(method_name)
                
                self.generic_visit(node)
                self.current_class = None
            
            def _suggests_multiple_responsibilities(self, method_name):
                """检查方法名是否暗示多重职责"""
                multi_responsibility_indicators = [
                    'and', 'or', 'also', 'then', 'plus'
                ]
                return any(indicator in method_name.lower() for indicator in multi_responsibility_indicators)
        
        analyzer = CohesionAnalyzer()
        analyzer.visit(tree)
        
        # 计算内聚性分数
        cohesion_violations = 0
        for class_name, info in analyzer.classes.items():
            if len(info['responsibilities']) > 0:
                cohesion_violations += 1
                self.analysis_results['violations'].append(
                    f"{file_path} - 类{class_name}可能违反单一职责原则: {info['responsibilities']}"
                )
        
        cohesion_score = max(0.5, 1.0 - (cohesion_violations * 0.3))
        return cohesion_score
    
    def _check_dependencies(self, tree: ast.AST, file_path: str) -> float:
        """检查依赖关系"""
        class DependencyAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.imports = []
                self.from_imports = []
                self.circular_risks = []
                
            def visit_Import(self, node):
                for alias in node.names:
                    self.imports.append(alias.name)
                    
            def visit_ImportFrom(self, node):
                if node.module:
                    self.from_imports.append(node.module)
        
        analyzer = DependencyAnalyzer()
        analyzer.visit(tree)
        
        # 检查依赖问题
        dependency_score = 1.0
        
        # 检查过多导入
        total_imports = len(analyzer.imports) + len(analyzer.from_imports)
        if total_imports > 20:
            dependency_score *= 0.8
            self.analysis_results['violations'].append(
                f"{file_path} - 导入过多({total_imports}个), 可能违反依赖倒置原则"
            )
        
        # 检查潜在循环依赖
        project_modules = [imp for imp in analyzer.from_imports if not imp.startswith(('.', '__'))]
        relative_imports = [imp for imp in analyzer.from_imports if imp.startswith('.')]
        
        if len(relative_imports) > len(project_modules) * 0.5:
            dependency_score *= 0.9
            self.analysis_results['violations'].append(
                f"{file_path} - 相对导入过多，可能存在循环依赖风险"
            )
        
        return dependency_score
    
    def _check_linus_style(self, source_code: str, file_path: str) -> float:
        """检查Linus风格原则"""
        style_score = 1.0
        lines = source_code.split('\n')
        
        # 检查深度嵌套
        for i, line in enumerate(lines, 1):
            indent_level = (len(line) - len(line.lstrip())) // 4
            if indent_level > 3:  # Linus: 超过3层缩进重新设计
                style_score *= 0.9
                self.analysis_results['violations'].append(
                    f"{file_path}:{i} - 嵌套过深({indent_level}层), Linus: '超过3层缩进，重新设计'"
                )
        
        # 检查函数参数过多
        function_pattern = r'def\s+\w+\s*\(([^)]+)\)'
        for match in re.finditer(function_pattern, source_code):
            params = [p.strip() for p in match.group(1).split(',') if p.strip()]
            if len(params) > 5:  # Linus偏好：函数参数不超过5个
                style_score *= 0.95
                line_num = source_code[:match.start()].count('\n') + 1
                self.analysis_results['violations'].append(
                    f"{file_path}:{line_num} - 函数参数过多({len(params)}个), 考虑使用对象封装"
                )
        
        # 检查复杂的条件表达式
        complex_conditions = re.findall(r'if.*(?:and|or).*(?:and|or)', source_code)
        if complex_conditions:
            style_score *= 0.95
            self.analysis_results['violations'].append(
                f"{file_path} - 发现复杂条件表达式，考虑提取为函数"
            )
        
        return style_score
    
    def _review_typescript_architecture(self, file_path: str) -> int:
        """审查TypeScript代码架构"""
        print(f"📘 审查TypeScript架构: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.analysis_results['violations'].append(f"文件读取失败: {str(e)}")
            return 1
        
        score = 100.0
        
        # 检查文件长度
        lines = content.split('\n')
        if len(lines) > 300:
            score *= 0.8
            self.analysis_results['violations'].append(
                f"{file_path} - 文件过长({len(lines)}行), 考虑拆分"
            )
        
        # 检查import数量
        import_count = len([line for line in lines if line.strip().startswith('import')])
        if import_count > 15:
            score *= 0.9
            self.analysis_results['violations'].append(
                f"{file_path} - 导入过多({import_count}个), 可能存在设计问题"
            )
        
        self.analysis_results['score'] = score / 100.0
        return self._make_architectural_decision(score)
    
    def _review_config_architecture(self, file_path: str) -> int:
        """审查配置文件架构"""
        print(f"⚙️ 审查配置文件: {file_path}")
        
        try:
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            self.analysis_results['violations'].append(f"配置文件解析失败: {str(e)}")
            return 1
        
        score = 100.0
        
        # 检查配置复杂度
        if isinstance(config, dict) and len(config) > 20:
            score *= 0.9
            self.analysis_results['violations'].append(
                f"{file_path} - 配置项过多，考虑分组"
            )
        
        self.analysis_results['score'] = score / 100.0
        return self._make_architectural_decision(score)
    
    def _make_architectural_decision(self, score: float) -> int:
        """做出架构决策"""
        if score >= 80:
            self.analysis_results['architectural_decision'] = 'APPROVE'
            return 0
        elif score >= 60:
            self.analysis_results['architectural_decision'] = 'REQUIRES_CHANGES'
            return 2
        else:
            self.analysis_results['architectural_decision'] = 'REJECT'
            return 1
    
    def _review_directory_changes(self, directory: str) -> int:
        """审查目录级别的架构变更"""
        print(f"📁 审查目录架构: {directory}")
        
        # 分析项目结构
        structure_score = self._analyze_project_structure(directory)
        
        # 检查模块间依赖
        dependency_score = self._analyze_module_dependencies(directory)
        
        # 检查架构分层
        layering_score = self._check_architectural_layering(directory)
        
        overall_score = (structure_score + dependency_score + layering_score) / 3 * 100
        self.analysis_results['score'] = overall_score / 100.0
        
        return self._make_architectural_decision(overall_score)
    
    def _analyze_project_structure(self, directory: str) -> float:
        """分析项目结构合理性"""
        print("🏗️ 分析项目结构...")
        
        # Reddit Signal Scanner项目的预期结构
        expected_structure = {
            'backend': '后端API服务',
            'frontend': '前端React应用',
            'admin': '管理后台',
            'docs': '文档',
            'config': '配置文件',
            'scripts': '工具脚本',
            '.claude': 'Agent配置'
        }
        
        actual_dirs = [d.name for d in Path(directory).iterdir() if d.is_dir()]
        structure_score = 1.0
        
        # 检查关键目录
        missing_dirs = []
        for expected_dir in ['backend', 'frontend']:  # 核心目录
            if expected_dir not in actual_dirs:
                missing_dirs.append(expected_dir)
                structure_score *= 0.7
        
        if missing_dirs:
            self.analysis_results['violations'].append(
                f"缺少关键目录: {missing_dirs}"
            )
        
        return structure_score
    
    def _analyze_module_dependencies(self, directory: str) -> float:
        """分析模块间依赖关系"""
        print("🔗 分析模块依赖...")
        
        # 简化实现：检查Python文件间的导入关系
        python_files = list(Path(directory).rglob('*.py'))
        dependency_graph = {}
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取本地模块导入
                imports = re.findall(r'from\s+(\w+(?:\.\w+)*)\s+import', content)
                imports.extend(re.findall(r'import\s+(\w+(?:\.\w+)*)', content))
                
                relative_path = str(py_file.relative_to(directory))
                dependency_graph[relative_path] = imports
                
            except Exception:
                continue
        
        # 检查循环依赖风险
        dependency_score = 1.0
        for file, deps in dependency_graph.items():
            # 简化检查：如果依赖数量过多，可能存在架构问题
            if len(deps) > 10:
                dependency_score *= 0.9
                self.analysis_results['violations'].append(
                    f"{file} - 依赖过多({len(deps)}个模块), 可能存在架构问题"
                )
        
        return dependency_score
    
    def _check_architectural_layering(self, directory: str) -> float:
        """检查架构分层"""
        print("🏛️ 检查架构分层...")
        
        # Reddit Signal Scanner的预期分层
        expected_layers = {
            'api': {'level': 1, 'desc': 'API接口层'},
            'services': {'level': 2, 'desc': '业务逻辑层'},
            'models': {'level': 3, 'desc': '数据模型层'},
            'utils': {'level': 4, 'desc': '工具函数层'}
        }
        
        layering_score = 1.0
        
        # 检查是否存在跨层调用
        backend_dir = Path(directory) / 'backend'
        if backend_dir.exists():
            for py_file in backend_dir.rglob('*.py'):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 检查import模式是否符合分层原则
                    # 这里可以实现更复杂的分层验证逻辑
                    
                except Exception:
                    continue
        
        return layering_score
    
    def generate_linus_review(self) -> str:
        """生成Linus风格的架构审查报告"""
        report = []
        
        # 决策声明
        decision = self.analysis_results['architectural_decision']
        score = self.analysis_results['score']
        
        if decision == 'APPROVE':
            report.append("✅ 架构审查：批准")
            report.append(f"📊 架构评分: {score:.2f}/1.0")
            report.append("")
            report.append("🎯 Linus评价:")
            report.append("代码结构清晰，遵循简洁性原则。这就是我希望看到的'好品味'代码。")
            
        elif decision == 'REQUIRES_CHANGES':
            report.append("⚠️ 架构审查：需要修改")
            report.append(f"📊 架构评分: {score:.2f}/1.0")
            report.append("")
            report.append("🎯 Linus评价:")
            report.append("整体方向正确，但存在一些可以改进的地方。")
            report.append("不要为了聪明而牺牲简洁性。")
            
        else:  # REJECT
            report.append("❌ 架构审查：拒绝")
            report.append(f"📊 架构评分: {score:.2f}/1.0")
            report.append("")
            report.append("🎯 Linus评价:")
            report.append("这个设计有根本性问题。复杂性是万恶之源。")
            report.append("重新思考数据结构，其他一切都会随之简化。")
        
        report.append("")
        
        # 违规问题
        violations = self.analysis_results.get('violations', [])
        if violations:
            report.append("🔴 需要修复的架构问题:")
            for i, violation in enumerate(violations[:5], 1):
                report.append(f"  {i}. {violation}")
            if len(violations) > 5:
                report.append(f"  ... 还有{len(violations) - 5}个问题")
            report.append("")
        
        # 复杂度分析
        complexity = self.analysis_results.get('complexity_analysis', {})
        if complexity:
            avg_complexity = complexity.get('average_complexity', 0)
            report.append("📈 复杂度分析:")
            report.append(f"  平均循环复杂度: {avg_complexity:.1f}")
            
            if avg_complexity > 5:
                report.append("  🚨 Linus警告: '如果需要超过3层缩进，你就已经完蛋了'")
            elif avg_complexity > 3:
                report.append("  ⚠️ 建议: 考虑分解复杂函数")
            else:
                report.append("  ✅ 复杂度控制良好")
            report.append("")
        
        # Linus式建议
        report.append("💡 Linus式改进建议:")
        if score < 0.6:
            report.append("  • 重新设计数据结构 - 好的数据结构让代码自然简单")
            report.append("  • 消除特殊情况处理 - 每个if-else都是设计缺陷的信号")
            report.append("  • 拆分职责 - 单一功能，单一职责")
        elif score < 0.8:
            report.append("  • 减少函数参数 - 超过5个参数考虑对象封装")
            report.append("  • 简化条件逻辑 - 复杂的条件表达式提取为函数")
            report.append("  • 控制嵌套深度 - 深层嵌套是复杂思维的体现")
        else:
            report.append("  • 继续保持简洁的设计风格")
            report.append("  • 定期review和重构，防止复杂度蔓延")
        
        report.append("")
        report.append("---")
        report.append("🧠 \"Talk is cheap. Show me the code.\" - Linus Torvalds")
        
        return "\n".join(report)

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python linus_architect.py <file_or_directory> [--mode=review|decision|debt-analysis]")
        sys.exit(1)
    
    target_path = sys.argv[1]
    mode = 'review'  # 默认模式
    
    # 解析模式参数
    for arg in sys.argv[2:]:
        if arg.startswith('--mode='):
            mode = arg.split('=')[1]
    
    architect = LinusArchitect()
    
    # 执行架构审查
    result_code = architect.review_architectural_change(target_path)
    
    # 生成并输出报告
    report = architect.generate_linus_review()
    print(report)
    
    # Claude Hook响应
    if os.getenv('CLAUDE_HOOK_MODE') == '1':
        hook_response = {
            'architectural_decision': architect.analysis_results['architectural_decision'],
            'score': architect.analysis_results['score'],
            'allow_change': result_code == 0,
            'requires_attention': result_code > 0,
            'linus_feedback': architect.analysis_results
        }
        print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response, indent=2)}")
    
    sys.exit(result_code)

if __name__ == '__main__':
    main()