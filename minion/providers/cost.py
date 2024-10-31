from typing import List

from pydantic import BaseModel

from minion.utils.model_price import get_model_price
from minion.utils.token_counter import num_tokens_from_messages


class CostManager(BaseModel):
    total_cost: float = 0.0
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def update_cost(self, prompt_tokens: int, completion_tokens: int, model: str):
        price_info = get_model_price(model)

        if price_info:
            new_prompt_cost = prompt_tokens * price_info["prompt"]
            new_completion_cost = completion_tokens * price_info["completion"]

            self.prompt_cost += new_prompt_cost
            self.completion_cost += new_completion_cost
            self.total_cost = self.prompt_cost + self.completion_cost

        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    @staticmethod
    def calculate(messages: List[dict], completion_tokens: int, model: str) -> tuple[int, int]:
        """计算API调用的token数量"""
        prompt_tokens = num_tokens_from_messages(messages, model)
        return prompt_tokens, completion_tokens