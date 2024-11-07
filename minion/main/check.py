import doctest
import inspect
import re
import xml.etree.ElementTree as ET
from io import StringIO

from jinja2 import Template

from minion.logs import logger
from minion.main.check_route import register_check_minion
from minion.main.minion import Minion
from minion.main.prompt import CHECK_PROMPT, ASK_PROMPT
from minion.actions.lmp_action_node import LmpActionNode
from minion.models.schemas import CheckResult


def extract_root_content(text):
    pattern = r"(<root>.*?</root>)"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def extract_feedback_parts(xml_string):
    try:
        # Create a file-like object from the string
        xml_string = extract_root_content(xml_string)
        xml_file = StringIO(xml_string)

        # Parse the XML
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Extract feedback content
        feedback_content = root.find("feedback").text.strip()

        # Extract correctness and convert to boolean
        correct_text = root.find("correct").text.lower()
        correct = correct_text.lower() == "true"

        # Extract score and convert to float
        score = float(root.find("score").text)

        return {"feedback_content": feedback_content, "correct": correct, "score": score}
    except Exception as e:
        logger.error(e)
        return None

@register_check_minion
class CheckMinion(Minion):
    """Check Minion"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to verify this answer"

    async def execute(self):
        for _ in range(3):
            prompt = Template(CHECK_PROMPT)
            prompt = prompt.render(input=self.input)
            
            node = LmpActionNode(self.brain.llm)
            result = await node.execute(prompt, response_format=CheckResult)
            
            self.answer_node = result
            self.answer = self.input.feedback = {
                "feedback": result.feedback,
                "correct": result.correct,
                "score": result.score
            }
            
            if result:
                return self.answer

@register_check_minion
class TestMinion(CheckMinion):
    """Test Minion for verifying code solutions with test cases"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.test_cases = []

    async def execute(self):
        if not self.input.metadata.get('test_cases'):
            return await super().execute()
            
        self.test_cases = self.input.metadata['test_cases']
        prompt = Template(CHECK_PROMPT)
        context = {
            'input': self.input,
            'test_cases': self.test_cases,
            'test_type': 'test'
        }
        prompt = prompt.render(**context)
        
        return await self._execute_test(prompt)

    async def _execute_test(self, prompt):
        """Execute test logic"""
        node = LmpActionNode(self.brain.llm)
        result = await node.execute(prompt, response_format=CheckResult)
        
        self.answer_node = result
        self.answer = self.input.feedback = {
            "feedback": result.feedback,
            "correct": result.correct,
            "score": result.score,
            "test_results": result.test_results if hasattr(result, 'test_results') else None
        }
        
        return self.answer

@register_check_minion
class DoctestMinion(CheckMinion):
    """Test Minion for verifying code solutions with doctest examples"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.test_cases = self.extract_doctest(self.input.answer)

    def extract_doctest(self, query):
        """Extract test cases from docstring"""
        parser = doctest.DocTestParser()
        doctests = []
        tests = parser.get_examples(query)
        doctests.extend(tests)
        return doctests

    async def execute(self):
        if not self.test_cases:
            return await super().execute()
            
        prompt = Template(CHECK_PROMPT)
        context = {
            'input': self.input,
            'test_cases': self.test_cases,
            'test_type': 'doctest'
        }
        prompt = prompt.render(**context)
        
        return await self._execute_test(prompt)

    async def _execute_test(self, prompt):
        """Execute test logic"""
        node = LmpActionNode(self.brain.llm)
        result = await node.execute(prompt, response_format=CheckResult)
        
        self.answer_node = result
        self.answer = self.input.feedback = {
            "feedback": result.feedback,
            "correct": result.correct,
            "score": result.score,
            "test_results": result.test_results if hasattr(result, 'test_results') else None
        }
        
        return self.answer


class ScoreMinion(CheckMinion):
    async def execute(self):
        node = LmpActionNode(self.brain.llm)
        score = await node.execute_answer(
            ASK_PROMPT + "\nanswer:\n{input.answer}".format(input=self.input)
        )
        return float(score)