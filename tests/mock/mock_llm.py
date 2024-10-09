import json
from typing import Optional, Union

from metagpt.config2 import config
from metagpt.configs.llm_config import LLMType
from metagpt.logs import logger
from metagpt.provider.azure_openai_api import AzureOpenAILLM
from metagpt.provider.constant import GENERAL_FUNCTION_SCHEMA
from metagpt.provider.openai_api import OpenAILLM
from metagpt.schema import Message

OriginalLLM = OpenAILLM if config.llm.api_type == LLMType.OPENAI else AzureOpenAILLM


class MockLLM(OriginalLLM):
    def __init__(self, allow_open_api_call):
        """Initialize the LLMTestAdapter object.
        
        Args:
            allow_open_api_call (bool): Flag to allow or disallow open API calls.
        
        Returns:
            None: This method initializes the object and doesn't return anything.
        """
        original_llm_config = (
            config.get_openai_llm() if config.llm.api_type == LLMType.OPENAI else config.get_azure_llm()
        )
        super().__init__(original_llm_config)
        self.allow_open_api_call = allow_open_api_call
        self.rsp_cache: dict = {}
        self.rsp_candidates: list[dict] = []  # a test can have multiple calls with the same llm, thus a list

    async def acompletion_text(self, messages: list[dict], stream=False, timeout=3) -> str:
        """Overwrite original acompletion_text to cancel retry"""
        if stream:
            resp = await self._achat_completion_stream(messages, timeout=timeout)
            return resp

        rsp = await self._achat_completion(messages, timeout=timeout)
        return self.get_choice_text(rsp)

    async def original_aask(
        """Asynchronously generates a response based on the given message and optional parameters.
        
        Args:
            msg Union[str, list[dict[str, str]]]: The main message or list of message dictionaries to process.
            system_msgs Optional[list[str]]: Optional list of system messages to include.
            format_msgs Optional[list[dict[str, str]]]: Optional list of formatting message dictionaries.
            images Optional[Union[str, list[str]]]: Optional image(s) to include with the message.
            timeout int: The timeout duration for the request in seconds. Defaults to 3.
            stream bool: Whether to stream the response. Defaults to True.
        
        Returns:
            str: The generated response text.
        """        self,
        msg: Union[str, list[dict[str, str]]],
        system_msgs: Optional[list[str]] = None,
        format_msgs: Optional[list[dict[str, str]]] = None,
        images: Optional[Union[str, list[str]]] = None,
        timeout=3,
        stream=True,
    ) -> str:
        if system_msgs:
            message = self._system_msgs(system_msgs)
        else:
            message = [self._default_system_msg()]
        if not self.use_system_prompt:
            message = []
        if format_msgs:
            message.extend(format_msgs)
        if isinstance(msg, str):
            message.append(self._user_msg(msg, images=images))
        else:
            message.extend(msg)
        logger.debug(message)
        rsp = await self.acompletion_text(message, stream=stream, timeout=timeout)
        return rsp

    async def original_aask_batch(self, msgs: list, timeout=3) -> str:
        """A copy of metagpt.provider.base_llm.BaseLLM.aask_batch, we can't use super().aask because it will be mocked"""
        context = []
        for msg in msgs:
            umsg = self._user_msg(msg)
            context.append(umsg)
            rsp_text = await self.acompletion_text(context, timeout=timeout)
            context.append(self._assistant_msg(rsp_text))
        return self._extract_assistant_rsp(context)

    async def original_aask_code(self, messages: Union[str, Message, list[dict]], **kwargs) -> dict:
        """Asynchronously asks a question and returns the response.
        
        Args:
            msg Union[str, list[dict[str, str]]]: The message to be sent, either as a string or a list of dictionaries.
            system_msgs Optional[list[str]]: Optional list of system messages to be prepended to the conversation.
            format_msgs Optional[list[dict[str, str]]]: Optional list of formatting messages.
            images Optional[Union[str, list[str]]]: Optional image(s) to be included in the message.
            timeout int: The timeout for the request in seconds. Defaults to 3.
            stream bool: Whether to stream the response. Defaults to True.
        
        Returns:
            str: The response from the model.
        """
        """
        A copy of metagpt.provider.openai_api.OpenAILLM.aask_code, we can't use super().aask because it will be mocked.
        Since openai_api.OpenAILLM.aask_code is different from base_llm.BaseLLM.aask_code, we use the former.
        """
        if "tools" not in kwargs:
            configs = {"tools": [{"type": "function", "function": GENERAL_FUNCTION_SCHEMA}]}
            kwargs.update(configs)
        rsp = await self._achat_completion_function(messages, **kwargs)
        return self.get_choice_function_arguments(rsp)

    async def aask(
        self,
        msg: Union[str, list[dict[str, str]]],
        system_msgs: Optional[list[str]] = None,
        format_msgs: Optional[list[dict[str, str]]] = None,
        images: Optional[Union[str, list[str]]] = None,
        timeout=3,
        stream=True,
    ) -> str:
        # used to identify it a message has been called before
        if isinstance(msg, list):
            msg_key = "#MSG_SEP#".join([m["content"] for m in msg])
        else:
            msg_key = msg
