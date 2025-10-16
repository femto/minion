#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent State Aware Tool Base Class

This module provides a base class for tools that need access to agent state,
input, brain, and other agent context information.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
from .base_tool import BaseTool

if TYPE_CHECKING:
    from ..agents.base_agent import BaseAgent
    from ..main.input import Input
    from ..main.brain import Brain


class AgentStateAwareTool(BaseTool):
    """
    Base class for tools that need access to agent state and context.
    
    This class provides convenient methods to access:
    - Agent state (strongly typed AgentState object)
    - Input object
    - Brain instance
    - Agent instance itself
    
    Tools inheriting from this class will automatically receive agent context
    when used within an agent execution.
    """
    
    # Flag to indicate this tool needs state
    needs_state = True
    
    def __init__(self):
        super().__init__()
        self._agent_context = None
    
    def get_agent_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the current agent state.
        
        Returns:
            Dict containing agent state, or None if not available
        """
        if hasattr(self, '_agent_context') and self._agent_context:
            agent = self._agent_context
            if hasattr(agent, 'state'):
                # Convert AgentState to dict for backward compatibility
                state = agent.state
                if hasattr(state, 'model_dump'):
                    # Pydantic model
                    return state.model_dump()
                elif hasattr(state, 'dict'):
                    # Pydantic v1 model
                    return state.dict()
                elif isinstance(state, dict):
                    return state
                else:
                    # Convert object attributes to dict
                    return {
                        key: getattr(state, key) 
                        for key in dir(state) 
                        if not key.startswith('_') and not callable(getattr(state, key))
                    }
        return None
    
    def get_agent(self) -> Optional['BaseAgent']:
        """
        Get the agent instance.
        
        Returns:
            BaseAgent instance, or None if not available
        """
        if hasattr(self, '_agent_context') and self._agent_context:
            return self._agent_context
        return None
    
    def get_input(self) -> Optional['Input']:
        """
        Get the current input object.
        
        Returns:
            Input object, or None if not available
        """
        agent = self.get_agent()
        if agent and hasattr(agent, 'state') and agent.state:
            return getattr(agent.state, 'input', None)
        return None
    
    def get_brain(self) -> Optional['Brain']:
        """
        Get the brain instance.
        
        Returns:
            Brain instance, or None if not available
        """
        agent = self.get_agent()
        if agent and hasattr(agent, 'brain'):
            return agent.brain
        return None
    
    def get_task(self) -> Optional[str]:
        """
        Get the current task description.
        
        Returns:
            Task string, or None if not available
        """
        agent_state = self.get_agent_state()
        if agent_state:
            return agent_state.get('task')
        return None
    
    def get_step_count(self) -> int:
        """
        Get the current step count.
        
        Returns:
            Step count, or 0 if not available
        """
        agent_state = self.get_agent_state()
        if agent_state:
            return agent_state.get('step_count', 0)
        return 0
    
    def get_history(self) -> list:
        """
        Get the execution history.
        
        Returns:
            List of history items, or empty list if not available
        """
        agent_state = self.get_agent_state()
        if agent_state:
            return agent_state.get('history', [])
        return []
    
    def is_final_answer(self) -> bool:
        """
        Check if the agent has reached a final answer.
        
        Returns:
            True if final answer is reached, False otherwise
        """
        agent_state = self.get_agent_state()
        if agent_state:
            return agent_state.get('is_final_answer', False)
        return False
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get the agent state metadata.
        
        Returns:
            Metadata dict, or empty dict if not available
        """
        agent_state = self.get_agent_state()
        if agent_state:
            return agent_state.get('metadata', {})
        return {}
    
    def _discover_agent_context(self) -> Optional['BaseAgent']:
        """
        Discover agent context from the current execution environment.
        This method attempts to find the agent instance that's currently executing.
        
        Returns:
            BaseAgent instance if found, None otherwise
        """
        # The agent context should be set by the agent's tool wrapping mechanism
        return getattr(self, '_agent_context', None)
    
    def _set_agent_context(self, agent: 'BaseAgent') -> None:
        """
        Set the agent context (used internally by the agent framework).
        
        Args:
            agent: The BaseAgent instance to set as context
        """
        self._agent_context = agent