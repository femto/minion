#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ThinkTool Meta工具
支持CodeAgent内部思考和分析
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from .agent_state_aware_tool import AgentStateAwareTool

class ThinkTool(AgentStateAwareTool):
    """
    思考工具 - 支持CodeAgent在代码执行中进行思考和分析
    
    特点：
    1. 跟踪思考历史
    2. 分析思考模式和复杂度
    3. 生成思考反馈和建议
    4. 对LLM透明，但在代码中可调用
    """
    
    name = "think"
    description = "Internal thinking tool for agent reasoning and reflection"
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
        "category": {
            "type": "string",
            "description": "Thought category: analysis, planning, debugging, decision, reflection",
            "required": False
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.thought_history = []
        self.insights = []
        self._last_context = None
        self._auto_discover = True
        
    async def forward(self, 
                     thought: str = None, 
                     context: Optional[Dict] = None, 
                     category: str = "analysis") -> Dict[str, Any]:
        """
        执行思考操作
        
        Args:
            thought: 思考内容 (可选，如果未提供会自动从agent上下文中提取)
            context: 上下文信息 (可选)
            category: 思考类别
            
        Returns:
            思考结果和建议
        """
        # 自动发现agent上下文
        self._agent_context = self._discover_agent_context()
        
        # 如果没有提供思考内容，尝试从agent上下文中提取
        if thought is None:
            thought = self._extract_thought_from_agent()
        
        if context is None:
            context = self._build_context_from_agent()
        
        # 创建思考记录
        thought_entry = {
            "id": len(self.thought_history) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "thought": thought,
            "category": category,
            "context": context,
            "agent_state": self._extract_agent_state(),
        }
        
        # 记录思考历史
        self.thought_history.append(thought_entry)
        
        # 分析思考内容
        analysis = await self._analyze_thought(thought, category, context)
        
        # 更新agent记忆（如果可用）
        await self._update_agent_memory(thought_entry, analysis)
        
        # 生成建议
        suggestions = self._generate_suggestions(analysis, category)
        
        return {
            "thinking_complete": True,
            "thought_id": thought_entry["id"],
            "timestamp": thought_entry["timestamp"],
            "analysis": analysis,
            "suggestions": suggestions,
            "total_thoughts": len(self.thought_history)
        }
    
    def _extract_thought_from_agent(self) -> str:
        """从agent上下文中提取思考内容"""
        # 尝试从当前任务或查询中提取
        input_obj = self.get_input()
        if input_obj and hasattr(input_obj, 'query'):
            return f"思考任务: {input_obj.query[:100]}..."
        
        # 尝试从状态提取
        agent_state = self.get_agent_state()
        if agent_state and 'task' in agent_state:
            return f"思考任务: {agent_state['task'][:100]}..."
            
        # 如果都没有，创建默认思考内容
        return "分析当前状态和任务进展"
    
    def _build_context_from_agent(self) -> Dict[str, Any]:
        """从agent上下文构建丰富的思考上下文"""
        context = {}
        
        # 从agent获取信息
        agent = self.get_agent()
        if agent:
            context["agent_name"] = getattr(agent, 'name', 'unknown')
            context["agent_type"] = agent.__class__.__name__
        
        # 从状态获取信息
        agent_state = self.get_agent_state()
        if agent_state:
            if 'history' in agent_state and agent_state['history']:
                # 最近的历史记录
                recent_history = agent_state['history'][-3:] if len(agent_state['history']) > 3 else agent_state['history']
                context["recent_actions"] = recent_history
                
            # 其他相关信息
            for key in ['task', 'step_count', 'error_count', 'is_final_answer']:
                if key in agent_state:
                    context[key] = agent_state[key]
        
        # 从输入获取信息
        input_obj = self.get_input()
        if input_obj:
            context["query"] = getattr(input_obj, 'query', '')[:200]  # 限制长度
            context["route"] = getattr(input_obj, 'route', None)
        
        return context
    
    @property
    def state(self) -> Dict[str, Any]:
        """获取代理的当前状态（便于外部访问）"""
        agent = self.get_agent()
        if agent and hasattr(agent, 'state'):
            return agent.state
        return self.get_agent_state()
    
    def _extract_agent_state(self) -> Dict[str, Any]:
        """提取相关的agent状态信息"""
        if not self._agent_context:
            return {}
        
        state_info = {}
        
        # 从agent状态获取信息
        agent_state = self.get_agent_state()
        if agent_state:
            state_info.update({
                "step_count": agent_state.get('step_count', 0),
                "history_length": len(agent_state.get('history', [])),
                "has_errors": any('error' in str(h).lower() for h in agent_state.get('history', [])),
            })
        
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
        
        return state_info
    
    async def _analyze_thought(self, 
                             thought: str, 
                             category: str, 
                             context: Optional[Dict]) -> Dict[str, Any]:
        """分析思考内容和类型"""
        # 保存最后一次上下文，便于后续访问
        self._last_context = context
        
        if not thought:
            return {
                "error": "No thought provided for analysis",
                "complexity": "unknown",
                "key_concepts": []
            }
            
        analysis = {
            "complexity": self._assess_complexity(thought),
            "key_concepts": self._extract_key_concepts(thought),
            "reasoning_pattern": self._identify_reasoning_pattern(thought),
        }
        
        # 基于类别的分析
        if category == "analysis":
            analysis["detailed"] = self._analyze_analytical_thought(thought)
        elif category == "planning":
            analysis["detailed"] = self._analyze_planning_thought(thought)
        elif category == "debugging":
            analysis["detailed"] = self._analyze_debugging_thought(thought)
        elif category == "decision":
            analysis["detailed"] = self._analyze_decision_thought(thought)
        elif category == "reflection":
            analysis["detailed"] = self._analyze_reflective_thought(thought)
        
        # 基于历史思考分析趋势
        if len(self.thought_history) > 1:
            analysis["trend_analysis"] = self._analyze_thought_trends()
        
        return analysis
    
    def _assess_complexity(self, thought: str) -> str:
        """评估思考复杂度"""
        complexity_score = 0
        
        # 基于长度
        if len(thought) > 300:
            complexity_score += 3
        elif len(thought) > 150:
            complexity_score += 2
        elif len(thought) > 50:
            complexity_score += 1
        
        # 基于关键词
        complex_keywords = [
            'algorithm', 'optimize', 'architecture', 'recursive', 'refactor',
            'concurrency', 'asynchronous', 'parallel', 'dependency', 'pattern'
        ]
        complexity_score += sum(1 for keyword in complex_keywords if keyword.lower() in thought.lower())
        
        # 基于结构分析
        if '?' in thought:
            complexity_score += 1  # 包含问题
        if ':' in thought:
            complexity_score += 1  # 包含定义或解释
        
        if complexity_score >= 5:
            return "high"
        elif complexity_score >= 3:
            return "medium"
        else:
            return "low"
    
    def _extract_key_concepts(self, thought: str) -> List[str]:
        """提取关键概念"""
        from collections import Counter
        
        # 去除常用词和标点
        common_words = {
            'the', 'and', 'that', 'this', 'with', 'for', 'from', 'have',
            'but', 'not', 'what', 'all', 'are', 'when', 'how', 'been',
            'can', 'will', 'should', 'would', 'could', 'may', 'must',
            'then', 'than', 'there', 'their', 'they', 'them', 'these',
            'those', 'some', 'such', 'just', 'now', 'more', 'most', 'other',
            'our', 'out', 'over', 'into'
        }
        
        # 提取所有单词并转小写
        words = re.findall(r'\b[a-zA-Z]{4,}\b', thought)
        words = [word.lower() for word in words if word.lower() not in common_words]
        
        # 计算词频
        concept_counts = Counter(words)
        
        # 返回最多5个最常见的概念
        return [concept for concept, _ in concept_counts.most_common(5)]
    
    def _identify_reasoning_pattern(self, thought: str) -> str:
        """识别推理模式"""
        thought_lower = thought.lower()
        
        # 因果推理
        if any(word in thought_lower for word in ['because', 'since', 'therefore', 'thus', 'consequently']):
            return "causal"
        
        # 比较推理
        elif any(word in thought_lower for word in ['compared', 'better', 'worse', 'versus', 'vs', 'similar', 'different']):
            return "comparative"
        
        # 演绎推理（从一般到特殊）
        elif any(word in thought_lower for word in ['all', 'every', 'always', 'never', 'must']):
            return "deductive"
        
        # 归纳推理（从特殊到一般）
        elif any(word in thought_lower for word in ['some', 'many', 'most', 'likely', 'probably', 'pattern']):
            return "inductive"
        
        # 过程推理
        elif any(word in thought_lower for word in ['first', 'then', 'next', 'finally', 'step', 'process']):
            return "procedural"
        
        # 问题解决
        elif any(word in thought_lower for word in ['problem', 'solution', 'solve', 'fix', 'issue', 'error', 'bug']):
            return "problem_solving"
        
        # 默认
        else:
            return "exploratory"
    
    def _analyze_analytical_thought(self, thought: str) -> Dict[str, Any]:
        """分析解析型思考"""
        return {
            "depth": "deep" if len(thought) > 200 else "surface",
            "approach": "systematic" if any(w in thought.lower() for w in ['first', 'then', 'finally', 'steps']) else "intuitive",
            "focus": "detail" if thought.count(",") > 3 else "big_picture"
        }
    
    def _analyze_planning_thought(self, thought: str) -> Dict[str, Any]:
        """分析规划型思考"""
        has_numbered_steps = bool(re.search(r'\d[\.\)]\s', thought))
        has_explicit_goals = "goal" in thought.lower() or "objective" in thought.lower()
        
        return {
            "structure": "step_by_step" if has_numbered_steps else "conceptual",
            "timeframe": "immediate" if "now" in thought.lower() else "future",
            "has_explicit_goals": has_explicit_goals,
            "scope": "comprehensive" if len(thought) > 200 else "focused"
        }
    
    def _analyze_debugging_thought(self, thought: str) -> Dict[str, Any]:
        """分析调试型思考"""
        mentions_errors = "error" in thought.lower() or "exception" in thought.lower() or "bug" in thought.lower()
        suggests_solution = "fix" in thought.lower() or "solution" in thought.lower() or "resolve" in thought.lower()
        
        return {
            "identifies_problem": mentions_errors,
            "suggests_solution": suggests_solution,
            "approach": "systematic" if "step" in thought.lower() else "intuitive",
            "focus": "root_cause" if "because" in thought.lower() or "cause" in thought.lower() else "symptoms"
        }
    
    def _analyze_decision_thought(self, thought: str) -> Dict[str, Any]:
        """分析决策型思考"""
        compares_options = "or" in thought.lower() or "versus" in thought.lower() or "vs" in thought.lower()
        considers_tradeoffs = "tradeoff" in thought.lower() or "pro" in thought.lower() and "con" in thought.lower()
        
        return {
            "compares_options": compares_options,
            "considers_tradeoffs": considers_tradeoffs,
            "decisiveness": "high" if "should" in thought.lower() or "must" in thought.lower() else "low",
            "risk_assessment": "considered" if "risk" in thought.lower() or "if" in thought.lower() else "not_explicit"
        }
    
    def _analyze_reflective_thought(self, thought: str) -> Dict[str, Any]:
        """分析反思型思考"""
        mentions_past = any(w in thought.lower() for w in ["previous", "earlier", "before", "past"])
        evaluates_performance = any(w in thought.lower() for w in ["better", "worse", "improve", "successful", "failed"])
        
        return {
            "temporal_focus": "past" if mentions_past else "present",
            "evaluates_performance": evaluates_performance,
            "self_critical": "high" if "mistake" in thought.lower() or "wrong" in thought.lower() else "low",
            "learning_oriented": "yes" if "learn" in thought.lower() or "next time" in thought.lower() else "no"
        }
    
    def _analyze_thought_trends(self) -> Dict[str, Any]:
        """分析思考趋势"""
        if len(self.thought_history) < 2:
            return {}
        
        recent_thoughts = self.thought_history[-5:]  # 最近5个思考
        
        # 分析类型分布
        categories = [t.get("category", "unknown") for t in recent_thoughts]
        category_distribution = {c: categories.count(c) for c in set(categories)}
        
        # 分析复杂度趋势
        recent_complexities = [
            t.get("analysis", {}).get("complexity", "low") 
            for t in self.thought_history[-3:]
        ]
        complexity_values = {"low": 1, "medium": 2, "high": 3}
        complexity_scores = [complexity_values.get(c, 1) for c in recent_complexities]
        
        complexity_trend = "increasing" if complexity_scores[-1] > complexity_scores[0] else "decreasing" if complexity_scores[-1] < complexity_scores[0] else "stable"
        
        return {
            "category_distribution": category_distribution,
            "dominant_category": max(category_distribution, key=category_distribution.get) if category_distribution else "unknown",
            "complexity_trend": complexity_trend,
            "thought_frequency": len(self.thought_history) 
        }
    
    def _generate_suggestions(self, analysis: Dict[str, Any], category: str) -> List[str]:
        """基于分析生成建议"""
        suggestions = []
        
        # 基于思考类别的建议
        if category == "analysis":
            suggestions.append("Consider exploring different perspectives on this problem")
            if analysis.get("complexity") == "high":
                suggestions.append("Break down this complex analysis into smaller parts")
        
        elif category == "planning":
            suggestions.append("Set clear success criteria for your plan")
            if analysis.get("detailed", {}).get("structure") == "conceptual":
                suggestions.append("Add specific actionable steps to your plan")
        
        elif category == "debugging":
            if not analysis.get("detailed", {}).get("identifies_problem", False):
                suggestions.append("Clearly define the specific error or issue")
            if not analysis.get("detailed", {}).get("suggests_solution", False):
                suggestions.append("Propose concrete solutions to address the problem")
        
        elif category == "decision":
            if not analysis.get("detailed", {}).get("compares_options", False):
                suggestions.append("Compare multiple options before making a decision")
            if not analysis.get("detailed", {}).get("considers_tradeoffs", False):
                suggestions.append("Consider the tradeoffs of each option")
        
        elif category == "reflection":
            suggestions.append("Identify specific learnings from this experience")
            if not analysis.get("detailed", {}).get("learning_oriented", False):
                suggestions.append("Consider how to apply these insights in the future")
        
        # 基于复杂度的通用建议
        complexity = analysis.get("complexity", "medium")
        if complexity == "high":
            suggestions.append("Consider using systematic thinking tools to manage complexity")
        elif complexity == "low":
            suggestions.append("You might want to explore this topic in more depth")
        
        # 基于推理模式的建议
        reasoning_pattern = analysis.get("reasoning_pattern", "")
        if reasoning_pattern == "exploratory":
            suggestions.append("Try to identify specific patterns or connections")
        elif reasoning_pattern == "problem_solving":
            suggestions.append("Evaluate multiple potential solutions")
        
        # 返回最多3个最相关的建议
        return suggestions[:3]
    
    async def _update_agent_memory(self, thought_entry: Dict, analysis: Dict):
        """更新agent记忆系统（如果可用）"""
        brain = self.get_brain()
        if not brain or not hasattr(brain, 'mem') or not brain.mem:
            return
        
        try:
            # 构建记忆内容
            memory_content = f"Thought ({thought_entry['category']}): {thought_entry['thought'][:100]}..."
            
            # 构建元数据
            metadata = {
                "type": "agent_thought",
                "thought_category": thought_entry["category"],
                "complexity": analysis.get("complexity"),
                "timestamp": thought_entry["timestamp"],
                "key_concepts": analysis.get("key_concepts", []),
                "reasoning_pattern": analysis.get("reasoning_pattern")
            }
            
            # 添加到记忆
            brain.mem.add(memory_content, metadata=metadata)
            
        except Exception as e:
            # 静默失败，不影响主要功能
            pass
    
    def get_thought_history_summary(self) -> Dict[str, Any]:
        """获取思考历史摘要"""
        if not self.thought_history:
            return {"total_thoughts": 0}
        
        # 类型分布
        categories = [t.get("category", "unknown") for t in self.thought_history]
        category_counts = {c: categories.count(c) for c in set(categories)}
        
        # 复杂度分布
        complexities = [
            t.get("analysis", {}).get("complexity", "medium") 
            for t in self.thought_history if "analysis" in t
        ]
        complexity_counts = {c: complexities.count(c) for c in set(complexities)}
        
        # 最近活动
        recent = self.thought_history[-1] if self.thought_history else None
        
        return {
            "total_thoughts": len(self.thought_history),
            "category_distribution": category_counts,
            "most_common_category": max(category_counts, key=category_counts.get) if category_counts else "unknown",
            "complexity_distribution": complexity_counts,
            "last_thought_time": recent["timestamp"] if recent else None,
            "last_thought_category": recent["category"] if recent else None
        }