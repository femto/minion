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
from minion.main.utils import replace_placeholders_with_env
from minion.providers import create_llm_provider

async def smart_brain():
    # 使用从 minion/__init__.py 导入的 config 对象
    llm_config = config.models.get("default")
    
    llm = create_llm_provider(llm_config)

    python_env_config = {"port": 3007}

    brain = Brain(
        python_env=RpycPythonEnv(port=python_env_config.get("port", 3007)), 
        llm=llm
    )

    # # 示例使用
    # obs, score, *_ = await brain.step(
    #     query='''
    # from typing import List def has_close_elements(numbers: List[float], threshold: float) -> bool: """ Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True """''',
    #     route="native",
    #     post_processing="extract_python",
    # )
    # print(obs)
    # cache_plan = os.path.join(MINION_ROOT/"logs", "game24.1.json")
    # obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 4 3 9 8",
    #                                   route="python",
    #                                   cache_plan=cache_plan)
    # print(obs)
    # obs, score, *_ = await brain.step(
    #     query='''
    #     ['https://en.wikipedia.org/wiki/President_of_the_United_States', 'https://en.wikipedia.org/wiki/James_Buchanan', 'https://en.wikipedia.org/wiki/Harriet_Lane', 'https://en.wikipedia.org/wiki/List_of_presidents_of_the_United_States_who_died_in_office', 'https://en.wikipedia.org/wiki/James_A._Garfield']
    #
    # If my future wife has the same first name as the 15th first lady of the United States' mother and her surname is the same as the second assassinated president's mother's maiden name, what is my future wife's name?
    # ''',
    #     route="optillm-readurls&memory",
    # )
    # print(obs)

    # 示例使用
    obs, score, *_ = await brain.step(
        query='''
from typing import List def has_close_elements(numbers: List[float], threshold: float) -> bool: """ Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True """''',
        route="optillm-bon",
        post_processing="extract_python",
    )
    print(obs)


if __name__ == "__main__":
    asyncio.run(smart_brain())
