from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import uuid
import logging

from .code_agent import CodeAgent
from ..main.input import Input
from minion.types.agent_response import AgentResponse

logger = logging.getLogger(__name__)

@dataclass
class StateCodeAgent(CodeAgent):
    """
    State-aware Code Agent with Conversation Management
    
    This agent combines:
    - Code-based reasoning from CodeAgent (smolagents-style)
    - Persistent state management across sessions
    - Conversation history tracking
    - Reset capability for state management (reset=True/False)
    """
    
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    persistent_state: Dict[str, Any] = field(default_factory=dict)
    auto_save_state: bool = True
    conversation_context_limit: int = 10  # Limit conversation history for context
    
    def __post_init__(self):
        """Initialize the conversational agent with code capabilities."""
        super().__post_init__()
        
        # Initialize persistent state if empty
        if not self.persistent_state:
            self.persistent_state = {
                'initialized_at': str(uuid.uuid4()),
                'conversation_count': 0,
                'variables': {},
                'memory_store': {},
                'learned_patterns': []
            }
    
    async def run_async(self, input_data: Input, reset: bool = False, **kwargs) -> Any:
        """
        Run the agent with state management and reset capability.
        
        Args:
            input_data: Input data for the agent
            reset: If True, reset the agent state before execution
            **kwargs: Additional parameters
            
        Returns:
            Agent response with conversation context
        """
        # Handle reset functionality
        if reset:
            self.reset_state()
            logger.info("Agent state has been reset")
        
        # Update conversation context in input
        enhanced_input = self._add_conversation_context(input_data)
        
        # Prepare state with persistent information
        state = kwargs.get('state', {})
        state.update(self.persistent_state)
        state['conversation_history'] = self.get_recent_history()
        kwargs['state'] = state
        
        # Execute the step with enhanced input and state
        try:
            result = await super().run_async(enhanced_input, **kwargs)
            
            # Record this interaction
            await self._record_interaction(input_data, result, reset)
            
            # Auto-save state if enabled
            if self.auto_save_state:
                self._save_persistent_state(state)
            
            return result
            
        except Exception as e:
            logger.error(f"Conversational agent execution failed: {e}")
            # Still record the failed interaction
            await self._record_interaction(input_data, f"Error: {e}", reset)
            raise
    
    def reset_state(self) -> None:
        """
        Reset agent state similar to smolagents.
        
        This clears:
        - Conversation history
        - Working variables
        - Temporary memory
        But preserves:
        - Learned patterns
        - Core configuration
        """
        # Clear conversation history
        self.conversation_history = []
        
        # Reset session ID
        self.session_id = str(uuid.uuid4())
        
        # Reset working state but preserve learned patterns
        learned_patterns = self.persistent_state.get('learned_patterns', [])
        self.persistent_state = {
            'initialized_at': str(uuid.uuid4()),
            'conversation_count': 0,
            'variables': {},
            'memory_store': {},
            'learned_patterns': learned_patterns  # Preserve learned patterns
        }
        
        # Reset code executor state if available
        if self.python_executor:
            if hasattr(self.python_executor, 'reset'):
                self.python_executor.reset()
        
        logger.info("Agent state reset completed")
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current agent state including conversation and persistent state.
        
        Returns:
            Complete state dictionary
        """
        return {
            'conversation_history': self.conversation_history,
            'persistent_state': self.persistent_state,
            'session_id': self.session_id,
            'conversation_count': len(self.conversation_history) // 2,  # Approximate turns
        }
    
    def load_state(self, state: Dict[str, Any]) -> None:
        """
        Load agent state from dictionary.
        
        Args:
            state: State dictionary to load
        """
        if 'conversation_history' in state:
            self.conversation_history = state['conversation_history']
        
        if 'persistent_state' in state:
            self.persistent_state = state['persistent_state']
        
        if 'session_id' in state:
            self.session_id = state['session_id']
        
        logger.info(f"Agent state loaded with {len(self.conversation_history)} conversation entries")
    
    def _add_conversation_context(self, input_data: Input) -> Input:
        """Add conversation context to input for better continuity."""
        
        # Get recent conversation for context
        recent_history = self.get_recent_history(limit=self.conversation_context_limit)
        
        if not recent_history:
            return input_data
        
        # Format conversation context
        context_lines = []
        for entry in recent_history:
            role = entry['role'].upper()
            content = str(entry['content'])[:200]  # Limit content length
            context_lines.append(f"{role}: {content}")
        
        conversation_context = "\n".join(context_lines)
        
        # Enhanced query with conversation context
        enhanced_query = f"""**Conversation Context:**
{conversation_context}

**Current Request:**
{input_data.query}

**Instructions:**
- Consider the conversation context when responding
- Maintain consistency with previous interactions
- Use any relevant information from the conversation history
- If variables or results from previous steps are relevant, reference them in your code
"""
        
        return Input(
            query=enhanced_query,
            route=getattr(input_data, 'route', None) or 'code',
            check=getattr(input_data, 'check', False),
            dataset=getattr(input_data, 'dataset', None),
            metadata=getattr(input_data, 'metadata', {})
        )
    
    async def _record_interaction(self, input_data: Input, result: Any, was_reset: bool) -> None:
        """Record the interaction in conversation history."""
        # Record user input
        self.add_to_history("user", input_data.query)
        
        # Record system response
        if isinstance(result, AgentResponse):
            response_content = result.final_answer or result.response
        else:
            response_content = str(result)
        
        self.add_to_history("assistant", response_content)
        
        # Add reset indicator if state was reset
        if was_reset:
            self.add_to_history("system", "State was reset before this interaction")
        
        # Update conversation count in persistent state
        self.persistent_state['conversation_count'] = len(self.conversation_history) // 2
    
    def _save_persistent_state(self, current_state: Dict[str, Any]) -> None:
        """Save relevant information to persistent state."""
        # Extract variables from execution state
        variables = {}
        for key, value in current_state.items():
            if key.startswith('code_result_'):
                variables[key] = value
        
        if variables:
            self.persistent_state['variables'].update(variables)
        
        # Save any learned patterns or insights
        if 'learned_patterns' in current_state:
            self.persistent_state['learned_patterns'].extend(current_state['learned_patterns'])
    
    def get_recent_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        if limit is None:
            return self.conversation_history
        return self.conversation_history[-limit:] if self.conversation_history else []
    
    def clear_history(self) -> None:
        """Clear conversation history while preserving persistent state."""
        self.conversation_history = []
        self.session_id = str(uuid.uuid4())
        logger.info("Conversation history cleared")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get complete conversation history."""
        return self.conversation_history
    
    def add_to_history(self, role: str, content: Any) -> None:
        """
        Add entry to conversation history.
        
        Args:
            role: Role (user, assistant, system)
            content: Content of the message
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": str(uuid.uuid4())[:8]  # Short timestamp
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation and usage statistics."""
        return {
            'total_conversations': self.persistent_state.get('conversation_count', 0),
            'current_session_messages': len(self.conversation_history),
            'session_id': self.session_id,
            'variables_stored': len(self.persistent_state.get('variables', {})),
            'patterns_learned': len(self.persistent_state.get('learned_patterns', [])),
            'auto_save_enabled': self.auto_save_state
        } 