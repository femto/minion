from typing import List

from pydantic import BaseModel

from minion.utils.model_price import get_model_price
from minion.utils.token_counter import num_tokens_from_messages


class CostManager(BaseModel):
    total_cost: float = 0.0
    total_prompt_cost: float = 0.0
    total_completion_cost: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    def update_cost(self, prompt_tokens: int, completion_tokens: int, model: str):
        price_info = get_model_price(model)

        if price_info:
            new_prompt_cost = prompt_tokens * price_info["prompt"] 
            new_completion_cost = completion_tokens * price_info["completion"]

            self.total_prompt_cost += new_prompt_cost
            self.total_completion_cost += new_completion_cost
            self.total_cost = self.total_prompt_cost + self.total_completion_cost

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

    def reset(self):
        """重置所有成本指标为零"""
        self.total_cost = 0.0
        self.total_prompt_cost = 0.0
        self.total_completion_cost = 0.0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    @staticmethod
    def calculate(messages: List[dict], completion_tokens: int, model: str) -> tuple[int, int]:
        """计算API调用的token数量"""
        prompt_tokens = num_tokens_from_messages(messages, model)
        return prompt_tokens, completion_tokens
