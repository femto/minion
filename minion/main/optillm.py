import logging
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI, AzureOpenAI
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class OptillmMinion(ABC):
    """Base class for all Optillm optimization approaches"""
    
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model
        
    @abstractmethod
    def process(self, system_prompt: str, initial_query: str) -> Tuple[str, int]:
        """
        Process the input using specific optimization approach
        
        Args:
            system_prompt: The system prompt
            initial_query: The user query
            
        Returns:
            Tuple[str, int]: (processed response, completion tokens used)
        """
        pass
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> Tuple[str, int]:
        """Helper method to call LLM with proper error handling"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content, response.usage.completion_tokens
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

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
