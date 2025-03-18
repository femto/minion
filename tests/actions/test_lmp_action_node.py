import pytest
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.worker import IdentifyMinion
from minion.schema.message_types import Message
from minion.schema.messages import user, system
from minion.models.schemas import Answer
from minion.providers import create_llm_provider
from minion.configs.config import config
from minion.main.input import Input
from jinja2 import Template
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
import json

# 定义测试用的 Pydantic model
class TestResponse(BaseModel):
    message: str
    items: List[str]
    score: Optional[float] = None

class TestXMLResponse(BaseModel):
    message: str
    score: float
    is_correct: bool
    feedback: Optional[str] = None

@pytest.fixture
def lmp_action_node():
    llm = create_llm_provider(config.models.get("default"))
    return LmpActionNode(llm=llm)

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_string(lmp_action_node):
    result = await lmp_action_node.execute("Tell me a short joke.")

    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_message(lmp_action_node):
    result = await lmp_action_node.execute("What's the capital of France?")
    assert isinstance(result, str)
    assert "Paris" in result

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_message_list(lmp_action_node):
    messages = [
        system("You are a helpful assistant."),
        user("What's 2 + 2?")
    ]
    result = await lmp_action_node.execute(messages)
    assert isinstance(result, str)
    assert "4" in result

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_output_parser(lmp_action_node):
    lmp_action_node.output_parser = lambda x: x.upper()
    result = await lmp_action_node.execute("Say hello.")
    assert isinstance(result, str)
    assert result.isupper()

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_kwargs(lmp_action_node):
    result = await lmp_action_node.execute("Tell me a color.", temperature=0.7, max_tokens=10)
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_choose_mind(lmp_action_node):
    minds = {
        "left_mind": {
            "id": "left_mind",
            "description": "I'm the left mind, adept at logical reasoning and analytical thinking."
        },
        "right_mind": {
            "id": "right_mind",
            "description": "I'm the right mind, flourishing in creative and artistic tasks."
        },
        "hippocampus_mind": {
            "id": "hippocampus_mind",
            "description": "I'm the hippocampus mind, specializing in memory formation, organization, and retrieval."
        }
    }

    input_data = Input(query="What is the square root of 144?", query_type="math")

    mind_template = Template(
        """
I have minds:
{% for mind in minds.values() %}
1. **ID:** {{ mind.id }}  
   **Description:** 
   "{{ mind.description }}"
{% endfor %}
According to the current user's query, 
which is of query type: {{ input.query_type }},
and user's query: {{ input.query }}
help me choose the right mind to process the query.
return the id of the mind, please note you *MUST* return exactly case same as I provided here, do not uppercase or downcase yourself.
"""
    )

    filled_template = mind_template.render(minds=minds, input=input_data)

    # Execute the node with the filled template
    result = await lmp_action_node.execute_answer(filled_template)
    # Validate the result
    assert result in minds.keys(), f"Expected one of {minds.keys()}, but got {result}"
    assert result == "left_mind", f"Expected 'left_mind' for a math question, but got {result}"

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_lmp_action_node_with_response_format(lmp_action_node):
    # 执行节点
    result = await lmp_action_node.execute("List 3 fruits", response_format=TestResponse)
    
    # 验证结果是否符合预期格式
    assert isinstance(result, TestResponse)
    assert isinstance(result.message, str)
    assert isinstance(result.items, list)
    assert len(result.items) == 3

# async def test_lmp_action_node_without_response_format():
#     # 测试不设置 response_format 的情况
#     node = LMPActionNode(
#         name="test_node",
#         system_prompt="You are a helpful assistant",
#         user_prompt="List 3 fruits"
#     )
#
#     # 执行节点
#     result = await node.execute()
#
#     # 验证结果是字符串
#     assert isinstance(result, str)

# 添加新的 fixture 用于 identify minion 测试
@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.llm = create_llm_provider(config.models.get("default"))
    return brain

