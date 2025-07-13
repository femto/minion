#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试multi_tool_use.parallel功能

这个脚本直接使用multi_tool_use.parallel模块测试并行工具调用
"""

import asyncio
import sys
import os
import json
import types

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion.tools.async_base_tool import AsyncBaseTool
from minion.tools.multi_tool_use import parallel


# 定义测试用的异步工具函数
async def async_greeting(name: str) -> str:
    """简单的问候工具"""
    await asyncio.sleep(0.2)  # 模拟网络延迟
    print(f"async_greeting called with name={name}")
    return f"你好，{name}！"


async def async_calculator(a: float, b: float, operation: str = "add") -> dict:
    """简单的计算器工具"""
    await asyncio.sleep(0.1)  # 模拟处理延迟
    print(f"async_calculator called with a={a}, b={b}, operation={operation}")
    
    result = None
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        result = a / b if b != 0 else "错误: 除数不能为零"
    else:
        return {"error": f"不支持的操作: {operation}"}
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }


class AsyncDataFormatter(AsyncBaseTool):
    """异步数据格式化工具"""
    
    name = "async_data_formatter"
    description = "格式化各种数据类型"
    
    async def forward(self, data: any, format_type: str = "json") -> dict:
        """
        格式化数据
        
        Args:
            data: 要格式化的数据
            format_type: 格式化类型 (json, text, html)
            
        Returns:
            格式化结果
        """
        await asyncio.sleep(0.15)  # 模拟处理延迟
        print(f"async_data_formatter called with data={data}, format_type={format_type}")
        
        try:
            if format_type == "json":
                return {"formatted": str(data), "type": "json"}
            elif format_type == "text":
                return {"formatted": str(data), "type": "text"}
            elif format_type == "html":
                html = f"<pre>{str(data)}</pre>"
                return {"formatted": html, "type": "html"}
            else:
                return {"error": f"不支持的格式类型: {format_type}"}
        except Exception as e:
            return {"error": f"格式化错误: {str(e)}"}


async def main():
    print("\n🧪 直接测试 multi_tool_use.parallel")
    print("=" * 50)

    # 创建一个静态工具字典，模拟Python执行器的环境
    # 这是multi_tool_use.parallel函数查找工具的地方
    static_tools = {}
    
    # 创建functions命名空间
    functions_ns = types.SimpleNamespace()
    setattr(functions_ns, "async_greeting", async_greeting)
    setattr(functions_ns, "async_calculator", async_calculator)
    
    data_formatter = AsyncDataFormatter()
    setattr(functions_ns, "async_data_formatter", data_formatter)
    
    # 将functions命名空间添加到static_tools中
    static_tools["functions"] = functions_ns
    
    # 在调用之前确保static_tools变量在全局作用域中可用
    # 这对multi_tool_use.parallel的工具发现机制很重要
    globals()["static_tools"] = static_tools
    
    # 测试1: 标准的parallel调用方式
    print("\n✨ 测试1: 标准的parallel调用方式")
    result1 = await parallel({
        "tool_uses": [
            {
                "recipient_name": "functions.async_greeting",
                "parameters": {"name": "小明"}
            },
            {
                "recipient_name": "functions.async_calculator",
                "parameters": {"a": 12.5, "b": 7.5, "operation": "add"}
            },
            {
                "recipient_name": "functions.async_data_formatter",
                "parameters": {"data": [1, 2, 3], "format_type": "json"}
            }
        ]
    })
    print("标准调用结果:")
    print(json.dumps(result1, indent=2, ensure_ascii=False))
    
    # 测试2: 直接列表形式调用
    print("\n✨ 测试2: 直接列表形式调用")
    result2 = await parallel({
        "tool_uses": [
            {
                "recipient_name": "functions.async_greeting", 
                "parameters": {"name": "小红"}
            },
            {
                "recipient_name": "functions.async_calculator", 
                "parameters": {"a": 10, "b": 5, "operation": "multiply"}
            }
        ]
    })
    print("列表形式调用结果:")
    print(json.dumps(result2, indent=2, ensure_ascii=False))
    
    # 测试3: 关键字参数形式调用
    print("\n✨ 测试3: 关键字参数形式调用")
    result3 = await parallel({
        "tool_uses": [
            {
                "recipient_name": "functions.async_calculator", 
                "parameters": {"a": 30, "b": 6, "operation": "divide"}
            },
            {
                "recipient_name": "functions.async_data_formatter", 
                "parameters": {"data": "Hello World", "format_type": "html"}
            }
        ]
    })
    print("关键字参数形式调用结果:")
    print(json.dumps(result3, indent=2, ensure_ascii=False))
    
    print("\n🎉 所有测试完成!")


if __name__ == "__main__":
    asyncio.run(main())