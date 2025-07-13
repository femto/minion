#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Think in Code Examples Package
展示Meta工具在不同场景下的使用
"""

__version__ = "1.0.0"
__author__ = "CodeMinion Team"
__description__ = "Think in Code Meta工具演示和示例"

# 导出主要演示模块
from . import basic_demo
from . import code_execution_demo  
from . import real_code_agent_demo
from . import run_demos

__all__ = [
    "basic_demo",
    "code_execution_demo",
    "real_code_agent_demo", 
    "run_demos"
]