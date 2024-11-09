#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import List
from pydantic import BaseModel, Field
class Answer(BaseModel):
    answer: str = Field(default="", description="answer")
class MetaPlan(BaseModel):
    name: str = Field(default="naive", description="The name of stragety.")
    score: float = Field(
        default=0,
        description="estimate score of choosing this stragety of success, 1.0 means perfect match,"
        "if we choose this stragety, we are most likely to solve this problem, 0.0 means a"
        "bad match, if we choose this stragety, we are most likely fail to solve this problem",
    )
    recommended_llm: str = Field(default="", description="The recommended LLM for this task based on its capabilities.")

class Identification(BaseModel):
    complexity: str = Field(
        default="",
        description="estimate this problem's difficulty, when the problem is simple,only required one or several steps to solve this problem,"
        "return low, when the problem difficulty is medium and require more steps to solve it, return medium,"
        "when the problem seemed quite difficult, generally should involve complex process and careful step planning to solve it,"
        "return high",
    )
    difficulty: str = Field(
        default="",
        description="Represents the educational difficulty level of the problem. Return elementary school/middle school/high school/undergraduate/graduate/postgraduate/olympiad etc.",
    )
    query_range: str = Field(
        default="",
        description="Determine the required range of attention for processing the query based on its complexity and the extent of contextual memory required. "
        "If the query can be completed in a few steps with minimal context, return 'short'. "
        "For tasks that require a moderate amount of contextual memory and processing, return 'medium'. "
        "For complex, multi-step queries necessitating extensive long-term contextual memory, return 'long'. "
        "For highly intricate queries, such as writing an entire novel or solving problems with multiple interdependent variables, return 'super long'.",
    )
    field: str = Field(
        default="",
        description="classify the problem within a relevant academic field such as Mathematics, Physics, Chemistry, Biology, Computer Science, Linguistics, Sociology, or Psychology. ",
    )
    subfield: str = Field(
        default="",
        description="Further refine the classification by identifying the appropriate subfield, such as Mathematical Analysis, Quantum Mechanics, Organic Chemistry, Molecular Biology, Artificial Intelligence, Semantics, or Social Psychology. ",
    )

class QuestionAndAnswer(BaseModel):
    answer: str = Field(
        default="",
        description="the answer to the question",
    )

class EnsembleLogic(BaseModel):
    name: str = Field(default="sc", description="the name of the ensemble logic")
    description: str = Field(
        default="",
        description="describe how to carry out the ensemble to make sure the answer is correct",
    )

class Plan(BaseModel):
    task_id: str = Field(
        default="some id",
        description="unique identifier for a task in plan, can be an ordinal",
    )
    dependent_task_ids: List[str] = Field(
        default_factory=list,
        description="ids of tasks prerequisite to this task",
    )
    instruction: str = Field(
        default="some instruction",
        description="what you should do in this task, one short phrase or sentence",
    )
    task_type: str = Field(
        default="some task type",
        description="type of this task",
    )
    task_params: str = Field(
        default="{}",
        description="a json dictionary of task parameters and values",
    )

class CheckResult(BaseModel):
    feedback: str = ""
    correct: bool = False
    score: float = 0.0
