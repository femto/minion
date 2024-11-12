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
from minion.const import MINION_ROOT
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.providers import create_llm_provider

async def smart_brain():
    # 使用从 minion/__init__.py 导入的 config 对象
    model = "default"
    #model = "llama3.2"
    llm_config = config.models.get(model)
    
    llm = create_llm_provider(llm_config)

    python_env_config = {"port": 3007}

    brain = Brain(
        python_env=RpycPythonEnv(port=python_env_config.get("port", 3007)), 
        llm=llm,
        llms={"route": [ "llama3.2","llama3.1"]}
    )
    # obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 4 3 9 8")
    # print(obs)

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
        route="dcot",
        post_processing="extract_python",
        entry_point=test_data["entry_point"],
        check=False,
        metadata={"test_cases": test_data["test"]}  # 添加测试用例到 metadata
    )
    print(obs)

if __name__ == "__main__":
    asyncio.run(smart_brain())
