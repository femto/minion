#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 multi_tool_use.parallel 功能
验证是否能正确拦截和处理 GPT 生成的并行工具调用
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion.main.brain import Brain
from minion.main.async_python_executor import AsyncPythonExecutor


async def async_test_tool(name: str, delay: float = 0.1) -> dict:
    """测试用的异步工具"""
    await asyncio.sleep(delay)
    return {"tool": "async_test_tool", "name": name, "result": f"Processed {name}"}


async def async_weather_tool(city: str) -> dict:
    """模拟天气工具"""
    await asyncio.sleep(0.1)
    weather_data = {
        "Beijing": {"temp": 15, "condition": "sunny"},
        "Shanghai": {"temp": 18, "condition": "cloudy"},
        "Shenzhen": {"temp": 25, "condition": "rainy"}
    }
    return weather_data.get(city, {"temp": 20, "condition": "unknown"})


async def test_multi_tool_use_parallel():
    """测试 multi_tool_use.parallel 功能"""
    print("🧪 测试 multi_tool_use.parallel 功能")
    print("=" * 50)
    
    # 创建执行器和Brain
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    tools = [async_test_tool, async_weather_tool]
    
    # 测试直接使用 multi_tool_use.parallel
    code_test = """
from multi_tool_use import parallel

# 模拟 GPT 生成的并行工具调用代码
config = {
    "tool_uses": [
        {
            "recipient_name": "functions.async_test_tool",
            "parameters": {"name": "test1", "delay": "0.1"}
        },
        {
            "recipient_name": "functions.async_test_tool", 
            "parameters": {"name": "test2", "delay": "0.1"}
        },
        {
            "recipient_name": "functions.async_weather_tool",
            "parameters": {"city": "Beijing"}
        }
    ]
}

# 执行并行调用
results = await parallel(config)
print(f"并行执行结果: {results}")
print(f"成功调用数: {results['successful_calls']}")
print(f"失败调用数: {results['failed_calls']}")

for i, result in enumerate(results['results']):
    if result['success']:
        print(f"工具 {i+1}: {result['recipient_name']} -> {result['result']}")
    else:
        print(f"工具 {i+1}: {result['recipient_name']} -> 错误: {result['error']}")
"""
    
    try:
        result = await brain.step(
            query=f"执行以下代码来测试并行工具调用:\n\n{code_test}",
            tools=tools,
            route="code"
        )
        print(f"✅ 测试结果: {result.response}")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gpt_generated_parallel_code():
    """测试 GPT 生成的并行调用代码"""
    print("\n🤖 测试 GPT 生成的并行调用代码")
    print("=" * 50)
    
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    tools = [async_test_tool, async_weather_tool]
    
    try:
        result = await brain.step(
            query="""
请使用 multi_tool_use.parallel 来并行执行以下工具调用：
1. async_test_tool 处理 "item1" 和 "item2" 
2. async_weather_tool 获取 "Beijing" 和 "Shanghai" 的天气

请写代码使用 from multi_tool_use import parallel 来实现并行调用。
""",
            tools=tools,
            route="code"
        )
        print(f"✅ GPT生成代码执行结果: {result.response}")
        return True
    except Exception as e:
        print(f"❌ GPT生成代码测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("🎯 multi_tool_use.parallel 功能测试")
    print("=" * 60)
    
    success_count = 0
    total_tests = 2
    
    # 测试1: 直接测试 parallel 功能
    if await test_multi_tool_use_parallel():
        success_count += 1
    
    # 测试2: 测试 GPT 生成的代码
    if await test_gpt_generated_parallel_code():
        success_count += 1
    
    print(f"\n📊 测试结果: {success_count}/{total_tests} 测试通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！multi_tool_use.parallel 功能正常工作")
    else:
        print("⚠️ 部分测试失败，需要检查实现")


if __name__ == "__main__":
    asyncio.run(main()) 