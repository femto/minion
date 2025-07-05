from abc import ABC, abstractmethod
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import Minion, register_improver_minion
from minion.main.prompt import IMPROVE_CODE_PROMPT, IMPROVE_PROMPT
from minion.utils.template import render_template_with_variables, construct_simple_message

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
        node = LmpActionNode(self.brain.llm)
        tools = (self.input.tools or []) + (self.brain.tools or [])
        
        # 检查输入是否为消息列表（multimodal support）
        if hasattr(self.input, 'query') and isinstance(self.input.query, list):
            # 构建包含反馈信息的消息列表
            enhanced_messages = list(self.input.query)  # 复制原消息列表
            
            # 添加改进上下文信息
            improvement_context = f"\n\nImprovement Context:\n"
            improvement_context += f"Previous Answer: {self.worker.input.answer}\n"
            if hasattr(self.worker.input, 'feedback') and self.worker.input.feedback:
                improvement_context += f"Feedback: {self.worker.input.feedback}\n"
            improvement_context += "Please improve the answer based on this feedback."
            
            # 添加改进信息到最后一个消息
            if enhanced_messages and isinstance(enhanced_messages[-1], str):
                enhanced_messages[-1] += improvement_context
            else:
                enhanced_messages.append(improvement_context)
                
            messages = construct_simple_message(enhanced_messages)
            improved_answer = await node.execute(messages, tools=tools)
        else:
            # 原有的模板渲染方式
            prompt = render_template_with_variables(
                template_str=IMPROVE_PROMPT,
                input={
                    "answer": self.worker.input.answer, #todo, maybe stateful agent connections?
                    "feedback": self.worker.input.feedback,
                    **self.worker.input.__dict__  # 包含其他上下文信息
                }
            )
            
            improved_answer = await node.execute(prompt, tools=tools)
        
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
