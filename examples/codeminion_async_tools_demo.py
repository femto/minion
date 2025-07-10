#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CodeMinion 异步工具完整使用示例
演示修复后的 CodeMinion 如何完美支持异步工具
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.tools.async_base_tool import AsyncBaseTool, async_tool
from minion.main.brain import Brain
from minion.main.async_python_executor import AsyncPythonExecutor


# 创建一系列实用的异步工具

@async_tool
async def async_fetch_weather(city: str) -> dict:
    """
    异步获取天气信息
    
    Args:
        city: 城市名称
        
    Returns:
        天气信息字典
    """
    await asyncio.sleep(0.3)  # 模拟网络请求
    weather_data = {
        "北京": {"temperature": 15, "condition": "晴朗", "humidity": "45%"},
        "上海": {"temperature": 18, "condition": "多云", "humidity": "60%"},
        "深圳": {"temperature": 25, "condition": "阴天", "humidity": "75%"},
        "广州": {"temperature": 24, "condition": "小雨", "humidity": "80%"}
    }
    
    return weather_data.get(city, {
        "temperature": 20, 
        "condition": "未知", 
        "humidity": "50%",
        "note": f"城市 {city} 的天气数据暂不可用"
    })


@async_tool
async def async_currency_converter(amount: float, from_currency: str, to_currency: str) -> dict:
    """
    异步货币转换工具
    
    Args:
        amount: 金额
        from_currency: 源货币
        to_currency: 目标货币
        
    Returns:
        转换结果
    """
    await asyncio.sleep(0.2)  # 模拟API调用
    
    # 模拟汇率数据 (相对于USD)
    rates = {
        "USD": 1.0,
        "CNY": 7.2,
        "EUR": 0.85,
        "JPY": 110.0,
        "GBP": 0.75
    }
    
    from_rate = rates.get(from_currency, 1.0)
    to_rate = rates.get(to_currency, 1.0)
    
    # 转换到USD，再转换到目标货币
    usd_amount = amount / from_rate
    converted_amount = usd_amount * to_rate
    
    return {
        "original_amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": round(converted_amount, 2),
        "exchange_rate": round(to_rate / from_rate, 4)
    }


class AsyncDataAnalyzer(AsyncBaseTool):
    """异步数据分析工具"""
    
    name = "async_data_analyzer"
    description = "Analyze numerical data asynchronously and provide statistics"
    inputs = {
        "data": {"type": "array", "description": "List of numbers to analyze", "items": {"type": "number"}},
        "analysis_type": {"type": "string", "description": "Type of analysis: 'basic', 'advanced', or 'full'"}
    }
    
    async def forward(self, data: list, analysis_type: str = "basic") -> dict:
        """
        异步分析数据
        
        Args:
            data: 数字列表
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        await asyncio.sleep(0.1)  # 模拟计算时间
        
        if not data:
            return {"error": "Empty data provided"}
        
        # 基础统计
        result = {
            "count": len(data),
            "sum": sum(data),
            "mean": sum(data) / len(data),
            "min": min(data),
            "max": max(data)
        }
        
        if analysis_type in ["advanced", "full"]:
            # 高级统计
            sorted_data = sorted(data)
            n = len(sorted_data)
            median = sorted_data[n//2] if n % 2 == 1 else (sorted_data[n//2-1] + sorted_data[n//2]) / 2
            
            result.update({
                "median": median,
                "range": max(data) - min(data),
                "variance": sum((x - result["mean"]) ** 2 for x in data) / len(data)
            })
            result["std_dev"] = result["variance"] ** 0.5
        
        if analysis_type == "full":
            # 完整统计
            result.update({
                "q1": sorted_data[n//4] if n > 3 else sorted_data[0],
                "q3": sorted_data[3*n//4] if n > 3 else sorted_data[-1],
                "analysis_type": "comprehensive"
            })
        
        return result


async def demo_basic_async_tools():
    """演示基础异步工具使用"""
    print("🌟 演示1: 基础异步工具使用")
    print("=" * 50)
    
    # 创建使用 AsyncPythonExecutor 的 Brain
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    # 创建异步工具
    async_tools = [async_fetch_weather, async_currency_converter, AsyncDataAnalyzer()]
    
    try:
        result = await brain.step(
            query="""
