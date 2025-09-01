# 流式输出支持 (Stream Support)

Minion 现在支持流式输出功能，允许实时显示 LLM 的响应过程，提供更好的用户体验。

## 功能特性

- ✅ **实时响应**: 实时显示 LLM 生成的内容，无需等待完整响应
- ✅ **统一接口**: 通过简单的 `stream=True` 参数启用
- ✅ **向后兼容**: 默认 `stream=False`，不影响现有代码
- ✅ **完整支持**: 从 Brain 到 Provider 的完整流式调用链
- ✅ **多层级支持**: 支持 Brain、Agent、Worker Minions 等各个层级

## 使用方法

### 1. Brain 层级使用

```python
import asyncio
from minion.main.brain import Brain

async def example():
    brain = Brain()
    
    # 启用流式输出
    result = await brain.step(
        query="解释什么是人工智能？",
        route="cot",
        stream=True  # 启用流式输出
    )
    
    print(f"最终结果: {result.answer}")

asyncio.run(example())
```

### 2. Agent 层级使用

```python
import asyncio
from minion.agents.base_agent import BaseAgent

async def example():
    agent = BaseAgent(name="my_agent")
    
    async with agent:
        # 启用流式输出
        result = await agent.run_async(
            task="详细解释机器学习的工作原理",
            stream=True,  # 启用流式输出
            route="cot"
        )
        
        print(f"Agent 结果: {result}")

asyncio.run(example())
```

### 3. 统一参数命名

```python
# 统一使用 stream 参数
result = await agent.run_async(
    task="任务描述", 
    stream=True  # 统一的参数名
)

# Brain 层级也使用相同的参数名
result = await brain.step(
    query="问题",
    stream=True  # 统一的参数名
)
```

## 参数传递路径

```
brain.step(stream=True) 
    ↓
Input.stream = True
    ↓  
LmpActionNode.execute(stream=True)
    ↓
Provider.generate_stream_response()
```

## 支持的 Routes

所有 Worker Minions 都支持流式输出：

- `raw`: 原始 LLM 调用
- `cot`: Chain of Thought 推理
- `python`: Python 代码执行
- `plan`: 计划分解执行
- 其他自定义 minions

## 实现细节

### Input 类扩展

```python
class Input(BaseModel):
    # ... 其他字段
    stream: bool = False  # 流式输出控制字段
```

### LmpActionNode 扩展

```python
async def execute(self, messages, stream=False, **kwargs):
    if stream:
        api_params['stream'] = True
        response = await super().execute_stream(messages, **api_params)
    else:
        response = await super().execute(messages, **api_params)
```

### BaseAgent 方法命名

```python
# 统一的方法命名
async def _run_stream(self, state, max_steps, kwargs):
    """返回异步迭代器，逐步执行并返回中间结果"""
    # ...
```

### Provider 层支持

OpenAI Provider 已支持：
- `generate_stream_response()`: 流式响应方法
- `generate_stream()`: 流式文本生成
- `generate_stream_chunk()`: 原始流式块

## Agent 流式输出

Agent 的 `stream=True` 返回异步生成器：

```python
async with agent:
    # 返回异步生成器
    stream_generator = await agent.run_async(
        task="复杂任务",
        stream=True
    )
    
    # 处理流式结果
    async for result in stream_generator:
        print(f"步骤结果: {result}")
        if hasattr(result, 'terminated') and result.terminated:
            break
```

## 注意事项

1. **性能**: 流式输出可能会略微增加网络开销
2. **兼容性**: 确保使用的 LLM Provider 支持流式输出
3. **错误处理**: 流式输出中的错误会在流结束时抛出
4. **工具调用**: 流式模式下仍支持工具调用功能
5. **Agent 流式**: Agent 的 `stream=True` 返回异步生成器，需要用 `async for` 处理

## 示例代码

查看 `examples/stream_demo.py` 获取完整的使用示例。

## 配置建议

对于交互式应用，建议：

```python
# 短查询使用普通模式
result = await brain.step(query="简单问题", stream=False)

# 长查询或需要实时反馈时使用流式模式  
result = await brain.step(query="复杂分析任务", stream=True)
```

## 故障排除

### 常见问题

1. **参数冲突**: 确保没有重复的 `model` 参数
2. **Provider 不支持**: 确认使用的 LLM Provider 支持流式输出
3. **网络问题**: 流式输出对网络稳定性要求较高

### 调试建议

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 测试流式功能
result = await brain.step(query="测试", stream=True, route="raw")
```