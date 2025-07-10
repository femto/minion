# Brain 异步工具使用指南

## 概述

`brain.step` 已经完全支持异步工具！您可以直接将异步工具传递给 `brain.step`，系统会自动识别并正确执行异步工具调用。

## 支持的异步工具类型

### 1. 使用 `@async_tool` 装饰器

```python
from minion.tools.async_base_tool import async_tool

@async_tool
async def async_web_search(query: str, max_results: int = 5) -> dict:
    """异步网页搜索工具"""
    await asyncio.sleep(0.5)  # 模拟网络延迟
    return {"query": query, "results": [...]}
```

### 2. 继承 `AsyncBaseTool` 类

```python
from minion.tools.async_base_tool import AsyncBaseTool

class AsyncCalculatorTool(AsyncBaseTool):
    name = "async_calculator"
    description = "Perform asynchronous mathematical calculations"
    inputs = {
        "operation": {"type": "string", "description": "Operation type"},
        "a": {"type": "number", "description": "First number"},
        "b": {"type": "number", "description": "Second number"}
    }
    
    async def forward(self, operation: str, a: float, b: float) -> float:
        await asyncio.sleep(0.1)  # 模拟异步计算
        if operation == "add":
            return a + b
        # ... 其他操作
```

## 使用方式

### 方式 1: 通过 `tools` 参数传递

```python
from minion.main.brain import Brain
from minion.main.local_python_env import LocalPythonEnv

# 创建 Brain 实例
brain = Brain(
    python_env=LocalPythonEnv(verbose=False, is_agent=True),
    tools=[]
)

# 准备异步工具
async_tools = [
    async_web_search,
    AsyncCalculatorTool()
]

# 在 brain.step 中使用异步工具
result = await brain.step(
    query="使用async_web_search搜索'机器学习'相关内容",
    tools=async_tools
)
```

### 方式 2: 在 Brain 初始化时预定义

```python
# 在初始化时设置异步工具
async_tools = [
    async_web_search,
    AsyncCalculatorTool()
]

brain = Brain(
    python_env=LocalPythonEnv(verbose=False, is_agent=True),
    tools=async_tools  # 预定义工具
)

# 直接使用，无需再传递 tools 参数
result = await brain.step(
    query="搜索'深度学习'相关内容"
)
```

## 实际使用示例

### 基础使用

```python
import asyncio
from minion.main.brain import Brain
from minion.tools.async_base_tool import async_tool

@async_tool
async def async_translate(text: str, target_lang: str = "en") -> dict:
    await asyncio.sleep(0.3)
    return {
        "original": text,
        "translated": f"[{target_lang}]: {text}",
        "confidence": 0.95
    }

async def main():
    brain = Brain()
    
    result = await brain.step(
        query="用async_translate把'Hello World'翻译成中文",
        tools=[async_translate]
    )
    
    print(result.response)

asyncio.run(main())
```

### 复杂工作流

```python
# 组合使用多个异步工具
complex_query = """
请执行以下任务流程：
1. 用async_web_search搜索'AI发展趋势'
2. 用async_data_analyzer分析相关数据
3. 用async_notification发送完成通知
"""

result = await brain.step(
    query=complex_query,
    tools=[async_web_search, async_data_analyzer, async_notification]
)
```

### 并发执行

```python
# 并发执行多个 brain.step 调用
tasks = [
    brain.step(query="搜索Python编程", tools=async_tools),
    brain.step(query="翻译文本", tools=async_tools),
    brain.step(query="分析数据", tools=async_tools)
]

results = await asyncio.gather(*tasks)
```

## 核心优势

### 1. 自动异步处理
- 系统自动检测异步工具
- 自动 `await` 异步函数调用
- 无需手动处理 `asyncio` 逻辑

### 2. 向后兼容
- 同步工具依然正常工作
- 可以混合使用同步和异步工具
- 现有代码无需修改

### 3. 并发支持
- 支持多个 `brain.step` 并发执行
- 充分利用异步 I/O 优势
- 提高整体性能

### 4. 灵活配置
- 支持运行时传递工具
- 支持预定义工具
- 支持动态工具组合

## 技术原理

`brain.step` 的异步工具支持基于以下机制：

1. **工具识别**: `LmpActionNode` 自动识别异步工具类型
2. **异步执行**: 使用 `inspect.iscoroutine()` 检测并 `await` 异步调用
3. **结果处理**: 统一处理同步和异步工具的返回结果
4. **错误处理**: 统一的异常处理机制

## 最佳实践

### 1. 工具命名
```python
# 推荐：清晰的命名
@async_tool
async def async_web_search(query: str) -> dict:
    pass

class AsyncDataAnalyzer(AsyncBaseTool):
    name = "async_data_analyzer"  # 明确的工具名称
```

### 2. 类型提示
```python
# 推荐：完整的类型提示
@async_tool
async def async_translate(text: str, target_lang: str = "en") -> dict:
    """提供详细的文档字符串"""
    pass
```

### 3. 错误处理
```python
@async_tool
async def async_api_call(url: str) -> dict:
    try:
        # 异步操作
        await asyncio.sleep(0.1)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### 4. 性能优化
```python
# 对于 I/O 密集型操作，使用异步工具
@async_tool
async def async_file_processor(filepath: str) -> dict:
    async with aiofiles.open(filepath, 'r') as f:
        content = await f.read()
    return {"content": content}
```

## 注意事项

1. **异步上下文**: 确保在异步函数中调用 `brain.step`
2. **工具兼容性**: 异步工具需要实现正确的 `forward` 方法或使用 `@async_tool` 装饰器
3. **性能考虑**: 对于 CPU 密集型任务，同步工具可能更合适
4. **错误处理**: 异步工具中的异常会被正确捕获和处理

## 完整示例

查看 `examples/brain_async_tools_demo.py` 文件以获取完整的使用示例和演示代码。

## 总结

`brain.step` 的异步工具支持为您提供了：

- ✅ **即开即用**: 直接传递异步工具，无需额外配置
- ✅ **高性能**: 充分利用异步 I/O 优势
- ✅ **灵活性**: 支持多种工具定义和使用方式
- ✅ **兼容性**: 完全向后兼容现有同步工具
- ✅ **可扩展**: 支持复杂的异步工作流和并发操作 