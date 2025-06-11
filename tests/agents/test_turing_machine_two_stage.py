#!/usr/bin/env python3
"""
pytest测试：两阶段架构
阶段1：生成纯粹的 next_instruction (描述要做什么)
阶段2：LLM判断是否需要工具调用，生成具体的工具调用
阶段3：执行工具调用
"""

import pytest
import asyncio
from minion.agents.turing_machine_agent import (
    TuringMachineAgent, AgentInput, Memory, Plan, AgentState
)
from minion.tools.base_tool import BaseTool


class MockCalculatorTool(BaseTool):
    """Mock计算器工具"""
    
    name = "calculator"
    description = "Perform mathematical calculations"
    inputs = {
        "expression": {
            "type": "string",
            "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, expression: str) -> str:
        """Execute calculation"""
        try:
            # 安全的数学计算
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return f"Error: Invalid characters in expression '{expression}'"
            
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Calculation error: {str(e)}"


class MockSearchTool(BaseTool):
    """Mock搜索工具"""
    
    name = "web_search"
    description = "Search the web for information"
    inputs = {
        "query": {
            "type": "string", 
            "description": "Search query string"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, query: str) -> str:
        """Execute web search (mocked)"""
        # Mock搜索结果
        mock_results = {
            "python tutorial": "Found comprehensive Python tutorials on python.org and w3schools",
            "weather": "Current weather: 22°C, partly cloudy",
            "restaurants": "Top restaurants: 1) Italian Bistro 2) Sushi House 3) Local Cafe",
            "default": f"Mock search results for: {query}"
        }
        
        for key in mock_results:
            if key.lower() in query.lower():
                return mock_results[key]
        
        return mock_results["default"]


@pytest.fixture
def agent():
    """创建测试用的agent"""
    return TuringMachineAgent(
        name="test_agent",
        llm_config="gpt-4o-mini",
        tools=[MockCalculatorTool(), MockSearchTool()]
    )


@pytest.mark.asyncio
async def test_math_calculation_with_tools(agent):
    """测试数学计算（需要工具调用）"""
    goal = "Calculate the result of 15 * 8 + 27"
    memory = Memory()
    plan = Plan(goal=goal)
    
    agent_input = AgentInput(
        goal=goal,
        plan=plan,
        memory=memory,
        prompt=goal,
        available_tools=[MockCalculatorTool(), MockSearchTool()]
    )
    
    result = await agent.turing_machine.step(agent_input, debug=False)
    
    # 验证结果
    assert result.next_instruction is not None
    assert "calculate" in result.next_instruction.lower() or "15" in result.next_instruction
    
    # 如果有工具调用，验证包含计算器
    if result.tool_calls:
        tool_names = [call.get('tool_name') for call in result.tool_calls]
        assert 'calculator' in tool_names


@pytest.mark.asyncio
async def test_text_analysis_without_tools(agent):
    """测试纯文本分析（不需要工具调用）"""
    goal = "Explain the concept of object-oriented programming"
    agent_input = AgentInput(
        goal=goal,
        plan=Plan(goal=goal),
        memory=Memory(),
        prompt=goal,
        available_tools=[MockCalculatorTool(), MockSearchTool()]
    )
    
    result = await agent.turing_machine.step(agent_input, debug=False)
    
    # 验证结果
    assert result.next_instruction is not None
    # 对于文本解释任务，通常不需要工具调用或者会直接提供解释
    assert result.current_result is not None or len(result.tool_calls) == 0


@pytest.mark.asyncio
async def test_search_task_with_tools(agent):
    """测试信息搜索（需要工具调用）"""
    goal = "Find information about Python programming tutorials"
    agent_input = AgentInput(
        goal=goal,
        plan=Plan(goal=goal),
        memory=Memory(),
        prompt=goal,
        available_tools=[MockCalculatorTool(), MockSearchTool()]
    )
    
    result = await agent.turing_machine.step(agent_input, debug=False)
    
    # 验证结果
    assert result.next_instruction is not None
    assert "search" in result.next_instruction.lower() or "python" in result.next_instruction.lower()
    
    # 如果有工具调用，验证包含搜索工具
    if result.tool_calls:
        tool_names = [call.get('tool_name') for call in result.tool_calls]
        assert 'web_search' in tool_names


@pytest.mark.asyncio
async def test_streaming_execution(agent):
    """测试流式执行"""
    task = "Calculate 23 * 45 and then search for information about the result"
    
    step_count = 0
    results = []
    
    async for response in agent.run(task, streaming=True, max_steps=3):
        step_count += 1
        results.append(response)
        
        # 解包响应
        result_response, score, terminated, truncated, info = response
        
        # 验证基本字段
        assert isinstance(score, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)
        
        if terminated:
            break
    
    # 验证至少执行了一步
    assert step_count > 0
    # 验证最后一步是终止的
    if results:
        _, _, terminated, _, _ = results[-1]
        assert terminated or step_count >= 3  # 要么正常终止，要么达到最大步数


@pytest.mark.asyncio  
async def test_agent_state_transitions(agent):
    """测试Agent状态转换"""
    goal = "Simple test task"
    agent_input = AgentInput(
        goal=goal,
        plan=Plan(goal=goal),
        memory=Memory(),
        prompt=goal,
        available_tools=[]
    )
    
    # 初始状态应该是PLANNING
    assert agent.turing_machine.current_state == AgentState.PLANNING
    
    result = await agent.turing_machine.step(agent_input, debug=False)
    
    # 验证状态转换
    assert result.next_state in [AgentState.EXECUTING, AgentState.HALTED, AgentState.REFLECTING]


@pytest.mark.asyncio
async def test_tool_execution_results(agent):
    """测试工具执行结果格式"""
    goal = "Calculate 5 + 3"
    
    response = await agent.execute_step(
        input_data=type('Input', (), {'query': goal})(),
        debug=False
    )
    
    # 解包响应
    result_response, score, terminated, truncated, info = response
    
    # 验证返回格式
    assert 0 <= score <= 1  # 分数应该在0-1之间
    assert 'state' in info
    assert 'success' in info
    assert info['success'] is True or info['success'] is False
    
    # 如果有工具执行结果，验证格式
    if result_response and "Tool Execution Results:" in str(result_response):
        assert "executed successfully" in str(result_response) or "Error executing" in str(result_response)


if __name__ == "__main__":
    pytest.main([__file__]) 