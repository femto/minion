#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : tool_example.py

演示如何使用BaseTool和@tool装饰器创建工具
"""
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from minion.tools.base_tool import BaseTool, tool

# 示例1: 使用 BaseTool 类创建工具
class CalculatorTool(BaseTool):
    """基础计算器工具"""
    
    name = "calculator"
    description = "执行基本的数学计算"
    inputs = {
        "expression": {
            "type": "string",
            "description": "要计算的数学表达式"
        }
    }
    output_type = "number"
    
    def forward(self, expression: str) -> float:
        """
        执行数学计算
        
        Args:
            expression: 数学表达式，如 "1 + 2 * 3"
            
        Returns:
            计算结果
        """
        try:
            # 安全的eval，仅允许基本数学运算
            allowed_names = {"__builtins__": {}}
            return eval(expression, allowed_names)
        except Exception as e:
            return {"error": f"计算错误: {str(e)}"}

# 示例2: 使用@tool装饰器创建工具
@tool
def random_number_generator(min_value: int = 1, max_value: int = 100) -> int:
    """
    生成指定范围内的随机整数
    
    Args:
        min_value: 最小值，默认为1
        max_value: 最大值，默认为100
        
    Returns:
        随机整数
    """
    return random.randint(min_value, max_value)

@tool
def text_analyzer(text: str) -> Dict[str, Any]:
    """
    分析文本并返回统计信息
    
    Args:
        text: 要分析的文本
        
    Returns:
        包含文本统计信息的字典
    """
    if not text:
        return {"error": "文本为空"}
    
    words = text.split()
    char_count = len(text)
    word_count = len(words)
    
    # 统计词频
    word_frequencies = {}
    for word in words:
        word = word.lower().strip('.,!?;:()[]{}""\'')
        if word:
            word_frequencies[word] = word_frequencies.get(word, 0) + 1
    
    # 找出最常用的词
    top_words = sorted(word_frequencies.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "char_count": char_count,
        "word_count": word_count,
        "unique_words": len(word_frequencies),
        "top_words": top_words,
        "avg_word_length": sum(len(word) for word in words) / max(1, len(words))
    }

@tool
def weather_tool(city: str, days: int = 1) -> Dict[str, Any]:
    """
    查询指定城市的天气情况（示例工具）
    
    Args:
        city: 城市名称
        days: 查询天数，默认为1（今天）
    Returns:
        天气信息字典
    """
    _cities = {
        "北京": {"lat": 39.9042, "lon": 116.4074, "region": "北方"},
        "上海": {"lat": 31.2304, "lon": 121.4737, "region": "东部"},
        "广州": {"lat": 23.1291, "lon": 113.2644, "region": "南方"},
        "深圳": {"lat": 22.5431, "lon": 114.0579, "region": "南方"},
        "成都": {"lat": 30.5728, "lon": 104.0668, "region": "西部"},
        "西安": {"lat": 34.3416, "lon": 108.9398, "region": "西北"},
        "杭州": {"lat": 30.2741, "lon": 120.1551, "region": "东部"},
        "武汉": {"lat": 30.5928, "lon": 114.3055, "region": "中部"},
        "重庆": {"lat": 29.4316, "lon": 106.9123, "region": "西部"},
        "南京": {"lat": 32.0584, "lon": 118.7965, "region": "东部"},
    }
    _weather_types = ["晴朗", "多云", "阴天", "小雨", "中雨", "大雨", "雷阵雨", "小雪", "中雪", "大雪", "雾霾"]
    _temp_range = {
        "北方": {"spring": (10, 25), "summer": (25, 35), "autumn": (15, 28), "winter": (-10, 10)},
        "南方": {"spring": (15, 30), "summer": (28, 38), "autumn": (20, 32), "winter": (5, 20)},
        "东部": {"spring": (12, 28), "summer": (25, 36), "autumn": (18, 30), "winter": (0, 15)},
        "西部": {"spring": (8, 25), "summer": (22, 32), "autumn": (15, 28), "winter": (-5, 12)},
        "西北": {"spring": (5, 22), "summer": (20, 30), "autumn": (10, 25), "winter": (-15, 5)},
        "中部": {"spring": (10, 26), "summer": (25, 35), "autumn": (15, 28), "winter": (-5, 15)},
    }
    if city not in _cities:
        return {"error": f"不支持查询该城市: {city}，支持的城市有: {', '.join(_cities.keys())}"}
    if days < 1 or days > 7:
        return {"error": "查询天数必须在1-7之间"}
    city_info = _cities[city]
    region = city_info["region"]
    now = datetime.now()
    month = now.month
    if 3 <= month <= 5:
        season = "spring"
    elif 6 <= month <= 8:
        season = "summer"
    elif 9 <= month <= 11:
        season = "autumn"
    else:
        season = "winter"
    temp_range = _temp_range[region][season]
    forecasts = []
    for i in range(days):
        date = now + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weather_type = random.choice(_weather_types)
        if "雨" in weather_type or "雪" in weather_type:
            temp_min = temp_range[0] - random.randint(1, 3)
            temp_max = temp_range[1] - random.randint(2, 5)
        elif "晴" in weather_type:
            temp_min = temp_range[0] + random.randint(0, 2)
            temp_max = temp_range[1] + random.randint(0, 3)
        else:
            temp_min = temp_range[0]
            temp_max = temp_range[1]
        temp_min += random.randint(-2, 2)
        temp_max += random.randint(-2, 2)
        if temp_max <= temp_min:
            temp_max = temp_min + random.randint(3, 8)
        humidity = random.randint(30, 90)
        wind_speed = random.randint(1, 30)
        wind_direction = random.choice(["东", "南", "西", "北", "东北", "东南", "西北", "西南"])
        forecast = {
            "date": date_str,
            "day_name": ["今天", "明天", "后天"][i] if i < 3 else f"{i+1}天后",
            "weather": weather_type,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction
        }
        forecasts.append(forecast)
    result = {
        "city": city,
        "location": {
            "lat": city_info["lat"],
            "lon": city_info["lon"],
            "region": region
        },
        "forecasts": forecasts,
        "units": {
            "temperature": "摄氏度",
            "wind_speed": "km/h",
            "humidity": "%"
        }
    }
    # 增加穿衣建议
    def _get_clothing_suggestions(forecast: Dict[str, Any]) -> Dict[str, str]:
        temp_avg = (forecast["temp_min"] + forecast["temp_max"]) / 2
        weather = forecast["weather"]
        clothing = ""
        activities = ""
        if temp_avg >= 30:
            clothing = "天气炎热，建议穿轻薄透气的短袖短裤，选择棉麻材质的衣物，有条件可使用防晒霜和太阳镜"
        elif 25 <= temp_avg < 30:
            clothing = "天气温暖，建议穿短袖T恤、短裤或裙子，外出可戴遮阳帽"
        elif 20 <= temp_avg < 25:
            clothing = "天气舒适，建议穿长袖衬衫、长裤或裙子，早晚可加一件薄外套"
        elif 15 <= temp_avg < 20:
            clothing = "天气微凉，建议穿长袖衬衫、轻薄毛衣或夹克、长裤等"
        elif 10 <= temp_avg < 15:
            clothing = "天气凉爽，建议穿毛衣、夹克或风衣、长裤等保暖衣物"
        elif 5 <= temp_avg < 10:
            clothing = "天气较冷，建议穿厚外套、保暖内衣、帽子和保暖鞋袜"
        elif 0 <= temp_avg < 5:
            clothing = "天气寒冷，建议穿羽绒服或厚大衣，戴帽子、手套和围巾等保暖"
        else:
            clothing = "天气严寒，建议穿多层厚重保暖衣物，包括羽绒服、保暖帽、手套、围巾和保暖鞋袜"
        if "雨" in weather:
            clothing += "，建议携带雨伞或穿防水外套和防水鞋"
            activities = "不宜进行户外活动，可以选择室内娱乐"
        elif "雪" in weather:
            clothing += "，建议穿防滑保暖鞋靴，注意路面结冰情况"
            activities = "可以进行滑雪等冬季运动，但注意安全防护"
        elif "晴" in weather:
            if temp_avg >= 25:
                activities = "适合游泳、水上活动等夏季户外活动，但注意防晒和补水"
            else:
                activities = "天气晴好，适合户外活动如徒步、旅游等"
        elif "雾霾" in weather:
            clothing += "，建议戴口罩"
            activities = "空气质量较差，建议减少户外活动时间"
        else:
            activities = "天气一般，可适当进行户外活动"
        return {
            "clothing": clothing,
            "activities": activities
        }
    result["suggestions"] = _get_clothing_suggestions(forecasts[0])
    return result

def main():
    """主函数，演示各种工具的使用"""
    print("=== 工具示例演示 ===")
    
    # 创建工具实例
    calculator_tool = CalculatorTool()
    
    # 测试1: 直接调用工具
    print("\n1. 直接调用工具:")
    weather_result = weather_tool("北京", 3)
    print(f"北京未来3天天气: {weather_result['forecasts'][0]['weather']}，"
          f"温度: {weather_result['forecasts'][0]['temp_min']}~{weather_result['forecasts'][0]['temp_max']}°C")
    
    calc_result = calculator_tool("(5 + 3) * 2")
    print(f"计算结果: (5 + 3) * 2 = {calc_result}")
    
    random_num = random_number_generator(1, 10)
    print(f"随机数(1-10): {random_num}")
    
    # 测试文本分析工具
    text = "这是一个示例文本，用于测试文本分析工具。这个工具可以分析文本的字数、词频等信息。"
    analysis_result = text_analyzer(text)
    print(f"\n文本分析结果:")
    print(f"字符数: {analysis_result['char_count']}")
    print(f"词数: {analysis_result['word_count']}")
    print(f"唯一词数: {analysis_result['unique_words']}")
    print(f"平均词长: {analysis_result['avg_word_length']:.2f}")
    print(f"常用词: {analysis_result['top_words']}")
    
    # 测试3: 工具集合
    from minion.tools.base_tool import ToolCollection
    
    tool_collection = ToolCollection([weather_tool, calculator_tool])
    print("\n3. 工具集合:")
    for tool in tool_collection.tools:
        print(f"- {tool.name}: {tool.description}")

if __name__ == "__main__":
    main() 