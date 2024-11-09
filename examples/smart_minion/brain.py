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
    llm_config = config.models.get("default")
    
    llm = create_llm_provider(llm_config)

    python_env_config = {"port": 3007}

    brain = Brain(
        python_env=RpycPythonEnv(port=python_env_config.get("port", 3007)), 
        llm=llm,
        llms={"route": [ "llama3.2","llama3.1"]}
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
#     obs, score, *_ = await brain.step(
#         query='''
# from typing import List def has_close_elements(numbers: List[float], threshold: float) -> bool: """ Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True """''',
#         route="cot",
#         post_processing="extract_python",
#     )
#     print(obs)

    # 示例使用
#     obs, score, *_ = await brain.step(
#         query='''
#         <optillm_approach>leap</optillm_approach>
#     def encode_cyclic(s: str):
#     """
#     returns encoded string by cycling groups of three characters.
#     """
#     # split string to groups. Each of length 3.
#     groups = [s[(3 * i):min((3 * i + 3), len(s))] for i in range((len(s) + 2) // 3)]
#     # cycle elements in each group. Unless group has fewer elements than 3.
#     groups = [(group[1:] + group[0]) if len(group) == 3 else group for group in groups]
#     return "".join(groups)
# def decode_cyclic(s: str):
#     """
#     takes as input string encoded with encode_cyclic function. Returns decoded string.
#     """
#     ''',
#         route="cot",
#         post_processing="extract_python",
#     )
#     print(obs)

    # obs, score, *_ = await brain.step(
    #     query="from typing import List\n\n\ndef concatenate(strings: List[str]) -> str:\n    \"\"\" Concatenate list of strings into a single string\n    >>> concatenate([])\n    ''\n    >>> concatenate(['a', 'b', 'c'])\n    'abc'\n    \"\"\"\n",
    #     route="cot",
    #     post_processing="extract_python",
    # )
    # print(obs)

    obs, score, *_ = await brain.step(
        query="\ndef circular_shift(x, shift):\n    \"\"\"Circular shift the digits of the integer x, shift the digits right by shift\n    and return the result as a string.\n    If shift > number of digits, return digits reversed.\n    >>> circular_shift(12, 1)\n    \"21\"\n    >>> circular_shift(12, 2)\n    \"12\"\n    \"\"\"\n",
        route="cot",
        post_processing="extract_python",

        #check_route="doctest"
    )
    print(obs)


    # obs, score, *_ = await brain.step(
    #     query="solve \log_{\sqrt{5}}{125\sqrt{5}}",
    #     route="cot",
    #     check=False
    # )
    # print(obs)


if __name__ == "__main__":
    asyncio.run(smart_brain())
