"""
Reddit Signal Scanner - 标准TodoWrite任务模板

每个新任务都应该使用此模板创建标准化的任务列表，确保完整的Agent审核流程。

使用方法：
1. 将 TASK_NAME 替换为具体任务名称
2. 将 TASK_DESCRIPTION 替换为任务描述
3. 直接复制到TodoWrite中使用
"""

# 标准7步任务模板
STANDARD_TODO_TEMPLATE = [
    {
        "id": "1", 
        "content": "调用task-analyzer Agent分析{TASK_NAME}任务", 
        "status": "pending"
    },
    {
        "id": "2", 
        "content": "基于分析结果实现{TASK_DESCRIPTION}", 
        "status": "pending"
    },
    {
        "id": "3", 
        "content": "调用quality-gate Agent进行代码质量检查", 
        "status": "pending"
    },
    {
        "id": "4", 
        "content": "修复Agent发现的问题并重新检查", 
        "status": "pending"
    },
    {
        "id": "5", 
        "content": "调用signal-validator Agent验证API响应", 
        "status": "pending"
    },
    {
        "id": "6", 
        "content": "调用linus-architect Agent最终审核", 
        "status": "pending"
    },
    {
        "id": "7", 
        "content": "通过所有审核后标记任务完成", 
        "status": "pending"
    }
]

# 使用示例
def create_todo_for_task(task_name: str, task_description: str) -> list:
    """
    为特定任务创建标准TodoWrite列表
    
    Args:
        task_name: 任务标识符，如"prd02-03"
        task_description: 任务核心功能描述
    
    Returns:
        标准化的TodoWrite任务列表
    """
    template = []
    for item in STANDARD_TODO_TEMPLATE:
        new_item = item.copy()
        new_item["content"] = item["content"].format(
            TASK_NAME=task_name,
            TASK_DESCRIPTION=task_description
        )
        template.append(new_item)
    
    return template

# 示例用法
if __name__ == "__main__":
    # 示例：创建prd02-03任务的TodoWrite列表
    prd02_03_todos = create_todo_for_task(
        task_name="prd02-03",
        task_description="SSE实时推送系统核心功能"
    )
    
    print("PRD02-03任务TodoWrite模板:")
    for todo in prd02_03_todos:
        print(f"  {todo['id']}. [{todo['status']}] {todo['content']}")

# 快速复制模板（用于直接粘贴到TodoWrite调用中）
QUICK_TEMPLATE = '''[
    {"id": "1", "content": "调用task-analyzer Agent分析{TASK_NAME}任务", "status": "pending"},
    {"id": "2", "content": "基于分析结果实现{TASK_DESCRIPTION}", "status": "pending"},
    {"id": "3", "content": "调用quality-gate Agent进行代码质量检查", "status": "pending"},
    {"id": "4", "content": "修复Agent发现的问题并重新检查", "status": "pending"},
    {"id": "5", "content": "调用signal-validator Agent验证API响应", "status": "pending"},
    {"id": "6", "content": "调用linus-architect Agent最终审核", "status": "pending"},
    {"id": "7", "content": "通过所有审核后标记任务完成", "status": "pending"}
]'''

# Agent调用模板
AGENT_CALL_TEMPLATES = {
    "task-analyzer": '''Task(
        subagent_type="task-analyzer",
        description="分析{TASK_NAME}任务",
        prompt="请深度分析{TASK_NAME}任务的需求、技术方案和潜在风险"
    )''',
    
    "quality-gate": '''Task(
        subagent_type="quality-gate", 
        description="代码质量检查",
        prompt="请对{TASK_NAME}的实现进行全面质量检查，包括代码风格、安全性和性能"
    )''',
    
    "signal-validator": '''Task(
        subagent_type="signal-validator",
        description="验证API响应质量", 
        prompt="请验证{TASK_NAME}的API响应和数据质量"
    )''',
    
    "linus-architect": '''Task(
        subagent_type="linus-architect",
        description="最终架构审核",
        prompt="请对{TASK_NAME}进行最终的架构和质量审核"
    )'''
}

print("""
🚀 Reddit Signal Scanner - 标准任务模板已加载

使用步骤:
1. 复制STANDARD_TODO_TEMPLATE到TodoWrite调用中
2. 替换{TASK_NAME}和{TASK_DESCRIPTION}占位符
3. 按顺序执行每个步骤，确保通过所有Agent审核
4. 只有第7步通过后才能标记任务完成

严格遵循此流程，确保代码质量！
""")