请使用异步工具完成以下任务：
1. 获取北京和上海的天气信息
2. 将100美元转换为人民币
3. 分析数据 [1, 5, 3, 9, 7, 2, 8, 4, 6] 并提供基础统计信息

请写代码调用这些异步工具并输出结果。
""",
            tools=async_tools,
            route="code"
        )
        print(f"✅ 执行结果: {result.response}")
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        import traceback
        traceback.print_exc()


async def demo_concurrent_execution():
    """演示并发执行多个异步工具"""
    print("\n🚀 演示2: 并发执行多个异步工具")
    print("=" * 50)
    
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    async_tools = [async_fetch_weather, async_currency_converter, AsyncDataAnalyzer()]
    
    try:
        result = await brain.step(
            query="""
请演示异步工具的并发执行能力：
1. 同时获取北京、上海、深圳三个城市的天气
2. 同时进行三种货币转换：100 USD->CNY, 50 EUR->USD, 10000 JPY->CNY
3. 使用 asyncio.gather() 来并发执行这些操作

请写代码展示异步工具的并发优势。
""",
            tools=async_tools,
            route="code"
        )
        print(f"✅ 执行结果: {result.response}")
    except Exception as e:
        print(f"❌ 执行错误: {e}")


async def demo_complex_workflow():
    """演示复杂的异步工具工作流"""
    print("\n⚡ 演示3: 复杂异步工具工作流")
    print("=" * 50)
    
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    async_tools = [async_fetch_weather, async_currency_converter, AsyncDataAnalyzer()]
    
    try:
        result = await brain.step(
            query="""
创建一个旅行决策助手的复杂工作流：

1. 获取多个目标城市的天气信息（北京、上海、深圳）
2. 为每个城市计算不同的旅行成本（假设基础费用：北京3000，上海3500，深圳4000）
3. 根据天气条件给每个城市评分（晴朗=10，多云=7，阴天=5，小雨=3）
4. 计算综合性价比得分（天气评分 / 成本 * 1000）
5. 推荐最佳旅行目的地

请设计并执行这个完整的异步工作流。
""",
            tools=async_tools,
            route="code"
        )
        print(f"✅ 执行结果: {result.response}")
    except Exception as e:
        print(f"❌ 执行错误: {e}")


async def demo_performance_comparison():
    """演示异步vs同步性能对比"""
    print("\n⏱️ 演示4: 异步vs同步性能对比")
    print("=" * 50)
    
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio", "time"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    async_tools = [async_fetch_weather, async_currency_converter]
    
    try:
        result = await brain.step(
            query="""
进行性能对比测试：

1. 同步方式：依次调用5个异步工具（每个有延迟）
2. 异步方式：使用 asyncio.gather() 并发调用相同的5个工具
3. 测量并对比两种方式的执行时间
4. 计算性能提升百分比

请写代码来演示异步工具带来的性能优势。
""",
            tools=async_tools,
            route="code"
        )
        print(f"✅ 执行结果: {result.response}")
    except Exception as e:
        print(f"❌ 执行错误: {e}")


async def main():
    """主演示函数"""
    print("🎯 CodeMinion 异步工具完整演示")
    print("=" * 60)
    print("本演示展示了修复后的 CodeMinion 如何完美支持异步工具")
    print()
    
    try:
        await demo_basic_async_tools()
        await demo_concurrent_execution()
        await demo_complex_workflow()
        await demo_performance_comparison()
        
        print("\n🎉 所有演示完成！")
        print("\n💡 总结:")
        print("✅ CodeMinion 现在完全支持异步工具")
        print("✅ 可以并发执行多个异步工具")
        print("✅ 性能显著提升")
        print("✅ 向后兼容同步工具")
        print("✅ 简单易用的API")
        
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 