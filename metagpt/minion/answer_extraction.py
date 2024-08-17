#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
from metagpt.minion.minion import Minion


class AnswerExtractionMinion(Minion):
    pass


class MathAnswerExtractionMinion(AnswerExtractionMinion):
    def execute(self):
        return self.input
