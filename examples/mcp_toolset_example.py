#!/usr/bin/env python3
"""
示例：使用新的MCPToolSet API和agent生命周期管理

这个示例展示了如何：
1. 创建MCPToolSet并绑定到agent生命周期
2. 使用agent的setup()和close()方法管理MCP资源
3. 在agent运行期间使用MCP工具

参考Google ADK Python的ToolSet设计模式
"""

import asyncio
import logging
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import MCPToolSet, create_filesystem_toolset_factory
from minion.main.input import Input

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_manual_toolset_management():
    """示例1：手动管理MCPToolSet的生命周期"""
    logger.info("=== 示例1：手动管理MCPToolSet ===")
    
    # 创建agent
    agent = BaseAgent(name="filesystem_agent")
    
    # 创建MCPToolSet
    mcp_toolset = MCPToolSet("filesystem_tools")
    
    # 添加MCPToolSet到agent（必须在setup之前）
    agent.add_mcp_toolset(mcp_toolset)
    
    try:
        # 设置agent（这会初始化所有MCPToolSet）
        await agent.setup()
        
        # 添加filesystem工具到toolset
        await mcp_toolset.add_filesystem_tool(["/workspace"])
        
        # 现在可以使用agent了
        logger.info(f"Agent has {len(agent.tools)} tools available")
        
        # 创建一个简单的任务
        task = Input(query="List the files in the current directory")
        
        # 注意：这里只是演示工具的可用性，实际的brain.step调用需要完整的环境
        logger.info("Tools available:")
        for tool in agent.tools:
            logger.info(f"  - {tool.name}: {tool.description}")
            
    finally:
        # 重要：必须调用close来清理资源
        await agent.close()


async def example_context_manager():
    """示例2：使用async context manager自动管理生命周期"""
    logger.info("=== 示例2：使用context manager ===")
    
    # 使用async with自动管理生命周期
    async with BaseAgent(name="auto_managed_agent") as agent:
        # 创建并添加MCPToolSet
        mcp_toolset = MCPToolSet("auto_filesystem_tools")
        agent.add_mcp_toolset(mcp_toolset)
        
        # 需要手动调用setup，因为我们在context manager进入后添加了toolset
        await agent.setup()
        
        # 添加filesystem工具
        await mcp_toolset.add_filesystem_tool(["/workspace"])
        
        logger.info(f"Agent has {len(agent.tools)} tools available")
        
        # 在退出context manager时会自动调用close()


async def example_factory_pattern():
    """示例3：使用工厂模式创建预配置的toolset"""
    logger.info("=== 示例3：使用工厂模式 ===")
    
    # 创建filesystem toolset工厂
    filesystem_factory = create_filesystem_toolset_factory(["/workspace"])
    
    async with BaseAgent(name="factory_agent") as agent:
        # 使用工厂创建toolset
        filesystem_toolset = await filesystem_factory()
        agent.add_mcp_toolset(filesystem_toolset)
        
        # 需要手动调用setup
        await agent.setup()
        
        logger.info(f"Agent has {len(agent.tools)} tools available")
        for tool in agent.tools:
            logger.info(f"  - {tool.name}: {tool.description}")


async def example_multiple_toolsets():
    """示例4：使用多个MCPToolSet"""
    logger.info("=== 示例4：多个MCPToolSet ===")
    
    async with BaseAgent(name="multi_toolset_agent") as agent:
        # 添加文件系统toolset
        filesystem_toolset = MCPToolSet("filesystem")
        agent.add_mcp_toolset(filesystem_toolset)
        
        # 可以添加更多不同类型的toolset
        # custom_toolset = MCPToolSet("custom_tools")
        # agent.add_mcp_toolset(custom_toolset)
        
        await agent.setup()
        
        # 添加文件系统工具
        await filesystem_toolset.add_filesystem_tool(["/workspace"])
        
        # 如果有其他MCP服务器，也可以添加
        # await custom_toolset.add_mcp_server("sse", url="http://localhost:8080/sse")
        
        logger.info(f"Agent has {len(agent.tools)} tools from {len(agent.get_mcp_toolsets())} toolsets")
        
        # 获取所有toolset的信息
        for i, toolset in enumerate(agent.get_mcp_toolsets()):
            logger.info(f"  Toolset {i+1}: {getattr(toolset, 'name', 'unnamed')} with {len(toolset.get_tools())} tools")


async def example_error_handling():
    """示例5：错误处理和资源清理"""
    logger.info("=== 示例5：错误处理 ===")
    
    agent = BaseAgent(name="error_handling_agent")
    mcp_toolset = MCPToolSet("test_toolset")
    agent.add_mcp_toolset(mcp_toolset)
    
    try:
        await agent.setup()
        
        # 模拟在工具设置过程中出现错误
        try:
            # 这个可能会失败如果没有npx或者网络问题
            await mcp_toolset.add_filesystem_tool(["/workspace"])
            logger.info("Successfully added filesystem tool")
        except Exception as e:
            logger.error(f"Failed to add filesystem tool: {e}")
            
    except Exception as e:
        logger.error(f"Error during agent setup: {e}")
    finally:
        # 确保资源被清理
        await agent.close()


async def main():
    """运行所有示例"""
    logger.info("开始MCP ToolSet示例")
    
    try:
        await example_manual_toolset_management()
        await example_context_manager()
        await example_factory_pattern()
        await example_multiple_toolsets()
        await example_error_handling()
    except Exception as e:
        logger.error(f"示例运行出错: {e}")
    
    logger.info("所有示例完成")


if __name__ == "__main__":
    asyncio.run(main())