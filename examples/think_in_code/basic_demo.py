#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Think in Code 基础演示
展示Meta工具的基本功能
"""
import asyncio
from minion.tools.think_in_code_tool import ThinkInCodeTool
from minion.tools.meta_tools import PlanTool, ReflectionTool

async def basic_meta_tools_demo():
    """基础Meta工具演示"""
    print("🧠 Think in Code 基础功能演示\n")
    
    # 1. ThinkInCodeTool 演示
    print("1️⃣ ThinkInCodeTool - 内部思考演示:")
    think_tool = ThinkInCodeTool()
    
    # 思考一个数学问题
    result = await think_tool.forward(
        "I need to solve the equation x² - 5x + 6 = 0. Let me think about the best approach.",
        context={"problem_type": "quadratic_equation", "difficulty": "basic"},
        priority="medium"
    )
    
    print(f"   💭 思考完成: {result['thinking_complete']}")
    print(f"   🔍 思考类型: {result['analysis']['thought_type']}")
    print(f"   📊 复杂度: {result['analysis']['complexity']}")
    print(f"   💡 建议: {', '.join(result['suggestions'][:2])}")
    
    # 继续思考解题过程
    result2 = await think_tool.forward(
        "I can use the quadratic formula: x = (-b ± √(b²-4ac)) / 2a. For this equation a=1, b=-5, c=6.",
        context={"method": "quadratic_formula", "step": "applying_formula"},
        priority="high"
    )
    
    print(f"   💭 第二次思考: {result2['analysis']['thought_type']}")
    print(f"   📈 思考总数: {result2['total_thoughts']}")
    
    # 显示思考总结
    summary = think_tool.get_thought_summary()
    print(f"   📋 思考总结: {summary['total_thoughts']}次思考, 主要类型: {summary['most_common_type']}")
    
    print("\n" + "="*60 + "\n")
    
    # 2. PlanTool 演示
    print("2️⃣ PlanTool - 任务规划演示:")
    plan_tool = PlanTool()
    
    # 创建解题计划
    plan_result = await plan_tool.forward("create", {
        "title": "解二次方程 x² - 5x + 6 = 0",
        "goal": "找到方程的所有实数解",
        "steps": [
            "识别方程类型和系数",
            "计算判别式 b² - 4ac",
            "应用求根公式",
            "计算两个解",
            "验证答案正确性"
        ],
        "metadata": {"difficulty": "basic", "expected_time": "5 minutes"}
    })
    
    print(f"   📝 计划创建: {plan_result['plan_created']}")
    print(f"   📊 总步数: {plan_result['total_steps']}")
    print(f"   ➡️ 下一步: {plan_result['next_step']}")
    
    # 模拟执行步骤
    steps_results = [
        {"result": "确认: a=1, b=-5, c=6", "notes": "标准二次方程形式"},
        {"result": "判别式 = 25 - 24 = 1 > 0", "notes": "有两个不同实数解"},
        {"result": "x = (5 ± √1) / 2", "notes": "应用求根公式"},
        {"result": "x₁ = 3, x₂ = 2", "notes": "计算得到两个解"},
        {"result": "验证: 3² - 5×3 + 6 = 0 ✓, 2² - 5×2 + 6 = 0 ✓", "notes": "答案正确"}
    ]
    
    for i, step_data in enumerate(steps_results, 1):
        step_result = await plan_tool.forward("complete_step", step_data)
        print(f"   ✅ 步骤 {i} 完成: {step_result['progress']}")
        if step_result['plan_complete']:
            print(f"   🎉 计划完成! 完成度: {step_result['progress']}")
            break
        else:
            print(f"   ➡️ 下一步: {step_result['next_step']}")
    
    # 获取最终状态
    status = await plan_tool.forward("get_status")
    print(f"   📊 最终状态: {status['status']}, 完成度: {status['completion_percentage']:.0f}%")
    
    print("\n" + "="*60 + "\n")
    
    # 3. ReflectionTool 演示
    print("3️⃣ ReflectionTool - 自我反思演示:")
    reflect_tool = ReflectionTool()
    
    # 对解题过程进行反思
    reflection_result = await reflect_tool.forward(
        subject="process",
        data={
            "method_used": "quadratic_formula",
            "steps_completed": 5,
            "time_taken": "3 minutes",
            "errors_encountered": 0,
            "final_answers": ["x₁ = 3", "x₂ = 2"],
            "verification_successful": True
        },
        questions=[
            "What went well in this problem-solving approach?",
            "Could the process be more efficient?", 
            "What did I learn from this experience?"
        ]
    )
    
    print(f"   🔍 反思完成: {reflection_result['reflection_complete']}")
    print(f"   📚 学习点数量: {len(reflection_result['learning_points'])}")
    
    if reflection_result['learning_points']:
        print("   💡 关键学习点:")
        for point in reflection_result['learning_points']:
            print(f"      • {point}")
    
    if reflection_result['recommendations']:
        print("   📋 改进建议:")
        for rec in reflection_result['recommendations']:
            print(f"      • {rec}")
    
    # 对最终结果进行反思
    result_reflection = await reflect_tool.forward(
        subject="result",
        data={
            "problem": "x² - 5x + 6 = 0",
            "solutions": ["x = 3", "x = 2"],
            "method": "quadratic_formula",
            "confidence": "high",
            "verification": "passed"
        }
    )
    
    print(f"   🎯 结果反思完成: {result_reflection['reflection_complete']}")
    print(f"   📊 结果评估: 完整性={result_reflection['analysis']['result_assessment']['completeness']}")
    
    print("\n🎉 基础Meta工具演示完成!")
    print("\n📋 演示总结:")
    print("   • ThinkInCodeTool: 支持复杂思考和推理分析")
    print("   • PlanTool: 提供结构化的任务规划和执行跟踪")
    print("   • ReflectionTool: 实现深度自我反思和学习改进")
    print("   • 所有工具都支持自动状态感知和上下文访问")

if __name__ == "__main__":
    asyncio.run(basic_meta_tools_demo())