#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的并行工具测试
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion.main.brain import Brain
from minion.main.async_python_executor import AsyncPythonExecutor


async def simple_async_tool(message: str) -> dict:
    """简单的异步工具"""
    await asyncio.sleep(0.1)
    return {"message": f"Processed: {message}", "status": "success"}


async def test_simple_parallel():
    """测试简单的并行调用"""
    print("🧪 测试简单的并行工具调用")
    print("=" * 50)
    
    async_executor = AsyncPythonExecutor(additional_authorized_imports=["asyncio"])
    brain = Brain(python_env=async_executor, llm="gpt-4o")
    
    tools = [simple_async_tool]
    
    # 直接测试工具是否能正常工作
    test_code = """
# 测试1: 检查工具是否可直接调用
print("🔧 测试工具直接调用:")
result = await simple_async_tool("test direct call")
print(f"直接调用结果: {result}")

# 测试2: 检查 multi_tool_use 是否可用
print("\\n📦 测试 multi_tool_use 导入:")
from multi_tool_use import parallel
print("multi_tool_use 导入成功")

# 测试3: 检查当前环境中的工具
print("\\n🔍 检查环境变量:")
import inspect
current_frame = inspect.currentframe()
if 'static_tools' in current_frame.f_locals:
    tools_dict = current_frame.f_locals['static_tools']
    print(f"发现 static_tools: {list(tools_dict.keys())}")
else:
    print("未在当前frame中发现 static_tools")

# 测试4: 尝试并行调用
print("\\n🚀 测试并行调用:")
config = {
    "tool_uses": [
        {
            "recipient_name": "functions.simple_async_tool",
            "parameters": {"message": "hello parallel"}
        }
    ]
}
result = parallel(config)
print(f"并行调用结果: {result}")
"""
    
    try:
        result = await brain.step(
            query=f"执行以下测试代码:\n\n{test_code}",
            tools=tools,
            route="code"
        )
        print(f"✅ 测试完成: {result.response}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_simple_parallel()) 