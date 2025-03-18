import pytest
import json
from minion.actions.action_node import LLMActionNode
from minion.providers.base_llm import BaseLLM
from minion.schema.message_types import Message
from typing import List, Optional, AsyncIterator, Type
from pydantic import BaseModel

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

# 添加测试用的 Response 模型
class TestXMLResponse(BaseModel):
    message: str
    score: float
    is_correct: bool
    feedback: Optional[str] = None

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


def test_normalize_response_json_string2(llm_action_node):
    # 测试JSON字符串输入
    json_input = r'''
    ```json
{
    "feedback": "The provided function implementation generally follows the instructions and addresses the problem context effectively. However, there are a few areas that could be improved for clarity and correctness:\n\n1. **Variable Naming**: The variable `total_needed` is not used in the logic. It might be clearer to directly use `number + need` in the comparison.\n2. **Edge Cases**: The function does not explicitly handle the edge cases where `need` is 0 or `remaining` is 0. While the logic implicitly covers these cases, it would be better to explicitly mention them in the comments or handle them separately.\n3. **Clarity in Logic**: The logic could be slightly simplified by directly comparing `remaining` with `need` without calculating `total_needed` separately.\n\nSuggested Improvement:\n```python\ndef eat(number, need, remaining):\n    # Calculate the total number of carrots eaten\n    if remaining >= need:\n        total_eaten = number + need\n        carrots_left = remaining - need\n    else:\n        total_eaten = number + remaining\n        carrots_left = 0\n    \n    # Return the result\n    return [total_eaten, carrots_left]\n```\n\nThis version simplifies the logic and makes it clearer by directly comparing `remaining` with `need`.",
    "correct": true,
    "score": 0.9
}
```
    '''

    result = llm_action_node.normalize_response(json_input)
    # 验证返回的是提取并格式化后的JSON字符串
    assert isinstance(result, str)
    # 确保可以被解析回JSON对象
    parsed_result = json.loads(result)
    assert "feedback" in parsed_result
    assert "correct" in parsed_result
    assert "score" in parsed_result
    assert parsed_result["correct"] is True
    assert parsed_result["score"] == 0.9
def test_normalize_response_json_string3(llm_action_node):
    # 测试JSON字符串输入
    json_input = r'''
    ```json
{
    "feedback": "a\(\)",
    "correct": true,
    "score": 0.9
}
```
    '''

    result = llm_action_node.normalize_response(json_input)
    # 验证返回的是提取并格式化后的JSON字符串
    assert isinstance(result, str)
    # 确保可以被解析回JSON对象
    print(result)
    parsed_result = json.loads(result)
    assert "feedback" in parsed_result
    assert "correct" in parsed_result
    assert "score" in parsed_result
    assert parsed_result["correct"] is True
    assert parsed_result["score"] == 0.9

# def test_normalize_response_json_string4(llm_action_node):
#     # 测试JSON字符串输入
#     json_input = r'''
#     ```json
# {
#     "feedback": "abc"xx"def",
#     "correct": true,
#     "score": 0.9
# }
# ```
#     '''
#
#     result = llm_action_node.normalize_response(json_input)
#     # 验证返回的是提取并格式化后的JSON字符串
#     assert isinstance(result, str)
#     # 确保可以被解析回JSON对象
#     print(result)
#     parsed_result = json.loads(result)
#     assert "feedback" in parsed_result
#     assert "correct" in parsed_result
#     assert "score" in parsed_result
#     assert parsed_result["correct"] is True
#     assert parsed_result["score"] == 0.9

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

def test_normalize_response_complex_json(llm_action_node):
    # 测试包含详细反馈、正确性和分数的复杂 JSON 响应
    complex_json = {
        "feedback": "The provided function implementation is generally correct...",
        "correct": True,
        "score": 0.9
    }
    
    result = llm_action_node.normalize_response(complex_json)
    assert isinstance(result, dict)
    assert "feedback" in result
    assert "correct" in result
    assert "score" in result
    assert isinstance(result["feedback"], str)
    assert isinstance(result["correct"], bool)
    assert isinstance(result["score"], (int, float))
    assert result["correct"] is True
    assert result["score"] == 0.9

def test_normalize_response_nested_json_string(llm_action_node):
    # 测试嵌套引号的 JSON 字符串输入
    nested_json = r'''```json
{
    "feedback": "The provided function implementation generally follows the instructions and addresses the problem context effectively. However, there are a few areas that could be improved for clarity and correctness:\n\n1. **Variable Naming**: The variable `total_needed` is not used in the logic. It might be clearer to directly use `number + need` in the comparison.\n2. **Edge Cases**: The function does not explicitly handle the edge cases where `need` is 0 or `remaining` is 0. While the logic implicitly covers these cases, it would be better to explicitly mention them in the comments or handle them separately.\n3. **Clarity in Logic**: The logic could be slightly simplified by directly comparing `remaining` with `need` without calculating `total_needed` separately.\n\nSuggested Improvement:\n```python\ndef eat(number, need, remaining):\n    # Calculate the total number of carrots eaten\n    if remaining >= need:\n        total_eaten = number + need\n        carrots_left = remaining - need\n    else:\n        total_eaten = number + remaining\n        carrots_left = 0\n    \n    # Return the result\n    return [total_eaten, carrots_left]\n```\n\nThis version simplifies the logic and makes it clearer by directly comparing `remaining` with `need`.",
    "correct": true,
    "score": 0.9
}
```'''
    
    result = llm_action_node.normalize_response(nested_json)
    # 验证返回的是提取并格式化后的JSON字符串
    print(result)
    result = json.loads(result)
    assert isinstance(result, dict)
    assert "feedback" in result
    assert "correct" in result
    assert "score" in result
    # 确保内部的代码块被正确保留
    assert "```python" in result["feedback"]
    assert result["correct"] is True
    assert result["score"] == 0.9

def test_normalize_response_starts_with_brace(llm_action_node):
    # 测试以 { 开头的 JSON 字符串输入
    json_input = '''{
        "process": [
            "Step 1: Analysis",
            "Step 2: Implementation"
        ],
        "feedback": "Good implementation",
        "correct": true,
        "score": 1
    }'''
    
    result = llm_action_node.normalize_response(json_input)
    # 验证返回的是提取并格式化后的JSON字符串
    assert isinstance(result, str)
    # 确保可以被解析回JSON对象
    parsed_result = json.loads(result)
    assert "process" in parsed_result
    assert "feedback" in parsed_result
    assert parsed_result["correct"] is True
    assert parsed_result["score"] == 1

