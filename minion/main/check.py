import doctest
import inspect
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


class TestMinion(CheckMinion):
    """Test Minion for verifying code solutions with test cases"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.test_cases = []

    def extract_doctest(self, query):
        """Extract test cases from docstring"""

        parser = doctest.DocTestParser()
        doctests = []

        tests = parser.get_examples(query)
        doctests.extend(tests)

        return doctests

        # # 使用非贪婪匹配和分组来捕获多行输出
        # doctest_pattern = r'>>>\s*(.*?)\n\s*([\'"].*?[\'"]|\{[\s\S]*?\}|\[.*?\]|.*?)\n(?=\s*(?:>>>|\Z|[^\s]))'
        # matches = re.findall(doctest_pattern, query)
        #
        # def process_output(output):
        #     output = output.strip()
        #
        #     # 如果输出已经带有引号，直接返回
        #     if (output.startswith('"') and output.endswith('"')) or \
        #        (output.startswith("'") and output.endswith("'")):
        #         return output
        #
        #     # 处理列表
        #     if output.startswith('[') and output.endswith(']'):
        #         return output
        #
        #     # 处理多行字典
        #     if output.startswith('{') and output.endswith('}'):
        #         # 保持原始缩进和换行
        #         lines = output.splitlines()
        #         if len(lines) > 1:
        #             # 对于多行字典，保持原始格式
        #             return output
        #         return output.strip()
        #
        #     # 如果输出包含换行符，保持原格式
        #     if '\n' in output:
        #         return output.rstrip()
        #
        #     # 如果输出是数字，不加引号
        #     if output.replace('.', '').replace('-', '').isdigit():
        #         return output
        #
        #     # 其他情况，添加单引号
        #     return f"'{output}'"
        #
        # return [f"assert {m[0]} == {process_output(m[1])}" for m in matches]

    async def execute(self):
        # First try to get test cases from input
        self.test_cases = self.input.metadata.get('test_cases', [])
        
        # If no test cases provided, try to extract from doctest
        if not self.test_cases and self.input.query:
            self.test_cases = self.extract_doctest(self.input.query)
        
        # If still no test cases, use default checking logic
        if not self.test_cases:
            return await super().execute()
            
        return await self._check_with_tests()

    async def _check_with_tests(self):
        prompt = Template(CHECK_PROMPT)
        context = {
            'input': self.input,
            'test_cases': self.test_cases
        }
        prompt = prompt.render(**context)
        
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