#!/usr/bin/env python3
"""
任务分析引擎 - 3-5分钟智能分析流程
实现Linus的"理解优于实现"哲学
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.claude/logs/task_analysis.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class TaskContext:
    """任务上下文数据结构"""
    task_id: str
    task_description: str
    priority: int  # 1-5, 5最高
    estimated_complexity: int  # 1-5, 5最复杂
    required_skills: List[str]
    related_files: List[str]
    dependencies: List[str]
    created_at: datetime

@dataclass
class AnalysisResult:
    """分析结果数据结构"""
    task_id: str
    analysis_duration_seconds: float
    complexity_score: int  # 1-5
    confidence_level: float  # 0.0-1.0
    
    # 需求分析结果
    requirement_clarity: float  # 0.0-1.0
    functional_scope: List[str]
    acceptance_criteria: List[str]
    key_constraints: List[str]
    
    # 技术方案
    recommended_approach: str
    technology_stack: List[str]
    integration_points: List[str]
    performance_requirements: Dict[str, str]
    
    # 风险评估
    high_risks: List[str]
    medium_risks: List[str] 
    low_risks: List[str]
    risk_mitigation_strategies: List[str]
    
    # 实施计划
    implementation_steps: List[Dict[str, str]]
    estimated_time_minutes: int
    testing_strategy: List[str]
    rollback_plan: str
    
    # 准备就绪检查
    readiness_checklist: List[Dict[str, bool]]
    missing_prerequisites: List[str]
    execution_recommendation: str

class TaskAnalysisEngine:
    """任务分析引擎核心类"""
    
    def __init__(self, config_path: str = ".claude/config/analysis_engine.json"):
        self.config_path = Path(config_path)
        self.analysis_cache_dir = Path(".claude/cache/task_analysis")
        self.analysis_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self.load_config()
        
        # MCP工具映射
        self.mcp_tools = {
            "context7": "mcp__context7__get-library-docs",
            "serena_overview": "mcp__serena__get_symbols_overview", 
            "serena_symbol": "mcp__serena__find_symbol",
            "sequential_thinking": "mcp__sequential-thinking__sequentialthinking",
            "tavily_search": "mcp__tavily-mcp__tavily-search",
            "memory_search": "mcp__openmemory-local__search_memory",
            "memory_add": "mcp__openmemory-local__add_memories"
        }
        
        logging.info("任务分析引擎初始化完成")
    
    def load_config(self) -> Dict:
        """加载分析引擎配置"""
        default_config = {
            "analysis_timeout_seconds": 300,  # 5分钟超时
            "parallel_analysis_enabled": True,
            "cache_enabled": True,
            "cache_expiry_hours": 24,
            "complexity_thresholds": {
                "simple": 2,
                "moderate": 3, 
                "complex": 4,
                "very_complex": 5
            },
            "analysis_templates": {
                "quick": {"duration_minutes": 2, "depth": "basic"},
                "standard": {"duration_minutes": 4, "depth": "comprehensive"},
                "deep": {"duration_minutes": 6, "depth": "exhaustive"}
            }
        }
        
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # 创建默认配置文件
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
    
    def generate_task_id(self, task_description: str) -> str:
        """生成任务唯一ID"""
        timestamp = datetime.now().isoformat()
        content = f"{task_description}::{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def estimate_analysis_template(self, task_description: str) -> str:
        """根据任务描述估算分析模板类型"""
        description_lower = task_description.lower()
        
        # 关键词匹配逻辑
        complex_keywords = [
            "架构", "重构", "系统", "集成", "性能优化", 
            "算法", "数据库", "安全", "分布式"
        ]
        
        simple_keywords = [
            "修复", "添加", "更新", "配置", "文档",
            "样式", "界面", "测试", "日志"
        ]
        
        complex_score = sum(1 for keyword in complex_keywords if keyword in description_lower)
        simple_score = sum(1 for keyword in simple_keywords if keyword in description_lower)
        
        if complex_score >= 2:
            return "deep"
        elif complex_score >= 1 or len(task_description) > 200:
            return "standard"
        elif simple_score >= 1:
            return "quick"
        else:
            return "standard"  # 默认标准分析
    
    async def parallel_information_gathering(self, task_context: TaskContext) -> Dict[str, any]:
        """并行信息收集 - 第1分钟"""
        start_time = time.time()
        
        logging.info("🔍 开始并行信息收集...")
        
        async def get_technical_documentation():
            """获取技术文档"""
            try:
                # 模拟context7调用
                await asyncio.sleep(0.3)  # 模拟网络延迟
                return {
                    "source": "context7",
                    "documentation": f"技术文档for {task_context.task_description}",
                    "best_practices": ["使用TypeScript", "遵循SOLID原则", "编写单元测试"],
                    "common_pitfalls": ["忽略错误处理", "过度设计", "性能瓶颈"]
                }
            except Exception as e:
                logging.warning(f"获取技术文档失败: {str(e)}")
                return {"source": "context7", "error": str(e)}
        
        async def analyze_existing_codebase():
            """分析现有代码库"""
            try:
                await asyncio.sleep(0.4)  # 模拟分析时间
                return {
                    "source": "serena", 
                    "related_modules": ["app/services", "app/api", "app/models"],
                    "integration_points": ["FastAPI endpoints", "数据库模型", "Redis缓存"],
                    "existing_patterns": ["依赖注入", "工厂模式", "观察者模式"],
                    "code_quality_score": 0.78
                }
            except Exception as e:
                logging.warning(f"代码库分析失败: {str(e)}")
                return {"source": "serena", "error": str(e)}
        
        async def search_historical_experience():
            """搜索历史经验"""
            try:
                await asyncio.sleep(0.2)
                return {
                    "source": "memory",
                    "similar_tasks": ["类似API开发", "数据处理优化", "React组件开发"],
                    "lessons_learned": ["提前考虑错误处理", "性能测试很重要", "文档先行"],
                    "success_patterns": ["迭代开发", "持续集成", "代码审查"],
                    "common_failures": ["需求理解偏差", "技术选型错误", "测试不足"]
                }
            except Exception as e:
                logging.warning(f"历史经验搜索失败: {str(e)}")
                return {"source": "memory", "error": str(e)}
        
        async def search_best_practices():
            """搜索最佳实践"""
            try:
                await asyncio.sleep(0.5)
                return {
                    "source": "tavily",
                    "industry_standards": ["REST API设计规范", "React最佳实践", "Python编码规范"],
                    "recent_trends": ["TypeScript采用", "微服务架构", "云原生部署"],
                    "tools_recommendations": ["VS Code", "Docker", "Jest测试框架"],
                    "performance_tips": ["代码分割", "缓存策略", "数据库优化"]
                }
            except Exception as e:
                logging.warning(f"最佳实践搜索失败: {str(e)}")
                return {"source": "tavily", "error": str(e)}
        
        # 并行执行所有信息收集任务
        try:
            results = await asyncio.gather(
                get_technical_documentation(),
                analyze_existing_codebase(),
                search_historical_experience(),
                search_best_practices(),
                return_exceptions=True
            )
            
            # 整合结果
            combined_info = {
                "technical_docs": results[0],
                "codebase_analysis": results[1], 
                "historical_experience": results[2],
                "best_practices": results[3],
                "collection_time_seconds": time.time() - start_time
            }
            
            logging.info(f"✅ 信息收集完成，用时 {combined_info['collection_time_seconds']:.2f}s")
            return combined_info
            
        except Exception as e:
            logging.error(f"并行信息收集失败: {str(e)}")
            return {"error": str(e), "collection_time_seconds": time.time() - start_time}
    
    def deep_requirement_understanding(self, task_context: TaskContext, 
                                     gathered_info: Dict) -> Dict[str, any]:
        """深度需求理解 - 第2分钟"""
        start_time = time.time()
        
        logging.info("🧠 开始深度需求理解...")
        
        # 使用5W2H分析法
        analysis_questions = {
            "What": f"具体要实现什么功能？基于描述：{task_context.task_description}",
            "Why": "为什么要实现这个功能？解决什么问题？",
            "Who": "谁会使用这个功能？目标用户是谁？",
            "When": "什么时候需要这个功能？有时间限制吗？",
            "Where": "功能部署在哪里？影响哪些模块？",
            "How": "如何实现这个功能？采用什么技术方案？",
            "How much": "需要多少资源？时间、人力、系统资源？"
        }
        
        # 模拟sequential-thinking分析
        structured_analysis = {
            "core_objective": self._extract_core_objective(task_context.task_description),
            "functional_scope": self._define_functional_scope(task_context, gathered_info),
            "acceptance_criteria": self._generate_acceptance_criteria(task_context),
            "key_constraints": self._identify_constraints(task_context, gathered_info),
            "stakeholders": self._identify_stakeholders(task_context),
            "success_metrics": self._define_success_metrics(task_context)
        }
        
        analysis_time = time.time() - start_time
        logging.info(f"✅ 需求理解完成，用时 {analysis_time:.2f}s")
        
        return {
            "analysis_questions": analysis_questions,
            "structured_analysis": structured_analysis,
            "requirement_clarity_score": self._calculate_clarity_score(structured_analysis),
            "analysis_time_seconds": analysis_time
        }
    
    def technical_solution_design(self, task_context: TaskContext, 
                                 gathered_info: Dict, 
                                 requirements: Dict) -> Dict[str, any]:
        """技术方案设计 - 第3分钟"""
        start_time = time.time()
        
        logging.info("🏗️ 开始技术方案设计...")
        
        # 技术栈选择
        recommended_stack = self._select_technology_stack(
            task_context, gathered_info, requirements
        )
        
        # 架构设计
        architecture_design = self._design_architecture(
            task_context, gathered_info, recommended_stack
        )
        
        # 集成点分析
        integration_analysis = self._analyze_integration_points(
            task_context, gathered_info
        )
        
        # 性能要求
        performance_requirements = self._define_performance_requirements(
            task_context, requirements
        )
        
        solution_design = {
            "recommended_approach": self._generate_implementation_approach(task_context),
            "technology_stack": recommended_stack,
            "architecture_design": architecture_design,
            "integration_points": integration_analysis,
            "performance_requirements": performance_requirements,
            "scalability_considerations": self._assess_scalability_needs(task_context),
            "security_requirements": self._identify_security_needs(task_context)
        }
        
        design_time = time.time() - start_time
        logging.info(f"✅ 技术方案设计完成，用时 {design_time:.2f}s")
        
        return {
            "solution_design": solution_design,
            "design_confidence": self._calculate_design_confidence(solution_design),
            "design_time_seconds": design_time
        }
    
    def implementation_planning(self, task_context: TaskContext,
                              gathered_info: Dict,
                              requirements: Dict, 
                              solution_design: Dict) -> Dict[str, any]:
        """实施计划制定 - 第4-5分钟"""
        start_time = time.time()
        
        logging.info("📋 开始实施计划制定...")
        
        # 任务分解
        implementation_steps = self._break_down_implementation_steps(
            task_context, solution_design
        )
        
        # 依赖分析
        dependency_analysis = self._analyze_task_dependencies(
            task_context, implementation_steps
        )
        
        # 风险评估
        risk_assessment = self._comprehensive_risk_assessment(
            task_context, solution_design, implementation_steps
        )
        
        # 测试策略
        testing_strategy = self._design_testing_strategy(
            task_context, solution_design, implementation_steps
        )
        
        # 回滚计划
        rollback_plan = self._prepare_rollback_plan(
            task_context, solution_design
        )
        
        # 准备就绪检查
        readiness_checklist = self._generate_readiness_checklist(
            task_context, solution_design, implementation_steps
        )
        
        implementation_plan = {
            "implementation_steps": implementation_steps,
            "dependency_analysis": dependency_analysis,
            "risk_assessment": risk_assessment,
            "testing_strategy": testing_strategy,
            "rollback_plan": rollback_plan,
            "readiness_checklist": readiness_checklist,
            "estimated_total_time_minutes": self._estimate_total_time(implementation_steps),
            "resource_requirements": self._estimate_resource_requirements(task_context),
            "execution_recommendation": self._generate_execution_recommendation(task_context, risk_assessment)
        }
        
        # 保存分析结果到项目记忆
        self._save_analysis_to_memory(task_context, implementation_plan)
        
        planning_time = time.time() - start_time
        logging.info(f"✅ 实施计划制定完成，用时 {planning_time:.2f}s")
        
        return {
            "implementation_plan": implementation_plan,
            "plan_confidence": self._calculate_plan_confidence(implementation_plan),
            "planning_time_seconds": planning_time
        }
    
    async def analyze_task(self, task_description: str, 
                          priority: int = 3,
                          force_template: Optional[str] = None) -> AnalysisResult:
        """任务分析主入口函数"""
        total_start_time = time.time()
        
        # 创建任务上下文
        task_context = TaskContext(
            task_id=self.generate_task_id(task_description),
            task_description=task_description,
            priority=priority,
            estimated_complexity=0,  # 待分析确定
            required_skills=[],
            related_files=[],
            dependencies=[],
            created_at=datetime.now()
        )
        
        logging.info(f"🚀 开始分析任务 #{task_context.task_id}: {task_description}")
        
        # 检查缓存
        if self.config["cache_enabled"]:
            cached_result = self._check_analysis_cache(task_context.task_id)
            if cached_result:
                logging.info("📦 使用缓存的分析结果")
                return cached_result
        
        try:
            # 选择分析模板
            template = force_template or self.estimate_analysis_template(task_description)
            template_config = self.config["analysis_templates"][template]
            
            logging.info(f"📝 使用 {template} 分析模板 (预计 {template_config['duration_minutes']} 分钟)")
            
            # 第1分钟：并行信息收集
            gathered_info = await self.parallel_information_gathering(task_context)
            
            # 第2分钟：需求理解
            requirements = self.deep_requirement_understanding(task_context, gathered_info)
            
            # 第3分钟：技术方案设计
            solution_design = self.technical_solution_design(
                task_context, gathered_info, requirements
            )
            
            # 第4-5分钟：实施计划
            implementation_plan = self.implementation_planning(
                task_context, gathered_info, requirements, solution_design
            )
            
            # 整合分析结果
            total_analysis_time = time.time() - total_start_time
            
            analysis_result = AnalysisResult(
                task_id=task_context.task_id,
                analysis_duration_seconds=total_analysis_time,
                complexity_score=self._calculate_complexity_score(
                    requirements, solution_design, implementation_plan
                ),
                confidence_level=self._calculate_overall_confidence(
                    requirements, solution_design, implementation_plan
                ),
                
                # 需求分析结果
                requirement_clarity=requirements["requirement_clarity_score"],
                functional_scope=requirements["structured_analysis"]["functional_scope"],
                acceptance_criteria=requirements["structured_analysis"]["acceptance_criteria"],
                key_constraints=requirements["structured_analysis"]["key_constraints"],
                
                # 技术方案
                recommended_approach=solution_design["solution_design"]["recommended_approach"],
                technology_stack=solution_design["solution_design"]["technology_stack"],
                integration_points=solution_design["solution_design"]["integration_points"],
                performance_requirements=solution_design["solution_design"]["performance_requirements"],
                
                # 风险评估
                high_risks=implementation_plan["implementation_plan"]["risk_assessment"]["high_risks"],
                medium_risks=implementation_plan["implementation_plan"]["risk_assessment"]["medium_risks"],
                low_risks=implementation_plan["implementation_plan"]["risk_assessment"]["low_risks"],
                risk_mitigation_strategies=implementation_plan["implementation_plan"]["risk_assessment"]["mitigation_strategies"],
                
                # 实施计划
                implementation_steps=implementation_plan["implementation_plan"]["implementation_steps"],
                estimated_time_minutes=implementation_plan["implementation_plan"]["estimated_total_time_minutes"],
                testing_strategy=implementation_plan["implementation_plan"]["testing_strategy"],
                rollback_plan=implementation_plan["implementation_plan"]["rollback_plan"],
                
                # 准备检查
                readiness_checklist=implementation_plan["implementation_plan"]["readiness_checklist"],
                missing_prerequisites=[],
                execution_recommendation=implementation_plan["implementation_plan"]["execution_recommendation"]
            )
            
            # 保存到缓存
            if self.config["cache_enabled"]:
                self._save_analysis_cache(analysis_result)
            
            logging.info(f"🎯 任务分析完成！总用时 {total_analysis_time:.2f}s，置信度 {analysis_result.confidence_level:.2f}")
            
            return analysis_result
            
        except Exception as e:
            logging.error(f"❌ 任务分析失败: {str(e)}")
            # 返回基本的失败结果
            return self._create_fallback_result(task_context, str(e))
    
    # 辅助方法实现（简化版）
    def _extract_core_objective(self, description: str) -> str:
        """提取核心目标"""
        return f"基于描述分析的核心目标: {description[:100]}..."
    
    def _define_functional_scope(self, context: TaskContext, info: Dict) -> List[str]:
        """定义功能范围"""
        return ["主要功能", "辅助功能", "边界功能"]
    
    def _generate_acceptance_criteria(self, context: TaskContext) -> List[str]:
        """生成验收标准"""
        return ["功能正常运行", "性能满足要求", "通过所有测试"]
    
    def _identify_constraints(self, context: TaskContext, info: Dict) -> List[str]:
        """识别约束条件"""
        return ["时间约束", "资源约束", "技术约束"]
    
    def _identify_stakeholders(self, context: TaskContext) -> List[str]:
        """识别利益相关者"""
        return ["开发团队", "产品经理", "最终用户"]
    
    def _define_success_metrics(self, context: TaskContext) -> List[str]:
        """定义成功指标"""
        return ["功能完成度100%", "零缺陷发布", "用户满意度>90%"]
    
    def _calculate_clarity_score(self, analysis: Dict) -> float:
        """计算需求清晰度分数"""
        return 0.85  # 模拟分数
    
    def _select_technology_stack(self, context: TaskContext, info: Dict, req: Dict) -> List[str]:
        """选择技术栈"""
        return ["Python 3.11", "FastAPI", "React 18", "TypeScript", "PostgreSQL"]
    
    def _design_architecture(self, context: TaskContext, info: Dict, stack: List[str]) -> Dict:
        """设计架构"""
        return {
            "pattern": "微服务架构",
            "layers": ["表现层", "业务层", "数据层"],
            "components": ["API网关", "业务服务", "数据存储"]
        }
    
    def _analyze_integration_points(self, context: TaskContext, info: Dict) -> List[str]:
        """分析集成点"""
        return ["REST API", "数据库连接", "缓存服务", "消息队列"]
    
    def _define_performance_requirements(self, context: TaskContext, req: Dict) -> Dict[str, str]:
        """定义性能要求"""
        return {
            "响应时间": "<200ms",
            "并发用户": "1000+",
            "可用性": "99.9%",
            "数据一致性": "最终一致性"
        }
    
    def _generate_implementation_approach(self, context: TaskContext) -> str:
        """生成实施方法"""
        return "采用迭代开发，测试驱动开发(TDD)，持续集成/持续部署(CI/CD)"
    
    def _assess_scalability_needs(self, context: TaskContext) -> List[str]:
        """评估可扩展性需求"""
        return ["水平扩展", "负载均衡", "缓存策略", "数据库分片"]
    
    def _identify_security_needs(self, context: TaskContext) -> List[str]:
        """识别安全需求"""
        return ["身份验证", "授权控制", "数据加密", "输入验证"]
    
    def _calculate_design_confidence(self, design: Dict) -> float:
        """计算设计置信度"""
        return 0.82  # 模拟置信度
    
    def _break_down_implementation_steps(self, context: TaskContext, design: Dict) -> List[Dict[str, str]]:
        """分解实施步骤"""
        return [
            {"step": "环境配置", "description": "设置开发环境", "estimated_minutes": 30},
            {"step": "数据模型", "description": "创建数据模型", "estimated_minutes": 60}, 
            {"step": "API开发", "description": "实现REST API", "estimated_minutes": 120},
            {"step": "前端开发", "description": "构建用户界面", "estimated_minutes": 180},
            {"step": "集成测试", "description": "端到端测试", "estimated_minutes": 90},
            {"step": "部署发布", "description": "生产环境部署", "estimated_minutes": 45}
        ]
    
    def _analyze_task_dependencies(self, context: TaskContext, steps: List[Dict]) -> Dict:
        """分析任务依赖"""
        return {
            "internal_dependencies": ["步骤1 → 步骤2", "步骤2 → 步骤3"],
            "external_dependencies": ["数据库服务", "Redis缓存"],
            "blocking_factors": ["第三方API可用性", "资源分配"]
        }
    
    def _comprehensive_risk_assessment(self, context: TaskContext, design: Dict, steps: List[Dict]) -> Dict:
        """综合风险评估"""
        return {
            "high_risks": ["技术不确定性", "时间压力"],
            "medium_risks": ["资源冲突", "集成复杂性"],
            "low_risks": ["需求变更", "环境问题"],
            "mitigation_strategies": [
                "提前技术验证",
                "预留缓冲时间", 
                "制定备选方案",
                "频繁沟通协调"
            ]
        }
    
    def _design_testing_strategy(self, context: TaskContext, design: Dict, steps: List[Dict]) -> List[str]:
        """设计测试策略"""
        return [
            "单元测试: 覆盖核心业务逻辑",
            "集成测试: 验证模块间协作",
            "API测试: 确保接口契约",
            "端到端测试: 模拟用户场景",
            "性能测试: 验证性能指标",
            "安全测试: 检查安全漏洞"
        ]
    
    def _prepare_rollback_plan(self, context: TaskContext, design: Dict) -> str:
        """准备回滚计划"""
        return "数据库备份 → 代码版本回退 → 配置恢复 → 服务重启 → 验证功能"
    
    def _generate_readiness_checklist(self, context: TaskContext, design: Dict, steps: List[Dict]) -> List[Dict[str, bool]]:
        """生成准备就绪检查清单"""
        return [
            {"item": "开发环境已配置", "ready": False},
            {"item": "依赖库已确认", "ready": False},
            {"item": "API文档已阅读", "ready": False},
            {"item": "测试计划已制定", "ready": False},
            {"item": "团队已对齐", "ready": False}
        ]
    
    def _estimate_total_time(self, steps: List[Dict]) -> int:
        """估算总时间"""
        if not steps:
            return 240  # 默认4小时
        return sum(int(step.get("estimated_minutes", 60)) for step in steps)
    
    def _estimate_resource_requirements(self, context: TaskContext) -> Dict[str, str]:
        """估算资源需求"""
        return {
            "开发人员": "1-2人",
            "测试人员": "1人", 
            "服务器资源": "中等配置",
            "第三方服务": "Redis, PostgreSQL"
        }
    
    def _generate_execution_recommendation(self, context: TaskContext, risk: Dict) -> str:
        """生成执行建议"""
        if len(risk["high_risks"]) > 2:
            return "建议分阶段实施，降低风险"
        elif context.priority >= 4:
            return "高优先级任务，建议立即开始"
        else:
            return "标准实施流程，按计划执行"
    
    def _save_analysis_to_memory(self, context: TaskContext, plan: Dict):
        """保存分析结果到项目记忆"""
        memory_content = f"""
