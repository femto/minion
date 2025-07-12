# MCP ToolSet重构说明

## 概述

根据要求，我们对MCP客户端的作用域进行了重构，使其绑定到agent的生命周期，并参考Google ADK Python的ToolSet设计模式。

## 主要变更

### 1. 新增MCPToolSet类 (`minion/tools/mcp/mcp_toolset.py`)

- 参考Google ADK Python的ToolSet设计
- 绑定到agent生命周期，而不是全局使用
- 支持async context manager模式
- 提供完整的生命周期管理（setup/close）

**主要特性：**
- `setup()`: 初始化MCPToolSet资源
- `close()`: 清理MCPToolSet资源  
- `add_mcp_server()`: 添加MCP服务器
- `get_tools()`: 获取工具列表
- `add_filesystem_tool()`: 添加文件系统工具

### 2. 修改BaseAgent类 (`minion/agents/base_agent.py`)

添加了生命周期管理功能：

- `setup()`: Agent初始化，设置所有MCPToolSet
- `close()`: Agent清理，关闭所有MCPToolSet
- `add_mcp_toolset()`: 添加MCPToolSet到agent
- `__aenter__/__aexit__`: 支持async context manager
- `_ensure_setup()`: 确保agent已初始化

**生命周期管理：**
- `_is_setup`: 跟踪agent是否已设置
- `_mcp_toolsets`: 存储绑定的MCPToolSet列表

### 3. 工厂函数

- `create_filesystem_toolset_factory()`: 创建文件系统工具集工厂

### 4. 向后兼容性

- 保留原有的`MCPBrainClient`类（标记为legacy）
- 更新`__init__.py`导出新的API

## 使用方式

### 手动生命周期管理

```python
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import MCPToolSet

# 创建agent和toolset
agent = BaseAgent(name="my_agent")
mcp_toolset = MCPToolSet("filesystem_tools")

# 添加toolset到agent（必须在setup之前）
agent.add_mcp_toolset(mcp_toolset)

try:
    # 设置agent（会自动设置所有MCPToolSet）
    await agent.setup()
    
    # 添加工具到toolset
    await mcp_toolset.add_filesystem_tool(["/workspace"])
    
    # 使用agent...
    result = await agent.run_async("List files")
    
finally:
    # 清理资源
    await agent.close()
```

### Context Manager模式（推荐）

```python
# 使用async context manager自动管理生命周期
async with BaseAgent(name="my_agent") as agent:
    # 创建并添加MCPToolSet
    mcp_toolset = MCPToolSet("filesystem_tools")
    agent.add_mcp_toolset(mcp_toolset)
    
    # 设置agent
    await agent.setup()
    
    # 添加工具
    await mcp_toolset.add_filesystem_tool(["/workspace"])
    
    # 使用agent...
    result = await agent.run_async("List files")
    
    # 退出时自动调用close()
```

### 工厂模式

```python
from minion.tools.mcp import create_filesystem_toolset_factory

# 创建预配置的toolset工厂
filesystem_factory = create_filesystem_toolset_factory(["/workspace"])

async with BaseAgent(name="my_agent") as agent:
    # 使用工厂创建toolset
    filesystem_toolset = await filesystem_factory()
    agent.add_mcp_toolset(filesystem_toolset)
    
    await agent.setup()
    # 文件系统工具已经预配置好了
```

## 与Google ADK的对比

### Google ADK Python ToolSet特性
- 生命周期管理
- 工具集合管理
- 类型安全
- 错误处理

### 我们的MCPToolSet实现
✅ **生命周期管理**: `setup()`/`close()`方法  
✅ **工具集合管理**: 统一管理多个MCP工具  
✅ **类型安全**: 使用TypedDict和类型提示  
✅ **错误处理**: 完整的异常处理和资源清理  
✅ **Context Manager**: 支持`async with`语法  
✅ **Agent绑定**: 绑定到agent生命周期而非全局  

## 优势

### 1. 生命周期绑定
- MCP客户端不再是全局的
- 与agent生命周期同步
- 自动资源清理

### 2. 更好的资源管理
- 明确的setup/close流程
- 防止资源泄漏
- 支持异常情况下的清理

### 3. 模块化设计
- 每个agent可以有自己的MCPToolSet
- 支持多个不同的ToolSet
- 便于测试和调试

### 4. 类型安全
- 完整的类型提示
- 编译时错误检查
- 更好的IDE支持

## 迁移指南

### 从旧的MCPBrainClient迁移

**旧方式：**
```python
async with MCPBrainClient() as mcp_client:
    await mcp_client.add_mcp_server("stdio", command="npx", args=[...])
    tools = mcp_client.get_tools_for_brain()
```

**新方式：**
```python
async with BaseAgent(name="my_agent") as agent:
    mcp_toolset = MCPToolSet("my_tools")
    agent.add_mcp_toolset(mcp_toolset)
    await agent.setup()
    
    await mcp_toolset.add_mcp_server("stdio", command="npx", args=[...])
    tools = agent.tools  # 工具自动添加到agent
```

## 测试

创建了完整的测试套件：
- `tests/test_mcp_toolset.py`: MCPToolSet和agent生命周期测试
- 包含单元测试、集成测试和错误处理测试
- 使用mock避免实际MCP依赖

## 示例

- `examples/mcp_toolset_example.py`: 完整的使用示例
- 展示多种使用模式
- 包含错误处理示例

## 向后兼容性

- 保留了原有的`MCPBrainClient`类
- 现有代码仍可正常工作
- 推荐新项目使用`MCPToolSet`

## 总结

这次重构成功实现了：

1. ✅ **MCP客户端作用域修改**: 不再是全局的，绑定到agent生命周期
2. ✅ **Agent生命周期管理**: 在setup时创建，close时清理
3. ✅ **ToolSet设计**: 参考Google ADK Python的ToolSet命名和模式
4. ✅ **类型安全和错误处理**: 完整的类型提示和异常处理
5. ✅ **向后兼容**: 保持现有API可用

新的设计更加健壮、类型安全，并且与现代异步Python开发的最佳实践保持一致。