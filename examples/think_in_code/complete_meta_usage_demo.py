#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整展示Meta工具结果应用的真实CodeAgent示例
"""
import asyncio
from minion.agents.code_agent import CodeAgent
from minion.main.brain import Brain
from minion.main.async_python_executor import AsyncPythonExecutor, evaluate_async_python_code

async def demo_real_world_meta_usage():
    """真实世界的Meta工具结果应用示例"""
    print("🌟 真实世界Meta工具应用演示\n")
    
    # 一个真正体现Meta工具价值的算法优化示例
    real_world_code = '''
def adaptive_search_algorithm(data, target, optimization_level="auto"):
    """自适应搜索算法 - 根据Meta工具分析选择最优搜索策略"""
    
    # 🔥 初始思考：分析数据特征选择算法
    thinking_result = _meta_call("think", 
        f"需要在{len(data)}个元素中搜索{target}，优化级别：{optimization_level}",
        {
            "data_size": len(data),
            "target": str(target),
            "optimization": optimization_level
        },
        "high" if len(data) > 1000 else "medium"
    )
    
    # 🔥 利用思考结果选择搜索策略
    search_algorithm = "linear"  # 默认
    preprocessing_needed = False
    
    if thinking_result:
        analysis = thinking_result.get("analysis", {})
        complexity = analysis.get("complexity", "medium")
        suggestions = thinking_result.get("suggestions", [])
        
        # 根据思考分析决定算法
        if complexity == "high" and len(data) > 100:
            # 复杂场景，值得预处理成本
            search_algorithm = "binary"
            preprocessing_needed = True
        elif complexity == "low" or len(data) <= 10:
            # 简单场景，直接搜索
            search_algorithm = "linear"
        else:
            # 中等场景，考虑数据特征
            if optimization_level == "speed":
                search_algorithm = "binary"
                preprocessing_needed = True
            elif optimization_level == "memory":
                search_algorithm = "linear"
            else:  # auto
                # 根据数据大小自动选择
                search_algorithm = "binary" if len(data) > 50 else "linear"
                preprocessing_needed = search_algorithm == "binary"
        
        # 如果有建议，进一步调整
        if suggestions:
            main_suggestion = suggestions[0].lower()
            if "systematic" in main_suggestion and not preprocessing_needed:
                search_algorithm = "binary"
                preprocessing_needed = True
    
    # 🔥 制定执行计划
    plan_steps = ["数据预处理", "执行搜索", "验证结果"] if preprocessing_needed else ["执行搜索", "验证结果"]
    
    plan_result = _meta_call("plan", "create", {
        "title": f"{search_algorithm}搜索算法执行",
        "algorithm": search_algorithm,
        "preprocessing": preprocessing_needed,
        "steps": plan_steps,
        "expected_complexity": "O(log n)" if search_algorithm == "binary" else "O(n)"
    })
    
    execution_mode = "optimized"
    if plan_result:
        total_steps = plan_result.get("total_steps", len(plan_steps))
        if total_steps > 3:
            execution_mode = "comprehensive"
        elif total_steps < 3:
            execution_mode = "minimal"
    
    # 执行搜索
    steps_completed = 0
    search_result = None
    
    # 步骤1: 预处理（如果需要）
    if preprocessing_needed:
        # 排序以支持二分搜索
        sorted_data = sorted(enumerate(data), key=lambda x: x[1])
        sorted_values = [item[1] for item in sorted_data]
        
        _meta_call("plan", "complete_step", {
            "result": "数据预处理完成",
            "notes": f"排序{len(data)}个元素用于二分搜索"
        })
        steps_completed += 1
        
        # 二分搜索
        left, right = 0, len(sorted_values) - 1
        position = -1
        
        while left <= right:
            mid = (left + right) // 2
            if sorted_values[mid] == target:
                # 找到目标，获取原始索引
                position = sorted_data[mid][0]
                break
            elif sorted_values[mid] < target:
                left = mid + 1
            else:
                right = mid - 1
        
        search_result = position
        algorithm_used = "binary_search"
        
    else:
        # 线性搜索
        for i, value in enumerate(data):
            if value == target:
                search_result = i
                break
        
        if search_result is None:
            search_result = -1
        
        algorithm_used = "linear_search"
    
    _meta_call("plan", "complete_step", {
        "result": f"搜索完成，结果索引: {search_result}",
        "notes": f"算法: {algorithm_used}"
    })
    steps_completed += 1
    
    # 验证结果
    is_correct = False
    if search_result >= 0 and search_result < len(data):
        is_correct = data[search_result] == target
    elif search_result == -1:
        is_correct = target not in data
    
    _meta_call("plan", "complete_step", {
        "result": f"验证{'通过' if is_correct else '失败'}",
        "notes": f"找到位置: {search_result}, 正确性: {is_correct}"
    })
    steps_completed += 1
    
    # 🔥 反思算法选择和性能
    reflection_result = _meta_call("reflect", "decision", {
        "algorithm_chosen": search_algorithm,
        "preprocessing_used": preprocessing_needed,
        "data_characteristics": {
            "size": len(data),
            "target_found": search_result >= 0
        },
        "performance_factors": {
            "steps_completed": steps_completed,
            "execution_mode": execution_mode,
            "correctness": is_correct
        },
        "alternatives_considered": ["linear_search", "binary_search"]
    })
    
    # 🔥 利用反思结果评估算法选择质量
    choice_quality = "good"
    efficiency_score = 0.8
    
    if reflection_result:
        learning_points = reflection_result.get("learning_points", [])
        recommendations = reflection_result.get("recommendations", [])
        
        # 根据反思评估选择质量
        if preprocessing_needed and len(data) < 20:
            choice_quality = "over_engineered"
            efficiency_score = 0.6
        elif not preprocessing_needed and len(data) > 100:
            choice_quality = "sub_optimal"
            efficiency_score = 0.7
        elif is_correct and steps_completed <= len(plan_steps):
            choice_quality = "excellent"
            efficiency_score = 0.9
        
        # 如果有太多建议，说明选择有问题
        if len(recommendations) > 2:
            efficiency_score -= 0.1
    
    return {
        "target": target,
        "found_at_index": search_result,
        "algorithm_used": search_algorithm,
        "preprocessing_used": preprocessing_needed,
        "steps_completed": steps_completed,
        "execution_mode": execution_mode,
        "correctness": is_correct,
        "choice_quality": choice_quality,
        "efficiency_score": efficiency_score,
        "thinking_influenced_choice": thinking_result is not None,
        "plan_guided_execution": plan_result is not None,
        "reflection_provided_feedback": reflection_result is not None
    }

# 🔥 测试用例 - 展示不同场景下Meta工具如何影响算法选择
test_cases = [
    {
        "name": "小数据集",
        "data": [3, 1, 4, 1, 5, 9, 2, 6],
        "target": 5,
        "optimization": "auto"
    },
    {
        "name": "中等数据集",
        "data": list(range(1, 51)),  # 1到50
        "target": 25,
        "optimization": "speed"
    },
    {
        "name": "大数据集", 
        "data": list(range(1, 201)),  # 1到200
        "target": 150,
        "optimization": "auto"
    },
    {
        "name": "目标不存在",
        "data": [10, 20, 30, 40, 50],
        "target": 35,
        "optimization": "memory"
    }
]

for i, test_case in enumerate(test_cases, 1):
    result = adaptive_search_algorithm(
        test_case["data"], 
        test_case["target"], 
        test_case["optimization"]
    )
    
    print(f"\\n测试 {i}: {test_case['name']}")
    print(f"数据量: {len(test_case['data'])}, 目标: {test_case['target']}")
    print(f"结果: 索引 {result['found_at_index']} ({'找到' if result['found_at_index'] >= 0 else '未找到'})")
    print(f"算法: {result['algorithm_used']}")
    print(f"预处理: {'是' if result['preprocessing_used'] else '否'}")
    print(f"执行模式: {result['execution_mode']}")
    print(f"选择质量: {result['choice_quality']}")
    print(f"效率评分: {result['efficiency_score']:.1f}")
    print(f"Meta工具影响: 思考{'✓' if result['thinking_influenced_choice'] else '✗'} 计划{'✓' if result['plan_guided_execution'] else '✗'} 反思{'✓' if result['reflection_provided_feedback'] else '✗'}")
    print("-" * 60)

print("\\n🎯 关键展示:")
print("1. 🧠 thinking_result.analysis.complexity → 算法选择")
print("2. 📋 plan_result.total_steps → 执行模式控制") 
print("3. 🔍 reflection_result.recommendations → 质量评估")
print("4. 💡 Meta工具结果直接驱动所有关键决策!")
'''
    
    print("🔧 执行真实世界Meta工具应用演示...")
    
    # 创建执行器
    executor = AsyncPythonExecutor(additional_authorized_imports=[])
    executor.send_tools({})
    
    try:
        result = await evaluate_async_python_code(
            real_world_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=[]
        )
        print("✅ 真实世界演示执行成功!")
        print("\n🎉 演示要点:")
        print("   🔥 Meta工具结果直接影响算法选择")
        print("   🔥 thinking → 选择linear vs binary search")
        print("   🔥 plan → 控制执行步骤和模式")
        print("   🔥 reflect → 评估选择质量和效率")
        print("   🔥 完整的思考→规划→执行→反思闭环")
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

# 添加一个简化的直接测试
async def test_direct_meta_usage():
    """直接测试Meta工具结果的获取和使用"""
    print("\n🧪 直接Meta工具结果测试\n")
    
    from minion.tools.think_in_code_tool import ThinkInCodeTool
    from minion.tools.meta_tools import PlanTool, ReflectionTool
    
    # 直接测试思考工具
    think_tool = ThinkInCodeTool()
    result = await think_tool.forward(
        "测试复杂的算法选择问题",
        {"complexity": "high", "domain": "algorithms"},
        "high"
    )
    
    print("🧠 ThinkInCodeTool 直接结果:")
    print(f"   思考完成: {result.get('thinking_complete')}")
    print(f"   分析复杂度: {result.get('analysis', {}).get('complexity')}")
    print(f"   思考类型: {result.get('analysis', {}).get('thought_type')}")
    print(f"   建议数量: {len(result.get('suggestions', []))}")
    if result.get('suggestions'):
        print(f"   主要建议: {result['suggestions'][0]}")
    
    # 测试计划工具
    plan_tool = PlanTool()
    plan_result = await plan_tool.forward("create", {
        "title": "测试计划",
        "steps": ["分析", "设计", "实现"]
    })
    
    print(f"\n📋 PlanTool 直接结果:")
    print(f"   计划创建: {plan_result.get('plan_created')}")
    print(f"   计划ID: {plan_result.get('plan_id')}")
    print(f"   总步数: {plan_result.get('total_steps')}")
    
    # 测试反思工具
    reflect_tool = ReflectionTool()
    reflect_result = await reflect_tool.forward("result", {
        "algorithm": "binary_search",
        "performance": "good"
    })
    
    print(f"\n🔍 ReflectionTool 直接结果:")
    print(f"   反思完成: {reflect_result.get('reflection_complete')}")
    print(f"   学习点: {len(reflect_result.get('learning_points', []))}")
    print(f"   建议数: {len(reflect_result.get('recommendations', []))}")
    
    print(f"\n✅ 所有Meta工具返回了结构化的可用结果!")

if __name__ == "__main__":
    asyncio.run(demo_real_world_meta_usage())
    asyncio.run(test_direct_meta_usage())