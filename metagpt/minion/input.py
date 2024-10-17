#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""

import uuid
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from metagpt.minion.answer_extraction import extract_math_answer
from metagpt.minion.symbol_table import SymbolTable
from metagpt.minion.utils import extract_number_from_string, extract_python


class PostProcessingType(Enum):
    NONE = "none"
    EXTRACT_NUMBER = "extract_number_from_string"
    EXTRACT_MATH_ANSWER = "extract_math_answer"
    EXTRACT_PYTHON = "extract_python"


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


class ExecutionState(BaseModel):
    current_minion: Optional[str] = None
    current_iteration: int = 0
    current_task_index: int = 0
    last_completed_task: Optional[str] = None
    chosen_minion: Optional[str] = None
    check_result: Optional[Dict[str, Any]] = None


class Input(BaseModel):
    long_context: str = Field(default="")
    short_context: str = ""  # abstract/summarized version

    query: str = ""
    query_type: str = ""  # generate,question(solve) or execution, requirement
    query_sub_type: str = ""
    images: Optional[Union[str, list[str]]] = None

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
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # for training
    item_id: Any = None
    raw_correct_answer: Optional[str] = None
    correct_answer: Any = None
    extract_correct_answer: Any = None
    compare_answer: Any = None

    # 新增字段
    execution_state: ExecutionState = Field(default_factory=ExecutionState)

    post_processing: PostProcessingType = Field(
        default=PostProcessingType.NONE, description="The type of post-processing to apply to the answer"
    )

    def save_state(self, file_path: str):
        """将当前状态保存到文件"""
        import os

        import dill

        # Create directory if it doesn't exist
        file_path = os.path.join(os.getcwd(), file_path) if not os.path.isabs(file_path) else file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            dill.dump(self, f)

    @classmethod
    def load_state(cls, file_path: str) -> "Input":
        """从文件加载状态"""
        import os

        import dill

        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return dill.load(f)

    def update_execution_state(self, **kwargs):
        """更新执行状态"""
        for key, value in kwargs.items():
            setattr(self.execution_state, key, value)

    @property
    def context(self):
        return self.long_context

    @context.setter
    def context(self, context):
        self.long_context = context

    def apply_post_processing(self, raw_answer: str) -> Any:
        """Apply the specified post-processing to the raw answer."""
        if self.post_processing == PostProcessingType.EXTRACT_NUMBER:
            return extract_number_from_string(raw_answer)
        elif self.post_processing == PostProcessingType.EXTRACT_MATH_ANSWER:
            return extract_math_answer(raw_answer)
        elif self.post_processing == PostProcessingType.EXTRACT_PYTHON:
            return extract_python(raw_answer)
        else:
            return raw_answer


Task.update_forward_refs()
