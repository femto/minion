#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import uuid

from minion.main.prompt import ASK_PROMPT, COT_PROBLEM_INSTRUCTION, DOT_PROMPT
from minion.main.utils import camel_case_to_snake_case, extract_content
from minion.actions.lmp_action_node import LmpActionNode
from minion.utils.answer_extraction import math_equal

MINION_REGISTRY = {}
MINION_ROUTE_DOWNSTREAM = {}


# a dummy score that does nothing, always return 1 to shortcut the score process
class NullScore:
    def __call__(self, **kwargs):
        return 1


class SubclassHookMeta(type):
    def __init__(cls, name, bases, clsdict):
        super().__init__(name, bases, clsdict)
        cls._subclassed_hook()


def register_route_downstream(cls):
    # Register the class in the dictionary with its name as the key
    MINION_ROUTE_DOWNSTREAM[camel_case_to_snake_case(cls.__name__)] = cls
    return cls


class Minion(metaclass=SubclassHookMeta):
    def __init__(self, input=None, brain=None, id=None, score_func=None, task=None, task_execution=False, **kwargs):
        if brain is None:
            raise ValueError("The 'brain' parameter cannot be None.")

        self.id = id or uuid.uuid4()

        self.input = input
        self.brain = brain
        self.followers = []
        self.score_func = score_func
        self.task = task
        self.task_execution = task_execution

    def propagate_information(self, other):
        other.input = self.input
        other.brain = self.brain

    async def score(self):
        pass

    @classmethod
    def _subclassed_hook(cls):
        if cls.__name__ != "Minion":
            MINION_REGISTRY[camel_case_to_snake_case(cls.__name__)] = cls
        # print(f"{cls.__name__} has been subclassed")

    def add_followers(self, follower):
        self.followers.append(follower)

    def __hash__(self):
        # Use a tuple of attributes to compute the hash value
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        return False

    def __repr__(self):
        return f"Minion({self.id})"

    def get_compare_answer_func(self):
        if self.input.compare_answer == "math_equal":
            return math_equal
        return None

    async def update_stats(self, minion_name, result, raw_answer):
        if self.brain.stats_storer:
            compare_answer_func = self.get_compare_answer_func()
            if compare_answer_func:
                outcome = "correct" if compare_answer_func(self.input.correct_answer, result) else "incorrect"
                stats_data = {
                    "item_id": str(self.input.item_id),
                    "minion_name": minion_name,
                    "answer": str(result),
                    "raw_answer": raw_answer,
                    "raw_correct_answer": self.input.raw_correct_answer,
                    "correct_answer": self.input.correct_answer,
                    "complexity": self.input.complexity,
                    "query_range": self.input.query_range,
                    "difficulty": self.input.difficulty,
                    "field": self.input.field,
                    "subfield": self.input.subfield,
                    "additional_attributes": self.input.metadata,
                    "outcome": outcome,
                }

                await self.brain.stats_storer.update_stats(stats_data)

                # To retrieve stats
                # stats = await stats_storer.get_stats(item_id)

    @property
    def clean_answer(self):
        answer = extract_content(self.answer_node.content)
        return answer

    async def execute(self):
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(ASK_PROMPT.format(input=self.input))
        self.answer_node = response
        self.answer = self.input.answer = response
        return self.answer

class CotMinion(Minion):
    async def execute(self):
        prompt = (COT_PROBLEM_INSTRUCTION + ASK_PROMPT).format(input=self.input)
        prompt += "\nPlease provide your response in JSON format."
        context = {"messages": [{"role": "user", "content": prompt}], "images": self.input.images}
        
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(context)
        self.answer_node = response

        if self.input.query_type == "code_solution" or self.input.post_processing == "extract_python":
            self.answer = self.extract_python_code(response)
        else:
            self.answer = extract_final_answer(response)

        self.input.answer = self.answer
        self.raw_answer = self.input.raw_answer = response
        return self.raw_answer

class DotMinion(Minion):
    async def execute(self):
        node = LmpActionNode(self.brain.llm)
        prompt = Template(DOT_PROMPT).render(input=self.input)
        response = await node.execute(prompt)
        self.answer_node = response
        self.answer = self.input.answer = extract_final_answer(response)
        
        for _ in range(3):  # try using llm 3 times to extract answer
            if not self.answer:
                # try using llm to extract answer
                node = LmpActionNode(self.brain.llm)
                response = await node.execute(response)
                self.answer = self.input.answer = extract_final_answer(response)
            else:
                break
                
        self.raw_answer = self.input.raw_answer = response
        return self.answer
