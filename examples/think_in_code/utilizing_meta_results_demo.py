#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接利用Meta工具返回结果的示例
展示如何获取并使用thinking/plan/reflect的返回值来指导算法决策
"""
import asyncio
from minion.main.async_python_executor import AsyncPythonExecutor, evaluate_async_python_code

async def demo_direct_meta_usage():
    """演示直接使用Meta工具返回结果"""
    print("💡 直接利用Meta工具返回结果演示\n")
    
    # 示例：智能数值处理，根据Meta工具结果调整策略
    smart_processing_code = '''
def smart_number_processor(numbers, target_operation="auto"):
    """根据Meta工具分析结果智能选择数值处理策略"""
    
    # 🔥 关键：获取思考结果并用于决策
    thinking_result = _meta_call("think", 
        f"分析{len(numbers)}个数值，需要选择最佳处理策略",
        {"data_size": len(numbers), "operation": target_operation},
        "medium"
    )
    
    # 🔥 利用思考结果中的分析信息
    if thinking_result and "analysis" in thinking_result:
        complexity = thinking_result["analysis"].get("complexity", "unknown")
        print(f"📊 思考分析复杂度: {complexity}")
        
        # 根据思考复杂度调整处理策略
        if complexity == "high":
            strategy = "conservative"
            max_iterations = 100
        elif complexity == "medium":
            strategy = "balanced" 
            max_iterations = 500
        else:
            strategy = "aggressive"
            max_iterations = 1000
    else:
        strategy = "default"
        max_iterations = 300
    
    print(f"🎯 选择策略: {strategy} (最大迭代: {max_iterations})")
    
    # 🔥 制定计划并获取计划ID用于后续跟踪
    plan_result = _meta_call("plan", "create", {
        "title": f"数值处理 - {strategy}策略",
        "strategy": strategy,
        "max_iterations": max_iterations,
        "steps": [
            "数据预处理",
            "算法执行",
            "结果验证"
        ]
    })
    
    # 🔥 利用计划结果调整执行参数
    plan_id = plan_result.get("plan_id") if plan_result else None
    total_steps = plan_result.get("total_steps", 3) if plan_result else 3
    
    print(f"📋 计划ID: {plan_id}, 总步数: {total_steps}")
    
    # 步骤1: 数据预处理 - 根据策略调整
    if strategy == "conservative":
        # 保守策略：严格数据验证
        processed = []
        for num in numbers:
            if isinstance(num, (int, float)) and -1000 <= num <= 1000:
                processed.append(num)
        validation_strict = True
    elif strategy == "aggressive":
        # 激进策略：尽可能转换数据
        processed = []
        for num in numbers:
            try:
                converted = float(num)
                processed.append(converted)
            except:
                pass  # 忽略无法转换的数据
        validation_strict = False
    else:
        # 平衡策略：标准处理
        processed = [x for x in numbers if isinstance(x, (int, float))]
        validation_strict = False
    
    _meta_call("plan", "complete_step", {
        "result": f"预处理完成，{len(processed)}/{len(numbers)}个有效数据",
        "notes": f"策略: {strategy}, 严格验证: {validation_strict}"
    })
    
    # 步骤2: 根据策略执行不同算法
    if len(processed) == 0:
        result = {"error": "No valid data", "strategy": strategy}
    elif target_operation == "auto":
        # 🔥 再次思考选择具体操作
        operation_thinking = _meta_call("think",
            f"有{len(processed)}个有效数据，需要选择合适的数学操作",
            {"valid_data_count": len(processed), "strategy": strategy}
        )
        
        # 根据数据量和策略选择操作
        if len(processed) <= 5:
            chosen_operation = "median"  # 小数据集用中位数
        elif strategy == "conservative":
            chosen_operation = "median"  # 保守策略避免异常值
        else:
            chosen_operation = "mean"   # 其他情况用均值
            
        print(f"🔍 自动选择操作: {chosen_operation}")
        
        if chosen_operation == "median":
            sorted_data = sorted(processed)
            mid = len(sorted_data) // 2
            if len(sorted_data) % 2 == 0:
                result_value = (sorted_data[mid-1] + sorted_data[mid]) / 2
            else:
                result_value = sorted_data[mid]
        else:  # mean
            result_value = sum(processed) / len(processed)
            
        result = {
            "value": result_value,
            "operation": chosen_operation,
            "strategy": strategy,
            "data_used": len(processed)
        }
    else:
        # 使用指定操作
        if target_operation == "sum":
            result_value = sum(processed)
        elif target_operation == "max":
            result_value = max(processed) if processed else 0
        else:
            result_value = sum(processed) / len(processed)  # 默认均值
            
        result = {
            "value": result_value,
            "operation": target_operation,
            "strategy": strategy,
            "data_used": len(processed)
        }
    
    _meta_call("plan", "complete_step", {
        "result": f"计算完成: {result.get('value', 'N/A')}",
        "notes": f"操作: {result.get('operation', 'N/A')}"
    })
    
    # 步骤3: 结果验证和反思
    if "error" not in result:
        # 🔥 进行反思并获取反思结果用于质量评估
        reflection_result = _meta_call("reflect", "result", {
            "strategy_used": strategy,
            "operation": result.get("operation"),
            "data_efficiency": len(processed) / len(numbers),
            "final_value": result.get("value")
        })
        
        # 🔥 利用反思结果评估质量
        if reflection_result:
            learning_points = reflection_result.get("learning_points", [])
            recommendations = reflection_result.get("recommendations", [])
            
            # 根据反思结果调整结果质量评级
            if len(learning_points) > 0:
                quality_score = 0.9  # 有学习点说明处理良好
            elif len(recommendations) > 2:
                quality_score = 0.6  # 太多建议说明有问题
            else:
                quality_score = 0.8  # 标准质量
                
            result["quality_score"] = quality_score
            result["learning_points"] = learning_points
            
            print(f"📈 质量评分: {quality_score:.1f}")
            if learning_points:
                print(f"💡 学习要点: {learning_points[0]}")
    
    _meta_call("plan", "complete_step", {
        "result": "验证完成",
        "notes": f"质量评分: {result.get('quality_score', 'N/A')}"
    })
    
    return result

# 测试不同场景
test_scenarios = [
    {
        "name": "小数据集",
        "data": [1, 2, 3, 4, 5],
        "operation": "auto"
    },
    {
        "name": "混合数据",
        "data": [1, "2", 3.5, None, 5],
        "operation": "auto"
    },
    {
        "name": "大数据集",
        "data": list(range(1, 51)),  # 1到50
        "operation": "mean"
    }
]

print("🧪 智能数值处理测试:")
print("=" * 60)

for scenario in test_scenarios:
    print(f"\\n📋 测试场景: {scenario['name']}")
    print(f"📊 数据: {scenario['data'] if len(scenario['data']) <= 10 else str(len(scenario['data'])) + '个数值'}")
    
    result = smart_number_processor(scenario["data"], scenario["operation"])
    
    if "error" not in result:
        print(f"✅ 结果: {result['value']:.2f}")
        print(f"🔧 操作: {result['operation']}")
        print(f"📊 策略: {result['strategy']}")
        print(f"📈 数据利用: {result['data_used']}/{len(scenario['data'])}")
        if "quality_score" in result:
            print(f"⭐ 质量: {result['quality_score']:.1f}")
    else:
        print(f"❌ 错误: {result['error']}")
    
    print("-" * 40)
'''
    
    print("🔧 执行智能数值处理演示...")
    
    # 创建执行器
    executor = AsyncPythonExecutor(additional_authorized_imports=[])
    executor.send_tools({})
    
    try:
        result = await evaluate_async_python_code(
            smart_processing_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=[]
        )
        print("✅ 智能数值处理演示执行成功!")
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

# 更简单的示例：直接使用Meta工具结果
async def demo_simple_meta_usage():
    """更简单的Meta工具结果使用示例"""
    print("\n🎯 简化的Meta工具结果使用演示\n")
    
    simple_code = '''
def decision_maker_with_thinking(problem_type, difficulty_level):
    """基于思考结果做决策的简单示例"""
    
    # 🔥 获取思考结果
    thinking_result = _meta_call("think", 
        f"需要解决{problem_type}问题，难度{difficulty_level}",
        {"type": problem_type, "difficulty": difficulty_level},
        "high" if difficulty_level > 7 else "medium"
    )
    
    print(f"💭 思考结果: {thinking_result}")
    
    # 🔥 直接使用思考结果中的分析
    if thinking_result:
        analysis = thinking_result.get("analysis", {})
        complexity = analysis.get("complexity", "medium")
        thought_type = analysis.get("thought_type", "unknown")
        suggestions = thinking_result.get("suggestions", [])
        
        print(f"📊 分析复杂度: {complexity}")
        print(f"🧠 思考类型: {thought_type}")
        
        # 🔥 基于思考结果做决策
        if complexity == "high":
            approach = "systematic"
            time_allocation = 60
        elif complexity == "low":
            approach = "direct"
            time_allocation = 15
        else:
            approach = "balanced"
            time_allocation = 30
            
        # 🔥 如果有建议，采纳第一个建议
        if suggestions:
            main_suggestion = suggestions[0]
            if "break down" in main_suggestion.lower():
                approach = "decomposition"
            elif "gather" in main_suggestion.lower():
                approach = "research_first"
                
        print(f"🎯 选择方法: {approach}")
        print(f"⏱️ 时间分配: {time_allocation}分钟")
        
        # 🔥 制定计划并获取结果
        plan_result = _meta_call("plan", "create", {
            "title": f"{problem_type}问题解决",
            "approach": approach,
            "time_limit": time_allocation,
            "steps": ["分析", "执行", "验证"]
        })
        
        if plan_result and plan_result.get("plan_created"):
            print(f"📋 计划创建成功，ID: {plan_result.get('plan_id')}")
            
            # 🔥 根据计划结果调整执行
            total_steps = plan_result.get("total_steps", 3)
            if total_steps > 3:
                execution_mode = "detailed"
            else:
                execution_mode = "simplified"
                
            print(f"⚙️ 执行模式: {execution_mode}")
        
        return {
            "approach": approach,
            "time_allocation": time_allocation,
            "complexity": complexity,
            "thought_type": thought_type,
            "has_suggestions": len(suggestions) > 0
        }
    
    return {"error": "思考失败"}

# 测试决策制定
test_problems = [
    ("数学", 8),
    ("编程", 5),
    ("设计", 3)
]

print("🤖 智能决策制定测试:")
for problem, difficulty in test_problems:
    print(f"\\n🎯 问题: {problem}, 难度: {difficulty}")
    result = decision_maker_with_thinking(problem, difficulty)
    if "error" not in result:
        print(f"  ✅ 方法: {result['approach']}")
        print(f"  ⏱️ 时间: {result['time_allocation']}分钟")
        print(f"  🧠 思考类型: {result['thought_type']}")
    else:
        print(f"  ❌ {result['error']}")
'''
    
    print("🔧 执行简化演示...")
    
    # 创建新的执行器实例
    executor = AsyncPythonExecutor(additional_authorized_imports=[])
    executor.send_tools({})
    
    try:
        result = await evaluate_async_python_code(
            simple_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=[]
        )
        print("✅ 简化演示执行成功!")
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")

if __name__ == "__main__":
    asyncio.run(demo_direct_meta_usage())
    asyncio.run(demo_simple_meta_usage())