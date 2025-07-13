#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清晰展示Meta工具结果利用的示例
"""
import asyncio
from minion.main.async_python_executor import AsyncPythonExecutor, evaluate_async_python_code

async def demo_clear_meta_usage():
    """清晰展示Meta工具结果的利用"""
    print("🔥 Meta工具结果利用的关键示例\n")
    
    # 一个真正利用Meta工具结果的完整示例
    clear_demo_code = '''
def solve_problem_intelligently(problem_description, difficulty):
    """智能问题解决器 - 展示Meta工具结果的直接利用"""
    
    print(f"🎯 开始解决问题: {problem_description}")
    print(f"📊 难度等级: {difficulty}/10")
    
    # 🔥 步骤1: 获取思考结果并直接使用
    thinking_result = _meta_call("think", 
        f"分析问题: {problem_description}, 难度: {difficulty}",
        {"problem": problem_description, "difficulty": difficulty},
        "high" if difficulty >= 7 else "medium"
    )
    
    print(f"💭 思考结果获取: {'成功' if thinking_result else '失败'}")
    
    # 🔥 关键：直接从思考结果中提取决策信息
    strategy = "default"
    time_estimate = 30
    
    if thinking_result:
        analysis = thinking_result.get("analysis", {})
        suggestions = thinking_result.get("suggestions", [])
        
        # 根据思考的复杂度评估选择策略
        complexity = analysis.get("complexity", "medium")
        thought_type = analysis.get("thought_type", "general")
        
        print(f"🧠 思考分析 - 复杂度: {complexity}, 类型: {thought_type}")
        
        # 🔥 思考结果直接影响策略选择
        if complexity == "high":
            strategy = "systematic_breakdown"
            time_estimate = 60
        elif complexity == "low":
            strategy = "direct_approach"
            time_estimate = 15
        else:
            strategy = "balanced_approach"
            time_estimate = 30
            
        # 🔥 利用建议进一步调整策略
        if suggestions:
            first_suggestion = suggestions[0].lower()
            print(f"💡 主要建议: {suggestions[0]}")
            
            if "break down" in first_suggestion:
                strategy = "decomposition"
                time_estimate += 15
            elif "gather" in first_suggestion:
                strategy = "research_first"
                time_estimate += 10
    
    print(f"🎯 选定策略: {strategy}")
    print(f"⏱️ 预估时间: {time_estimate}分钟")
    
    # 🔥 步骤2: 制定计划并获取计划信息用于执行控制
    plan_result = _meta_call("plan", "create", {
        "title": f"解决: {problem_description}",
        "strategy": strategy,
        "time_estimate": time_estimate,
        "steps": [
            "问题分析",
            "方案设计", 
            "实施解决",
            "验证结果"
        ]
    })
    
    execution_steps = 4  # 默认步数
    plan_id = "unknown"
    
    if plan_result:
        plan_id = plan_result.get("plan_id", "unknown")
        execution_steps = plan_result.get("total_steps", 4)
        
        print(f"📋 计划创建成功 - ID: {plan_id}, 步数: {execution_steps}")
        
        # 🔥 根据计划步数调整执行深度
        if execution_steps > 4:
            execution_depth = "detailed"
        elif execution_steps < 4:
            execution_depth = "simplified"
        else:
            execution_depth = "standard"
    else:
        execution_depth = "basic"
        
    print(f"⚙️ 执行深度: {execution_depth}")
    
    # 🔥 步骤3: 模拟执行过程，每步完成后更新计划
    results = []
    
    for step_num in range(1, execution_steps + 1):
        step_name = f"步骤{step_num}"
        
        # 模拟执行
        if strategy == "systematic_breakdown":
            step_result = f"{step_name}: 系统化分析完成"
        elif strategy == "direct_approach":
            step_result = f"{step_name}: 直接方法执行"
        else:
            step_result = f"{step_name}: 平衡方法处理"
            
        results.append(step_result)
        
        # 更新计划进度
        _meta_call("plan", "complete_step", {
            "result": step_result,
            "notes": f"策略: {strategy}, 深度: {execution_depth}"
        })
        
        print(f"✅ {step_result}")
    
    # 🔥 步骤4: 反思并获取反思结果用于质量评估
    reflection_result = _meta_call("reflect", "result", {
        "problem": problem_description,
        "strategy_used": strategy,
        "time_spent": time_estimate,
        "steps_completed": len(results),
        "execution_depth": execution_depth,
        "success_indicators": ["计划完成", "策略有效", "时间可控"]
    })
    
    # 🔥 利用反思结果计算最终质量分数
    quality_score = 0.7  # 基础分数
    confidence = "medium"
    
    if reflection_result:
        learning_points = reflection_result.get("learning_points", [])
        recommendations = reflection_result.get("recommendations", [])
        
        # 根据反思结果调整质量评估
        if len(learning_points) > 0:
            quality_score += 0.2  # 有学习说明执行良好
        if len(recommendations) <= 1:
            quality_score += 0.1  # 建议少说明质量高
        else:
            quality_score -= 0.1  # 建议多说明有问题
            
        # 根据策略和复杂度匹配度评估
        if strategy == "systematic_breakdown" and thinking_result:
            analysis = thinking_result.get("analysis", {})
            if analysis.get("complexity") == "high":
                quality_score += 0.1  # 策略匹配
                confidence = "high"
    
    # 确保分数在合理范围内
    quality_score = min(1.0, max(0.0, quality_score))
    
    print(f"📊 最终质量评分: {quality_score:.1f}/1.0")
    print(f"🎯 置信度: {confidence}")
    
    return {
        "problem": problem_description,
        "strategy": strategy,
        "time_estimate": time_estimate,
        "execution_depth": execution_depth,
        "steps_completed": len(results),
        "quality_score": quality_score,
        "confidence": confidence,
        "plan_id": plan_id,
        "learning_occurred": len(reflection_result.get("learning_points", [])) > 0 if reflection_result else False
    }

# 🔥 测试不同类型的问题，展示Meta工具结果如何影响决策
test_problems = [
    ("优化网站性能", 8),
    ("写一个排序函数", 4),
    ("设计分布式系统架构", 9),
    ("修复简单的bug", 2)
]

print("🧪 智能问题解决测试 - 展示Meta工具结果的实际影响:")
print("=" * 80)

for problem, difficulty in test_problems:
    print(f"\\n🎯 问题类型: {problem}")
    print("-" * 50)
    
    result = solve_problem_intelligently(problem, difficulty)
    
    print(f"\\n📋 执行总结:")
    print(f"  🎯 策略: {result['strategy']}")
    print(f"  ⏱️ 时间: {result['time_estimate']}分钟")
    print(f"  ⚙️ 深度: {result['execution_depth']}")
    print(f"  ✅ 步数: {result['steps_completed']}")
    print(f"  📊 质量: {result['quality_score']:.1f}")
    print(f"  🎯 置信: {result['confidence']}")
    print(f"  📚 学习: {'是' if result['learning_occurred'] else '否'}")
    
    print("\\n" + "="*50)

print("\\n🎉 演示完成!")
print("\\n💡 关键展示点:")
print("  🔥 thinking_result直接影响策略选择")
print("  🔥 plan_result控制执行步数和深度")  
print("  🔥 reflection_result用于质量评估")
print("  🔥 Meta工具结果驱动整个决策流程")
'''
    
    print("🔧 执行清晰的Meta工具结果利用演示...")
    
    # 创建执行器
    executor = AsyncPythonExecutor(additional_authorized_imports=[])
    executor.send_tools({})
    
    try:
        result = await evaluate_async_python_code(
            clear_demo_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=[]
        )
        print("✅ 清晰演示执行成功!")
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(demo_clear_meta_usage())