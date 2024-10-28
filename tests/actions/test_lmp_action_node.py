import pytest
from minion.actions.lmp_action_node import LmpActionNode
from minion.message_types import Message
from minion.providers import create_llm_provider
from minion.configs.config import config
from minion.main.input import Input
from jinja2 import Template
from pydantic import BaseModel
from typing import List, Optional

# 定义测试用的 Pydantic model
class TestResponse(BaseModel):
    message: str
    items: List[str]
    score: Optional[float] = None

@pytest.fixture
def lmp_action_node():
    llm = create_llm_provider(config.models.get("default"))
    #llm = create_llm_provider(config.models.get("o1-mini"))
    #llm = create_llm_provider(config.models.get("gpt-4o-mini"))
    llm = create_llm_provider(config.models.get("llama2"))
    return LmpActionNode(llm=llm)

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_string(lmp_action_node):
    result = await lmp_action_node.execute("Tell me a short joke.")

    assert isinstance(result, str)
    assert len(result) > 0

# @pytest.mark.llm_integration
# @pytest.mark.asyncio
# async def test_execute_with_message(lmp_action_node):
#     result = await lmp_action_node.execute("What's the capital of France?")
#     assert isinstance(result, str)
#     assert "Paris" in result
#
# @pytest.mark.llm_integration
# @pytest.mark.asyncio
# async def test_execute_with_message_list(lmp_action_node):
#     messages = [
#         Message(role="system", content="You are a helpful assistant."),
#         Message(role="user", content="What's 2 + 2?")
#     ]
#     result = await lmp_action_node.execute(messages)
#     assert isinstance(result, str)
#     assert "4" in result
#
# @pytest.mark.llm_integration
# @pytest.mark.asyncio
# async def test_execute_with_output_parser(lmp_action_node):
#     lmp_action_node.output_parser = lambda x: x.upper()
#     result = await lmp_action_node.execute("Say hello.")
#     assert isinstance(result, str)
#     assert result.isupper()
#
# @pytest.mark.llm_integration
# @pytest.mark.asyncio
# async def test_execute_with_kwargs(lmp_action_node):
#     result = await lmp_action_node.execute("Tell me a color.", temperature=0.7, max_tokens=10)
#     assert isinstance(result, str)
#     assert len(result) > 0

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

    result = await lmp_action_node.execute(filled_template)

    assert result in minds.keys(), f"Expected one of {minds.keys()}, but got {result}"
    assert result == "left_mind", f"Expected 'left_mind' for a math question, but got {result}"

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_lmp_action_node_with_response_format(lmp_action_node):

    # 执行节点
    result = await lmp_action_node.execute("List 3 fruits",response_format=TestResponse)
    
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
