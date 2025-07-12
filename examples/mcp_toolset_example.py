#!/usr/bin/env python3
"""
示例：使用简化的MCP API

这个示例展示了如何：
1. 使用简化的MCPToolset API
2. 直接在agent的tools参数中传递MCPToolset对象
3. 自动管理MCP资源的生命周期
4. 使用工厂函数创建常用工具集
"""

import asyncio
import logging
from pathlib import Path
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import (
    MCPToolset, 
    StdioServerParameters,
    SSEServerParameters,
    create_filesystem_toolset,
    create_brave_search_toolset
)
from minion.const import MINION_ROOT

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """示例1：基本使用方式"""
    logger.info("=== 示例1：基本使用方式 ===")
    
    # 创建agent时直接在tools参数中传递MCPToolset对象
    agent = BaseAgent(
        name="filesystem_agent",
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "str(MINION_ROOT)"]
                ),
                name="filesystem_tools"
            )
        ]
    )
    
    # 使用async context manager自动管理生命周期
    async with agent:
        logger.info(f"Agent has {len(agent.tools)} tools available")
        
        # 列出可用工具
        logger.info("Available tools:")
        for tool in agent.tools:
            logger.info(f"  - {tool.name}: {tool.description}")


async def example_factory_functions():
    """示例2：使用工厂函数"""
    logger.info("=== 示例2：使用工厂函数 ===")
    
    # 使用工厂函数创建常用的MCP toolset
    agent = BaseAgent(
        name="multi_tool_agent",
        tools=[
            create_filesystem_toolset(
                workspace_paths=[
                    str(MINION_ROOT),  # 项目根目录
                    str(MINION_ROOT / "docs1"),  # docs目录
                ]
            ),
            # create_brave_search_toolset("your_api_key"),  # 需要API key
        ]
    )
    
    async with agent:
        logger.info(f"Agent has {len(agent.tools)} tools available")
        for tool in agent.tools:
            logger.info(f"  - {tool.name}: {tool.description}")



async def example_sse_server():
    """示例4：连接到SSE MCP服务器"""
    logger.info("=== 示例4：连接到SSE MCP服务器 ===")
    
    # 连接到SSE MCP服务器
    sse_toolset = MCPToolset(
        connection_params=SSEServerParameters(
            url="http://localhost:8080/sse",
            headers={"Authorization": "Bearer your_token"},
            timeout=30.0
        ),
        name="sse_server"
    )
    
    agent = BaseAgent(
        name="sse_agent",
        tools=[sse_toolset]
    )
    
    try:
        async with agent:
            logger.info(f"Connected to SSE server with {len(agent.tools)} tools")
    except Exception as e:
        logger.error(f"Failed to connect to SSE server: {e}")
        logger.info("This is expected if the SSE server is not running")


async def example_multiple_toolsets():
    """示例5：使用多个工具集"""
    logger.info("=== 示例5：使用多个工具集 ===")
    
    # 创建多个工具集
    agent = BaseAgent(
        name="multi_toolset_agent",
        tools=[
            create_filesystem_toolset(
                workspace_paths=[
                    str(MINION_ROOT),  # 项目根目录
                    str(MINION_ROOT / "docs"),  # docs目录
                ]
            ),
            MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", str(MINION_ROOT / "tmp")]
                ),
                name="temp_filesystem"
            )
        ]
    )
    
    async with agent:
        logger.info(f"Agent has {len(agent.tools)} tools from multiple toolsets")
        
        # 分组显示工具
        tool_groups = {}
        for tool in agent.tools:
            # 根据工具名称前缀分组
            group = tool.name.split('_')[0] if '_' in tool.name else 'other'
            if group not in tool_groups:
                tool_groups[group] = []
            tool_groups[group].append(tool)
        
        for group, tools in tool_groups.items():
            logger.info(f"  {group.title()} tools ({len(tools)}):")
            for tool in tools:
                logger.info(f"    - {tool.name}: {tool.description}")


async def example_error_handling():
    """示例6：错误处理"""
    logger.info("=== 示例6：错误处理 ===")
    
    # 创建一个可能失败的工具集
    bad_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="nonexistent_command",
            args=["--invalid-arg"]
        ),
        name="bad_toolset"
    )
    
    agent = BaseAgent(
        name="error_handling_agent",
        tools=[bad_toolset]
    )
    
    try:
        async with agent:
            logger.info("This should not be reached")
    except Exception as e:
        logger.error(f"Expected error: {e}")
        logger.info("Error handling works correctly")


async def example_brave_search():
    """示例7：Brave搜索工具集（需要API key）"""
    logger.info("=== 示例7：Brave搜索工具集 ===")
    
    # 注意：这个示例需要真实的API key才能工作
    api_key = "your_brave_api_key_here"
    
    if api_key == "your_brave_api_key_here":
        logger.info("跳过Brave搜索示例，因为没有提供API key")
        return
    
    try:
        search_toolset = create_brave_search_toolset(api_key)
        
        agent = BaseAgent(
            name="search_agent",
            tools=[search_toolset]
        )
        
        async with agent:
            logger.info(f"Search agent has {len(agent.tools)} tools")
            for tool in agent.tools:
                logger.info(f"  - {tool.name}: {tool.description}")
                
    except Exception as e:
        logger.error(f"Failed to create Brave search toolset: {e}")


async def main():
    """运行所有示例"""
    logger.info("开始MCP简化API示例")
    
    try:
        await example_basic_usage()
        print("\n")
        await example_factory_functions()
        print("\n")
        #await example_sse_server()
        await example_multiple_toolsets()
        await example_error_handling()
        await example_brave_search()
        
        logger.info("所有示例完成")
        
    except Exception as e:
        logger.error(f"运行示例时出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())