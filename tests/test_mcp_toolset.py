#!/usr/bin/env python3
"""
Pytest tests for MCPToolSet and agent lifecycle management
"""

import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from minion.tools.mcp.mcp_toolset import MCPToolSet, MCPToolConfig, create_filesystem_toolset_factory
from minion.agents.base_agent import BaseAgent


class TestMCPToolSet:
    """Test MCPToolSet class"""
    
    @pytest.fixture
    def toolset(self):
        """Create an MCPToolSet instance for testing"""
        return MCPToolSet("test_toolset")
    
    def test_toolset_initialization(self, toolset):
        """Test MCPToolSet initialization"""
        assert toolset.name == "test_toolset"
        assert toolset.sessions == {}
        assert toolset.available_tools == []
        assert not toolset.is_initialized
        assert toolset.exit_stack is None
    
    @pytest.mark.asyncio
    async def test_setup_and_close(self, toolset):
        """Test MCPToolSet setup and close lifecycle"""
        # Initial state
        assert not toolset.is_initialized
        
        # Setup
        await toolset.setup()
        assert toolset.is_initialized
        assert toolset.exit_stack is not None
        
        # Setup again should warn but not fail
        await toolset.setup()
        assert toolset.is_initialized
        
        # Close
        await toolset.close()
        assert not toolset.is_initialized
        assert toolset.exit_stack is None
        assert toolset.sessions == {}
        assert toolset.available_tools == []
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test MCPToolSet as context manager"""
        async with MCPToolSet("context_test") as toolset:
            assert toolset.is_initialized
            assert isinstance(toolset, MCPToolSet)
        # After exiting context, should be cleaned up
        assert not toolset.is_initialized
    
    def test_ensure_initialized_check(self, toolset):
        """Test that methods check for initialization"""
        with pytest.raises(RuntimeError, match="not initialized"):
            toolset.get_tools()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            toolset.get_tool_functions()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            toolset.get_tool_specs()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            toolset.get_tools_dict()
    
    @pytest.mark.asyncio
    async def test_add_mcp_server_not_initialized(self, toolset):
        """Test adding MCP server when not initialized"""
        with pytest.raises(RuntimeError, match="not initialized"):
            await toolset.add_mcp_server("stdio", command="test")
    
    @pytest.mark.asyncio 
    async def test_add_filesystem_tool_not_initialized(self, toolset):
        """Test adding filesystem tool when not initialized"""
        with pytest.raises(RuntimeError, match="not initialized"):
            await toolset.add_filesystem_tool(["/test"])


class TestMCPToolSetWithMocking:
    """Test MCPToolSet with mocked MCP dependencies"""
    
    @pytest.mark.asyncio
    async def test_add_mcp_server_missing_library(self):
        """Test behavior when MCP library is not available"""
        async with MCPToolSet("test") as toolset:
            with patch('minion.tools.mcp.mcp_toolset.ClientSession', side_effect=ImportError("MCP not available")):
                with pytest.raises(RuntimeError, match="MCP library not available"):
                    await toolset.add_mcp_server("stdio", command="test")
    
    @pytest.mark.asyncio
    async def test_add_mcp_server_unsupported_type(self):
        """Test adding unsupported server type"""
        async with MCPToolSet("test") as toolset:
            with pytest.raises(ValueError, match="Unsupported server type"):
                await toolset.add_mcp_server("unsupported_type", url="test://url")  # type: ignore
    
    @pytest.mark.asyncio
    async def test_get_methods_after_setup(self):
        """Test get methods after setup"""
        async with MCPToolSet("test") as toolset:
            # Should not raise after setup
            tools = toolset.get_tools()
            assert isinstance(tools, list)
            assert len(tools) == 0
            
            functions = toolset.get_tool_functions()
            assert isinstance(functions, dict)
            assert len(functions) == 0
            
            specs = toolset.get_tool_specs()
            assert isinstance(specs, list)
            assert len(specs) == 0
            
            tools_dict = toolset.get_tools_dict()
            assert isinstance(tools_dict, list)
            assert len(tools_dict) == 0


class TestBaseAgentLifecycle:
    """Test BaseAgent lifecycle management with MCPToolSet"""
    
    @pytest.fixture
    def agent(self):
        """Create a BaseAgent instance for testing"""
        return BaseAgent(name="test_agent")
    
    def test_agent_initialization(self, agent):
        """Test BaseAgent initialization"""
        assert agent.name == "test_agent"
        assert not agent.is_setup
        assert len(agent.get_mcp_toolsets()) == 0
        assert agent.brain is not None
    
    @pytest.mark.asyncio
    async def test_agent_setup_and_close(self, agent):
        """Test agent setup and close lifecycle"""
        # Initial state
        assert not agent.is_setup
        
        # Setup
        await agent.setup()
        assert agent.is_setup
        
        # Setup again should warn but not fail
        await agent.setup()
        assert agent.is_setup
        
        # Close
        await agent.close()
        assert not agent.is_setup
    
    @pytest.mark.asyncio
    async def test_agent_context_manager(self):
        """Test agent as context manager"""
        async with BaseAgent(name="context_test") as agent:
            assert agent.is_setup
            assert isinstance(agent, BaseAgent)
        # After exiting context, should be cleaned up
        assert not agent.is_setup
    
    def test_add_mcp_toolset_before_setup(self, agent):
        """Test adding MCP toolset before setup"""
        toolset = MCPToolSet("test_toolset")
        agent.add_mcp_toolset(toolset)
        
        assert len(agent.get_mcp_toolsets()) == 1
        assert agent.get_mcp_toolsets()[0] == toolset
    
    def test_add_mcp_toolset_after_setup(self, agent):
        """Test that adding MCP toolset after setup raises error"""
        async def test_async():
            await agent.setup()
            toolset = MCPToolSet("test_toolset")
            with pytest.raises(RuntimeError, match="Cannot add MCP toolset.*after setup"):
                agent.add_mcp_toolset(toolset)
            await agent.close()
        
        # Run the async test
        asyncio.get_event_loop().run_until_complete(test_async())
    
    @pytest.mark.asyncio
    async def test_agent_with_mcp_toolset(self, agent):
        """Test agent lifecycle with MCP toolset"""
        # Add toolset before setup
        toolset = MCPToolSet("test_toolset")
        agent.add_mcp_toolset(toolset)
        
        # Setup agent (should setup toolset too)
        await agent.setup()
        
        # Toolset should be initialized
        assert toolset.is_initialized
        assert agent.is_setup
        
        # Close agent (should close toolset too)
        await agent.close()
        
        # Both should be cleaned up
        assert not toolset.is_initialized
        assert not agent.is_setup
    
    def test_ensure_setup_check(self, agent):
        """Test that run_async checks for setup"""
        async def test_async():
            with pytest.raises(RuntimeError, match="not setup"):
                await agent.run_async("test task")
        
        asyncio.get_event_loop().run_until_complete(test_async())
    
    def test_is_mcp_tool(self, agent):
        """Test _is_mcp_tool method"""
        # Mock a BrainTool
        mock_brain_tool = MagicMock()
        mock_brain_tool.__class__.__name__ = 'BrainTool'
        
        # Mock a regular tool
        mock_regular_tool = MagicMock()
        mock_regular_tool.__class__.__name__ = 'RegularTool'
        
        assert agent._is_mcp_tool(mock_brain_tool)
        assert not agent._is_mcp_tool(mock_regular_tool)


class TestFactoryFunctions:
    """Test factory functions"""
    
    def test_create_filesystem_toolset_factory(self):
        """Test filesystem toolset factory creation"""
        factory = create_filesystem_toolset_factory(["/test/path"])
        assert callable(factory)
    
    @pytest.mark.asyncio
    async def test_filesystem_toolset_factory_execution(self):
        """Test executing filesystem toolset factory"""
        factory = create_filesystem_toolset_factory(["/test/path"])
        
        # Mock the filesystem tool addition to avoid actual MCP calls
        with patch.object(MCPToolSet, 'add_filesystem_tool', new_callable=AsyncMock) as mock_add:
            toolset = await factory()
            assert isinstance(toolset, MCPToolSet)
            assert toolset.name == "filesystem_toolset"
            assert toolset.is_initialized
            mock_add.assert_called_once_with(["/test/path"])
            
            # Clean up
            await toolset.close()


class TestMCPToolConfig:
    """Test MCPToolConfig class"""
    
    def test_filesystem_default_config(self):
        """Test filesystem default configuration"""
        config = MCPToolConfig.FILESYSTEM_DEFAULT
        
        assert config["type"] == "stdio"
        assert config["command"] == "npx"
        assert "-y" in config["args"]
        assert "@modelcontextprotocol/server-filesystem" in config["args"]
    
    @patch('os.path.abspath')
    def test_get_filesystem_config_default(self, mock_abspath):
        """Test get_filesystem_config with default path"""
        mock_abspath.return_value = "/test/path"
        
        config = MCPToolConfig.get_filesystem_config()
        
        assert config["type"] == "stdio"
        assert config["command"] == "npx"
        assert config["workspace_paths"] == ["/test/path"]
        assert "/test/path" in config["args"]
    
    def test_get_filesystem_config_custom_paths(self):
        """Test get_filesystem_config with custom paths"""
        custom_paths = ["/custom/path1", "/custom/path2"]
        
        config = MCPToolConfig.get_filesystem_config(custom_paths)
        
        assert config["workspace_paths"] == custom_paths
        assert "/custom/path1" in config["args"]
        assert "/custom/path2" in config["args"]


@pytest.mark.asyncio
async def test_integration_agent_with_multiple_toolsets():
    """Integration test: agent with multiple MCP toolsets"""
    async with BaseAgent(name="integration_test") as agent:
        # Add multiple toolsets
        toolset1 = MCPToolSet("toolset1")
        toolset2 = MCPToolSet("toolset2")
        
        agent.add_mcp_toolset(toolset1)
        agent.add_mcp_toolset(toolset2)
        
        # Setup should initialize all toolsets
        await agent.setup()
        
        assert len(agent.get_mcp_toolsets()) == 2
        assert toolset1.is_initialized
        assert toolset2.is_initialized
        
        # Tools should be combined
        assert len(agent.tools) == len(toolset1.get_tools()) + len(toolset2.get_tools())
    
    # After context exit, all should be cleaned up
    assert not agent.is_setup
    assert not toolset1.is_initialized
    assert not toolset2.is_initialized


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])