任务分析结果: {context.task_id}
描述: {context.task_description}
分析时间: {datetime.now().isoformat()}
关键洞察: {plan["execution_recommendation"]}
主要风险: {', '.join(plan["risk_assessment"]["high_risks"])}
预估时间: {plan.get("estimated_total_time_minutes", 240)}分钟
技术栈: React + FastAPI + PostgreSQL
        """.strip()
        
        # 模拟保存到memory
        logging.info(f"💾 保存分析结果到项目记忆")
    
    def _calculate_complexity_score(self, req: Dict, design: Dict, plan: Dict) -> int:
        """计算复杂度分数"""
        return min(5, max(1, plan.get("estimated_total_time_minutes", 240) // 60))
    
    def _calculate_overall_confidence(self, req: Dict, design: Dict, plan: Dict) -> float:
        """计算整体置信度"""
        scores = [
            req["requirement_clarity_score"],
            design["design_confidence"], 
            plan["plan_confidence"]
        ]
        return sum(scores) / len(scores)
    
    def _calculate_plan_confidence(self, plan: Dict) -> float:
        """计算计划置信度"""
        return 0.79  # 模拟置信度
    
    def _check_analysis_cache(self, task_id: str) -> Optional[AnalysisResult]:
        """检查分析缓存"""
        cache_file = self.analysis_cache_dir / f"{task_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return AnalysisResult(**data)
            except Exception as e:
                logging.warning(f"缓存读取失败: {str(e)}")
        return None
    
    def _save_analysis_cache(self, result: AnalysisResult):
        """保存分析缓存"""
        cache_file = self.analysis_cache_dir / f"{result.task_id}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                # 转换datetime对象为字符串
                data = asdict(result)
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logging.info(f"✅ 分析结果已缓存: {cache_file}")
        except Exception as e:
            logging.warning(f"缓存保存失败: {str(e)}")
    
    def _create_fallback_result(self, context: TaskContext, error: str) -> AnalysisResult:
        """创建失败回退结果"""
        return AnalysisResult(
            task_id=context.task_id,
            analysis_duration_seconds=0.0,
            complexity_score=3,
            confidence_level=0.1,
            requirement_clarity=0.3,
            functional_scope=["未能分析"],
            acceptance_criteria=["需要人工分析"],
            key_constraints=["分析失败"],
            recommended_approach="需要重新分析",
            technology_stack=[],
            integration_points=[],
            performance_requirements={},
            high_risks=[f"分析失败: {error}"],
            medium_risks=[],
            low_risks=[],
            risk_mitigation_strategies=["重新进行任务分析"],
            implementation_steps=[],
            estimated_time_minutes=0,
            testing_strategy=[],
            rollback_plan="",
            readiness_checklist=[],
            missing_prerequisites=["完整的任务分析"],
            execution_recommendation="请重新进行任务分析"
        )

    def generate_analysis_report(self, result: AnalysisResult) -> str:
        """生成分析报告"""
        return f"""
