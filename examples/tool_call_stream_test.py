import asyncio
import json
from typing import List, Dict, Any

from minion.configs.config import config
from minion.providers.azure_provider import AzureProvider
from minion.schema.message_types import Message, ToolCall


async def handle_tool_call(tool_calls):
    """模拟处理工具调用的函数"""
    if not tool_calls:
        return "No tool calls to process"
    
    results = []
    for tool_call in tool_calls:
        if tool_call.function.name == "get_weather":
            try:
                args = json.loads(tool_call.function.arguments)
                location = args.get("location", "未知位置")
                results.append(f"获取到了{location}的天气信息：晴朗，气温22°C，湿度65%")
            except json.JSONDecodeError:
                results.append(f"解析参数失败: {tool_call.function.arguments}")
        else:
            results.append(f"未知工具: {tool_call.function.name}")
    
    return "\n".join(results)


async def convert_openai_tool_calls_to_minion_format(openai_tool_calls):
    """将OpenAI格式的工具调用转换为Minion格式"""
    minion_tool_calls = []
    for tc in openai_tool_calls:
        # 创建符合ToolCall模型的对象
        tool_call = ToolCall(
            id=tc.id,
            type="function",
            function={
                "name": tc.function.name,
                "description": "Tool call function",  # 提供一个默认描述
                "parameters": {},  # 空参数定义
                "arguments": tc.function.arguments  # 添加参数
            }
        )
        minion_tool_calls.append(tool_call)
    return minion_tool_calls


async def main():
    # 使用配置中的 gpt-4o 模型
    llm = AzureProvider(config=config.models.get("gpt-4o"))

    # 定义天气查询工具
    weather_tool = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定位置的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名称，如'北京'、'上海'、'旧金山'等"
                    }
                },
                "required": ["location"]
            }
        }
    }

    # 创建用户消息
    messages = [
        Message(role="user", content="今天旧金山的天气如何？")
    ]

    print("===== 测试普通生成（非流式）=====")
    try:
        response = await llm.generate(messages, tools=[weather_tool])
        print(f"Response type: {type(response)}")
        
        if hasattr(response, "__iter__"):
            print("检测到工具调用：")
            for tool_call in response:
                print(f"Tool call ID: {tool_call.id}")
                print(f"Tool call type: {tool_call.type}")
                print(f"Function name: {tool_call.function.name}")
                print(f"Arguments: {tool_call.function.arguments}")
        else:
            print(f"直接回复: {response}")
        
        print(f"Cost: ${llm.get_cost().total_cost:.6f}")
    except Exception as e:
        print(f"非流式模式错误: {e}")

    print("\n===== 测试流式生成 =====")
    # 重置成本计算器以便单独计算流式生成的成本
    llm.cost_manager.reset()
    
    try:
        tool_call_response = await llm.generate_stream(messages, tools=[weather_tool])
        print(f"流式响应类型: {type(tool_call_response)}")
        
        # 处理流式工具调用结果
        if hasattr(tool_call_response, "__iter__"):
            print("检测到流式工具调用：")
            for tool_call in tool_call_response:
                print(f"Tool call ID: {tool_call.id}")
                print(f"Tool call type: {tool_call.type}")
                print(f"Function name: {tool_call.function.name}")
                print(f"Arguments: {tool_call.function.arguments}")
        else:
            print(f"直接回复: {tool_call_response}")
        
        print(f"流式生成最终成本: ${llm.get_cost().total_cost:.6f}")
    except Exception as e:
        print(f"流式模式错误: {e}")

    # 创建一个对话消息示例（非工具调用场景）
    chat_messages = [
        Message(role="user", content="如何提高编程效率？简单介绍几点。")
    ]
    
    print("\n===== 测试正常对话流式生成 =====")
    llm.cost_manager.reset()
    
    try:
        response = await llm.generate_stream(chat_messages)
        print(f"流式对话响应: {response}")
        print(f"流式对话最终成本: ${llm.get_cost().total_cost:.6f}")
    except Exception as e:
        print(f"正常对话流式模式错误: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 