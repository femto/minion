#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import uuid

from minion.main.prompt import ASK_PROMPT_JINJA
from minion.utils.utils import camel_case_to_snake_case, extract_content
from minion.actions.lmp_action_node import LmpActionNode
from minion.utils.answer_extraction import math_equal
from minion.main.improve_route import ImproveRoute

MINION_REGISTRY = {}
WORKER_MINIONS = {}
IMPROVER_MINIONS = {}


# a dummy score that does nothing, always return 1 to shortcut the score process
class NullScore:
    def __call__(self, **kwargs):
        return 1


class SubclassHookMeta(type):
    def __init__(cls, name, bases, clsdict):
        super().__init__(name, bases, clsdict)
        cls._subclassed_hook()

def register_worker_minion(cls=None, *, name=None):
    """Decorator to register worker minions.
    Can be used as @register_worker_minion or @register_worker_minion(name="custom_name")

    Args:
        cls: The class to register (when used as @register_worker_minion)
        name: Optional custom name (when used as @register_worker_minion(name="custom_name"))
    """
    def decorator(cls):
        # Use custom name if provided, otherwise convert class name to snake_case
        register_name = name if name is not None else camel_case_to_snake_case(cls.__name__)
        WORKER_MINIONS[register_name] = cls
        return cls

    # Handle both @register_worker_minion and @register_worker_minion(name="custom_name")
    if cls is None:
        return decorator
    return decorator(cls)

def register_improver_minion(cls=None, *, name=None):
    """Decorator to register improver minions.
    Can be used as @register_improver_minion or @register_improver_minion(name="custom_name")
    """
    def decorator(cls):
        register_name = name if name is not None else camel_case_to_snake_case(cls.__name__)
        IMPROVER_MINIONS[register_name] = cls
        return cls

    if cls is None:
        return decorator
    return decorator(cls)


class Minion(metaclass=SubclassHookMeta):
    def __init__(self, input=None, brain=None, id=None, score_func=None, worker_config=None, task=None, **kwargs):
        if brain is None:
            raise ValueError("The 'brain' parameter cannot be None.")

        self.id = id or uuid.uuid4()

        self.input = input
        self.brain = brain
        self.followers = []
        self.score_func = score_func

        self.worker_config = worker_config
        self.task = task

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

    async def update_stats(self, minion_name, result, answer_raw):
        if self.brain.stats_storer:
            compare_answer_func = self.get_compare_answer_func()
            if compare_answer_func:
                outcome = "correct" if compare_answer_func(self.input.ground_truth, result) else "incorrect"
                stats_data = {
                    "item_id": str(self.input.item_id),
                    "minion_name": minion_name,
                    "answer": str(result),
                    "answer_raw": answer_raw,
                    "raw_correct_answer": self.input.ground_truth_raw,
                    "correct_answer": self.input.ground_truth,
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
        response = await node.execute(ASK_PROMPT_JINJA.format(input=self.input))
        self.answer = self.input.answer = response
        return self.answer

    async def improve(self):
        # 获取改进路由
        route_name = getattr(self.input, 'improve_route', 'feedback')
        improve_route = ImproveRoute.get_route(route_name)
        
        # 获取对应的 improver class
        improver_cls = IMPROVER_MINIONS.get(improve_route.value)
        if improver_cls:
            improver = improver_cls(
                input=self.input, 
                brain=self.brain,
                worker=self
            )
            return await improver.execute()
        
        # fallback
        return await self.execute()