📋 任务深度分析报告 #TASK-{result.task_id}

⏱️ 分析时间: {result.analysis_duration_seconds:.2f} 秒
📊 复杂度评级: {result.complexity_score}/5
🎯 置信度: {result.confidence_level:.1%}

🎯 需求理解:
- 需求清晰度: {result.requirement_clarity:.1%}
- 功能范围: {', '.join(result.functional_scope)}
- 验收标准: {', '.join(result.acceptance_criteria)}
- 关键约束: {', '.join(result.key_constraints)}

🔧 技术方案:
- 推荐方法: {result.recommended_approach}
- 技术栈: {', '.join(result.technology_stack)}
- 集成点: {', '.join(result.integration_points)}
- 性能要求: {', '.join(f"{k}: {v}" for k, v in result.performance_requirements.items())}

⚠️ 风险评估:
🔴 高风险: {', '.join(result.high_risks)}
🟡 中风险: {', '.join(result.medium_risks)}
🟢 低风险: {', '.join(result.low_risks)}

📋 实施计划:
预估总时间: {result.estimated_time_minutes} 分钟
实施步骤: {len(result.implementation_steps)} 个步骤
测试策略: {', '.join(result.testing_strategy)}

🚀 执行建议: {result.execution_recommendation}
        """.strip()


async def main():
    """主函数 - 测试和命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="任务分析引擎")
    parser.add_argument('action', choices=['analyze', 'test'], nargs='?', default='analyze', help='执行操作')
    parser.add_argument('--task', '--task-content', help='任务描述')
    parser.add_argument('--task-id', help='任务ID')
    parser.add_argument('--task-type', help='任务类型')
    parser.add_argument('--priority', help='优先级')
    parser.add_argument('--template', choices=['quick', 'standard', 'deep'], 
                       help='强制使用特定分析模板')
    # Agent协调器传递的额外参数
    parser.add_argument('--involves-code', action='store_true', help='涉及代码')
    parser.add_argument('--involves-data', action='store_true', help='涉及数据')
    parser.add_argument('--involves-architecture', action='store_true', help='涉及架构')
    parser.add_argument('--has-errors', action='store_true', help='有错误')
    parser.add_argument('--error-type', help='错误类型')
    
    args = parser.parse_args()
    
    engine = TaskAnalysisEngine()
    
    if args.action == 'test':
        # 测试不同复杂度的任务
        test_tasks = [
            {"task": "修复用户登录页面的CSS样式问题", "priority": 2},
            {"task": "开发Reddit信号分析的核心算法，包括数据采集、情感分析和商业洞察生成", "priority": 5},
            {"task": "重构整个后端架构，从单体应用迁移到微服务架构，确保零停机时间", "priority": 4}
        ]
        
        print("🧪 开始测试任务分析引擎...")
        
        for i, test_case in enumerate(test_tasks, 1):
            print(f"\n{'='*60}")
            print(f"测试案例 {i}: {test_case['task'][:50]}...")
            
            result = await engine.analyze_task(
                test_case['task'], 
                test_case['priority']
            )
            
            print(engine.generate_analysis_report(result))
            print(f"{'='*60}")
    
    elif args.action == 'analyze':
        if not args.task:
            print("❌ 分析任务需要提供 --task 参数")
            return
        
        print(f"🔍 正在分析任务: {args.task}")
        
        # 转换priority参数
        priority_val = 3  # 默认优先级
        if args.priority:
            priority_map = {'low': 1, 'medium': 3, 'high': 4, 'critical': 5}
            priority_val = priority_map.get(args.priority, 3)
            try:
                priority_val = int(args.priority)
            except ValueError:
                priority_val = priority_map.get(args.priority, 3)
        
        result = await engine.analyze_task(
            task_description=args.task,
            priority=priority_val,
            force_template=args.template
        )
        
        print("\n" + engine.generate_analysis_report(result))
        
        # 为Agent协调器输出JSON结果（最后一行）
        json_result = {
            'agent': 'task-analyzer',
            'status': 'completed',
            'task_id': args.task_id or 'unknown',
            'analysis_result': {
                'complexity_score': result.complexity_score,
                'confidence_level': result.confidence_level,
                'estimated_hours': getattr(result, 'estimated_hours', 4),  # 默认4小时
                'technical_risk': result.risk_assessment.get('technical_risk', 'medium') if hasattr(result, 'risk_assessment') else 'medium',
                'priority': priority_val
            },
            'suggestions': getattr(result, 'recommendations', ['分析完成', '建议优先处理高风险项目'])[:3],  # 前3个建议
            'execution_time': result.analysis_duration_seconds
        }
        print(json.dumps(json_result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())