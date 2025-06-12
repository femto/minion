#!/usr/bin/env python3
"""
Demo script showing MCP integration usage
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from minion.tools.mcp.mcp_integration import (
    MCPBrainClient,
    create_calculator_tool,
    create_final_answer_tool,
    add_filesystem_tool
)


@pytest.mark.asyncio
async def test_basic_mcp_workflow():
    """Test a basic workflow using MCP tools"""
    
    # Create tools
    calculator = create_calculator_tool()
    final_answer = create_final_answer_tool()
    
    # Test calculator
    calc_result = await calculator(expression="15 + 25")
    assert "40" in calc_result
    
    # Test final answer
    answer_result = await final_answer(answer="The calculation is complete")
    assert "calculation is complete" in answer_result.lower()


@pytest.mark.asyncio
async def test_mcp_client_with_local_tools():
    """Test MCP client with local tools"""
    
    async with MCPBrainClient() as client:
        # Initially empty
        assert len(client.get_tools_for_brain()) == 0
        
        # Add local tools manually
        calculator = create_calculator_tool()
        final_answer = create_final_answer_tool()
        
        # Test that tools have expected interface
        tools = [calculator, final_answer]
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'parameters')
            assert callable(tool.to_function_spec)


def test_tool_specification_format():
    """Test that tools produce correct specification format"""
    
    calculator = create_calculator_tool()
    spec = calculator.to_function_spec()
    
    # Check spec format
    assert spec["type"] == "function"
    assert "function" in spec
    assert "name" in spec["function"]
    assert "description" in spec["function"]
    assert "parameters" in spec["function"]
    
    # Check calculator-specific details
    assert spec["function"]["name"] == "calculator"
    assert "arithmetic" in spec["function"]["description"].lower()
    assert "expression" in spec["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in tools"""
    
    calculator = create_calculator_tool()
    
    # Test with invalid expression
    result = await calculator(expression="invalid + syntax!")
    assert "Error" in result or "error" in result.lower()
    
    # Test with potentially dangerous expression
    result = await calculator(expression="__import__('os').system('ls')")
    assert "Error" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_calculator_operations():
    """Test various calculator operations"""
    
    calculator = create_calculator_tool()
    
    test_cases = [
        ("2 + 3", "5"),
        ("10 - 4", "6"),
        ("6 * 7", "42"),
        ("15 / 3", "5"),
        ("2 ** 3", "8"),
        ("(10 + 5) * 2", "30"),
    ]
    
    for expression, expected in test_cases:
        result = await calculator(expression=expression)
        assert expected in result, f"Expected {expected} in result for {expression}, got {result}"


if __name__ == "__main__":
    # Run demonstration
    async def main():
        print("=== MCP Integration Demo ===")
        
        # Test basic calculator
        print("\n1. Testing Calculator Tool:")
        calculator = create_calculator_tool()
        result = await calculator(expression="123 + 456")
        print(f"   123 + 456 = {result}")
        
        # Test final answer tool
        print("\n2. Testing Final Answer Tool:")
        final_answer = create_final_answer_tool()
        result = await final_answer(answer="All tests passed successfully!")
        print(f"   Final Answer: {result}")
        
        # Test tool specifications
        print("\n3. Tool Specifications:")
        spec = calculator.to_function_spec()
        print(f"   Calculator spec: {spec['function']['name']} - {spec['function']['description']}")
        
        spec = final_answer.to_function_spec()
        print(f"   Final Answer spec: {spec['function']['name']} - {spec['function']['description']}")
        
        print("\n=== Demo Complete ===")
    
    # Only run if executed directly
    asyncio.run(main()) 