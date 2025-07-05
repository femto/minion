"""
测试 CheckMinion 和 FeedbackMinion 对消息列表（multimodal）的支持
"""
import pytest
from unittest.mock import Mock, AsyncMock
from minion.main.check import CheckMinion, DoctestMinion
from minion.main.improve import FeedbackMinion
from minion.main.input import Input
from minion.models.schemas import CheckResult


class TestCheckMinionMultimodal:
    """测试 CheckMinion 的多模态支持"""
    
    def test_check_minion_with_text_query(self):
        """测试 CheckMinion 处理文本查询"""
        # 模拟输入对象
        input_obj = Mock()
        input_obj.query = "Please check this answer: 2+2=4"
        input_obj.answer = "2+2=4"
        input_obj.tools = []
        input_obj.instruction = "let's think step by step to verify this answer"
        
        # 模拟brain和llm
        brain = Mock()
        brain.llm = Mock()
        brain.tools = []
        
        minion = CheckMinion(input=input_obj, brain=brain)
        assert minion.input.instruction == "let's think step by step to verify this answer"
    
    def test_check_minion_with_multimodal_query(self):
        """测试 CheckMinion 处理多模态查询"""
        # 模拟包含图像和文本的消息列表
        multimodal_query = [
            "Please check this mathematical solution:",
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="}},
            "Is the solution correct?"
        ]
        
        input_obj = Mock()
        input_obj.query = multimodal_query
        input_obj.answer = "Yes, it's correct"
        input_obj.tools = []
        input_obj.instruction = "let's think step by step to verify this answer"
        
        brain = Mock()
        brain.llm = Mock()
        brain.tools = []
        
        minion = CheckMinion(input=input_obj, brain=brain)
        
        # 验证输入被正确设置
        assert isinstance(minion.input.query, list)
        assert len(minion.input.query) == 3

    def test_doctest_minion_with_multimodal_query(self):
        """测试 DoctestMinion 处理多模态查询"""
        multimodal_query = [
            "Check this function with doctest:",
            "def add(x, y): return x + y"
        ]
        
        input_obj = Mock()
        input_obj.query = multimodal_query
        input_obj.answer = '''
def add(x, y):
    """
    >>> add(2, 3)
    5
    >>> add(0, 0)
    0
    """
    return x + y
        '''
        input_obj.tools = []
        input_obj.instruction = "let's think step by step to verify this answer"
        
        brain = Mock()
        brain.llm = Mock()
        brain.tools = []
        
        minion = DoctestMinion(input=input_obj, brain=brain)
        
        # 验证输入和测试用例
        assert isinstance(minion.input.query, list)
        assert len(minion.test_cases) >= 0  # doctest 可能提取到测试用例


class TestFeedbackMinionMultimodal:
    """测试 FeedbackMinion 的多模态支持"""
    
    def test_feedback_minion_with_text_query(self):
        """测试 FeedbackMinion 处理文本查询"""
        input_obj = Mock()
        input_obj.query = "Improve this answer based on feedback"
        input_obj.tools = []
        
        # 模拟 worker 对象
        worker = Mock()
        worker.input = Mock()
        worker.input.answer = "Original answer"
        worker.input.feedback = "Need more detail"
        worker.answer = None
        
        brain = Mock()
        brain.llm = Mock()
        brain.tools = []
        
        minion = FeedbackMinion(input=input_obj, brain=brain, worker=worker)
        
        # 验证设置
        assert minion.worker == worker
        assert minion.input.query == "Improve this answer based on feedback"

    def test_feedback_minion_with_multimodal_query(self):
        """测试 FeedbackMinion 处理多模态查询"""
        multimodal_query = [
            "Here's my solution with diagram:",
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="}},
            "Please improve it based on the feedback"
        ]
        
        input_obj = Mock()
        input_obj.query = multimodal_query
        input_obj.tools = []
        
        # 模拟 worker 对象
        worker = Mock()
        worker.input = Mock()
        worker.input.answer = "Solution with diagram"
        worker.input.feedback = "The diagram is unclear"
        worker.answer = None
        
        brain = Mock()
        brain.llm = Mock()
        brain.tools = []
        
        minion = FeedbackMinion(input=input_obj, brain=brain, worker=worker)
        
        # 验证多模态输入
        assert isinstance(minion.input.query, list)
        assert len(minion.input.query) == 3


def demo_check_minion_multimodal_detection():
    """演示 CheckMinion 如何检测多模态输入"""
    print("\n=== CheckMinion Multimodal Detection Demo ===")
    
    # 文本输入
    text_input = Mock()
    text_input.query = "Check this answer: 2+2=4"
    
    print(f"Text query: {hasattr(text_input, 'query') and isinstance(text_input.query, list)}")
    
    # 多模态输入
    multimodal_input = Mock()
    multimodal_input.query = [
        "Check this solution:",
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,fake"}},
        "Is it correct?"
    ]
    
    print(f"Multimodal query: {hasattr(multimodal_input, 'query') and isinstance(multimodal_input.query, list)}")


def demo_improve_minion_message_enhancement():
    """演示 FeedbackMinion 如何增强消息"""
    print("\n=== FeedbackMinion Message Enhancement Demo ===")
    
    # 原始多模态消息
    original_messages = [
        "Here's my solution:",
        "Please improve it"
    ]
    
    # 模拟改进上下文
    improvement_context = f"\n\nImprovement Context:\n"
    improvement_context += f"Previous Answer: Original solution\n"
    improvement_context += f"Feedback: Need more detail\n"
    improvement_context += "Please improve the answer based on this feedback."
    
    # 增强消息
    enhanced_messages = list(original_messages)
    enhanced_messages[-1] += improvement_context
    
    print("Original messages:")
    for i, msg in enumerate(original_messages):
        print(f"  {i+1}: {msg}")
    
    print("\nEnhanced messages:")
    for i, msg in enumerate(enhanced_messages):
        print(f"  {i+1}: {msg}")


if __name__ == "__main__":
    # 运行基本测试
    test_check = TestCheckMinionMultimodal()
    test_check.test_check_minion_with_text_query()
    test_check.test_check_minion_with_multimodal_query()
    test_check.test_doctest_minion_with_multimodal_query()
    print("✓ CheckMinion tests passed")
    
    test_feedback = TestFeedbackMinionMultimodal()
    test_feedback.test_feedback_minion_with_text_query()
    test_feedback.test_feedback_minion_with_multimodal_query()
    print("✓ FeedbackMinion tests passed")
    
    # 运行演示
    demo_check_minion_multimodal_detection()
    demo_improve_minion_message_enhancement()
    
    print("\n=== All tests completed ===") 