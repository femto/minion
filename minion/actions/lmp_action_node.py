from typing import Any, Union, List, Optional, Type
from pydantic import BaseModel

import ell

from minion.configs.config import config
from minion.message_types import Message
from minion.actions.action_node import LLMActionNode
from minion.providers import create_llm_provider

class LmpActionNode(LLMActionNode):
    def __init__(self, llm, output_parser=None):
        super().__init__(llm, output_parser)
        ell.init(**config.ell, default_client=self.llm.client_ell)

    @ell.complex(model="gpt-4o-mini")
    def ell_call(self, ret):
        """You are a helpful assistant."""
        return ret

    async def execute(self, messages: Union[str, Message, List[Message]], **kwargs) -> Any:
        # 从 llm.config 获取配置
        api_params = {
            # "api_type": self.llm.config.api_type,
            # "api_key": self.llm.config.api_key,
            # "base_url": self.llm.config.base_url,
            "temperature": self.llm.config.temperature,
            "model": self.llm.config.model,
            "stream": True
        }
        
        # 将 kwargs 合并到 api_params 中，允许覆盖默认值
        api_params.update(kwargs)
        
        response = self.ell_call(messages, client=self.llm.client_ell, api_params=api_params)
        response = response.text

        if self.output_parser:
            return self.output_parser(response)

        return response
