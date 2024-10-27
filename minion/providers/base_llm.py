from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

from minion.configs.config import LLMConfig, config
from minion.message_types import Message
from minion.providers.cost import CostManager


class BaseLLM(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config
        self.cost_manager = CostManager()
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """初始化具体的LLM客户端"""
        pass

    @abstractmethod
    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """生成回复"""
        pass

    @abstractmethod
    async def generate_stream(
        self, messages: List[Message], temperature: Optional[float] = None, **kwargs
    ) -> AsyncIterator[str]:
        """流式生成回复"""
        pass

    def get_cost(self) -> CostManager:
        return self.cost_manager


def main():
    # 打印已注册的提供者
    print("Registered providers:", LLMRegistry._providers)

    # 确保至少有一个提供者被注册
    if not LLMRegistry._providers:
        print("No providers registered. Make sure to import the provider modules.")
        return

    # 假设配置文件中有一个名为 "deepseek-chat" 的模型配置
    llm_config = config.models.get("deepseek-chat")
    if not llm_config:
        print("Configuration for 'deepseek-chat' not found.")
        return

    try:
        llm = create_llm_provider(llm_config)
        print("Created LLM provider:", llm)
        # 使用 llm 进行生成或流式生成
    except ValueError as e:
        print(f"Error creating LLM provider: {e}")


if __name__ == "__main__":
    main()
