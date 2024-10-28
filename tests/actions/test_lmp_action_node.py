import pytest
from minion.actions.lmp_action_node import LmpActionNode
from minion.message_types import Message
from minion.providers import create_llm_provider
from minion.configs.config import config
from minion.main.input import Input
from jinja2 import Template



@pytest.fixture
def lmp_action_node():
    llm = create_llm_provider(config.models.get("default"))
    #llm = create_llm_provider(config.models.get("o1-mini"))
    #llm = create_llm_provider(config.models.get("gpt-4o-mini"))
    return LmpActionNode(llm=llm)

@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_execute_with_string(lmp_action_node):
    #result = await lmp_action_node.execute("Tell me a short joke.")
    result = await lmp_action_node.execute("""推导E[X∣Y=y]在连续情况下,
E[X∣Y=y]的公式是否是定义的，而不是推导的,
离散情况下如何，E[X∣Y=y]的公式是推导出来的还是定义出来的?""")
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
