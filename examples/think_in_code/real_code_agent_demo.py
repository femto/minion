#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实CodeAgent使用Think in Code
展示CodeAgent在处理复杂任务时自动调用Meta工具
"""
import asyncio
from minion.agents.code_agent import CodeAgent
from minion.main.brain import Brain
from minion.providers import create_llm_provider
from minion import config

class ThinkingCodeAgent(CodeAgent):
    """
    具有思考能力的CodeAgent
    会在适当时机自动使用Meta工具进行思考、规划和反思
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_think = True  # 启用自动思考
        self.task_complexity = "unknown"
        
    async def pre_step(self, input_obj, kwargs):
        """执行前的预处理 - 添加自动思考"""
        input_obj, kwargs = await super().pre_step(input_obj, kwargs)
        
        if self.auto_think:
            # 分析任务复杂度
            query = getattr(input_obj, 'query', '')
            self.task_complexity = self._assess_task_complexity(query)
            
            # 如果是复杂任务，注入思考代码
            if self.task_complexity in ['medium', 'high']:
                thinking_prompt = self._generate_thinking_prompt(query, self.task_complexity)
                original_query = input_obj.query
                input_obj.query = f"{thinking_prompt}\n\n{original_query}"
        
        return input_obj, kwargs
    
    def _assess_task_complexity(self, query: str) -> str:
        """评估任务复杂度"""
        query_lower = query.lower()
        
        # 高复杂度标识符
        high_complexity_keywords = [
            'algorithm', 'optimize', 'complex', 'machine learning', 'data analysis',
            'mathematical', 'statistical', 'multiple steps', 'comprehensive',
            'system design', 'architecture', 'performance'
        ]
        
        # 中等复杂度标识符
        medium_complexity_keywords = [
            'function', 'class', 'implement', 'create', 'build', 'develop',
            'solve', 'calculate', 'process', 'parse', 'validate', 'convert'
        ]
        
        # 简单任务标识符
        simple_keywords = [
            'print', 'hello world', 'simple', 'basic', 'easy', 'quick',
            'show', 'display', 'what is', 'how to'
        ]
        
        high_score = sum(1 for keyword in high_complexity_keywords if keyword in query_lower)
        medium_score = sum(1 for keyword in medium_complexity_keywords if keyword in query_lower)
        simple_score = sum(1 for keyword in simple_keywords if keyword in query_lower)
        
        # 长度也是复杂度指标
        if len(query) > 200:
            high_score += 1
        elif len(query) > 100:
            medium_score += 1
        
        if high_score >= 2 or (high_score >= 1 and len(query) > 150):
            return "high"
        elif medium_score >= 2 or high_score >= 1:
            return "medium"
        else:
            return "low"
    
    def _generate_thinking_prompt(self, query: str, complexity: str) -> str:
        """生成思考提示"""
        if complexity == "high":
            return '''# 🧠 智能代码生成 - 复杂任务处理

你现在处理的是一个复杂任务。请按照以下模式进行思考和实现：

```python
# 1. 首先进行深度思考分析
_meta_call("think", 
    "正在分析复杂任务的需求和约束条件...",
    {"task_type": "complex", "requires_planning": True},
    "high"
)

# 2. 制定详细的实现计划
_meta_call("plan", "create", {
    "title": "复杂任务实现计划",
    "goal": "分步骤实现任务目标",
    "steps": [
        "需求分析和架构设计",
        "核心算法实现",
        "边界情况处理",
        "性能优化",
        "测试和验证"
    ]
})

# 3. 在关键决策点进行思考
# 在实现过程中适当使用:
# _meta_call("think", "当前决策的考虑...", {"context": "..."})

# 4. 完成步骤时更新计划
# _meta_call("plan", "complete_step", {"result": "步骤结果", "notes": "注释"})

# 5. 最后进行反思总结
# _meta_call("reflect", "result", {"final_solution": "...", "approach": "..."})
```

现在请实现用户的需求：'''
        
        elif complexity == "medium":
            return '''# 🧠 智能代码生成 - 中等复杂任务

这是一个中等复杂度的任务。建议使用以下思考模式：

```python
# 开始前思考任务结构
_meta_call("think", 
    "分析任务需求，确定实现方法...",
    {"complexity": "medium"},
    "medium"
)

# 简化的规划（3-4个步骤）
_meta_call("plan", "create", {
    "title": "实现计划",
    "steps": ["设计结构", "核心实现", "测试验证"]
})

# 在实现过程中适当思考和更新计划
# 最后简单反思
```

用户需求：'''
        
        else:  # low complexity
            return '''# 💡 快速实现

这是一个简单任务，可以直接实现，可选择性使用轻量思考：

```python
# 可选：简单思考
# _meta_call("think", "快速分析实现思路...")
```

用户需求：'''

