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
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.main.utils import replace_placeholders_with_env
from minion.providers import create_llm_provider


async def smart_brain():
    # 使用从 minion/__init__.py 导入的 config 对象
    llm_config = config.models.get("default")
    llm = create_llm_provider(llm_config)
    python_env_config = {"port": 3007}  # 同上

    brain = Brain(
        python_env=RpycPythonEnv(port=python_env_config.get("port", 3007)), llm=llm
    )

    # 示例使用
    obs, score, *_ = await brain.step(
        query='''
from typing import List def has_close_elements(numbers: List[float], threshold: float) -> bool: """ Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True """''',
        route="cot",
        post_processing="extract_python",
    )
    print(obs)

    # 其他示例代码...


if __name__ == "__main__":
    asyncio.run(smart_brain())
