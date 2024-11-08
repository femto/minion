import pytest
import json
from minion.actions.action_node import LLMActionNode
from minion.providers.base_llm import BaseLLM
from minion.message_types import Message
from typing import List, Optional, AsyncIterator

class MockLLM(BaseLLM):
    def _setup(self) -> None:
        """实现抽象方法 _setup"""
        self._setup_retry_config()

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """实现抽象方法 generate"""
        # 返回一个模拟的响应用于测试
        return '{"answer": "mock response"}'

    async def generate_stream(
        self, messages: List[Message], temperature: Optional[float] = None, **kwargs
    ) -> AsyncIterator[str]:
        """实现抽象方法 generate_stream"""
        async def mock_stream():
            yield '{"answer": "mock stream response"}'
        return mock_stream()

@pytest.fixture
def llm_action_node():
    # 创建一个模拟的配置对象
    from minion.configs.config import LLMConfig
    mock_config = LLMConfig(
        name="mock",
        provider="mock",
        api_key="mock-key",
        model="mock-model"
    )
    return LLMActionNode(llm=MockLLM(config=mock_config))

def test_normalize_response_json_string(llm_action_node):
    # 测试JSON字符串输入
    json_input = '''{
        "feedback": "The provided answer correctly implements the circular shift functionality as described in the problem. It converts the integer to a string, determines the number of digits, and handles the case where the shift is greater than or equal to the number of digits by reversing the digits. The effective shift is calculated using modulo operation to ensure it fits within the bounds of the number of digits. The circular shift is then performed by concatenating the appropriate substrings. The solution is clear, accurate, and aligns well with the problem requirements. No logical inconsistencies, gaps, or errors are observed. The answer is a perfect match for the problem.",
        "correct": true,
        "score": 1
    }'''
    
    result = llm_action_node.normalize_response(json_input)
    # 验证返回的是提取并格式化后的JSON字符串
    assert isinstance(result, str)
    # 确保可以被解析回JSON对象
    parsed_result = json.loads(result)
    assert "feedback" in parsed_result
    assert "correct" in parsed_result
    assert "score" in parsed_result
    assert parsed_result["correct"] is True
    assert parsed_result["score"] == 1

def test_normalize_response_dict_with_answer(llm_action_node):
    # 测试包含answer字段的字典
    input_dict = {"answer": "test answer"}
    result = llm_action_node.normalize_response(input_dict)
    assert result == input_dict

def test_normalize_response_schema_format(llm_action_node):
    # 测试schema格式的输入
    schema_input = {
        "properties": {
            "answer": {
                "default": "test answer",
                "type": "string"
            }
        }
    }
    result = llm_action_node.normalize_response(schema_input, is_answer_format=True)
    assert result == {"answer": "test answer"}

def test_normalize_response_invalid_format(llm_action_node):
    # 测试无效格式的输入
    invalid_input = {"some": "data"}
    result = llm_action_node.normalize_response(invalid_input)
    assert result == {"some": "data"}

def test_normalize_response_plain_string(llm_action_node):
    # 测试普通字符串输入
    plain_string = "This is a test string"
    result = llm_action_node.normalize_response(plain_string)
    assert result == plain_string 