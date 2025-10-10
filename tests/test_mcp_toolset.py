#!/usr/bin/env python3
"""
Pytest tests for MCPToolset and agent lifecycle management
"""

import pytest
import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from minion.tools.mcp.mcp_toolset import MCPToolset, StdioServerParameters, SSEServerParameters, create_filesystem_toolset
from minion.agents.base_agent import BaseAgent


class TestMCPToolset:
    """Test MCPToolset class"""
    
    @pytest.fixture
    def toolset(self):
        """Create an MCPToolset instance for testing"""
        return MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."]
            ),
            name="test_toolset"
        )
    
    def test_toolset_initialization(self, toolset):
        """Test MCPToolset initialization"""
        assert toolset.name == "test_toolset"
        assert not toolset._is_setup
        assert toolset._tools == []
        assert toolset._exit_stack is None
        assert toolset._setup_error is None
    
    @pytest.mark.asyncio
    async def test_setup_and_close(self, toolset):
        """Test MCPToolset setup and close lifecycle"""
        # Initial state
        assert not toolset._is_setup
        
        # Setup
        with patch('mcp.ClientSession') as mock_session:
            mock_session.return_value = AsyncMock()
            await toolset.ensure_setup()
            assert toolset._is_setup
            assert toolset._exit_stack is not None
        
        # Setup again should not fail
        await toolset.ensure_setup()
        assert toolset._is_setup
        
        # Close
        await toolset.close()
        assert not toolset._is_setup
        assert toolset._exit_stack is None
        assert toolset._tools == []
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test MCPToolset as context manager"""
        with patch('mcp.ClientSession') as mock_session:
            mock_session.return_value = AsyncMock()
            toolset = MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "."]
                ),
                name="context_test"
            )
            await toolset.ensure_setup()
            assert toolset._is_setup
            assert isinstance(toolset, MCPToolset)
            await toolset.close()
            assert not toolset._is_setup


class TestMCPToolsetWithMocking:
    """Test MCPToolset with mocked MCP dependencies"""
    
    @pytest.mark.asyncio
    async def test_setup_missing_library(self):
        """Test behavior when MCP library is not available"""
        toolset = MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."]
            ),
            name="test"
        )
        with patch.dict('sys.modules', {'mcp': None}):
            with pytest.raises(RuntimeError, match="MCP library not available"):
                await toolset.ensure_setup()
    
    @pytest.mark.asyncio
    async def test_setup_unsupported_params(self):
        """Test setup with unsupported connection parameters"""
        class UnsupportedParams:
            pass
        
        toolset = MCPToolset(
            connection_params=UnsupportedParams(),
            name="test"
        )
        with pytest.raises(ValueError, match="Unsupported connection parameters type"):
            await toolset.ensure_setup()
    
    @pytest.mark.asyncio
    async def test_get_tools_after_setup(self):
        """Test get_tools method after setup"""
        toolset = MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."]
            ),
            name="test"
        )
        
        # Mock successful setup
        with patch('mcp.ClientSession') as mock_session:
            mock_session.return_value = AsyncMock()
            await toolset.ensure_setup()
            
            # Should not raise after setup
            tools = toolset.get_tools()
            assert isinstance(tools, list)


class TestBaseAgentLifecycle:
    """Test BaseAgent lifecycle management with MCPToolset"""
    
    @pytest.fixture
    def agent(self):
        """Create a BaseAgent instance for testing"""
        return BaseAgent(name="test_agent")
    
    def test_agent_initialization(self, agent):
        """Test BaseAgent initialization"""
        assert agent.name == "test_agent"
        assert not agent.is_setup
        assert len(agent._mcp_toolsets) == 0
        assert agent.brain is not None
    
    @pytest.mark.asyncio
    async def test_agent_setup_and_close(self, agent):
        """Test agent setup and close lifecycle"""
        # Initial state
        assert not agent.is_setup
        
        # Setup
        await agent.setup()
        assert agent.is_setup
        
        # Setup again should not fail
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
    
    def test_add_toolset_before_setup(self, agent):
        """Test adding MCP toolset before setup"""
        toolset = MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."]
            ),
            name="test_toolset"
        )
        agent.tools.append(toolset)
        agent._extract_mcp_toolsets_from_tools()
        
        assert len(agent._mcp_toolsets) == 1
        assert agent._mcp_toolsets[0] == toolset
    
    def test_add_toolset_after_setup(self, agent):
        """Test that adding MCP toolset after setup raises error"""
        async def test_async():
            await agent.setup()
            toolset = MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "."]
                ),
                name="test_toolset"
            )
            # Adding a toolset after setup should be allowed, but extracting it should fail
            agent.tools.append(toolset)
            with pytest.raises(RuntimeError, match="Cannot modify toolsets after setup"):
                agent._extract_mcp_toolsets_from_tools()
            await agent.close()
        
        # Run the async test
        asyncio.get_event_loop().run_until_complete(test_async())
    
    @pytest.mark.asyncio
    async def test_agent_with_mcp_toolset(self, agent):
        """Test agent lifecycle with MCP toolset"""
        # Add toolset before setup
        toolset = MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."]
            ),
            name="test_toolset"
        )
        agent.tools.append(toolset)
        agent._extract_mcp_toolsets_from_tools()
        
        # Setup agent (should setup toolset too)
        with patch('mcp.ClientSession') as mock_session:
            mock_session.return_value = AsyncMock()
            await agent.setup()
            
            # Toolset should be setup
            assert toolset._is_setup
            assert agent.is_setup
            
            # Close agent (should close toolset too)
            await agent.close()
            
            # Both should be cleaned up
            assert not toolset._is_setup
            assert not agent.is_setup


@pytest.mark.asyncio
async def test_integration_agent_with_multiple_toolsets():
    """Test agent with multiple toolsets"""
    agent = BaseAgent(
        name="multi_toolset_agent",
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "."]
                ),
                name="fs_toolset1"
            ),
            MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "tmp"]
                ),
                name="fs_toolset2"
            )
        ]
    )
    
    with patch('mcp.ClientSession') as mock_session:
        mock_session.return_value = AsyncMock()
        async with agent:
            assert len(agent._mcp_toolsets) == 2
            assert all(toolset._is_setup for toolset in agent._mcp_toolsets)
        
        assert all(not toolset._is_setup for toolset in agent._mcp_toolsets)


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])