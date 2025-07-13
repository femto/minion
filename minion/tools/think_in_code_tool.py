#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Think in Code Meta工具
支持agent内部思考和推理
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from .agent_state_aware_tool import AgentStateAwareTool

class ThinkInCodeTool(AgentStateAwareTool):
    """
    内部思考工具 - 支持agent在代码执行中进行思考和推理
    
    特点：
    1. 记录思考历史
    2. 分析思考模式
    3. 更新agent记忆（如果可用）
    4. 对LLM透明，但在代码中可调用
    """
    
    name = "think_in_code"
    description = "Internal thinking and reasoning tool for agent self-reflection"
    inputs = {
        "thought": {
            "type": "string", 
            "description": "Current thought or reasoning step"
        },
        "context": {
            "type": "object", 
            "description": "Optional context information for the thought",
            "required": False
        },
        "priority": {
            "type": "string",
            "description": "Thought priority: low, medium, high, critical",
            "required": False
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.thought_history = []
        self.insights = []
        
    async def forward(self, 
                     thought: str, 
                     context: Optional[Dict] = None, 
                     priority: str = "medium") -> Dict[str, Any]:
        """
        执行内部思考
        
        Args:
            thought: 思考内容
            context: 上下文信息
            priority: 优先级
            
        Returns:
            思考结果和建议
        """
        # 创建思考记录
        thought_entry = {
            "id": len(self.thought_history) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "thought": thought,
            "context": context or {},
            "priority": priority,
            "agent_state": self._extract_relevant_state(),
        }
        
        # 记录思考历史
        self.thought_history.append(thought_entry)
        
        # 分析思考模式
        analysis = await self._analyze_thought(thought, context, priority)
        
        # 更新agent记忆（如果可用）
        await self._update_agent_memory(thought_entry, analysis)
        
        # 生成建议
        suggestions = self._generate_suggestions(analysis)
        
        return {
            "thinking_complete": True,
            "thought_id": thought_entry["id"],
            "timestamp": thought_entry["timestamp"],
            "analysis": analysis,
            "suggestions": suggestions,
            "total_thoughts": len(self.thought_history)
        }
    
    def _extract_relevant_state(self) -> Dict[str, Any]:
        """提取相关的agent状态信息"""
        if not self._agent_context:
            return {}
        
        state_info = {}
        
        # 从Input获取信息
        input_obj = self.get_input()
        if input_obj:
            state_info.update({
                "query_type": getattr(input_obj, 'query_type', None),
                "mind_id": getattr(input_obj, 'mind_id', None),
                "query_length": len(getattr(input_obj, 'query', '')),
            })
        
        # 从Brain获取信息
        brain = self.get_brain()
        if brain:
            state_info.update({
                "available_tools": len(getattr(brain, 'tools', [])),
                "has_memory": hasattr(brain, 'mem') and brain.mem is not None,
            })
        
        # 从state获取信息
        agent_state = self.get_agent_state()
        if agent_state:
            state_info.update({
                "step_count": agent_state.get('step_count', 0),
                "history_length": len(agent_state.get('history', [])),
                "has_errors": any('error' in str(h).lower() for h in agent_state.get('history', [])),
            })
        
        return state_info
    
    async def _analyze_thought(self, thought: str, context: Optional[Dict], priority: str) -> Dict[str, Any]:
        """分析思考内容和模式"""
        analysis = {
            "thought_type": self._classify_thought_type(thought),
            "complexity": self._assess_complexity(thought, context),
            "emotional_tone": self._analyze_emotional_tone(thought),
            "key_concepts": self._extract_key_concepts(thought),
            "reasoning_pattern": self._identify_reasoning_pattern(thought),
        }
        
        # 基于历史思考分析趋势
        if len(self.thought_history) > 1:
            analysis["trend_analysis"] = self._analyze_thought_trends()
        
        return analysis
    
    def _classify_thought_type(self, thought: str) -> str:
        """分类思考类型"""
        thought_lower = thought.lower()
        
        if any(word in thought_lower for word in ['question', 'why', 'how', 'what', '?']):
            return "questioning"
        elif any(word in thought_lower for word in ['problem', 'issue', 'error', 'wrong']):
            return "problem_solving"
        elif any(word in thought_lower for word in ['plan', 'strategy', 'approach', 'method']):
            return "planning"
        elif any(word in thought_lower for word in ['conclusion', 'result', 'found', 'solved']):
            return "concluding"
        elif any(word in thought_lower for word in ['maybe', 'perhaps', 'consider', 'could']):
            return "hypothesizing"
        else:
            return "general_reflection"
    
    def _assess_complexity(self, thought: str, context: Optional[Dict]) -> str:
        """评估思考复杂度"""
        complexity_score = 0
        
        # 基于长度
        if len(thought) > 200:
            complexity_score += 2
        elif len(thought) > 100:
            complexity_score += 1
        
        # 基于关键词
        complex_keywords = ['analyze', 'synthesize', 'integrate', 'optimize', 'algorithm', 'strategy']
        complexity_score += sum(1 for keyword in complex_keywords if keyword in thought.lower())
        
        # 基于上下文
        if context and len(context) > 3:
            complexity_score += 1
        
        if complexity_score >= 4:
            return "high"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "low"
    
    def _analyze_emotional_tone(self, thought: str) -> str:
        """分析情感色调"""
        thought_lower = thought.lower()
        
        positive_words = ['good', 'great', 'excellent', 'perfect', 'success', 'achieved']
        negative_words = ['bad', 'wrong', 'error', 'fail', 'problem', 'difficult']
        neutral_words = ['analyze', 'consider', 'examine', 'evaluate', 'think']
        
        positive_count = sum(1 for word in positive_words if word in thought_lower)
        negative_count = sum(1 for word in negative_words if word in thought_lower)
        neutral_count = sum(1 for word in neutral_words if word in thought_lower)
        
        if positive_count > negative_count and positive_count > 0:
            return "positive"
        elif negative_count > positive_count and negative_count > 0:
            return "negative"
        elif neutral_count > 0:
            return "analytical"
        else:
            return "neutral"
    
    def _extract_key_concepts(self, thought: str) -> List[str]:
        """提取关键概念"""
        # 简单的关键词提取
        import re
        words = re.findall(r'\b[a-zA-Z]{4,}\b', thought)
        
        # 过滤常用词
        common_words = {'this', 'that', 'with', 'from', 'they', 'have', 'were', 'been', 'their', 'said', 'each', 'which', 'does', 'both', 'after', 'here', 'should', 'where', 'most', 'through', 'when', 'there', 'could', 'would', 'more', 'very', 'what', 'know', 'just', 'first', 'into', 'over', 'think', 'also', 'your', 'work', 'life', 'only', 'can', 'still', 'should', 'after', 'being', 'now', 'made', 'before', 'here', 'through', 'when', 'where', 'much', 'some', 'these', 'many', 'then', 'them', 'well', 'were'}
        
        key_concepts = [word.lower() for word in words if word.lower() not in common_words]
        
        # 返回出现频率高的概念（最多5个）
        from collections import Counter
        concept_counts = Counter(key_concepts)
        return [concept for concept, count in concept_counts.most_common(5)]
    
    def _identify_reasoning_pattern(self, thought: str) -> str:
        """识别推理模式"""
        thought_lower = thought.lower()
        
        if any(word in thought_lower for word in ['because', 'since', 'therefore', 'thus', 'consequently']):
            return "causal_reasoning"
        elif any(word in thought_lower for word in ['similar', 'like', 'analogous', 'compared']):
            return "analogical_reasoning"
        elif any(word in thought_lower for word in ['all', 'every', 'always', 'never', 'general']):
            return "deductive_reasoning"
        elif any(word in thought_lower for word in ['some', 'might', 'could', 'probably', 'likely']):
            return "inductive_reasoning"
        elif any(word in thought_lower for word in ['step', 'first', 'then', 'next', 'finally']):
            return "sequential_reasoning"
        else:
            return "unstructured"
    
    def _analyze_thought_trends(self) -> Dict[str, Any]:
        """分析思考趋势"""
        if len(self.thought_history) < 2:
            return {}
        
        recent_thoughts = self.thought_history[-5:]  # 最近5个思考
        
        # 分析类型分布
        types = [t.get("analysis", {}).get("thought_type", "unknown") for t in recent_thoughts]
        type_distribution = {t: types.count(t) for t in set(types)}
        
        # 分析复杂度趋势
        complexities = [t.get("analysis", {}).get("complexity", "low") for t in recent_thoughts]
        complexity_trend = "increasing" if complexities[-1] == "high" and complexities[0] != "high" else "stable"
        
        return {
            "type_distribution": type_distribution,
            "complexity_trend": complexity_trend,
            "thinking_frequency": len(self.thought_history),
            "dominant_pattern": max(type_distribution, key=type_distribution.get) if type_distribution else "unknown"
        }
    
    def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """基于分析生成建议"""
        suggestions = []
        
        thought_type = analysis.get("thought_type", "")
        complexity = analysis.get("complexity", "")
        emotional_tone = analysis.get("emotional_tone", "")
        
        # 基于思考类型的建议
        if thought_type == "questioning":
            suggestions.append("Consider gathering more information to answer these questions")
        elif thought_type == "problem_solving":
            suggestions.append("Break down the problem into smaller, manageable parts")
        elif thought_type == "planning":
            suggestions.append("Create concrete action steps with clear priorities")
        elif thought_type == "hypothesizing":
            suggestions.append("Test your hypotheses with small experiments or analysis")
        
        # 基于复杂度的建议
        if complexity == "high":
            suggestions.append("Consider using systematic thinking tools or frameworks")
        elif complexity == "low":
            suggestions.append("You might want to dig deeper into this topic")
        
        # 基于情感色调的建议
        if emotional_tone == "negative":
            suggestions.append("Take a step back and look for alternative approaches")
        elif emotional_tone == "positive":
            suggestions.append("Build on this positive momentum")
        
        return suggestions[:3]  # 最多返回3个建议
    
    async def _update_agent_memory(self, thought_entry: Dict, analysis: Dict):
        """更新agent记忆系统"""
        brain = self.get_brain()
        if not brain or not hasattr(brain, 'mem') or not brain.mem:
            return
        
        try:
            # 构建记忆内容
            memory_content = f"Internal thinking: {thought_entry['thought']}"
            
            # 构建元数据
            metadata = {
                "type": "internal_thought",
                "thought_type": analysis.get("thought_type"),
                "complexity": analysis.get("complexity"),
                "priority": thought_entry.get("priority"),
                "timestamp": thought_entry["timestamp"],
                "key_concepts": analysis.get("key_concepts", []),
            }
            
            # 添加到记忆
            brain.mem.add(memory_content, metadata=metadata)
            
        except Exception as e:
            # 静默失败，不影响主要功能
            pass
    
    def get_thought_summary(self) -> Dict[str, Any]:
        """获取思考总结"""
        if not self.thought_history:
            return {"total_thoughts": 0}
        
        # 统计信息
        total_thoughts = len(self.thought_history)
        
        # 类型分布
        types = [t.get("analysis", {}).get("thought_type", "unknown") for t in self.thought_history]
        type_counts = {t: types.count(t) for t in set(types)}
        
        # 最近活动
        recent_thought = self.thought_history[-1] if self.thought_history else None
        
        return {
            "total_thoughts": total_thoughts,
            "type_distribution": type_counts,
            "most_common_type": max(type_counts, key=type_counts.get) if type_counts else "none",
            "last_thought_time": recent_thought["timestamp"] if recent_thought else None,
            "insights_generated": len(self.insights),
        }