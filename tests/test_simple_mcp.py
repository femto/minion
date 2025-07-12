#!/usr/bin/env python3
"""
简化的MCP API测试

测试新的简化MCP API是否正常工作
"""

import asyncio
import logging
import pytest
from minion.agents.base_agent import BaseAgent
from minion.tools.mcp import (
    MCPToolset,
    StdioServerParameters,
    create_filesystem_toolset,
    create_brave_search_toolset
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_basic_mcp_api():
    """测试基本的MCP API"""
    logger.info("测试基本MCP API...")
    
    # 创建filesystem工具集
    filesystem_toolset = create_filesystem_toolset(
        workspace_paths=["."],
        name="test_filesystem"
    )
    
    # 创建代理
    agent = BaseAgent(
        name="test_agent",
        tools=[filesystem_toolset]
    )
    
    # 测试代理创建
    assert agent.name == "test_agent"
    assert len(agent._mcp_toolsets) == 1
    assert agent._mcp_toolsets[0].name == "test_filesystem"
    
    logger.info("✓ 基本MCP API测试通过")


@pytest.mark.asyncio
async def test_toolset_creation():
    """测试工具集创建"""
    logger.info("测试工具集创建...")
    
    # 测试手动创建工具集
    toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command="test_command",
            args=["arg1", "arg2"]
        ),
        name="test_toolset"
    )
    
    # 验证工具集属性
    assert toolset.name == "test_toolset"
    assert toolset.connection_params.command == "test_command"
    assert toolset.connection_params.args == ["arg1", "arg2"]
    assert not toolset._is_setup
    
    logger.info("✓ 工具集创建测试通过")


@pytest.mark.asyncio
async def test_multiple_toolsets():
    """测试多个工具集"""
    logger.info("测试多个工具集...")
    
    # 创建两个工具集
    toolset1 = create_filesystem_toolset(
        workspace_paths=["."],
        name="fs1"
    )
    
    toolset2 = create_filesystem_toolset(
        workspace_paths=["."],
        name="fs2"
    )
    
    # 创建代理
    agent = BaseAgent(
        name="multi_toolset_test",
        tools=[toolset1, toolset2]
    )
    
    # 测试代理创建
    assert len(agent._mcp_toolsets) == 2
    assert agent._mcp_toolsets[0].name == "fs1"
    assert agent._mcp_toolsets[1].name == "fs2"
    
    logger.info("✓ 多工具集测试通过")


@pytest.mark.asyncio
async def test_api_simplicity():
    """测试API简洁性"""
    logger.info("测试API简洁性...")
    
    # 一行代码创建工具集
    toolset = create_filesystem_toolset()
    
    # 一行代码创建代理
    agent = BaseAgent(name="simple_agent", tools=[toolset])
    
    # 测试
    assert len(agent._mcp_toolsets) == 1
    assert agent._mcp_toolsets[0].name == "filesystem_toolset"
    
    logger.info("✓ API简洁性测试通过")


@pytest.mark.asyncio
async def test_parameter_handling():
    """测试参数处理"""
    logger.info("测试参数处理...")
    
    # 测试StdioServerParameters
    params = StdioServerParameters(
        command="test_cmd",
        args=["arg1", "arg2"],
        env={"KEY": "value"},
        cwd="/test/path"
    )
    
    assert params.command == "test_cmd"
    assert params.args == ["arg1", "arg2"]
    assert params.env == {"KEY": "value"}
    assert params.cwd == "/test/path"
    
    # 测试默认值
    params_default = StdioServerParameters(command="test")
    assert params_default.args == []
    assert params_default.env == {}
    assert params_default.cwd is None
    
    logger.info("✓ 参数处理测试通过")


@pytest.mark.asyncio
async def test_factory_functions():
    """测试工厂函数"""
    logger.info("测试工厂函数...")
    
    # 测试create_filesystem_toolset
    fs_toolset = create_filesystem_toolset(
        workspace_paths=["/path1", "/path2"],
        name="custom_fs"
    )
    
    assert fs_toolset.name == "custom_fs"
    assert fs_toolset.connection_params.command == "npx"
    assert "-y" in fs_toolset.connection_params.args
    assert "@modelcontextprotocol/server-filesystem" in fs_toolset.connection_params.args
    assert "/path1" in fs_toolset.connection_params.args
    assert "/path2" in fs_toolset.connection_params.args
    
    # 测试create_brave_search_toolset
    brave_toolset = create_brave_search_toolset(
        api_key="test_key",
        name="search_test"
    )
    
    assert brave_toolset.name == "search_test"
    assert brave_toolset.connection_params.env["BRAVE_API_KEY"] == "test_key"
    
    logger.info("✓ 工厂函数测试通过")


@pytest.mark.asyncio
async def test_agent_tool_separation():
    """测试代理和工具的分离"""
    logger.info("测试代理和工具的分离...")
    
    # 创建混合工具列表
    from minion.tools.default_tools import FinalAnswerTool
    
    regular_tool = FinalAnswerTool()
    mcp_toolset = create_filesystem_toolset(name="fs_test")
    
    # 创建代理
    agent = BaseAgent(
        name="mixed_agent",
        tools=[regular_tool, mcp_toolset]
    )
    
    # 验证分离
    assert len(agent.tools) == 1  # 只有常规工具
    assert len(agent._mcp_toolsets) == 1  # MCP工具集被分离
    assert agent.tools[0].name == "final_answer"
    assert agent._mcp_toolsets[0].name == "fs_test"
    
    logger.info("✓ 代理和工具分离测试通过")


async def main():
    """运行所有测试"""
    logger.info("开始简化MCP API测试")
    
    try:
        await test_basic_mcp_api()
        await test_toolset_creation()
        await test_multiple_toolsets()
        await test_api_simplicity()
        await test_parameter_handling()
        await test_factory_functions()
        await test_agent_tool_separation()
        
        logger.info("🎉 所有测试通过！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 