# 自动工具转换功能

## 概述

Minion 项目现在支持在构造 `BaseAgent`、`CodeAgent` 或 `ToolCallingAgent` 时自动将原始函数转换为相应的工具类型。这个功能让开发者可以直接传入普通的 Python 函数，而无需手动使用 `@tool` 装饰器。

## 功能特性

### 🔄 智能类型检测
- **同步函数** → 自动转换为 `BaseTool` 实例
- **异步函数** → 自动转换为 `AsyncBaseTool` 实例
- **已转换的工具** → 保持不变，不重复转换

### 📊 完整的元数据提取
- 自动解析函数名称、描述和参数
- 从 docstring 提取参数描述
- 支持类型提示和返回类型验证
- 生成完整的 JSON schema

### 🛡️ 错误处理
- 优雅处理转换失败的情况
- 详细的日志记录
- 保留无法转换的原始函数

## 使用方法

### 基本用法

```python
from minion.agents import BaseAgent, CodeAgent
import asyncio

# 定义原始函数
def calculate_area(length: float, width: float) -> float:
    """
    计算矩形面积
    
    Args:
        length: 矩形长度
        width: 矩形宽度
    """
    return length * width

async def fetch_weather(city: str) -> str:
    """
    获取天气信息
    
    Args:
        city: 城市名称
    """
    await asyncio.sleep(0.1)  # 模拟 API 调用
    return f"{city} 的天气：晴天，25°C"

# 直接传入原始函数，无需装饰器
agent = BaseAgent(
    name="my_agent",
    tools=[
        calculate_area,    # 同步函数 → BaseTool
        fetch_weather,     # 异步函数 → AsyncBaseTool
    ]
)

# 在 setup() 时自动转换
await agent.setup()

# 现在所有函数都已转换为相应的工具类型
for tool in agent.tools:
    print(f"{tool.name}: {type(tool)}")
```

### 混合使用

```python
from minion.tools import tool

# 预转换的工具
@tool
def pre_converted_tool(x: int) -> int:
    """已经转换的工具"""
    return x * 2

# 原始函数
def raw_function(y: int) -> int:
    """原始函数"""
    return y + 1

# 混合使用
agent = CodeAgent(
    tools=[
        pre_converted_tool,  # 已转换 → 保持不变
        raw_function,        # 原始函数 → 自动转换
    ]
)
```

## 转换时机

自动转换发生在 `agent.setup()` 方法中，具体流程：

1. **工具集设置** - 首先设置 MCP、UTCP 等工具集
2. **工具集工具合并** - 将工具集中的工具添加到 agent.tools
3. **🔄 自动转换** - 检测并转换原始函数
4. **Brain 初始化** - 初始化 Brain 组件
5. **标记完成** - 设置 `_is_setup = True`

## 转换逻辑

### 通用检测策略

系统使用更通用的检测逻辑来识别是否需要转换：

```python
# 通用检测：检查是否具有工具的基本属性
if callable(item) and not (hasattr(item, 'name') and hasattr(item, 'description')):
    # 需要转换的原始函数
    pass
else:
    # 已经是工具或工具兼容对象，保持不变
    pass
```

这种方法的优势：
- 🔄 **更灵活** - 支持任何实现工具接口的对象
- 🛠️ **可扩展** - 不依赖特定的类继承关系
- 🎯 **精确** - 基于实际的工具属性而非类型检查

### 支持的对象类型

1. **原始函数** - 会被转换
   ```python
   def my_function(x: int) -> int:
       return x * 2
   ```

2. **预转换工具** - 保持不变
   ```python
   @tool
   def my_tool(x: int) -> int:
       return x * 2
   ```

3. **自定义工具对象** - 保持不变
   ```python
   class CustomTool:
       def __init__(self):
           self.name = "custom_tool"
           self.description = "My custom tool"
       
       def __call__(self, data):
           return f"Processed: {data}"
   ```

### 检测条件
```python
def _convert_raw_functions_to_tools(self):
    for item in self.tools:
        # 检查是否是原始函数（不是工具实例）
        # 使用更通用的判断：如果是可调用对象但没有工具的基本属性，则认为是原始函数
        if callable(item) and not (hasattr(item, 'name') and hasattr(item, 'description')):
            # 进行转换
            converted_tool = tool(item)
```

### 转换过程
1. **类型检测** - 使用 `asyncio.iscoroutinefunction()` 检测是否为异步函数
2. **Schema 提取** - 从函数签名和 docstring 提取元数据
3. **类创建** - 动态创建相应的工具类
4. **方法绑定** - 绑定原始函数到 `forward` 方法
5. **源码保存** - 保存原始源码用于检查

## 日志输出

转换过程会产生详细的日志：

```
INFO - Auto-converted function 'calculate_area' to BaseTool
INFO - Auto-converted function 'fetch_weather' to AsyncBaseTool  
INFO - Successfully auto-converted 2 raw functions to tools
```

## 错误处理

如果函数转换失败：

```
WARNING - Failed to convert function 'problematic_function' to tool: Missing return type hint
```

失败的函数会保留为原始状态，不会中断整个设置过程。

## 最佳实践

### ✅ 推荐做法

```python
# 1. 提供完整的类型提示
def good_function(x: int, y: str) -> float:
    """
    良好的函数定义
    
    Args:
        x: 整数参数
        y: 字符串参数
    """
    return float(x)

# 2. 编写清晰的 docstring
async def good_async_function(data: dict) -> str:
    """
    处理数据的异步函数
    
    Args:
        data: 要处理的数据字典
    """
    await asyncio.sleep(0.1)
    return str(data)
```

### ❌ 避免的做法

```python
# 缺少类型提示
def bad_function(x, y):  # ❌ 没有类型提示
    return x + y

# 缺少 docstring
def another_bad_function(x: int) -> int:  # ❌ 没有文档
    return x * 2
```

## 兼容性

- ✅ 与现有的 `@tool` 装饰器完全兼容
- ✅ 支持所有 Agent 类型（BaseAgent、CodeAgent、ToolCallingAgent）
- ✅ 保持向后兼容性
- ✅ 支持混合使用原始函数和预转换工具
- ✅ 支持任何实现了工具接口的自定义对象（具有 `name` 和 `description` 属性）

## 性能影响

- 转换只在 `setup()` 时执行一次
- 运行时性能与手动转换的工具相同
- 内存开销最小

## 示例项目

查看 `examples/agent_auto_convert_demo.py` 获取完整的使用示例。

## 总结

自动工具转换功能大大简化了 Agent 的使用：

- 🎯 **简化开发** - 无需手动装饰每个函数
- 🔄 **智能检测** - 自动识别同步/异步函数
- 🛠️ **无缝集成** - 与现有工具系统完美配合
- 📊 **完整元数据** - 自动提取类型和文档信息
- 🧹 **代码整洁** - Agent 初始化更加简洁明了