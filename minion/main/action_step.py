#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ActionStep implementation for streaming support
Based on smolagents ActionStep but adapted for minion
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncIterator
import time
import uuid

from minion.types.agent_response import AgentResponse


@dataclass
class StreamChunk:
    """单个流式输出块"""
    content: str
    chunk_type: str = "text"  # text, tool_call, observation, error
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActionStep:
    """
    表示 Agent 执行的一个步骤，支持流式输出
    类似 smolagents 的 ActionStep 但适配 minion
    """
    step_number: int
    step_type: str = "action"  # action, planning, tool_call, observation
    
    # 输入相关
    input_query: Optional[str] = None
    input_messages: Optional[List[Dict]] = None
    
    # 输出相关
    output_content: str = ""
    output_chunks: List[StreamChunk] = field(default_factory=list)
    
    # 工具调用相关
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None
    
    # 状态相关
    is_streaming: bool = False
    is_complete: bool = False
    is_final_answer: bool = False
    
    # 错误处理
    error: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def add_chunk(self, chunk: StreamChunk):
        """添加流式输出块"""
        self.output_chunks.append(chunk)
        self.output_content += chunk.content
        
    def mark_complete(self):
        """标记步骤完成"""
        self.is_complete = True
        self.is_streaming = False
        
    def to_agent_response(self) -> AgentResponse:
        """转换为 AgentResponse"""
        return AgentResponse(
            raw_response=self.output_content,
            answer=self.output_content,
            score=1.0 if not self.error else 0.0,
            terminated=self.is_final_answer,
            truncated=False,
            is_final_answer=self.is_final_answer,
            info={
                'step_id': self.step_id,
                'step_number': self.step_number,
                'step_type': self.step_type,
                'tool_calls': self.tool_calls,
                'tool_results': self.tool_results,
                'chunks_count': len(self.output_chunks),
                'metadata': self.metadata
            },
            error=self.error
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'step_id': self.step_id,
            'step_number': self.step_number,
            'step_type': self.step_type,
            'input_query': self.input_query,
            'output_content': self.output_content,
            'chunks_count': len(self.output_chunks),
            'tool_calls': self.tool_calls,
            'tool_results': self.tool_results,
            'is_streaming': self.is_streaming,
            'is_complete': self.is_complete,
            'is_final_answer': self.is_final_answer,
            'error': self.error,
            'metadata': self.metadata,
            'timestamp': self.timestamp
        }


class StreamingActionManager:
    """管理流式 ActionStep 的类"""
    
    def __init__(self):
        self.current_step: Optional[ActionStep] = None
        self.steps: List[ActionStep] = []
        self.step_counter = 0
    
    def start_step(self, step_type: str = "action", input_query: str = "", **kwargs) -> ActionStep:
        """开始新的步骤"""
        self.step_counter += 1
        
        self.current_step = ActionStep(
            step_number=self.step_counter,
            step_type=step_type,
            input_query=input_query,
            is_streaming=True,
            **kwargs
        )
        
        self.steps.append(self.current_step)
        return self.current_step
    
    def add_chunk_to_current(self, content: str, chunk_type: str = "text", **metadata):
        """向当前步骤添加流式块"""
        if self.current_step:
            chunk = StreamChunk(
                content=content,
                chunk_type=chunk_type,
                metadata=metadata
            )
            self.current_step.add_chunk(chunk)
    
    def complete_current_step(self, is_final_answer: bool = False):
        """完成当前步骤"""
        if self.current_step:
            self.current_step.is_final_answer = is_final_answer
            self.current_step.mark_complete()
    
    async def stream_step_generator(self, step: ActionStep) -> AsyncIterator[StreamChunk]:
        """为步骤生成流式输出"""
        for chunk in step.output_chunks:
            yield chunk
    
    def get_step_summary(self) -> List[Dict[str, Any]]:
        """获取所有步骤的摘要"""
        return [step.to_dict() for step in self.steps]
    
    def get_latest_step(self) -> Optional[ActionStep]:
        """获取最新的步骤"""
        return self.steps[-1] if self.steps else None