async def demo_thinking_code_agent():
    """演示具有思考能力的CodeAgent"""
    print("🤖 具有Think in Code能力的真实CodeAgent演示\n")
    
    # 创建配置（简化版本，实际使用时需要有效的LLM配置）
    try:
        # 尝试使用配置中的模型
        model = "gpt-4o-mini"  # 使用较小的模型进行演示
        llm_config = config.models.get(model)
        if llm_config:
            llm = create_llm_provider(llm_config)
        else:
            print("⚠️ 未找到LLM配置，使用模拟模式演示...")
            llm = None
    except Exception as e:
        print(f"⚠️ LLM初始化失败: {e}")
        print("使用模拟模式演示...")
        llm = None
    
    # 创建Brain和Agent
    brain = Brain(llm=llm) if llm else Brain()
    agent = ThinkingCodeAgent(brain=brain)
    
    print("🎯 测试案例1: 高复杂度任务 - 实现排序算法比较")
    print("="*60)
    
    complex_task = """
    实现一个综合的排序算法比较工具，要求：
    1. 实现至少3种不同的排序算法（快排、归并、堆排序）
    2. 对每种算法进行性能测试和比较
    3. 生成可视化的性能对比图表
    4. 分析各算法的时间复杂度和适用场景
    5. 提供详细的测试报告
    """
    
    if llm:
        try:
            print("🔄 处理复杂任务中...")
            result = await agent.run_async(complex_task, max_steps=3)
            print(f"✅ 复杂任务处理完成")
            print(f"📋 最终答案: {result.answer if hasattr(result, 'answer') else result}")
        except Exception as e:
            print(f"❌ 复杂任务处理失败: {e}")
    else:
        print("📝 任务复杂度评估:", agent._assess_task_complexity(complex_task))
        print("🧠 会自动注入思考提示，引导LLM使用Meta工具")
        
    print("\n" + "="*60)
    print("🎯 测试案例2: 中等复杂度任务 - 数据处理函数")
    print("="*60)
    
    medium_task = """
    创建一个数据清洗和分析函数，用于处理CSV文件：
    1. 读取CSV文件
    2. 检测和处理缺失值
    3. 数据类型转换和验证
    4. 基础统计分析
    5. 输出清洗后的数据和分析报告
    """
    
    if llm:
        try:
            print("🔄 处理中等复杂任务中...")
            result = await agent.run_async(medium_task, max_steps=2)
            print(f"✅ 中等任务处理完成")
            print(f"📋 最终答案: {result.answer if hasattr(result, 'answer') else result}")
        except Exception as e:
            print(f"❌ 中等任务处理失败: {e}")
    else:
        print("📝 任务复杂度评估:", agent._assess_task_complexity(medium_task))
        print("🧠 会注入适量的思考和规划提示")
    
    print("\n" + "="*60)
    print("🎯 测试案例3: 低复杂度任务 - 简单函数")
    print("="*60)
    
    simple_task = "写一个函数计算两个数的最大公约数"
    
    if llm:
        try:
            print("🔄 处理简单任务中...")
            result = await agent.run_async(simple_task, max_steps=1)
            print(f"✅ 简单任务处理完成")
            print(f"📋 最终答案: {result.answer if hasattr(result, 'answer') else result}")
        except Exception as e:
            print(f"❌ 简单任务处理失败: {e}")
    else:
        print("📝 任务复杂度评估:", agent._assess_task_complexity(simple_task))
        print("🧠 简单任务，最小化思考开销")

