#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : brain_tool.py

演示工具的使用，以及如何将其与Brain集成（概念演示）
"""
import json
from typing import Dict, List, Any, Optional

from minion.tools.base_tool import BaseTool, tool
from minion.tools.example_tool import WeatherTool

# 创建一个简单的翻译工具示例
@tool
def translate_tool(text: str, target_language: str = "英语") -> str:
    """
    将文本翻译成目标语言（模拟）
    
    Args:
        text: 要翻译的文本
        target_language: 目标语言，默认为"英语"
        
    Returns:
        翻译后的文本
    """
    # 这只是一个模拟翻译，实际应用中应该调用真实的翻译API
    translations = {
        "你好": {"英语": "Hello", "日语": "こんにちは", "法语": "Bonjour"},
        "谢谢": {"英语": "Thank you", "日语": "ありがとう", "法语": "Merci"},
        "再见": {"英语": "Goodbye", "日语": "さようなら", "法语": "Au revoir"},
        "天气": {"英语": "Weather", "日语": "天気", "法语": "Météo"},
        "今天": {"英语": "Today", "日语": "今日", "法语": "Aujourd'hui"},
        "明天": {"英语": "Tomorrow", "日语": "明日", "法语": "Demain"},
        "非常好": {"英语": "Very good", "日语": "とても良い", "法语": "Très bien"}
    }
    
    # 如果是已知词汇，直接返回翻译
    for cn_word, translations_dict in translations.items():
        if cn_word in text and target_language in translations_dict:
            return text.replace(cn_word, translations_dict[target_language])
    
    # 默认情况下，添加一个前缀表示翻译
    language_prefix = {
        "英语": "[EN]", 
        "日语": "[JP]", 
        "法语": "[FR]"
    }
    prefix = language_prefix.get(target_language, "[??]")
    return f"{prefix} {text}"

# 模拟Brain使用tools的过程的函数
def simulate_brain_with_tools():
    """模拟Brain如何使用工具"""
    print("=== 模拟Brain使用工具 ===")
    
    # 创建工具实例
    weather_tool = WeatherTool()
    
    # 模拟Brain的tools列表
    tools = [weather_tool, translate_tool]
    
    # 模拟用户查询
    user_queries = [
        "北京今天的天气怎么样？",
        "你能把'你好'和'谢谢'翻译成日语吗？",
        "请问明天上海天气如何，可以用日语告诉我吗？"
    ]
    
    # 模拟Brain处理过程
    for i, query in enumerate(user_queries):
        print(f"\n查询 {i+1}: {query}")
        
        # 模拟LLM决策选择合适的工具
        if "天气" in query and "北京" in query:
            # 使用天气工具
            print("(模拟Brain决策) 检测到天气查询，使用WeatherTool...")
            result = weather_tool("北京", 1)
            print(f"天气工具结果: 北京今天{result['forecasts'][0]['weather']}，"
                  f"温度{result['forecasts'][0]['temp_min']}~{result['forecasts'][0]['temp_max']}°C")
            response = f"根据查询，北京今天{result['forecasts'][0]['weather']}，温度{result['forecasts'][0]['temp_min']}~{result['forecasts'][0]['temp_max']}°C。{result['suggestions']['clothing']}"
            
        elif "翻译" in query and "日语" in query:
            # 使用翻译工具
            print("(模拟Brain决策) 检测到翻译请求，使用translate_tool...")
            result_hello = translate_tool("你好", "日语")
            result_thanks = translate_tool("谢谢", "日语")
            print(f"翻译结果: 你好 -> {result_hello}, 谢谢 -> {result_thanks}")
            response = f"这些词的日语翻译是：\n- 你好：{result_hello}\n- 谢谢：{result_thanks}"
            
        elif "天气" in query and "上海" in query and "日语" in query:
            # 组合使用多个工具
            print("(模拟Brain决策) 检测到需要组合多个工具...")
            
            # 先使用天气工具
            print("1. 使用WeatherTool查询上海天气...")
            weather_result = weather_tool("上海", 1)
            weather_summary = f"上海明天{weather_result['forecasts'][0]['weather']}，温度{weather_result['forecasts'][0]['temp_min']}~{weather_result['forecasts'][0]['temp_max']}°C"
            print(f"天气工具结果: {weather_summary}")
            
            # 再使用翻译工具
            print("2. 使用translate_tool翻译天气信息...")
            translated_result = translate_tool(weather_summary, "日语")
            print(f"翻译工具结果: {translated_result}")
            
            response = f"上海明天的天气: {weather_summary}\n日语翻译: {translated_result}"
        
        else:
            # 没有匹配的工具，使用默认回答
            response = "我不确定如何回答您的问题，请尝试询问有关天气或翻译的问题。"
        
        print(f"模拟Brain响应: {response}")
    
    # 说明Brain.step实现
    print("\n=== 在实际Brain中的工具使用 ===")
    print("在真实的Brain.step方法中，工具使用过程是：")
    print("1. 从input参数或self.tools中获取工具列表")
    print("2. 通过LLM决策选择合适的工具")
    print("3. 调用选定的工具获取结果")
    print("4. 将工具执行结果整合到最终答案中")
    
    # 演示Brain构造和step调用的伪代码示例
    print("\n=== Brain工具集成伪代码示例 ===")
    print("""
# 创建工具实例
weather_tool = WeatherTool()
translator_tool = translate_tool  # 从@tool装饰器创建

# 方法1: 在Brain构造时传入工具
brain = Brain(tools=[weather_tool, translator_tool])

# 方法2: 在Brain.step调用时传入工具
result = brain.step(
    input=Input(query="北京天气怎么样？"),
    tools=[weather_tool, translator_tool],
    system_prompt="你是一个助手，可以使用工具查询信息。"
)
    """)
    
    print("\n注意: 上面是伪代码示例，实际使用时需要导入Brain和Input类，并使用await关键字。")

if __name__ == "__main__":
    simulate_brain_with_tools()
