# MCP (Model Context Protocol) 集成

## 概述

Minion现在支持通过简化的API集成MCP (Model Context Protocol) 工具。这使得你可以轻松地连接到各种MCP服务器并使用它们的工具。

## 快速开始

### 1. 安装依赖

```bash
pip install mcp
```

### 2. 基本使用

```python
import asyncio
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import create_filesystem_toolset

async def main():
    # 创建filesystem工具集
    filesystem_tools = create_filesystem_toolset(
        workspace_paths=[".", "docs"],
        name="fs_tools"
    )
    
    # 创建agent，直接传递工具集
    agent = BaseAgent(
        name="my_agent",
        tools=[filesystem_tools]
    )
    
    # 使用async context manager自动管理生命周期
    async with agent:
        # agent已自动设置好MCP工具
        print(f"Agent有 {len(agent.tools)} 个工具")

if __name__ == "__main__":
    asyncio.run(main())
```

## API参考

### 核心类

#### MCPToolset

Google ADK风格的简化工具集，推荐使用。

```python
from minion.tools.mcp import MCPToolset, StdioServerParameters

# 创建工具集
toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
    ),
    name="my_toolset"
)
```

### 工厂函数

#### create_filesystem_toolset()

创建文件系统访问工具集：

```python
from minion.tools.mcp import create_filesystem_toolset

toolset = create_filesystem_toolset(
    workspace_paths=[".", "docs", "/tmp"],
    name="filesystem"
)
```

#### create_brave_search_toolset()

创建Brave搜索工具集：

```python
from minion.tools.mcp import create_brave_search_toolset

toolset = create_brave_search_toolset(
    api_key="your_brave_api_key",
    name="search"
)
```

### 连接参数

#### StdioServerParameters

用于连接本地MCP服务器：

```python
StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem"],
    env={"API_KEY": "value"},
    cwd="/working/directory"
)
```

#### SSEServerParameters

用于连接SSE MCP服务器：

```python
SSEServerParameters(
    url="https://mcp-server.example.com/sse",
    headers={"Authorization": "Bearer token"},
    timeout=30.0
)
```

## 支持的MCP服务器

### 文件系统服务器

```bash
# 安装
npm install -g @modelcontextprotocol/server-filesystem

# 使用
create_filesystem_toolset(workspace_paths=["/workspace"])
```

### Brave搜索服务器

```bash
# 安装
npm install -g @modelcontextprotocol/server-brave-search

# 使用
create_brave_search_toolset(api_key="your_api_key")
```

## 生命周期管理

MCP工具集自动绑定到agent的生命周期：

- 当调用 `agent.setup()` 或进入 `async with agent` 时，所有MCP工具集自动初始化
- 当调用 `agent.close()` 或退出 `async with agent` 时，所有MCP资源自动清理

## 示例

查看 `simple_mcp_example.py` 获取完整的使用示例。

## 错误处理

```python
async with agent:
    try:
        # 使用MCP工具
        result = await agent.step("列出当前目录的文件")
    except Exception as e:
        print(f"MCP工具执行错误: {e}")
```

## 最佳实践

1. **使用工厂函数**: 优先使用 `create_filesystem_toolset()` 等工厂函数
2. **生命周期管理**: 总是使用 `async with agent` 进行自动资源管理
3. **错误处理**: 对MCP操作进行适当的错误处理
4. **路径限制**: 只授予必要的文件系统访问权限 