# 创建一个模拟的CodeAgent演示（当没有LLM时）
async def demo_simulated_thinking():
    """模拟具有思考能力的代码生成过程"""
    print("\n🎭 模拟Think in Code代码生成过程\n")
    
    print("📝 假设用户要求: '实现一个高效的素数检测算法'")
    print("🤖 CodeAgent的内部思考过程:\n")
    
    # 模拟生成的代码（带有meta工具调用）
    generated_code = '''
# 🧠 智能素数检测算法实现

def is_prime_with_thinking(n):
    """带有智能思考的素数检测"""
    
    # 初始分析
    _meta_call("think", 
        f"需要检测 {n} 是否为素数。考虑算法效率和正确性。",
        {"input": n, "algorithm_choice": "to_be_determined"},
        "medium"
    )
    
    # 制定算法策略
    if n <= 1:
        _meta_call("think", "输入小于等于1，不是素数")
        return False
    elif n <= 3:
        _meta_call("think", "2和3都是素数")
        return True
    elif n % 2 == 0 or n % 3 == 0:
        _meta_call("think", "能被2或3整除，不是素数")
        return False
    
    # 对于较大的数，使用优化算法
    _meta_call("plan", "create", {
        "title": f"素数检测算法 - 输入: {n}",
        "steps": [
            "排除基本情况",
            "优化的除法测试",
            "返回结果"
        ]
    })
    
    _meta_call("plan", "complete_step", {
        "result": "基本情况处理完成",
        "notes": f"n={n}, 需要进一步检测"
    })
    
    # 优化的素数检测 - 只检测 6k±1 形式的数
    _meta_call("think", 
        "使用6k±1优化：所有素数(>3)都可以表示为6k±1的形式",
        {"optimization": "6k_plus_minus_1", "reason": "efficiency"}
    )
    
    import math
    limit = int(math.sqrt(n)) + 1
    
    i = 5
    while i < limit:
        if n % i == 0 or n % (i + 2) == 0:
            _meta_call("think", f"找到因子 {i} 或 {i+2}，不是素数")
            _meta_call("plan", "complete_step", {
                "result": "非素数",
                "notes": f"因子: {i} 或 {i+2}"
            })
            
            # 反思算法性能
            _meta_call("reflect", "process", {
                "algorithm": "6k_plus_minus_1",
                "efficiency": "good",
                "early_termination": True,
                "factor_found": i
            })
            
            return False
        i += 6
    
    # 完成检测，确认为素数
    _meta_call("plan", "complete_step", {
        "result": "确认为素数",
        "notes": f"检测范围: [5, {limit}), 未发现因子"
    })
    
    # 最终反思
    _meta_call("reflect", "result", {
        "input": n,
        "result": "prime",
        "algorithm": "6k_plus_minus_1_optimization",
        "complexity": "O(sqrt(n)/3)",
        "confidence": "high"
    })
    
    return True

# 测试算法
test_numbers = [17, 25, 97, 100]
print("🧮 智能素数检测测试:")

for num in test_numbers:
    result = is_prime_with_thinking(num)
    print(f"{num} 是{'素数' if result else '合数'}")
'''
    
    print("🎬 生成的代码预览:")
    print("-" * 40)
    print(generated_code[:500] + "...")
    print("-" * 40)
    
    print("\n💡 CodeAgent的智能特性:")
    print("   ✅ 自动评估任务复杂度")
    print("   ✅ 根据复杂度注入适当的思考提示")
    print("   ✅ 生成带有Meta工具调用的智能代码")
    print("   ✅ 实现自动的算法选择和优化")
    print("   ✅ 包含完整的思考、规划和反思流程")
    
    print("\n🚀 使用效果:")
    print("   • 代码更加智能和自适应")
    print("   • 自动进行算法复杂度分析")
    print("   • 包含详细的决策过程记录")
    print("   • 支持自动性能优化选择")
    print("   • 提供可追溯的推理过程")

if __name__ == "__main__":
    asyncio.run(demo_thinking_code_agent())
    asyncio.run(demo_simulated_thinking())