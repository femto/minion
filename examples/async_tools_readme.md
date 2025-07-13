# 异步工具使用指南

本文档演示如何在GPT生成的代码中正确使用异步工具，包括单独调用和并行调用。

## 1. 单独调用异步工具

异步工具需要提供所有必需的参数，否则会报错。

### async_greeting 工具

```python
# ✅ 正确用法 - 提供name参数
result = await functions.async_greeting(name="小明")
print(result)  # 输出: 你好，小明！

# ❌ 错误用法 - 缺少必需参数
result = await functions.async_greeting()  # 错误: missing 1 required positional argument: 'name'
```

### async_calculator 工具

```python
# ✅ 正确用法 - 提供所有必需参数
result = await functions.async_calculator(a=10, b=5, operation="add")
print(result)  # 输出: {'operation': 'add', 'a': 10, 'b': 5, 'result': 15}

# ✅ 也可以使用字符串表示数字
result = await functions.async_calculator(a="10", b="5", operation="multiply")
print(result)  # 输出: {'operation': 'multiply', 'a': '10', 'b': '5', 'result': 50}

# ❌ 错误用法 - 缺少必需参数
result = await functions.async_calculator(a=10)  # 错误: missing 1 required positional argument: 'b'
```

### async_data_formatter 工具

```python
# ✅ 正确用法 - 提供data参数
result = await functions.async_data_formatter(data=[1, 2, 3], format_type="json")
print(result)  # 输出: {'formatted': '[1, 2, 3]', 'type': 'json'}

# ✅ 使用不同格式类型
result = await functions.async_data_formatter(data="Hello World", format_type="html")
print(result)  # 输出: {'formatted': '<pre>Hello World</pre>', 'type': 'html'}

# ❌ 错误用法 - 缺少必需参数
result = await functions.async_data_formatter()  # 错误: missing 1 required positional argument: 'data'
```

## 2. 并行调用多个工具

使用 `multi_tool_use.parallel` 可以同时调用多个异步工具，提高效率。

### 标准字典格式调用（推荐）

```python
from multi_tool_use import parallel

# 标准方式调用
result = parallel({
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

print(result)
```

### 注意事项

1. `multi_tool_use.parallel` 只支持字典格式的配置
2. 必须为每个工具提供所有必需的参数
3. 工具名称必须包含 `functions.` 前缀
4. 参数必须放在 `parameters` 字典中

## 常见错误

```python
# ❌ 错误：工具调用没有提供必需参数
result = parallel({
    "tool_uses": [
        {
            "recipient_name": "functions.async_data_formatter",
            "parameters": {}  # 错误: 缺少必需的data参数
        }
    ]
})

# ❌ 错误：错误的参数名称
result = parallel({
    "tool_uses": [
        {
            "recipient_name": "functions.async_calculator",
            "parameters": {"x": 10, "y": 5}  # 错误: 参数名应为a和b
        }
    ]
})

# ❌ 错误：缺少functions前缀
result = parallel({
    "tool_uses": [
        {
            "recipient_name": "async_greeting",  # 错误: 缺少functions.前缀
            "parameters": {"name": "小明"}
        }
    ]
})
```

## 完整示例

```python
from multi_tool_use import parallel
import json

# 创建并行工具调用配置
config = {
    "tool_uses": [
        {
            "recipient_name": "functions.async_greeting",
            "parameters": {"name": "小明"}
        },
        {
            "recipient_name": "functions.async_calculator",
            "parameters": {"a": 10, "b": 5, "operation": "multiply"}
        },
        {
            "recipient_name": "functions.async_data_formatter",
            "parameters": {"data": {"name": "小红", "age": 18}, "format_type": "json"}
        }
    ]
}

# 并行执行所有工具
result = parallel(config)

# 格式化输出结果
print(json.dumps(result, indent=2, ensure_ascii=False))
```

输出结果:

```json
{
  "results": [
    {
      "recipient_name": "functions.async_greeting",
      "result": "你好，小明！",
      "success": true
    },
    {
      "recipient_name": "functions.async_calculator",
      "result": {
        "operation": "multiply",
        "a": 10,
        "b": 5,
        "result": 50
      },
      "success": true
    },
    {
      "recipient_name": "functions.async_data_formatter",
      "result": {
        "formatted": "{'name': '小红', 'age': 18}",
        "type": "json"
      },
      "success": true
    }
  ],
  "total_calls": 3,
  "successful_calls": 3,
  "failed_calls": 0
}
```