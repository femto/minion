#!/usr/bin/env python
# coding=utf-8
"""
Minion Exceptions

This module contains all custom exceptions used throughout the minion package.
"""

from typing import Any


class FinalAnswerException(Exception):
    """Exception raised when final_answer is called to indicate task completion"""
    
    def __init__(self, answer: Any):
        self.answer = answer
        self.value = f"{answer}"  # Compatibility with local_python_executor
        super().__init__(f"{answer}")