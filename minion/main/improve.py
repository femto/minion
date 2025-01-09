from abc import ABC, abstractmethod
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import Minion, register_improver_minion

class ImproverMinion(Minion):
    """所有 improver minion 的基类"""
    def __init__(self, input=None, brain=None, worker=None, **kwargs):
        super().__init__(input=input, brain=brain, **kwargs)
        self.worker = worker

    @abstractmethod
    async def execute(self):
        pass

@register_improver_minion(name="feedback")
class FeedbackMinion(ImproverMinion):
    async def execute(self):
        return await self.worker.execute()

@register_improver_minion(name="reasoning")
class ReasoningMinion(ImproverMinion):
    async def execute(self):
        # 实现基于推理的改进策略
        pass

@register_improver_minion(name="step_by_step")
class StepByStepMinion(ImproverMinion):
    async def execute(self):
        # 实现基于步骤分解的改进策略
        pass
