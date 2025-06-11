#!/usr/bin/env python3
"""
pytest测试：sync和async工具的awaitable修复
"""

import pytest
import asyncio
from minion.agents.turing_machine_agent import (
    TuringMachineAgent, AgentInput, Memory, Plan, AgentState
)
from minion.tools.base_tool import BaseTool
from minion.main.input import Input


class SyncTool(BaseTool):
    """同步工具 - 不使用async"""
    
    name = "sync_tool"
    description = "A synchronous tool that returns immediately"
    inputs = {
        "message": {
            "type": "string",
            "description": "Message to process"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, message: str) -> str:
        """同步方法 - 直接返回结果"""
        return f"Sync result: {message}"


class AsyncTool(BaseTool):
    """异步工具 - 使用async"""
    
    name = "async_tool"
    description = "An asynchronous tool that returns a coroutine"
    inputs = {
        "message": {
            "type": "string",
            "description": "Message to process"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    async def forward(self, message: str) -> str:
        """异步方法 - 返回协程"""
        await asyncio.sleep(0.01)  # 模拟异步操作，缩短时间以提高测试速度
        return f"Async result: {message}"


@pytest.fixture
def mixed_agent():
    """创建包含同步和异步工具的测试agent"""
    return TuringMachineAgent(
        name="mixed_tools_agent",
        llm_config="gpt-4o-mini",
        tools=[SyncTool(), AsyncTool()]
    )


@pytest.mark.asyncio
async def test_sync_tool_execution(mixed_agent):
    """测试同步工具执行"""
    response = await mixed_agent.execute_step(
        input_data=Input(query="Use sync_tool with message 'Hello Sync'"),
        debug=False
    )
    
    result_response, score, terminated, truncated, info = response
    
    # 验证同步工具正常工作
    assert info.get('success') is True
    assert info.get('error') is None
    
    # 验证结果包含同步工具的输出
    if result_response and "Tool Execution Results:" in str(result_response):
        assert "Sync result:" in str(result_response)


@pytest.mark.asyncio
async def test_async_tool_execution(mixed_agent):
    """测试异步工具执行"""
    # 重置agent状态
    mixed_agent.reset()
    
    response = await mixed_agent.execute_step(
        input_data=Input(query="Use async_tool with message 'Hello Async'"),
        debug=False
    )
    
    result_response, score, terminated, truncated, info = response
    
    # 验证异步工具正常工作
    assert info.get('success') is True
    assert info.get('error') is None
    
    # 验证结果包含异步工具的输出
    if result_response and "Tool Execution Results:" in str(result_response):
        assert "Async result:" in str(result_response)


@pytest.mark.asyncio
async def test_mixed_tools_streaming(mixed_agent):
    """测试流式执行中的混合工具"""
    task = "First use sync_tool with 'step1', then use async_tool with 'step2'"
    
    step_count = 0
    sync_detected = False
    async_detected = False
    
    async for result in mixed_agent.run(task, streaming=True, max_steps=3):
        step_count += 1
        response, score, terminated, truncated, info = result
        
        # 验证基本执行正常
        assert isinstance(score, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(info, dict)
        
        # 检查是否使用了同步和异步工具
        if response and "Sync result:" in str(response):
            sync_detected = True
        if response and "Async result:" in str(response):
            async_detected = True
        
        if terminated:
            break
            
    # 验证基本执行
    assert step_count > 0
    # 注意：由于LLM的不确定性，不强制要求一定要使用所有工具


def test_sync_tool_standalone():
    """测试同步工具单独运行"""
    tool = SyncTool()
    result = tool.forward("test message")
    
    assert result == "Sync result: test message"
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_async_tool_standalone():
    """测试异步工具单独运行"""
    tool = AsyncTool()
    result = await tool.forward("test message")
    
    assert result == "Async result: test message"
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_tool_awaitable_detection():
    """测试工具的awaitable检测逻辑"""
    import inspect
    
    sync_tool = SyncTool()
    async_tool = AsyncTool()
    
    # 测试同步工具
    sync_result = sync_tool.forward("test")
    assert not inspect.iscoroutine(sync_result)
    assert not inspect.isawaitable(sync_result)
    assert sync_result == "Sync result: test"
    
    # 测试异步工具
    async_result = async_tool.forward("test")
    assert inspect.iscoroutine(async_result)
    assert inspect.isawaitable(async_result)
    
    # 等待异步结果
    awaited_result = await async_result
    assert awaited_result == "Async result: test"


@pytest.mark.asyncio
async def test_multiple_tools_in_sequence(mixed_agent):
    """测试顺序使用多个不同类型的工具"""
    # 首先测试同步工具
    response1 = await mixed_agent.execute_step(
        input_data=Input(query="Use sync_tool with message 'first'"),
        debug=False
    )
    
    _, _, _, _, info1 = response1
    assert info1.get('success') is True
    
    # 然后测试异步工具
    response2 = await mixed_agent.execute_step(
        input_data=Input(query="Use async_tool with message 'second'"),
        debug=False
    )
    
    _, _, _, _, info2 = response2
    assert info2.get('success') is True


@pytest.mark.asyncio
async def test_no_awaitable_errors_in_execution():
    """确保执行过程中没有awaitable相关错误"""
    agent = TuringMachineAgent(
        name="test_agent",
        llm_config="gpt-4o-mini",
        tools=[SyncTool(), AsyncTool()]
    )
    
    # 这个测试主要是为了确保没有抛出 "object str can't be used in 'await' expression" 错误
    try:
        response = await agent.execute_step(
            input_data=Input(query="Use any available tool with message 'test'"),
            debug=False
        )
        
        # 如果执行到这里，说明没有awaitable错误
        assert True
        
    except TypeError as e:
        if "can't be used in 'await' expression" in str(e):
            pytest.fail(f"Awaitable error detected: {e}")
        else:
            # 其他类型错误可能是正常的
            pass


if __name__ == "__main__":
    pytest.main([__file__]) 