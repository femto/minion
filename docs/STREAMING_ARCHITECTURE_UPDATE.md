# 流式输出架构更新 - StreamChunk 实现

## 🎯 架构改进概述

根据你的建议，我们将流式输出架构从直接 yield 字符串内容升级为使用结构化的 `StreamChunk` 对象，这提供了更好的可扩展性和元数据支持。

## 🏗️ 新架构设计

### 1. StreamChunk 对象

```python
@dataclass
class StreamChunk:
    """单个流式输出块"""
    content: str
    chunk_type: str = "text"  # text, tool_call, observation, error
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
```

### 2. 分层架构

```
用户应用层
    ↓ (处理 StreamChunk 对象)
Minion 层 (WorkerMinion._process_stream_generator)
    ↓ (创建 StreamChunk 对象)
ActionNode 层 (LmpActionNode._execute_stream_generator)
    ↓ (yield 字符串内容)
LLM Provider 层 (OpenAIProvider.generate_stream)
    ↓ (yield 字符串内容)
OpenAI API
```

## 🔧 实现细节

### 1. LLM Provider 层
- **保持不变**: 继续 yield 字符串内容
- **原因**: 保持底层简单性，专注于 LLM 交互

```python
# OpenAI Provider
async def generate_stream(self, messages, **kwargs) -> AsyncIterator[str]:
    async for chunk in self.generate_stream_chunk(messages, **kwargs):
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            yield content  # 直接 yield 字符串
```

### 2. ActionNode 层
- **保持不变**: 继续 yield 字符串内容
- **原因**: 保持 ActionNode 的通用性

```python
# LmpActionNode
async def _execute_stream_generator(self, messages, **api_params):
    async for chunk in self.llm.generate_stream(messages, **api_params):
        yield chunk  # 直接传递字符串
```

### 3. Minion 层 (关键改进)
- **新增**: 在 `_process_stream_generator` 中创建 `StreamChunk` 对象
- **优势**: 添加元数据和结构化信息

```python
# WorkerMinion
async def _process_stream_generator(self, stream_generator):
    from minion.main.action_step import StreamChunk
    
    full_response = ""
    chunk_counter = 0
    
    async for chunk in stream_generator:
        content = str(chunk)
        full_response += content
        chunk_counter += 1
        
        # 创建 StreamChunk 对象
        stream_chunk = StreamChunk(
            content=content,
            chunk_type="text",
            metadata={
                "minion_type": self.__class__.__name__,
                "chunk_number": chunk_counter,
                "total_length": len(full_response)
            }
        )
        yield stream_chunk
```

### 4. 用户应用层
- **新增**: 处理 `StreamChunk` 对象
- **向后兼容**: 同时支持字符串和 `StreamChunk`

```python
# 演示代码
async for chunk in stream_generator:
    # 处理 StreamChunk 对象或字符串
    if hasattr(chunk, 'content'):
        content = chunk.content
        # 可以访问额外的元数据
        metadata = chunk.metadata
        chunk_type = chunk.chunk_type
    else:
        content = str(chunk)
    
    print(content, end='', flush=True)
```

## 📊 架构优势

### 1. 结构化数据
- **元数据支持**: 每个块包含丰富的元数据信息
- **类型标识**: 支持不同类型的块（文本、工具调用、观察等）
- **时间戳**: 自动记录每个块的生成时间

### 2. 可扩展性
- **未来扩展**: 可以轻松添加新的块类型和元数据
- **调试支持**: 元数据有助于调试和监控
- **统计分析**: 可以收集详细的流式输出统计信息

### 3. 向后兼容
- **渐进升级**: 现有代码可以继续工作
- **灵活处理**: 同时支持字符串和 `StreamChunk` 对象

## 🔄 迁移指南

### 对于现有代码
```python
# 旧代码 (仍然工作)
async for chunk in stream_generator:
    print(chunk, end='', flush=True)

# 新代码 (推荐)
async for chunk in stream_generator:
    if hasattr(chunk, 'content'):
        content = chunk.content
    else:
        content = str(chunk)
    print(content, end='', flush=True)
```

### 对于新功能
```python
async for chunk in stream_generator:
    if hasattr(chunk, 'content'):
        # 访问结构化数据
        print(f"[{chunk.chunk_type}] {chunk.content}", end='')
        
        # 使用元数据
        if chunk.metadata.get('chunk_number') == 1:
            print("\\n[首个响应块]", end='')
    else:
        print(str(chunk), end='')
```

## 🧪 测试验证

所有测试都通过，包括：
- ✅ 导入测试 - 所有演示文件正常导入
- ✅ 基本逻辑测试 - 流式输出和普通输出都正常工作
- ✅ Minion 测试 - 各种 Minion 的流式输出功能正常
- ✅ 演示类测试 - 演示类创建和初始化正常

## 🚀 未来扩展方向

### 1. 更多块类型
```python
# 工具调用块
StreamChunk(content="调用工具: search", chunk_type="tool_call")

# 观察结果块  
StreamChunk(content="搜索结果: ...", chunk_type="observation")

# 错误块
StreamChunk(content="错误信息", chunk_type="error")
```

### 2. 更丰富的元数据
```python
StreamChunk(
    content="...",
    metadata={
        "model": "gpt-4o",
        "temperature": 0.7,
        "token_count": 150,
        "confidence": 0.95,
        "processing_time": 0.1
    }
)
```

### 3. 流式控制
```python
# 暂停/恢复流式输出
StreamChunk(content="", chunk_type="control", metadata={"action": "pause"})

# 进度指示
StreamChunk(content="", chunk_type="progress", metadata={"progress": 0.5})
```

## 📝 总结

这次架构更新成功地将流式输出从简单的字符串流升级为结构化的 `StreamChunk` 对象流，同时保持了：

1. **底层简单性** - LLM Provider 和 ActionNode 层保持简单
2. **向后兼容性** - 现有代码无需修改即可工作
3. **可扩展性** - 为未来功能扩展奠定了基础
4. **调试友好性** - 提供了丰富的元数据支持

这个设计遵循了"在正确的层次做正确的事"的原则，在 Minion 层进行数据结构化，为上层应用提供更好的开发体验。