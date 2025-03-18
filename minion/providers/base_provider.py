from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional, Any, Generator


from minion.configs.config import LLMConfig, config
from minion.logs import logger
from minion.schema.message_types import Message
from minion.providers.cost import CostManager


class BaseProvider(ABC):
    """Base class for all LLM providers"""
    
    def __init__(self, config: Any) -> None:
        self.config = config
        self.cost_manager = CostManager()
        self._setup_retry_config()
        self.generate_sync = self.retry_decorator(self.generate_sync)
        self.generate = self.retry_decorator(self.generate)
        self.generate_stream = self.retry_decorator(self.generate_stream)
        self._setup()


    @abstractmethod
    def _setup(self) -> None:
        """Setup the LLM provider with configuration"""
        pass

    def _setup_retry_config(self):
        from tenacity import retry_if_exception_type
        from openai import APIError, APIConnectionError
        from tenacity import retry
        from tenacity import stop_after_attempt
        from tenacity import wait_exponential

        from openai import RateLimitError
        from openai import APITimeoutError
        from openai import InternalServerError
        retryable_errors = (
            RateLimitError,  # 429 - 速率限制，可以重试
            APIConnectionError,  # 网络连接问题
            APITimeoutError,  # 超时
            InternalServerError  # 5xx 服务器错误
        )

        from tenacity import before_sleep_log
        import logging
        self.retry_decorator = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type(retryable_errors),
            before_sleep=before_sleep_log(logger, logging.WARN)
        )

    @abstractmethod
    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages"""
        pass

    @abstractmethod
    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Generator[str, None, str]:
        """Generate streaming completion from messages"""
        pass

    @abstractmethod
    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages synchronously"""
        pass

    def get_cost(self) -> CostManager:
        return self.cost_manager


def main():
    # 假设配置文件中有一个名为 "deepseek-chat" 的模型配置
    llm_config = config.models.get("deepseek-chat")
    if not llm_config:
        print("Configuration for 'deepseek-chat' not found.")
        return

    try:
        from minion.providers import create_llm_provider
        llm = create_llm_provider(llm_config)
        print("Created LLM provider:", llm)
        # 使用 llm 进行生成或流式生成
    except ValueError as e:
        print(f"Error creating LLM provider: {e}")


if __name__ == "__main__":
    main()
