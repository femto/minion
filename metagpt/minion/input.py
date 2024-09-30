#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""

import uuid
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

from metagpt.minion.symbol_table import SymbolTable


class EnsembleStrategyType(Enum):
    EARLY_STOP = "early_stop"
    ESTIMATE = "estimate"  # estimate which one is better
    VOTE = "vote"  # vote which one is better


class QuestionType(Enum):
    BLANK_FILLING_QUESTION = "blank filling question"
    TRUE_FALSE_QUESTION = "true-false question"
    MULTIPLE_CHOICE_QUESTION = "multiple-choice question"


class Task(BaseModel):
    route: Optional[str] = ""  # a tempory solution for routing
    num_trials: int = 1  # how much times downstream node runs
    ensemble_strategy: str = EnsembleStrategyType.EARLY_STOP
    output: Any = None
    parent: Any = None
    # input : 'Input' = None


class Input(BaseModel):
    long_context: str = Field(default="")
    short_context: str = ""  # abstract/summarized version

    query: str = ""
    query_type: str = "question"  # question or requirement
    images: Optional[Union[str, list[str]]] = (None,)

    guidance: str = ""
    constraint: str = ""  # question or requirement
    instruction: str = ""  # instruction for each step, different step can have different instruction

    # identification
    complexity: str = None  # low,medium,high
    query_range: str = None  # short range query, or multiple step range like writing a very long novel
    difficulty: str = None
    field: str = None
    subfield: str = None

    # plan:str = "" # current plan
    score_func: Any = None

    answer: str = ""  # the extracted final answer
    solution: str = ""
    raw_answer: str = ""  # the complete answer with cot thought
    feedback: str = ""  # the feedback for improvement

    question_type: str = ""  # a query sub type that determines the answer protocol
    answer_protocol: str = ""

    ensemble_logic: dict = {}
    check: bool = True

    # plan cache
    cache_plan: str = ""
    task: Task = None  # current task being executed
    symbols: SymbolTable = Field(default_factory=SymbolTable)

    # metadata
    query_time: Any = None
    processed_minions: int = 0  # how many minions processed this
    metadata: dict = {}
    info: dict = {}
    route: Optional[str] = ""  # a tempory solution for routing
    num_trials: int = 1  # how much times downstream node runs
    ensemble_strategy: str = EnsembleStrategyType.EARLY_STOP

    dataset: str = ""  # which dataset this is
    dataset_description: str = ""  # the dataset description
    query_id: str = Field(default_factory=uuid.uuid4)
    run_id: str = Field(default_factory=uuid.uuid4)

    # for training
    item_id: Any = None
    raw_correct_answer: Optional[str] = None
    correct_answer: Any = None
    extract_correct_answer: Any = None
    compare_answer: Any = None

    @property
    def context(self):
        return self.long_context

    @context.setter
    def context(self, context):
        self.long_context = context


Task.update_forward_refs()
