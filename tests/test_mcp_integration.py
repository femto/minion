#!/usr/bin/env python3
"""
Pytest tests for MCP integration module
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from minion.tools.mcp.mcp_integration import (
    MCPBrainClient,
    BrainTool,
    format_mcp_result,
    create_final_answer_tool,
    create_calculator_tool,
    MCPToolConfig
)


class TestFormatMCPResult:
    """Test format_mcp_result function"""
    
    def test_format_string_result(self):
        """Test formatting string result"""
        result = "Simple string result"
        formatted = format_mcp_result(result)
        assert formatted == "Simple string result"
    
    def test_format_dict_result(self):
        """Test formatting dict result"""
        result = {"key": "value", "number": 42}
        formatted = format_mcp_result(result)
        assert "key" in formatted and "value" in formatted
    
    def test_format_none_result(self):
        """Test formatting None result"""
        result = None
        formatted = format_mcp_result(result)
        assert formatted == "None"


class TestBrainTool:
    """Test BrainTool class"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock MCP session"""
        session = AsyncMock()
        session.call_tool = AsyncMock()
        return session
    
    @pytest.fixture
    def brain_tool(self, mock_session):
        """Create a BrainTool instance for testing"""
        return BrainTool(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Test input"}
                },
                "required": ["input"]
            },
            session=mock_session
        )
    
    def test_brain_tool_initialization(self, brain_tool):
        """Test BrainTool initialization"""
        assert brain_tool.name == "test_tool"
        assert brain_tool.description == "A test tool"
        assert brain_tool.__name__ == "test_tool"
        assert brain_tool.__doc__ == "A test tool"
        assert brain_tool.__input_schema__ is not None
    
    @pytest.mark.asyncio
    async def test_brain_tool_call_success(self, brain_tool, mock_session):
        """Test successful BrainTool call"""
        mock_session.call_tool.return_value = "Success result"
        
        result = await brain_tool.forward(input="test input")
        
        assert result == "Success result"
        mock_session.call_tool.assert_called_once_with("test_tool", {"input": "test input"})
    
    @pytest.mark.asyncio
    async def test_brain_tool_call_error(self, brain_tool, mock_session):
        """Test BrainTool call with error"""
        mock_session.call_tool.side_effect = Exception("Test error")
        
        result = await brain_tool.forward(input="test input")
        
        assert "Error: Test error" in result
    
    def test_to_function_spec(self, brain_tool):
        """Test to_function_spec method"""
        spec = brain_tool.to_function_spec()
        
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "test_tool"
        assert spec["function"]["description"] == "A test tool"
        assert "parameters" in spec["function"]
    
    def test_to_dict(self, brain_tool):
        """Test to_dict method"""
        result = brain_tool.to_dict()
        
        assert result["name"] == "test_tool"
        assert result["description"] == "A test tool"
        assert "parameters" in result


class TestMCPBrainClient:
    """Test MCPBrainClient class"""
    
    @pytest.fixture
    def mcp_client(self):
        """Create an MCPBrainClient instance for testing"""
        return MCPBrainClient()
    
    def test_mcp_client_initialization(self, mcp_client):
        """Test MCPBrainClient initialization"""
        assert mcp_client.sessions == {}
        assert mcp_client.available_tools == []
        assert mcp_client.exit_stack is not None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test MCPBrainClient as context manager"""
        async with MCPBrainClient() as client:
            assert isinstance(client, MCPBrainClient)
    
    def test_get_tools_for_brain(self, mcp_client):
        """Test get_tools_for_brain method"""
        tools = mcp_client.get_tools_for_brain()
        assert isinstance(tools, list)
        assert len(tools) == 0  # Initially empty
    
    def test_get_tool_functions(self, mcp_client):
        """Test get_tool_functions method"""
        functions = mcp_client.get_tool_functions()
        assert isinstance(functions, dict)
        assert len(functions) == 0  # Initially empty
    
    def test_get_tool_specs(self, mcp_client):
        """Test get_tool_specs method"""
        specs = mcp_client.get_tool_specs()
        assert isinstance(specs, list)
        assert len(specs) == 0  # Initially empty
    
    def test_get_tools_dict(self, mcp_client):
        """Test get_tools_dict method"""
        tools_dict = mcp_client.get_tools_dict()
        assert isinstance(tools_dict, list)
        assert len(tools_dict) == 0  # Initially empty


class TestCreateFinalAnswerTool:
    """Test create_final_answer_tool function"""
    
    @pytest.mark.asyncio
    async def test_create_final_answer_tool(self):
        """Test final answer tool creation and execution"""
        tool = create_final_answer_tool()
        
        assert tool.name == "final_answer"
        assert "final answer" in tool.description.lower()
        assert "answer" in tool.parameters["properties"]
        
        # Test tool execution
        result = await tool(answer="This is the final answer")
        assert "This is the final answer" in result


class TestCreateCalculatorTool:
    """Test create_calculator_tool function"""
    
    @pytest.mark.asyncio
    async def test_create_calculator_tool(self):
        """Test calculator tool creation and basic operations"""
        tool = create_calculator_tool()
        
        assert tool.name == "calculator"
        assert "arithmetic" in tool.description.lower()
        assert "expression" in tool.parameters["properties"]
    
    @pytest.mark.asyncio
    async def test_calculator_addition(self):
        """Test calculator addition"""
        tool = create_calculator_tool()
        result = await tool(expression="2 + 3")
        assert "5" in result
    
    @pytest.mark.asyncio
    async def test_calculator_multiplication(self):
        """Test calculator multiplication"""
        tool = create_calculator_tool()
        result = await tool(expression="4 * 5")
        assert "20" in result
    
    @pytest.mark.asyncio
    async def test_calculator_complex_expression(self):
        """Test calculator with complex expression"""
        tool = create_calculator_tool()
        result = await tool(expression="(10 + 5) * 2")
        assert "30" in result
    
    @pytest.mark.asyncio
    async def test_calculator_invalid_expression(self):
        """Test calculator with invalid expression"""
        tool = create_calculator_tool()
        result = await tool(expression="invalid_expression")
        assert "Error" in result
    
    @pytest.mark.asyncio
    async def test_calculator_dangerous_expression(self):
        """Test calculator with potentially dangerous expression"""
        tool = create_calculator_tool()
        result = await tool(expression="import os; os.system('ls')")
        assert "Error" in result


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
async def test_integration_tools_compatibility():
    """Test that created tools are compatible with each other"""
    final_answer_tool = create_final_answer_tool()
    calculator_tool = create_calculator_tool()
    
    # Test that both tools have required attributes
    for tool in [final_answer_tool, calculator_tool]:
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')
        assert hasattr(tool, 'parameters')
        assert hasattr(tool, '__call__')
        assert callable(tool.to_function_spec)
        assert callable(tool.to_dict)
    
    # Test that tools can be called
    calc_result = await calculator_tool(expression="2 + 3")
    final_result = await final_answer_tool(answer="Calculation completed")
    
    assert "5" in calc_result
    assert "Calculation completed" in final_result


class TestMCPServerAddition:
    """Test adding MCP servers (mocked)"""
    
    @pytest.mark.asyncio
    async def test_add_mcp_server_unsupported_type(self):
        """Test adding unsupported server type"""
        async with MCPBrainClient() as client:
            with pytest.raises(ValueError, match="Unsupported server type"):
                await client.add_mcp_server("unsupported_type", url="test://url")


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])