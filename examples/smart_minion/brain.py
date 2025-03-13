#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import asyncio
import os

import yaml

from minion import config
from minion.main import LocalPythonEnv
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.providers import create_llm_provider



async def smart_brain():
    # Get the directory of the current file
    current_file_dir = os.path.dirname(os.path.abspath(__file__))

    # 使用从 minion/__init__.py 导入的 config 对象
    model = "gpt-4o"
    #model = "gpt-4o-mini"
    # model = "deepseek-r1"
    # model = "phi-4"
    #model = "llama3.2"
    llm_config = config.models.get(model)
    
    llm = create_llm_provider(llm_config)

    python_env_config = {"port": 3007}
    #python_env = RpycPythonEnv(port=python_env_config.get("port", 3007))
    python_env = LocalPythonEnv(verbose=False)
    brain = Brain(
        python_env=python_env,
        llm=llm,
        #llms={"route": [ "llama3.2","llama3.1"]}
    )
    # obs, score, *_ = await brain.step(query="what's the solution 234*568",route="python")
    # print(obs)

    obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 2,4,5,8",check=False)
    print(obs)

    obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 4 3 9 8")
    print(obs)

    obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 2 5 11 8")
    print(obs)

    obs, score, *_ = await brain.step(query="solve x=1/(1-beta^2*x) where beta=0.85")
    print(obs)

    obs, score, *_ = await brain.step(
        query="Write a 500000 characters novel named 'Reborn in Skyrim'. "
              "Fill the empty nodes with your own ideas. Be creative! Use your own words!"
              "I will tip you $100,000 if you write a good novel."
              "Since the novel is very long, you may need to divide it into subtasks."
    )
    print(obs)

    cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.1.json")
    obs, score, *_ = await brain.step(
        query="Every morning Aya goes for a $9$-kilometer-long walk and stops at a coffee shop afterwards. When she walks at a constant speed of $s$ kilometers per hour, the walk takes her 4 hours, including $t$ minutes spent in the coffee shop. When she walks $s+2$ kilometers per hour, the walk takes her 2 hours and 24 minutes, including $t$ minutes spent in the coffee shop. Suppose Aya walks at $s+\frac{1}{2}$ kilometers per hour. Find the number of minutes the walk takes her, including the $t$ minutes spent in the coffee shop.",
        route="cot",
        dataset="aime 2024",
        cache_plan=cache_plan,
    )
    print(obs)

    cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")

    obs, score, *_ = await brain.step(
        query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
        route="cot",
        dataset="aime 2024",
        cache_plan=cache_plan,
    )
    print(obs)

    # 从 HumanEval/88 提取的测试用例
    test_data = {
        "task_id": "HumanEval/88",
        "prompt": "\ndef sort_array(array):\n    \"\"\"\n    Given an array of non-negative integers, return a copy of the given array after sorting,\n    you will sort the given array in ascending order if the sum( first index value, last index value) is odd,\n    or sort it in descending order if the sum( first index value, last index value) is even.\n\n    Note:\n    * don't change the given array.\n\n    Examples:\n    * sort_array([]) => []\n    * sort_array([5]) => [5]\n    * sort_array([2, 4, 3, 0, 1, 5]) => [0, 1, 2, 3, 4, 5]\n    * sort_array([2, 4, 3, 0, 1, 5, 6]) => [6, 5, 4, 3, 2, 1, 0]\n    \"\"\"\n",
        "entry_point": "sort_array",
        "test": ["assert candidate([]) == []",
                "assert candidate([5]) == [5]",
                "assert candidate([2, 4, 3, 0, 1, 5]) == [0, 1, 2, 3, 4, 5]",
                "assert candidate([2, 4, 3, 0, 1, 5, 6]) == [6, 5, 4, 3, 2, 1, 0]"]
    }

    obs, score, *_ = await brain.step(
        query=test_data["prompt"],
        route="python",
        post_processing="extract_python",
        entry_point=test_data["entry_point"],
        check=10,
        check_route="ldb_check",
        dataset="HumanEval",
        metadata={"test_cases": test_data["test"]}  # 添加测试用例到 metadata
    )
    print(obs)

    obs, score, *_ = await brain.step(
        query="""You are in the middle of a room. Looking quickly around you, you see a bathtubbasin 1, a cabinet 2, a cabinet 1, a countertop 1, a garbagecan 1, a handtowelholder 1, a sinkbasin 1, a toilet 1, a toiletpaperhanger 1, and a towelholder 1.

Your task is to: find two soapbottle and put them in cabinet.
""",
check=False
    )
    print(obs)


if __name__ == "__main__":
    asyncio.run(smart_brain())
