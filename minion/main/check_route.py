from typing import Dict, Any, Type
from jinja2 import Template
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import Minion
from minion.models.schemas import MetaPlan
from minion.utils.utils import most_similar_minion, camel_case_to_snake_case
from minion.logs import logger

# Registry for check minions
CHECK_MINION_REGISTRY = {
    # "check": CheckMinion,
    # "test": TestMinion,
    # "doctest": DoctestMinion
}

# Template for choosing appropriate checker
CHECK_ROUTE_PROMPT = """You are helping to choose the most appropriate checker minion for verifying a solution.
The available checker minions are:

{% for name, minion in minions.items() %}
- {{name}}: {{minion.__doc__ or "No description available"}}
{% endfor %}

The input has the following properties:
- Query: {{input.query}}
- Solution type: {{input.query_type}}
{% if input.metadata and input.metadata.get('test_cases') %}
- Has test cases: Yes
{% else %}
- Has test cases: No
{% endif %}
{% if input.answer and ">>>" in input.answer %}
- Has doctests: Yes
{% else %}
- Has doctests: No
{% endif %}

Given these details, which checker minion would be most appropriate? Consider:
1. If there are explicit test cases, test is preferred
2. If the solution contains doctests, doctest is preferred
3. For general verification without specific test cases, check is used

Return JSON in this format:
{
    "name": "chosen minion name",
    "reason": "brief explanation of why this minion was chosen"
}

Analyze the situation and make your choice:"""


class CheckRouterMinion(Minion):
    """Router for selecting appropriate check minions"""

    # def __init__(self,**kwargs):
    #     super().__init__(**kwargs):

    async def choose_checker(self):
        """Choose appropriate checker based on input characteristics"""
        try:
            # Prepare template with registered minions
            choose_template = Template(CHECK_ROUTE_PROMPT)
            filled_template = choose_template.render(
                minions=CHECK_MINION_REGISTRY,
                input=self.input
            )

            # Get recommendation from LLM
            node = LmpActionNode(self.brain.llm)
            meta_plan = await node.execute(filled_template, response_format=MetaPlan)

            # Find closest matching minion name
            checker_name = meta_plan.name
            checker_name = most_similar_minion(checker_name, CHECK_MINION_REGISTRY.keys())

            logger.info(
                f"Selected checker: {checker_name}, Reason: {meta_plan.reason if hasattr(meta_plan, 'reason') else 'Not provided'}")

            # Get checker class
            checker_class = CHECK_MINION_REGISTRY.get(checker_name, CHECK_MINION_REGISTRY.get("check"))

            return checker_class

        except Exception as e:
            logger.error(f"Error in checker selection: {e}")
            # Fall back to default CheckMinion
            return CHECK_MINION_REGISTRY.get("check")

    async def execute(self, check_count=1):
        """Execute chosen checker specified number of times"""
        checker_class = await self.choose_checker()

        for iteration in range(check_count):
            checker = checker_class(input=self.input, brain=self.brain)
            result = await checker.execute()

            if result and result.get("correct", False):
                return result

        return result  # Return last result if no successful check


def register_check_minion(cls=None, *, name=None):
    """Decorator to register check minions.
    Can be used as @register_check_minion or @register_check_minion(name="custom_name")

    Args:
        cls: The class to register (when used as @register_check_minion)
        name: Optional custom name (when used as @register_check_minion(name="custom_name"))
    """

    def decorator(cls):
        # Use custom name if provided, otherwise convert class name to snake_case
        register_name = name if name is not None else camel_case_to_snake_case(cls.__name__)
        CHECK_MINION_REGISTRY[register_name] = cls
        return cls

    # Handle both @register_check_minion and @register_check_minion(name="custom_name")
    if cls is None:
        return decorator
    return decorator(cls)