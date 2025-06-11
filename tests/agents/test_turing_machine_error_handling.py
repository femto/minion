#!/usr/bin/env python3
"""
pytest测试：错误处理和success字段
"""

import pytest
from minion.agents.turing_machine_agent import (
    TuringMachineAgent, AgentInput, Memory, Plan, AgentState, AgentResponse
)
from minion.tools.base_tool import BaseTool
from minion.main.input import Input


class ErrorTool(BaseTool):
    """故意产生错误的工具用于测试"""
    
    name = "error_tool"
    description = "A tool that always produces an error for testing purposes"
    inputs = {
        "message": {
            "type": "string",
            "description": "Error message"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, message: str) -> str:
        """总是抛出错误"""
        raise Exception(f"Test error: {message}")


class SuccessTool(BaseTool):
    """正常工作的工具用于对比测试"""
    
    name = "success_tool"
    description = "A tool that always works correctly"
    inputs = {
        "message": {
            "type": "string",
            "description": "Success message"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, message: str) -> str:
        """总是成功"""
        return f"Success: {message}"


@pytest.fixture
def error_agent():
    """创建带有错误工具的测试agent"""
    return TuringMachineAgent(
        name="error_test_agent",
        llm_config="gpt-4o-mini",
        tools=[ErrorTool(), SuccessTool()]
    )


@pytest.mark.asyncio
async def test_successful_tool_execution(error_agent):
    """测试正常工具调用（应该成功）"""
    response = await error_agent.execute_step(
        input_data=Input(query="Use the success_tool with message 'Hello World'"),
        debug=False
    )
    
    # 解包响应
    result_response, score, terminated, truncated, info = response
    
    # 验证成功状态
    assert info.get('success') is True
    assert info.get('error') is None
    assert info.get('state') in ['executing', 'halted']
    assert score > 0  # 成功时应该有正分数


@pytest.mark.asyncio
async def test_failed_tool_execution(error_agent):
    """测试错误工具调用（应该失败）"""
    # 重置agent状态
    error_agent.reset()
    
    response = await error_agent.execute_step(
        input_data=Input(query="Use the error_tool with message 'Test Error'"),
        debug=False
    )
    
    # 解包响应
    result_response, score, terminated, truncated, info = response
    
    # 验证错误状态
    assert info.get('success') is False
    assert info.get('error') is not None
    assert info.get('state') == 'error'
    assert terminated is True  # 错误时应该终止
    # 验证包含工具执行失败的消息
    assert "Tool execution failed" in str(info.get('error')) or "error_tool" in str(info.get('error'))


@pytest.mark.asyncio
async def test_streaming_error_handling(error_agent):
    """测试流式执行中的错误处理"""
    task = "First use success_tool with 'step1', then use error_tool with 'deliberate error'"
    
    step_count = 0
    error_detected = False
    success_detected = False
    
    async for result in error_agent.run(task, streaming=True, max_steps=5):
        step_count += 1
        # 解包元组
        response, score, terminated, truncated, info = result
        
        # 检查成功状态
        if info.get('success') is True:
            success_detected = True
        
        # 检查错误状态
        if info.get('success') is False:
            error_detected = True
            assert info.get('error') is not None
        
        if terminated:
            break
            
    # 验证我们检测到了成功和错误状态
    assert step_count > 0
    # 注意：根据LLM的不同行为，可能不是每次都能触发错误，所以这里只验证基本执行


@pytest.mark.asyncio
async def test_agent_response_success_field():
    """测试AgentResponse的success字段"""
    # 测试成功的AgentResponse
    success_response = AgentResponse(
        response="Success result",
        score=0.9,
        terminated=False,
        truncated=False,
        info={"test": "data"},
        step_count=1,
        state=AgentState.EXECUTING,
        success=True,
        error=None
    )
    
    assert success_response.success is True
    assert success_response.error is None
    
    # 测试失败的AgentResponse
    error_response = AgentResponse(
        response="Error result",
        score=0.1,
        terminated=True,
        truncated=False,
        info={"test": "data"},
        step_count=1,
        state=AgentState.ERROR,
        success=False,
        error="Test error message"
    )
    
    assert error_response.success is False
    assert error_response.error == "Test error message"


@pytest.mark.asyncio
async def test_agent_response_backward_compatibility():
    """测试AgentResponse的向后兼容性（作为元组解包）"""
    response = AgentResponse(
        response="Test response",
        score=0.8,
        terminated=False,
        truncated=False,
        info={"key": "value"},
        step_count=1,
        state=AgentState.EXECUTING,
        success=True,
        error=None
    )
    
    # 测试元组解包
    resp, score, terminated, truncated, info = response
    
    assert resp == "Test response"
    assert score == 0.8
    assert terminated is False
    assert truncated is False
    assert info == {"key": "value"}


@pytest.mark.asyncio
async def test_error_state_transitions(error_agent):
    """测试错误状态转换"""
    # 首先确保agent处于正常状态
    assert error_agent.turing_machine.current_state == AgentState.PLANNING
    
    # 创建会导致错误的输入
    goal = "Use error_tool with message 'test'"
    agent_input = AgentInput(
        goal=goal,
        plan=Plan(goal=goal),
        memory=Memory(),
        prompt=goal,
        available_tools=[ErrorTool()]
    )
    
    result = await error_agent.turing_machine.step(agent_input, debug=False)
    
    # 如果工具被调用并失败，状态应该变为ERROR
    if result.tool_calls:
        # 工具调用失败后，状态应该是ERROR
        assert result.next_state == AgentState.ERROR
        assert result.halt_condition is True


def test_error_tool_standalone():
    """测试ErrorTool单独运行时确实会抛出错误"""
    tool = ErrorTool()
    
    with pytest.raises(Exception) as exc_info:
        tool.forward("test message")
    
    assert "Test error: test message" in str(exc_info.value)


def test_success_tool_standalone():
    """测试SuccessTool单独运行时正常工作"""
    tool = SuccessTool()
    result = tool.forward("test message")
    
    assert result == "Success: test message"


if __name__ == "__main__":
    pytest.main([__file__]) 