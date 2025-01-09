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
            # First check worker_config
            if self.worker_config and self.worker_config.get('check_route', None):
                checker_name = self.worker_config['check_route']
                if checker_name in CHECK_MINION_REGISTRY:
                    logger.info(f"Using checker from worker config: {checker_name}")
                    return CHECK_MINION_REGISTRY[checker_name]
                else:
                    logger.warning(f"Specified checker {checker_name} in worker_config not found, falling back to default")
                    return CHECK_MINION_REGISTRY.get("check")

            # Then check input.check_route
            if hasattr(self.input, 'check_route') and self.input.check_route:
                checker_name = self.input.check_route
                if checker_name in CHECK_MINION_REGISTRY:
                    logger.info(f"Using checker from input.check_route: {checker_name}")
                    return CHECK_MINION_REGISTRY[checker_name]
                else:
                    logger.warning(f"Specified checker {checker_name} in input.check_route not found, falling back to default")
                    return CHECK_MINION_REGISTRY.get("check")

            # Prepare template for LLM recommendation
            choose_template = Template(CHECK_ROUTE_PROMPT)
            filled_template = choose_template.render(
                minions=CHECK_MINION_REGISTRY,
                input=self.input
            )

            # Try using check_route specific LLMs first
            if hasattr(self.brain, 'llms'):
                # First try check_route specific LLMs
                if 'check_route' in self.brain.llms:
                    for llm in self.brain.llms['check_route']:
                        try:
                            node = LmpActionNode(llm)
                            meta_plan = await node.execute(filled_template, response_format=MetaPlan)
                            checker_name = meta_plan.name
                            if checker_name in CHECK_MINION_REGISTRY:
                                logger.info(f"Selected checker using check_route LLM {llm.config.model}: {checker_name}")
                                return CHECK_MINION_REGISTRY[checker_name]
                            else:
                                logger.warning(f"Recommended checker {checker_name} not found, trying next LLM")
                                continue
                        except Exception as e:
                            logger.warning(f"Failed to get checker using check_route LLM {llm.config.model}: {str(e)}")
                            continue

                # If check_route LLMs fail, try route LLMs
                if 'route' in self.brain.llms:
                    for llm in self.brain.llms['route']:
                        try:
                            node = LmpActionNode(llm)
                            meta_plan = await node.execute(filled_template, response_format=MetaPlan)
                            checker_name = meta_plan.name
                            if checker_name in CHECK_MINION_REGISTRY:
                                logger.info(f"Selected checker using route LLM {llm.config.model}: {checker_name}")
                                return CHECK_MINION_REGISTRY[checker_name]
                            else:
                                logger.warning(f"Recommended checker {checker_name} not found, trying next LLM")
                                continue
                        except Exception as e:
                            logger.warning(f"Failed to get checker using route LLM {llm.config.model}: {str(e)}")
                            continue

                logger.warning("All configured LLMs failed to recommend a valid checker, falling back to default brain.llm")

            # If no specific LLMs configured or all failed, use default brain.llm
            try:
                node = LmpActionNode(self.brain.llm)
                meta_plan = await node.execute(filled_template, response_format=MetaPlan)
                checker_name = meta_plan.name
                if checker_name in CHECK_MINION_REGISTRY:
                    logger.info(f"Selected checker using default brain.llm: {checker_name}")
                    return CHECK_MINION_REGISTRY[checker_name]
                else:
                    logger.warning(f"Recommended checker {checker_name} not found, falling back to default check")
            except Exception as e:
                logger.error(f"Error getting recommendation from default brain.llm: {e}")

            # If all attempts fail, fall back to default CheckMinion
            logger.info("Falling back to default check minion")
            return CHECK_MINION_REGISTRY.get("check")

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