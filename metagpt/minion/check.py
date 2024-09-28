import re
import xml.etree.ElementTree as ET
from io import StringIO

from jinja2 import Template

from metagpt.actions.action_node import ActionNode
from metagpt.logs import logger
from metagpt.minion.minion import Minion
from metagpt.minion.prompt import CHECK_PROMPT


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
            node = ActionNode(
                key="answer", expected_type=str, instruction="let's think step by step", example="", schema="raw"
            )
            prompt = Template(CHECK_PROMPT)
            prompt = prompt.render(input=self.input)
            node = await node.fill(context=prompt, llm=self.brain.llm)
            self.answer_node = node
            result = extract_feedback_parts(node.content)
            self.answer = self.input.feedback = result
            if result:
                return self.answer  # maybe also adds score?
