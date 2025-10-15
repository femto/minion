"""
Agent State Types

This module defines strongly-typed state classes for agents to replace
the weakly-typed Dict[str, Any] approach.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from ..main.input import Input


class AgentState(BaseModel):
    """
    Base agent state with strongly typed fields.
    
    This replaces the weakly-typed Dict[str, Any] state to provide:
    - Type safety
    - Clear field definitions
    - IDE autocompletion
    - Better documentation
    - Built-in serialization/deserialization via Pydantic
    """
    
    # Core execution state
    history: List[Any] = Field(default_factory=list, description="Execution history")
    step_count: int = Field(default=0, description="Number of steps executed")
    error_count: int = Field(default=0, description="Number of errors encountered")
    
    # Task and input
    task: Optional[str] = Field(default=None, description="Task description")
    input: Optional[Input] = Field(default=None, description="Current input object")
    
    # Completion state
    is_final_answer: bool = Field(default=False, description="Whether final answer is reached")
    final_answer_value: Optional[Any] = Field(default=None, description="Final answer value")
    
    # Confidence and reflection
    last_confidence: float = Field(default=1.0, description="Confidence score of last step")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        arbitrary_types_allowed = True  # Allow Input and other custom types
    
    def reset(self) -> None:
        """Reset the state to initial values."""
        self.history = []
        self.step_count = 0
        self.error_count = 0
        self.task = None
        self.input = None
        self.is_final_answer = False
        self.final_answer_value = None
        self.last_confidence = 1.0
        self.metadata = {}


class CodeAgentState(AgentState):
    """
    Extended state for CodeAgent with code execution specific fields.
    """
    
    # Code execution results
    code_results: Dict[str, Any] = Field(default_factory=dict, description="Code execution results")
    code_logs: Dict[str, str] = Field(default_factory=dict, description="Code execution logs")
    code_final_answers: Dict[str, bool] = Field(default_factory=dict, description="Code final answer flags")
    
    # Reflection state
    reflection_count: int = Field(default=0, description="Number of reflections performed")
    last_reflection_step: int = Field(default=0, description="Step number of last reflection")
    
    def reset(self) -> None:
        """Reset including code-specific fields."""
        super().reset()
        self.code_results = {}
        self.code_logs = {}
        self.code_final_answers = {}
        self.reflection_count = 0
        self.last_reflection_step = 0
    
    def add_code_result(self, index: int, output: Any, logs: str, is_final_answer: bool) -> None:
        """Add code execution result."""
        self.code_results[f'code_result_{index}'] = output
        self.code_logs[f'code_logs_{index}'] = logs
        self.code_final_answers[f'is_final_answer_{index}'] = is_final_answer
    
    def get_code_result(self, index: int) -> tuple[Any, str, bool]:
        """Get code execution result by index."""
        output = self.code_results.get(f'code_result_{index}')
        logs = self.code_logs.get(f'code_logs_{index}', '')
        is_final_answer = self.code_final_answers.get(f'is_final_answer_{index}', False)
        return output, logs, is_final_answer