#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple Brain Tools Demo - brain.step使用tools的简单演示
"""
import asyncio
from minion import config
from minion.main.brain import Brain
from minion.main.python_env import PythonEnv
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.providers import create_llm_provider
from minion.tools.base_tool import BaseTool
from minion.tools.default_tools import FinalAnswerTool


class SimpleTool(BaseTool):
    """简单的示例工具"""
    
    name = "simple_calculator"
    description = "执行简单的数学计算"
    inputs = {
        "expression": {
            "type": "string",
            "description": "数学表达式"
        }
    }
    output_type = "number"
    
    def forward(self, expression: str):
        """执行计算"""
        try:
            result = eval(expression)
            return f"计算结果: {result}"
        except:
            return "计算出错"


async def demo():
    """快速演示"""
    
    # 初始化Brain
    llm = create_llm_provider(config.models.get("gpt-4o-mini"))
    python_env_config = {"port": 3007}
    python_env = RpycPythonEnv(port=python_env_config.get("port", 3007))
    brain = Brain(python_env=python_env, llm=llm)
    
    # 创建工具
    tool = SimpleTool()
    final_answer_tool = FinalAnswerTool()
    
    print("=== brain.step使用tools演示 ===")
    
    # 方法1: 在step中传入tools参数
    print("\n1. 在step方法中传入tools:")
    response, *_ = await brain.step(
        query="请计算 2 + 3 * 4 的结果",
        tools=[tool,final_answer_tool],  # 在这里传入工具
        route="plan",
        check=False
    )
    print(f"回答: {response}")
    
    # 方法2: 初始化时添加工具
    print("\n2. 初始化时添加工具:")
    brain_with_tools = Brain(
        python_env=python_env,
        llm=llm,
        tools=[tool,final_answer_tool]  # 初始化时传入工具
    )
    
    response, *_ = await brain_with_tools.step(
        query="请计算 10 * 5 + 20 的结果",
        check=False,
    route = "native",
    )
    print(f"回答: {response}")
    
    # 方法3: 使用add_tool动态添加
    print("\n3. 使用add_tool动态添加:")
    brain_dynamic = Brain(python_env=python_env, llm=llm)
    brain_dynamic.add_tool(tool)  # 动态添加工具
    brain_dynamic.add_tool(final_answer_tool)  # 动态添加工具

    response, *_ = await brain_dynamic.step(
        query="请计算 100 / 4 的结果",
        check=False,
        route = "raw",
    )
    print(f"回答: {response}")


if __name__ == "__main__":
    asyncio.run(demo()) 