#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/5/11 14:45
@Author  : alexanderwu
@File    : llm.py
"""
from typing import Optional

from minion.configs.llm_config import LLMConfig
from minion.configs.config import config


def LLM(llm_config: Optional[LLMConfig] = None, context = None):

    return None


def some_function():
    # 使用配置
    api_key = config.get('api_key')
    # ... 其他代码 ...
