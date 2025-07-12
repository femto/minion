#!/usr/bin/env python3
"""
简单的MCP API使用示例

展示如何使用新的简化MCP API：
1. 创建filesystem工具集
2. 在agent中使用
3. 自动生命周期管理
"""

import asyncio
import logging
import os
from pathlib import Path
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import (
    MCPToolset, 
    StdioServerParameters,
    create_filesystem_toolset
)
from minion.const import MINION_ROOT

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """主函数：展示简化的MCP API使用"""
    
    print("=== 简化MCP API使用示例 ===\n")
    
    # 方式1: 使用工厂函数创建filesystem工具集
    print("方式1: 使用工厂函数")
    filesystem_toolset = create_filesystem_toolset(
        workspace_paths=[
            str(MINION_ROOT),  # 项目根目录
            str(MINION_ROOT / "docs"),  # docs目录
        ],
        name="filesystem_tools"
    )
    
    # 方式2: 手动创建工具集
    print("方式2: 手动创建")
    custom_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", str(MINION_ROOT)]
        ),
        name="custom_filesystem"
    )
    
    # 创建agent时直接在tools参数中传递MCPToolset对象
    agent = BaseAgent(
        name="mcp_agent",
        tools=[filesystem_toolset]  # 直接传递工具集
    )
    
    # 使用async context manager自动管理生命周期
    async with agent:
        print(f"\n✓ Agent已启动，包含 {len(agent.tools)} 个工具")
        
        # 列出可用工具
        print("\n可用的MCP工具:")
        for i, tool in enumerate(agent.tools, 1):
            print(f"  {i}. {tool.name}: {tool.description}")
        
        print(f"\n✓ 工具集自动管理生命周期完成")

    print("\n=== 示例完成 ===")


if __name__ == "__main__":
    asyncio.run(main()) 