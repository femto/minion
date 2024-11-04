import re
import xml.etree.ElementTree as ET
from io import StringIO

from jinja2 import Template

from minion.logs import logger
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

class ScoreMinion(CheckMinion):
    async def execute(self):
        node = LmpActionNode(self.brain.llm)
        score = await node.execute_answer(
            ASK_PROMPT + "\nanswer:\n{input.answer}".format(input=self.input)
        )
        return float(score)