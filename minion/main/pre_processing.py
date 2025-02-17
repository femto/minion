from typing import Dict, Any
from minion.main.minion import Minion, register_pre_processing_minion
from minion.main.prompt import PROBLEM_REFLECT_PROMPT, EXAMPLE_REASONING_PROMPT
from minion.actions.lmp_action_node import LmpActionNode
from jinja2 import Template
from minion.logs import logger

class PreProcessingMinion(Minion):
    """Base class for all pre-processing minions"""
    pass

@register_pre_processing_minion
class ProblemReflectMinion(PreProcessingMinion):
    """Minion that performs problem reflection before solving"""
    
    async def execute(self):
        """Execute the problem reflection process"""
        prompt = Template(PROBLEM_REFLECT_PROMPT)
        prompt = prompt.render(input=self.input)
        
        node = LmpActionNode(self.brain.llm)
        reflection = await node.execute(prompt)
        
        # Store reflection in input metadata for later use
        self.input.info["problem_reflection"] = reflection
        
        logger.info(f"Problem reflection completed: {reflection}")
        return reflection 

@register_pre_processing_minion
class ExampleReasoningMinion(PreProcessingMinion):
    """Minion that analyzes and reasons about examples in the query"""
    
    async def execute(self):
        """Execute the example reasoning process"""
        # Check if the input contains examples
        if not self._has_examples():
            logger.info("No examples found in the input, skipping example reasoning")
            return None
            
        prompt = Template(EXAMPLE_REASONING_PROMPT)
        prompt = prompt.render(input=self.input)
        
        node = LmpActionNode(self.brain.llm)
        reasoning = await node.execute(prompt)

        self.input.info["example_reasoning"] = reasoning

        logger.info(f"Example reasoning completed: {reasoning}")
        return reasoning
    
    def _has_examples(self) -> bool:
        """Check if the input contains examples"""
        # This can be implemented with more complex example detection logic as needed
        return 'example' in self.input.query.lower() or 'examples' in self.input.query.lower()