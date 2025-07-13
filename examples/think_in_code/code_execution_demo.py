#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Think in Code 代码执行演示
展示在AsyncPythonExecutor中使用Meta工具
"""
import asyncio
from minion.main.async_python_executor import AsyncPythonExecutor, evaluate_async_python_code

async def code_execution_demo():
    """代码执行中的Meta工具演示"""
    print("💻 Think in Code 代码执行演示\n")
    
    # 演示代码 - 一个智能的数据分析程序
    smart_code = '''
def analyze_dataset(data):
    """智能数据分析函数 - 带有内部思考"""
    
    # 开始分析前的思考
    _meta_call("think", 
        f"Starting data analysis. Dataset has {len(data)} records. Need to understand data structure and quality.",
        {"dataset_size": len(data), "task": "data_analysis"},
        "high"
    )
    
    # 制定分析计划
    _meta_call("plan", "create", {
        "title": "数据分析流程",
        "goal": "完成数据的探索性分析",
        "steps": [
            "检查数据基本信息",
            "识别数据类型和缺失值",
            "计算基础统计量",
            "发现数据模式和异常值",
            "生成分析结论"
        ]
    })
    
    import statistics
    import math
    
    # 步骤1: 检查数据基本信息
    _meta_call("think", "Examining basic data structure and size")
    basic_info = {
        "count": len(data),
        "type": type(data).__name__,
        "sample": data[:3] if len(data) >= 3 else data
    }
    
    _meta_call("plan", "complete_step", {
        "result": f"数据包含 {basic_info['count']} 个记录",
        "notes": f"数据类型: {basic_info['type']}, 样本: {basic_info['sample']}"
    })
    
    # 思考数据质量
    if len(data) < 10:
        _meta_call("think", 
            "Dataset is quite small. This might limit statistical reliability.",
            {"concern": "small_sample_size", "recommendation": "cautious_interpretation"}
        )
    
    # 步骤2: 识别数据类型
    numeric_data = [x for x in data if isinstance(x, (int, float))]
    non_numeric = len(data) - len(numeric_data)
    
    _meta_call("plan", "complete_step", {
        "result": f"找到 {len(numeric_data)} 个数值, {non_numeric} 个非数值",
        "notes": "数据类型分析完成"
    })
    
    if non_numeric > 0:
        _meta_call("think", 
            f"Found {non_numeric} non-numeric values. Need to handle these appropriately.",
            {"data_quality_issue": "mixed_types"}
        )
    
    # 步骤3: 计算基础统计量 (仅对数值数据)
    if len(numeric_data) >= 2:
        stats = {
            "mean": statistics.mean(numeric_data),
            "median": statistics.median(numeric_data),
            "stdev": statistics.stdev(numeric_data) if len(numeric_data) > 1 else 0,
            "min": min(numeric_data),
            "max": max(numeric_data)
        }
        
        _meta_call("plan", "complete_step", {
            "result": f"均值: {stats['mean']:.2f}, 标准差: {stats['stdev']:.2f}",
            "notes": f"范围: [{stats['min']}, {stats['max']}]"
        })
        
        # 思考统计结果
        if stats['stdev'] > stats['mean']:
            _meta_call("think", 
                "High standard deviation relative to mean suggests significant variability in data.",
                {"insight": "high_variability", "stdev_mean_ratio": stats['stdev'] / stats['mean']}
            )
    else:
        stats = {"error": "insufficient_numeric_data"}
        _meta_call("think", "Not enough numeric data for meaningful statistical analysis")
    
    # 步骤4: 发现模式和异常值
    if len(numeric_data) >= 3:
        # 简单的异常值检测 (使用1.5 IQR规则)
        sorted_data = sorted(numeric_data)
        q1_idx = len(sorted_data) // 4
        q3_idx = 3 * len(sorted_data) // 4
        q1 = sorted_data[q1_idx]
        q3 = sorted_data[q3_idx]
        iqr = q3 - q1
        
        outliers = [x for x in numeric_data if x < q1 - 1.5*iqr or x > q3 + 1.5*iqr]
        
        _meta_call("plan", "complete_step", {
            "result": f"发现 {len(outliers)} 个潜在异常值",
            "notes": f"异常值: {outliers}" if outliers else "数据分布正常"
        })
        
        if outliers:
            _meta_call("think", 
                f"Detected {len(outliers)} outliers using IQR method. These may need special attention.",
                {"outliers": outliers, "detection_method": "IQR_1.5"}
            )
    
    # 步骤5: 生成分析结论
    analysis_summary = {
        "total_records": len(data),
        "numeric_records": len(numeric_data),
        "statistics": stats,
        "outliers_detected": len(outliers) if 'outliers' in locals() else 0,
        "data_quality": "good" if non_numeric == 0 else "mixed"
    }
    
    _meta_call("plan", "complete_step", {
        "result": "数据分析完成",
        "notes": f"质量评级: {analysis_summary['data_quality']}"
    })
    
    # 最终反思分析过程
    _meta_call("reflect", "process", {
        "analysis_method": "exploratory_data_analysis",
        "steps_completed": 5,
        "insights_found": 2 if 'outliers' in locals() and outliers else 1,
        "data_quality_score": 0.8 if analysis_summary['data_quality'] == 'good' else 0.6
    })
    
    # 对结果进行反思
    _meta_call("reflect", "result", {
        "analysis_completeness": "comprehensive",
        "statistical_validity": "high" if len(numeric_data) >= 10 else "limited",
        "actionable_insights": len(outliers) if 'outliers' in locals() else 0
    })
    
    return analysis_summary

# 测试数据分析函数
test_data = [23, 45, 67, 89, 12, 34, 56, 78, 90, 100, 5, 200]  # 包含一个异常值 200
print("📊 分析测试数据集:")
print(f"数据: {test_data}")
print()

result = analyze_dataset(test_data)
print("✅ 分析完成!")
print(f"📋 分析结果: {result}")
'''
    
    print("🔧 执行包含Meta工具的智能代码...")
    
    # 创建执行器
    executor = AsyncPythonExecutor(additional_authorized_imports=["statistics", "math"])
    executor.send_tools({})  # 注册内置meta工具
    
    try:
        # 执行代码
        result = await evaluate_async_python_code(
            smart_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=["statistics", "math"]
        )
        
        print("✅ 代码执行成功!")
        print(f"📋 可用Meta工具: {executor.state.get('_meta_tools_available', [])}")
        
    except Exception as e:
        print(f"❌ 代码执行失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
    
    print("\n🎯 演示要点:")
    print("   • Meta工具在代码执行中完全透明运行")
    print("   • 自动进行任务规划和步骤跟踪")
    print("   • 实时思考分析和决策支持")
    print("   • 自动反思和学习改进")
    print("   • 支持复杂的数据分析和算法开发")

# 额外演示：算法开发中的思考
async def algorithm_development_demo():
    """算法开发中的Meta工具使用演示"""
    print("\n🧮 算法开发中的Think in Code演示\n")
    
    algorithm_code = '''
def fibonacci_with_thinking(n):
    """带思考的斐波那契数列实现"""
    
    # 开始思考算法选择
    _meta_call("think", 
        f"Need to compute fibonacci number for n={n}. Considering algorithm efficiency.",
        {"input_size": n, "algorithm_choice": "to_be_determined"}
    )
    
    # 根据输入大小制定策略
    if n <= 1:
        _meta_call("think", "Base case, simple return")
        return n
    elif n <= 20:
        _meta_call("think", 
            "Small input, recursive approach is acceptable",
            {"strategy": "recursive", "reason": "simplicity_over_efficiency"}
        )
        strategy = "recursive"
    else:
        _meta_call("think", 
            "Large input, need iterative approach for efficiency",
            {"strategy": "iterative", "reason": "efficiency_required"}
        )
        strategy = "iterative"
    
    # 制定实现计划
    _meta_call("plan", "create", {
        "title": f"计算Fibonacci({n})",
        "strategy": strategy,
        "steps": [
            "处理边界情况",
            "选择最优算法",
            "实现核心逻辑", 
            "验证结果正确性"
        ]
    })
    
    # 完成边界情况步骤
    _meta_call("plan", "complete_step", {
        "result": f"n={n}, 选择策略: {strategy}",
        "notes": "边界检查和策略选择完成"
    })
    
    # 实现算法
    if strategy == "recursive":
        _meta_call("think", "Implementing recursive solution - elegant but potentially slow")
        
        def fib_recursive(x):
            if x <= 1:
                return x
            return fib_recursive(x-1) + fib_recursive(x-2)
        
        result = fib_recursive(n)
        
    else:  # iterative
        _meta_call("think", "Implementing iterative solution - efficient for large inputs")
        
        a, b = 0, 1
        for i in range(2, n + 1):
            a, b = b, a + b
        result = b
    
    # 完成实现步骤
    _meta_call("plan", "complete_step", {
        "result": f"算法实现完成, 策略: {strategy}",
        "notes": f"计算结果: {result}"
    })
    
    # 简单验证 (检查是否符合斐波那契性质)
    if n >= 2:
        # 验证 F(n) = F(n-1) + F(n-2)
        prev1 = fibonacci_with_thinking(n-1) if n <= 5 else None  # 避免递归过深
        prev2 = fibonacci_with_thinking(n-2) if n <= 5 else None
        
        if prev1 is not None and prev2 is not None:
            expected = prev1 + prev2
            is_valid = (result == expected)
            
            _meta_call("plan", "complete_step", {
                "result": f"验证{'通过' if is_valid else '失败'}: F({n}) = {result}",
                "notes": f"验证: {prev2} + {prev1} = {expected}"
            })
            
            if not is_valid:
                _meta_call("think", 
                    "Validation failed! There might be an error in implementation.",
                    {"error": "validation_failed", "expected": expected, "actual": result}
                )
    
    # 反思算法选择和实现
    _meta_call("reflect", "decision", {
        "decision": f"选择{strategy}算法",
        "alternatives": ["recursive", "iterative", "matrix_multiplication"],
        "rationale": f"基于输入大小n={n}的效率考虑",
        "confidence": "high"
    })
    
    # 对整体结果反思
    _meta_call("reflect", "result", {
        "algorithm": strategy,
        "input": n,
        "output": result,
        "complexity": "O(n)" if strategy == "iterative" else "O(2^n)",
        "efficiency": "high" if strategy == "iterative" else "low"
    })
    
    return result

# 测试算法
print("🧮 智能斐波那契算法演示:")
print("计算 Fibonacci(15)...")

result = fibonacci_with_thinking(15)
print(f"✅ 结果: Fibonacci(15) = {result}")
'''
    
    print("🔧 执行算法开发演示...")
    
    try:
        # 执行算法代码
        result = await evaluate_async_python_code(
            algorithm_code,
            static_tools=executor.static_tools,
            custom_tools={},
            state=executor.state.copy(),
            authorized_imports=[]
        )
        
        print("✅ 算法演示执行成功!")
        
    except Exception as e:
        print(f"❌ 算法演示执行失败: {e}")

if __name__ == "__main__":
    asyncio.run(code_execution_demo())
    asyncio.run(algorithm_development_demo())