from abc import ABC, abstractmethod
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import Minion, register_improver_minion
from minion.main.prompt import IMPROVE_CODE_PROMPT, IMPROVE_PROMPT
from minion.utils.template import render_template_with_variables

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
    """基于反馈进行通用内容改进的 Minion"""
    async def execute(self):
        """基于反馈进行通用内容改进的执行方法"""
        # 构建改进提示
        prompt = render_template_with_variables(
            template_str=IMPROVE_PROMPT,
            input={
                "answer": self.worker.input.answer, #todo, maybe stateful agent connections?
                "feedback": self.worker.input.feedback,
                **self.worker.input.__dict__  # 包含其他上下文信息
            }
        )
        
        # 使用 LLM 改进内容
        node = LmpActionNode(self.brain.llm)
        improved_answer = await node.execute(prompt)
        
        # 更新 worker 的答案
        self.worker.answer = improved_answer
        return improved_answer

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
