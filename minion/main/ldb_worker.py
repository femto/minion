#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/3/21
@Author  : femto Zheng
@File    : ldb_worker.py
"""
from typing import List, Optional, Union, Literal
import dataclasses
from openai import OpenAI
from transformers import GPT2Tokenizer
from random import choice

from minion.main.check import TestMinion
from minion.main.check_route import register_check_minion
from minion.main.minion import register_worker_minion, register_improver_minion
from minion.main.worker import WorkerMinion
from minion.utils.syncheck import get_output

try:
    from generators.py_generate import PyGenerator
    from generators.model import ModelBase, Message


    # Add these new classes
    MessageRole = Literal["system", "user", "assistant"]


    @dataclasses.dataclass()
    class Message:
        role: MessageRole
        content: str


    class OpenaiChat(ModelBase):
        def __init__(self, model_name: str, api_key: str = "", base_url = ""):
            self.name = model_name
            self.is_chat = True
            self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
            if api_key != "":
                self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            else:
                self.client = OpenAI()

        def change_messages(self, messages, max_len):
            if isinstance(messages, str):
                message_lines = messages.split("\n")
                acc_msg_len = 0
                new_messages = ""
                for l in reversed(message_lines):
                    acc_msg_len += len(self.tokenizer.tokenize(l))
                    if acc_msg_len < max_len:
                        new_messages = l + "\n" + new_messages
                    else:
                        break
                new_messages = new_messages.strip()
                return new_messages
            else:
                original_messages = messages
                new_messages = messages[:1]
                total_msg_len = len(self.tokenizer.tokenize(messages[0].content))
                rest_messages = []
                for msg in reversed(messages[1:]):
                    msg_len = len(self.tokenizer.tokenize(msg.content))
                    if msg_len + total_msg_len < max_len:
                        rest_messages = [msg] + rest_messages
                        total_msg_len += msg_len
                    else:
                        break
                messages = new_messages + rest_messages
            return messages

        def generate_chat(self, messages: List[Message], stop: List[str] = None,
                          max_tokens: int = 1024, temperature: float = 0.0,
                          num_comps: int = 1) -> Union[List[str], str]:
            try:
                new_messages = self.change_messages(messages, 3097)
                messages = new_messages
                response = self.client.chat.completions.create(
                    model=self.name,
                    messages=[dataclasses.asdict(message) for message in messages],
                    temperature=temperature,
                    top_p=1,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    n=num_comps,
                    stop=stop
                )
            except Exception as e:
                print("GPT Error:", str(e))
                if "context_length_exceeded" in str(e):
                    messages = self.change_messages(messages, 2097)
                    print("AFTER CHANGE MESSAGE LEN:", len(messages))
                    print(messages)
                    response = self.client.chat.completions.create(
                        model=self.name,
                        messages=[dataclasses.asdict(message) for message in messages],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=1,
                        frequency_penalty=0.0,
                        presence_penalty=0.0,
                        n=num_comps,
                    )
                else:
                    assert False, "GPT API error: " + str(e)
            if num_comps == 1:
                return response.choices[0].message.content
            return [choice.message.content for choice in response.choices]

    HAS_LDB = True
except ImportError:
    HAS_LDB = False

if HAS_LDB:
    @register_worker_minion
    class LdbMinion(WorkerMinion):
        """LDB (LLM Debugger) Strategy - Uses LDB to generate and debug code"""

        def __init__(self, **kwargs):
            if not HAS_LDB:
                raise ImportError("LDB (PyGenerator) is not installed. Please install it first.")
            super().__init__(**kwargs)
            
            # 使用OpenaiChat替代ModelBase
            self.model = OpenaiChat(self.brain.llm.config.model, api_key=self.brain.llm.config.api_key, base_url=self.brain.llm.config.base_url)
            self.generator = PyGenerator()

    class LdbBaseMinion(TestMinion):
        def __init__(self, **kwargs):
            if not HAS_LDB:
                raise ImportError("LDB (PyGenerator) is not installed. Please install it first.")
            super().__init__(**kwargs)

            # 使用OpenaiChat替代ModelBase
            self.model = OpenaiChat(self.brain.llm.config.model, api_key=self.brain.llm.config.api_key,
                                    base_url=self.brain.llm.config.base_url)
            self.generator = PyGenerator()

        def _get_actual_output(self, test_code, func_impl):
            """运行测试代码并获取实际输出"""
            try:
                return get_output(func_impl, test_code, 5)
            except Exception as e:
                return str(e)

        def _convert_to_ldb_format(self, test_result, func_impl):
            """将测试结果转换为LDB格式"""
            test = test_result['test']
            # 获取实际运行输出
            actual_output = self._get_actual_output(test, func_impl)
            return f"{test} # Real Execution Output: {actual_output}"

    @register_check_minion
    class LdbCheckMinion(LdbBaseMinion):
        """LDB (LLM Debugger) Strategy - Uses LDB to generate and debug code"""

        async def execute(self):
            await super().execute()
            
            # 获取测试结果
            test_results = self.answer.get('test_results', [])
            failed_tests = [result for result in test_results if not result['passed']]
            
            if not failed_tests:
                self.answer = self.input.feedback = {
                    "feedback": "",
                    "correct": True,
                    "score": 1.0
                }
                return self.answer
                
            # 先随机选择一个失败的测试用例
            selected_failed_test = choice(failed_tests)
            
            # 获取当前函数实现
            func_impl = self.input.answer if self.input.answer else None
            
            # 将选中的测试用例转换为LDB格式
            ldb_format_test = self._convert_to_ldb_format(selected_failed_test, func_impl)
            
            # 设置调试所需参数
            messages: List[Message] = []
            func_sig = self.input.query

            # 使用LDB进行调试
            messages = self.generator.ldb_debug(
                prompt=func_sig,
                prev_func_impl=func_impl,
                failed_test=ldb_format_test,  # 使用转换后的选中测试用例
                entry=self.input.entry_point,
                model=self.model,
                messages=messages,
                dataset_type=self.input.dataset, #todo: this dataset type is just for prompt
                level="block"
            )
            self.input.metadata["messages"] = messages
            self.input.metadata["ldb_format_test"] = ldb_format_test
            self.input.improve_route = "ldb_improve"

            self.answer = self.input.feedback = {
                "feedback": f"failed {ldb_format_test}",
                "correct": False,
                "score": 0.0
            }
            return self.answer

        @register_improver_minion
        class LdbImproveMinion(LdbBaseMinion):
            """LDB (LLM Debugger) Strategy - Uses LDB to generate and debug code"""

            async def execute(self):
                # 获取当前函数实现
                func_impl = self.input.answer if self.input.answer else None

                # 设置调试所需参数
                messages = self.input.metadata["messages"]
                func_sig = self.input.query

                # 生成代码
                answer, messages = self.generator.ldb_generate(
                    func_sig=func_sig,
                    model=self.model,
                    messages=messages,
                    prev_func_impl=func_impl or "",
                    failed_tests=self.input.metadata["ldb_format_test"] ,
                    num_comps=1,
                    temperature=self.brain.llm.config.temperature,
                    dataset_type=self.input.dataset #todo: this dataset type is just for prompt
                )

                self.answer = answer

                return self.answer