"""Asynchronously process a batch of messages and return a response.

Args:
    msgs (list): A list of messages to process. Each message can be a string or an object with a 'content' attribute.
    timeout (int, optional): The maximum time to wait for a response, in seconds. Defaults to 3.
"""Asynchronously asks for code generation based on given messages.

Args:
    messages (Union[str, Message, list[dict]]): The input messages for code generation. Can be a string, Message object, or a list of dictionaries.
    **kwargs: Additional keyword arguments to be passed to the original ask_code method.
"""Mocks the response for a given message key.

Args:
    msg_key (str): The key to identify the message in the response cache.
    ask_func (callable): The original function to call if the message key is not in the cache.
    *args: Variable length argument list to pass to ask_func.
    **kwargs: Arbitrary keyword arguments to pass to ask_func.

Returns:
    Any: The mocked or actual response.

Raises:
    ValueError: If api call is not allowed and the message key is not in the cache.
"""

Returns:
    dict: The response containing the generated code.
"""

Returns:
    str: The response generated from processing the batch of messages.
"""

        if system_msgs:
            joined_system_msg = "#MSG_SEP#".join(system_msgs) + "#SYSTEM_MSG_END#"
            msg_key = joined_system_msg + msg_key
        rsp = await self._mock_rsp(msg_key, self.original_aask, msg, system_msgs, format_msgs, images, timeout, stream)
        return rsp

    async def aask_batch(self, msgs: list, timeout=3) -> str:
        msg_key = "#MSG_SEP#".join([msg if isinstance(msg, str) else msg.content for msg in msgs])
        rsp = await self._mock_rsp(msg_key, self.original_aask_batch, msgs, timeout)
        return rsp

    async def aask_code(self, messages: Union[str, Message, list[dict]], **kwargs) -> dict:
        msg_key = json.dumps(self.format_msg(messages), ensure_ascii=False)
        rsp = await self._mock_rsp(msg_key, self.original_aask_code, messages, **kwargs)
        return rsp

    async def _mock_rsp(self, msg_key, ask_func, *args, **kwargs):
        if msg_key not in self.rsp_cache:
            if not self.allow_open_api_call:
                raise ValueError(
                    "In current test setting, api call is not allowed, you should properly mock your tests, "
                    "or add expected api response in tests/data/rsp_cache.json. "
                    f"The prompt you want for api call: {msg_key}"
                )
            # Call the original unmocked method
            rsp = await ask_func(*args, **kwargs)
        else:
            logger.warning("Use response cache")
            rsp = self.rsp_cache[msg_key]
        self.rsp_candidates.append({msg_key: rsp})
        return rsp
