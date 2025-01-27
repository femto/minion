from abc import ABC, abstractmethod
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import Minion, register_improver_minion
from minion.main.prompt import IMPROVE_CODE_PROMPT

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
        # 使用测试用例来改进代码
        test_cases = self.worker.input.metadata.get("test_cases", [])
        ai_test_cases = self.worker.input.metadata.get("ai_test_cases", [])
        
        # 构建改进提示
        prompt = IMPROVE_CODE_PROMPT.format(
            code=self.worker.answer,
            test_cases=test_cases,
            ai_test_cases=ai_test_cases,
            entry_point=self.worker.input.entry_point
        )
        
        # 使用 LLM 改进代码
        node = LmpActionNode(self.brain.llm)
        improved_code = await node.execute(prompt)
        
        # 更新 worker 的答案
        self.worker.answer = improved_code
        return improved_code

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