@pytest.fixture
def mock_input():
    input_obj = Input(query="What is 2+2?")
    return input_obj

# 添加 IdentifyMinion 相关的测试用例
@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_lmp_identify_execute(mock_brain, mock_input):
    # Mock identification response
    mock_identification = {
        "complexity": "simple",
        "query_range": "basic_math",
        "difficulty": "easy",
        "field": "mathematics",
        "subfield": "arithmetic"
    }
    
    # Create and execute IdentifyMinion
    minion = IdentifyMinion(brain=mock_brain, input=mock_input)
    result = await minion.execute()
    
    # Verify the result
    assert result == "identified the input query"

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_lmp_identify_invalid_response(mock_brain, mock_input):
    # Mock invalid JSON response
    mock_brain.llm.execute = AsyncMock(return_value="invalid json")
    
    # Create IdentifyMinion
    minion = IdentifyMinion(brain=mock_brain, input=mock_input)
    
    # Test that invalid JSON raises an error
    with pytest.raises(json.JSONDecodeError):
        await minion.execute()

def test_simple_xml_to_json(lmp_action_node):
    # 测试简单XML格式的响应，包含特殊字符
    xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<message>Test < with special > characters</message>
<score>88.5</score>
<is_correct>true</is_correct>
<feedback>Good job! Here's some code: if (x < 10) { return true; }</feedback>'''
    
    result = lmp_action_node._simple_xml_to_json(TestXMLResponse, xml_response)
    assert isinstance(result, str)
    parsed_result = json.loads(result)
    assert parsed_result["message"] == "Test < with special > characters"
    assert parsed_result["score"] == 88.5
    assert parsed_result["is_correct"] is True
    assert parsed_result["feedback"] == "Good job! Here's some code: if (x < 10) { return true; }"

def test_simple_xml_to_json_without_declaration(lmp_action_node):
    # 测试没有XML声明的响应
    xml_response = '''<message>Simple message</message>
<score>75.0</score>
<is_correct>false</is_correct>
<feedback>Test feedback</feedback>'''
    
    result = lmp_action_node._simple_xml_to_json(TestXMLResponse, xml_response)
    assert isinstance(result, str)
    parsed_result = json.loads(result)
    assert parsed_result["message"] == "Simple message"
    assert parsed_result["score"] == 75.0
    assert parsed_result["is_correct"] is False
    assert parsed_result["feedback"] == "Test feedback"

@pytest.mark.asyncio
async def test_execute_with_xml_format(lmp_action_node):
    xml_response = '''```xml
<?xml version="1.0" encoding="UTF-8"?>
<message>Test message</message>
<score>95.5</score>
<is_correct>true</is_correct>
<feedback>Good job!</feedback>
```'''
    
    async def mock_execute(*args, **kwargs):
        return xml_response
    
    lmp_action_node.execute = mock_execute
    
    result = await lmp_action_node.execute(
        "test message",
        response_format=TestXMLResponse,
        format="xml_simple"
    )
    #result = lmp_action_node._simple_xml_to_json(TestXMLResponse, result)
    
    # assert isinstance(result, TestXMLResponse)
    # assert result.message == "Test message"
    # assert result.score == 95.5
    # assert result.is_correct is True
    # assert result.feedback == "Good job!"

@pytest.mark.asyncio
async def test_execute_with_xml_special_chars(lmp_action_node):
    xml_response = '''```xml
<?xml version="1.0" encoding="UTF-8"?>
<message>Test with < and > chars</message>
<score>92.5</score>
<is_correct>true</is_correct>
<feedback>Code example: if (x < 10) { return true; }</feedback>
```'''
    
    async def mock_execute(*args, **kwargs):
        return xml_response
    
    lmp_action_node.execute = mock_execute
    
    result = await lmp_action_node.execute(
        "test message",
        response_format=TestXMLResponse,
        format="xml_simple"
    )
    
    result = lmp_action_node._simple_xml_to_json(TestXMLResponse, result)

