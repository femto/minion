#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
流式输出演示
展示如何使用统一的 stream=True 参数获得实时响应
"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion import config
from minion.main.brain import Brain
from minion.main.local_python_env import LocalPythonEnv
from minion.providers import create_llm_provider
from minion.agents.base_agent import BaseAgent

async def demo_brain_stream():
    """演示 Brain 的流式输出"""
    print("=== Brain 流式输出演示 ===")
    
    # 配置模型
    model = "gpt-4o-mini"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    
    # 创建 Brain
    brain = Brain(llm=llm)
    
    # 流式输出示例
    print("问题: 请详细解释什么是机器学习？")
    print("流式回答:")
    print("-" * 50)
    
    result = await brain.step(
        query="请详细解释什么是机器学习，包括其主要类型和应用场景？", 
        route="cot",  # 使用 Chain of Thought 获得更详细的回答
        stream=True   # 启用流式输出
    )
    
    print("-" * 50)
    print(f"最终答案: {result.answer}")

async def demo_agent_stream():
    """演示 Agent 的流式输出"""
    print("\n=== Agent 流式输出演示 ===")
    
    # 创建 Agent
    agent = BaseAgent(name="demo_agent")
    
    async with agent:  # 使用 context manager 自动 setup 和 cleanup
        print("问题: 解释深度学习的工作原理")
        print("Agent 流式回答:")
        print("-" * 50)
        
        # 使用 Agent 的流式功能 - 返回异步生成器
        stream_generator = await agent.run_async(
            task="请解释深度学习的工作原理，包括神经网络的基本概念",
            stream=True,  # 启用流式输出
            route="cot"   # 使用详细推理
        )
        
        # 处理流式结果
        final_result = None
        async for result in stream_generator:
            print(f"步骤: {str(result)[:100]}...")
            final_result = result
            if hasattr(result, 'terminated') and result.terminated:
                break
        
        print("-" * 50)
        print(f"Agent 最终结果: {final_result}")

async def demo_comparison():
    """对比普通模式和流式模式"""
    print("\n=== 普通模式 vs 流式模式对比 ===")
    
    model = "gpt-4o-mini"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    brain = Brain(llm=llm)
    
    query = "计算斐波那契数列的第10项，并解释计算过程"
    
    # 普通模式
    print("1. 普通模式 (stream=False):")
    print("等待完整响应...")
    result_normal = await brain.step(
        query=query,
        route="cot",
        stream=False
    )
    print(f"普通模式结果: {result_normal.answer}")
    
    print("\n2. 流式模式 (stream=True):")
    print("实时显示响应:")
    print("-" * 30)
    result_stream = await brain.step(
        query=query,
        route="cot", 
        stream=True
    )
    print("-" * 30)
    print(f"流式模式结果: {result_stream.answer}")

async def main():
    """主函数"""
    print("🚀 Minion 统一流式输出功能演示")
    print("=" * 60)
    
    try:
        # 演示 Brain 流式输出
        await demo_brain_stream()
        
        # 演示 Agent 流式输出
        await demo_agent_stream()
        
        # 对比演示
        await demo_comparison()
        
        print("\n✅ 演示完成！")
        print("\n💡 使用提示:")
        print("- 统一使用 stream=True 参数启用流式输出")
        print("- Brain.step() 直接返回结果")
        print("- Agent.run_async() 返回异步生成器，需要用 async for 处理")
        print("- 流式输出会实时显示 LLM 的响应过程")
        print("- 适用于需要实时反馈的交互式应用")
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())