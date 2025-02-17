#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""

import uuid
from enum import Enum
from typing import Any, Dict, Optional, Union, Callable

from pydantic import BaseModel, Field

from minion.utils.utils import extract_number_from_string
from minion.utils.answer_extraction import extract_math_answer, extract_python

class PostProcessingType(str, Enum):
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
    chosen_minion: Optional[str] = None

    current_iteration: int = 0
    current_task_index: int = 0
    last_completed_task: Optional[str] = None
    check_result: Optional[Dict[str, Any]] = None


class Input(BaseModel):
    # Basic fields
    long_context: str = Field(default="")  # Full context of the input
    short_context: str = ""  # Summarized/abstracted version of context

    query: str = ""  # The actual query or question
    query_type: str = ""  # Type of query: generate/solve/execute
    query_sub_type: str = ""  # Specific sub-category of the query
    images: Optional[Union[str, list[str]]] = None  # Image data if any

    guidance: str = ""  # Additional guidance for processing
    constraint: str = ""  # Constraints or requirements
    instruction: str = ""  # Step-by-step instructions

    cache_plan: str = None
    system_prompt: str = ""
    task: Any = None
    symbols: Dict[str, Any] = Field(default_factory=dict)
    task_check: bool = False

    # Answer-related fields
    answer: str = ""  # The final extracted/processed answer
    answer_raw: str = ""  # Raw answer including chain of thought
    answer_code: str = ""  # Answer in code format if applicable
    answer_full: str = ""  # Complete output including all details, or should we call it reasoning_content?
    feedback: str = ""  # Feedback for improvement
    error: str = ""  # error for improvement
    entry_point: str = "" #entry_point name of function for code generation

    # Ground truth fields for evaluation
    ground_truth_raw: Optional[str] = None  # Raw ground truth text
    ground_truth: Any = None  # Processed ground truth
    extract_ground_truth: Optional[Callable[[Any], Any]] = None  # Function to extract/process ground truth
    compare_ground_truth: Optional[Callable[[Any, Any], bool]] = None  # Function to compare answer with ground truth

    # Identification fields
    complexity: str = None  # Complexity level: low/medium/high
    query_range: str = None  # Query scope: short/long range
    difficulty: str = None  # Difficulty level
    field: str = None  # Main field/domain
    subfield: str = None  # Specific subfield

    # Configuration and state
    question_type: str = ""  # Specific question type
    answer_protocol: str = ""  # Protocol for answer formatting, should we call it answer_format?
    execution_config: dict = {}  # Configuration for execution, like ensemble stragety etc.
    check: Union[bool,int] = True  # Whether to perform validation
    check_route:str = ""  # Whether to perform validation
    improve_route:str = "feedback"  # default improve stragety according to feedback

    # Metadata
    dataset: str = ""  # Source dataset identifier
    dataset_description: str = ""  # Description of the dataset
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique query identifier
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique execution identifier

    # Processing state
    processed_minions: int = 0  # Number of minions that processed this
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata including test cases"
    )
    info: dict = {}  # Additional information
    route: Optional[str] = ""  # Routing information
    num_trials: int = 1  # Number of execution trials
    ensemble_strategy: str = EnsembleStrategyType.EARLY_STOP  # Strategy for ensemble processing

    # Execution state tracking
    execution_state: ExecutionState = Field(default_factory=ExecutionState)  # Current execution state
    pre_processing: str = ""
    post_processing: PostProcessingType = Field(
        default=PostProcessingType.NONE,
        description="Type of post-processing to apply"
    )
    save_state: bool = Field(
        default=False,
        description="Whether to save state during execution"
    )

    # 添加system_prompt字段
    system_prompt: str = Field(
        default="",
        description="System prompt for LLM models"
    )
    mind_id : str = Field(
        default="",
        description="mind if to choose, left_mind/right_mind/hippocampus_mind"
    )

    def update_execution_state(self, **kwargs):
        """Update execution state with the provided key-value pairs.
        
        Args:
            **kwargs: Key-value pairs to update in the execution state
                current_minion (Optional[str]): Current executing minion name
                current_iteration (int): Current iteration number
                current_task_index (int): Current task index
                last_completed_task (Optional[str]): ID of the last completed task
                chosen_minion (Optional[str]): Name of the chosen minion
                check_result (Optional[Dict[str, Any]]): Result from check operation
        """
        for key, value in kwargs.items():
            if hasattr(self.execution_state, key):
                setattr(self.execution_state, key, value)
            else:
                raise ValueError(f"Invalid execution state field: {key}")

    def apply_post_processing(self, answer_raw: str, post_processing=None) -> Any:
        """Apply post-processing to the raw answer based on the post_processing type.
        
        Args:
            answer_raw (str): The raw answer to process
            post_processing (Optional[PostProcessingType]): Override default post processing type
            
        Returns:
            Any: The processed answer
        """
        if not answer_raw:
            return answer_raw
            
        # Use provided post_processing if specified, otherwise use instance value
        processing_type = post_processing if post_processing else self.post_processing
            
        if processing_type == PostProcessingType.EXTRACT_NUMBER:
            return extract_number_from_string(answer_raw)
        elif processing_type == PostProcessingType.EXTRACT_MATH_ANSWER:
            return extract_math_answer(answer_raw)
        elif processing_type == PostProcessingType.EXTRACT_PYTHON:
            return extract_python(answer_raw, self.entry_point)
        else:  # PostProcessingType.NONE
            return answer_raw

Task.model_rebuild()
