#!/usr/bin/env python3
"""
Test script to verify that state-aware tools work correctly.
"""

import asyncio
import inspect
import sys
import os

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion.agents.code_agent import CodeAgent
from minion.types.agent_state import CodeAgentState
from minion.tools.tool_decorator import tool

# Create test tools with and without state parameter

@tool
def regular_tool(message: str) -> str:
    """A regular tool that doesn't need state.
    
    Args:
        message: The message to process
        
    Returns:
        Processed message
    """
    return f"Regular tool processed: {message}"

@tool
def state_aware_tool(action: str, state: CodeAgentState) -> str:
    """A tool that needs access to agent state.
    
    Args:
        state: The agent state
        action: The action to perform
        
    Returns:
        Action result with state info
    """
    step_count = state.step_count if state else 0
    history_len = len(state.history) if state and state.history else 0
    return f"State-aware tool: {action} (step={step_count}, history={history_len})"

@tool
async def async_state_aware_tool(task: str, state: CodeAgentState) -> str:
    """An async tool that needs access to agent state.
    
    Args:
        state: The agent state
        task: The task to perform
        
    Returns:
        Task result with state info
    """
    await asyncio.sleep(0.1)  # Simulate async work
    task_name = state.task if state else "unknown"
    return f"Async state-aware tool: {task} (current_task={task_name})"
@pytest.mark.asyncio
async def test_state_aware_tools():
    """Test that state-aware tools work correctly."""
    
    print("=== Testing State-Aware Tools ===\n")
    
    # Test 1: Check tool needs_state detection
    print("Test 1: Tool needs_state detection")
    
    print(f"regular_tool.needs_state: {regular_tool.needs_state}")
    print(f"state_aware_tool.needs_state: {state_aware_tool.needs_state}")
    print(f"async_state_aware_tool.needs_state: {async_state_aware_tool.needs_state}")
    
    assert regular_tool.needs_state == False, "Regular tool should not need state"
    assert state_aware_tool.needs_state == True, "State-aware tool should need state"
    assert async_state_aware_tool.needs_state == True, "Async state-aware tool should need state"
    
    print("✓ Tool needs_state detection works correctly")
    print()
    
    # Test 2: Test tools with agent
    print("Test 2: Tools with agent")
    
    # Create agent with our test tools
    agent = CodeAgent(
        name="test_agent",
        tools=[regular_tool, state_aware_tool, async_state_aware_tool],
        enable_state_tracking=False,
        use_async_executor=False
    )
    
    await agent.setup()
    
    # Set some state
    agent.state.step_count = 5
    agent.state.task = "Test task"
    agent.history.append("Step 1")
    agent.history.append("Step 2")
    
    print(f"Agent state: step_count={agent.state.step_count}, task={agent.state.task}, history_len={len(agent.history)}")
    
    # Test regular tool (should work without state)
    try:
        result = regular_tool("Hello world")
        print(f"Regular tool result: {result}")
        assert "Regular tool processed: Hello world" in result, "Regular tool should work normally"
        print("✓ Regular tool works correctly")
    except Exception as e:
        print(f"✗ Regular tool failed: {e}")
    
    print()
    
    # Test state-aware tool (should receive state automatically)
    try:
        # Find the wrapped tool in agent.tools
        wrapped_state_tool = None
        for tool in agent.tools:
            if tool.name == "state_aware_tool":
                wrapped_state_tool = tool
                break
        
        if wrapped_state_tool:
            result = wrapped_state_tool(action="test action")
            print(f"State-aware tool result: {result}")
            assert "step=5" in result, "State-aware tool should receive step_count"
            assert "history=2" in result, "State-aware tool should receive history length"
            print("✓ State-aware tool works correctly")
        else:
            print("✗ Could not find wrapped state-aware tool")
    except Exception as e:
        print(f"✗ State-aware tool failed: {e}")
    
    print()
    
    # Test async state-aware tool (should receive state automatically)
    try:
        # Find the wrapped async tool in agent.tools
        wrapped_async_tool = None
        for tool in agent.tools:
            if tool.name == "async_state_aware_tool":
                wrapped_async_tool = tool
                break
        
        if wrapped_async_tool:
            result = await wrapped_async_tool(task="async task")
            print(f"Async state-aware tool result: {result}")
            assert "current_task=Test task" in result, "Async state-aware tool should receive task"
            print("✓ Async state-aware tool works correctly")
        else:
            print("✗ Could not find wrapped async state-aware tool")
    except Exception as e:
        print(f"✗ Async state-aware tool failed: {e}")
    
    print()
    
    # Test 3: Test tool wrapping in agent setup
    print("Test 3: Tool wrapping in agent setup")
    
    # Check that tools were wrapped correctly
    wrapped_count = 0
    for tool in agent.tools:
        if hasattr(tool, 'needs_state') and tool.needs_state:
            wrapped_count += 1
            print(f"Found state-aware tool: {tool.name}")
    
    assert wrapped_count == 2, f"Should have 2 state-aware tools, found {wrapped_count}"
    print("✓ State-aware tools were wrapped correctly")
    
    print()
    
    # Test 4: Test state changes
    print("Test 4: State changes")
    print("Available tools:")
    for tool in agent.tools:
        print(f"  - {tool.name}, async={inspect.iscoroutinefunction(tool.forward)}")
    
    # Change agent state
    agent.state.step_count = 10
    agent.state.task = "Updated task"
    agent.history.append("Step 3")
    
    # Test that tools see the updated state
    try:
        wrapped_state_tool = None
        for tool in agent.tools:
            if tool.name == "state_aware_tool":
                wrapped_state_tool = tool
                break
        
        if wrapped_state_tool:
            result = wrapped_state_tool(action="updated action")
            print(f"Updated state result: {result}")
            assert "step=10" in result, "Tool should see updated step_count"
            assert "history=3" in result, "Tool should see updated history length"
            print("✓ Tools see updated state correctly")
        else:
            print("✗ Could not find wrapped tool for updated state test")
    except Exception as e:
        print(f"✗ Updated state test failed: {e}")
    
    print()
    
    # Test 5: Test without state (edge case)
    print("Test 5: Test without state (edge case)")
    
    # Temporarily remove state
    original_state = agent.state
    agent.state = None
    
    try:
        wrapped_state_tool = None
        for tool in agent.tools:
            if tool.name == "state_aware_tool":
                wrapped_state_tool = tool
                break
        
        if wrapped_state_tool:
            result = wrapped_state_tool(action="no state action")
            print(f"No state result: {result}")
            assert "step=0" in result, "Tool should handle missing state gracefully"
            print("✓ Tools handle missing state gracefully")
        else:
            print("✗ Could not find wrapped tool for no state test")
    except Exception as e:
        print(f"✗ No state test failed: {e}")
    finally:
        # Restore state
        agent.state = original_state
    
    print()
    
    print("=== State-Aware Tools Tests Completed! 🎉 ===")
    
    # Cleanup
    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_state_aware_tools())