import logging
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI, AzureOpenAI
from abc import ABC, abstractmethod

from minion.main.prompt import ASK_PROMPT
from minion.main.worker import WorkerMinion
from minion.utils.answer_extraction import extract_final_answer


class OptillmMinion(WorkerMinion):
    async def execute(self):
        context = {"messages": [{"role": "user", "content": ASK_PROMPT.format(input=self.input)}]}
        response = await self.execute_action(self.llm_action, context)
        self.answer = self.input.answer = extract_final_answer(response)
        self.raw_answer = self.input.answer_raw = response
        return self.answer

class CotReflectionMinion(OptillmMinion):
    """Chain of Thought with Reflection implementation"""
    
    def process(self, system_prompt: str, initial_query: str) -> Tuple[str, int]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please think through this step by step:\n{initial_query}"}
        ]
        
        # First pass - thinking
        thinking_response, tokens1 = self._call_llm(messages)
        
        # Reflection pass
        reflection_prompt = f"Let's reflect on this reasoning:\n{thinking_response}"
        messages.append({"role": "assistant", "content": thinking_response})
        messages.append({"role": "user", "content": reflection_prompt})
        
        reflection_response, tokens2 = self._call_llm(messages)
        
        # Final output
        final_response = f"<thinking>{thinking_response}</thinking>\n<reflection>{reflection_response}</reflection>\n<output>{reflection_response}</output>"
        
        return final_response, tokens1 + tokens2

class PlanSearchMinion(OptillmMinion):
    """Plan Search implementation"""
    
    def process(self, system_prompt: str, initial_query: str) -> Tuple[str, int]:
        messages = [
            {"role": "system", "content": f"{system_prompt}\nGenerate and evaluate multiple solution plans."},
            {"role": "user", "content": initial_query}
        ]
        
        response, tokens = self._call_llm(messages)
        return response, tokens

class SelfConsistencyMinion(OptillmMinion):
    """Self Consistency implementation"""
    
    def __init__(self, client: Any, model: str, num_samples: int = 3):
        super().__init__(client, model)
        self.num_samples = num_samples
        
    def process(self, system_prompt: str, initial_query: str) -> Tuple[str, int]:
        total_tokens = 0
        responses = []
        
        for _ in range(self.num_samples):
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": initial_query}
            ]
            response, tokens = self._call_llm(messages)
            responses.append(response)
            total_tokens += tokens
            
        # Simple majority voting for consistency
        final_response = max(set(responses), key=responses.count)
        return final_response, total_tokens

# Additional minion classes can be implemented similarly for other approaches...
