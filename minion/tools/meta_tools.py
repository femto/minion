#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plan和Reflection Meta工具
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from .agent_state_aware_tool import AgentStateAwareTool

class PlanTool(AgentStateAwareTool):
    """
    规划工具 - 帮助agent制定和跟踪执行计划
    """
    
    name = "plan"
    description = "Internal planning tool for task decomposition and step tracking"
    inputs = {
        "action": {
            "type": "string",
            "description": "Action: create, update, complete_step, get_status"
        },
        "plan_data": {
            "type": "object",
            "description": "Plan data: steps, current_step, notes, etc.",
            "required": False
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.current_plan = None
        self.plan_history = []
        
    async def forward(self, action: str, plan_data: Optional[Dict] = None) -> Dict[str, Any]:
        """执行规划操作"""
        if action == "create":
            return await self._create_plan(plan_data or {})
        elif action == "update":
            return await self._update_plan(plan_data or {})
        elif action == "complete_step":
            return await self._complete_step(plan_data or {})
        elif action == "get_status":
            return await self._get_status()
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _create_plan(self, plan_data: Dict) -> Dict[str, Any]:
        """创建新计划"""
        # 从agent状态获取上下文
        context = self._get_planning_context()
        
        self.current_plan = {
            "id": len(self.plan_history) + 1,
            "created_at": datetime.utcnow().isoformat(),
            "title": plan_data.get("title", "Untitled Plan"),
            "goal": plan_data.get("goal", ""),
            "steps": plan_data.get("steps", []),
            "current_step": 0,
            "status": "active",
            "context": context,
            "metadata": plan_data.get("metadata", {})
        }
        
        self.plan_history.append(self.current_plan.copy())
        
        return {
            "plan_created": True,
            "plan_id": self.current_plan["id"],
            "total_steps": len(self.current_plan["steps"]),
            "next_step": self.current_plan["steps"][0] if self.current_plan["steps"] else None
        }
    
    async def _update_plan(self, plan_data: Dict) -> Dict[str, Any]:
        """更新现有计划"""
        if not self.current_plan:
            return {"error": "No active plan to update"}
        
        # 更新计划字段
        for key in ["title", "goal", "steps", "metadata"]:
            if key in plan_data:
                self.current_plan[key] = plan_data[key]
        
        self.current_plan["updated_at"] = datetime.utcnow().isoformat()
        
        return {
            "plan_updated": True,
            "plan_id": self.current_plan["id"],
            "total_steps": len(self.current_plan["steps"]),
            "current_step": self.current_plan["current_step"]
        }
    
    async def _complete_step(self, plan_data: Dict) -> Dict[str, Any]:
        """完成当前步骤"""
        if not self.current_plan:
            return {"error": "No active plan"}
        
        current_step_idx = self.current_plan["current_step"]
        total_steps = len(self.current_plan["steps"])
        
        if current_step_idx >= total_steps:
            return {"error": "All steps already completed"}
        
        # 记录步骤完成
        step_result = {
            "step_index": current_step_idx,
            "completed_at": datetime.utcnow().isoformat(),
            "result": plan_data.get("result", ""),
            "notes": plan_data.get("notes", "")
        }
        
        # 添加到完成历史
        if "completed_steps" not in self.current_plan:
            self.current_plan["completed_steps"] = []
        self.current_plan["completed_steps"].append(step_result)
        
        # 移动到下一步
        self.current_plan["current_step"] += 1
        
        # 检查是否完成
        is_complete = self.current_plan["current_step"] >= total_steps
        if is_complete:
            self.current_plan["status"] = "completed"
            self.current_plan["completed_at"] = datetime.utcnow().isoformat()
        
        return {
            "step_completed": True,
            "completed_step": current_step_idx,
            "next_step": (self.current_plan["steps"][self.current_plan["current_step"]] 
                         if not is_complete else None),
            "plan_complete": is_complete,
            "progress": f"{self.current_plan['current_step']}/{total_steps}"
        }
    
    async def _get_status(self) -> Dict[str, Any]:
        """获取计划状态"""
        if not self.current_plan:
            return {
                "has_active_plan": False,
                "total_plans": len(self.plan_history)
            }
        
        total_steps = len(self.current_plan["steps"])
        current_step = self.current_plan["current_step"]
        
        return {
            "has_active_plan": True,
            "plan_id": self.current_plan["id"],
            "title": self.current_plan["title"],
            "status": self.current_plan["status"],
            "progress": f"{current_step}/{total_steps}",
            "current_step_text": (self.current_plan["steps"][current_step] 
                                 if current_step < total_steps else "Plan completed"),
            "completion_percentage": (current_step / total_steps * 100) if total_steps > 0 else 0
        }
    
    def _get_planning_context(self) -> Dict[str, Any]:
        """获取规划上下文"""
        context = {}
        
        # 从agent状态获取信息
        agent_state = self.get_agent_state()
        if agent_state:
            context["agent_step_count"] = agent_state.get("step_count", 0)
            context["has_history"] = len(agent_state.get("history", [])) > 0
        
        # 从输入获取信息
        input_obj = self.get_input()
        if input_obj:
            context["query_type"] = getattr(input_obj, "query_type", None)
            context["original_query"] = getattr(input_obj, "query", "")[:100]  # 前100字符
        
        return context


class ReflectionTool(AgentStateAwareTool):
    """
    反思工具 - 帮助agent进行自我反思和评估
    """
    
    name = "reflect"
    description = "Internal reflection tool for self-assessment and learning"
    inputs = {
        "subject": {
            "type": "string",
            "description": "What to reflect on: result, process, decision, overall"
        },
        "data": {
            "type": "object",
            "description": "Data to reflect on",
            "required": False
        },
        "questions": {
            "type": "array",
            "description": "Specific reflection questions",
            "required": False
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.reflection_history = []
        
    async def forward(self, 
                     subject: str, 
                     data: Optional[Dict] = None, 
                     questions: Optional[List[str]] = None) -> Dict[str, Any]:
        """执行反思"""
        
        reflection_entry = {
            "id": len(self.reflection_history) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "subject": subject,
            "data": data or {},
            "questions": questions or [],
            "context": self._get_reflection_context()
        }
        
        # 执行反思分析
        analysis = await self._analyze_reflection(subject, data, questions)
        reflection_entry["analysis"] = analysis
        
        # 生成学习点
        learning_points = self._extract_learning_points(analysis)
        reflection_entry["learning_points"] = learning_points
        
        # 记录反思历史
        self.reflection_history.append(reflection_entry)
        
        # 更新agent记忆
        await self._update_reflection_memory(reflection_entry)
        
        return {
            "reflection_complete": True,
            "reflection_id": reflection_entry["id"],
            "analysis": analysis,
            "learning_points": learning_points,
            "recommendations": self._generate_recommendations(analysis)
        }
    
    async def _analyze_reflection(self, 
                                subject: str, 
                                data: Optional[Dict], 
                                questions: Optional[List[str]]) -> Dict[str, Any]:
        """分析反思内容"""
        analysis = {
            "reflection_type": subject,
            "data_quality": self._assess_data_quality(data),
            "insights": [],
            "patterns": [],
            "concerns": []
        }
        
        # 基于反思主题的具体分析
        if subject == "result":
            analysis.update(await self._analyze_result_reflection(data))
        elif subject == "process":
            analysis.update(await self._analyze_process_reflection(data))
        elif subject == "decision":
            analysis.update(await self._analyze_decision_reflection(data))
        elif subject == "overall":
            analysis.update(await self._analyze_overall_reflection(data))
        
        # 处理自定义问题
        if questions:
            analysis["question_responses"] = await self._process_reflection_questions(questions, data)
        
        return analysis
    
    async def _analyze_result_reflection(self, data: Optional[Dict]) -> Dict[str, Any]:
        """分析结果反思"""
        agent_state = self.get_agent_state()
        
        return {
            "result_assessment": {
                "completeness": self._assess_completeness(data, agent_state),
                "accuracy": self._assess_accuracy(data, agent_state),
                "efficiency": self._assess_efficiency(data, agent_state)
            },
            "improvement_areas": self._identify_improvement_areas(data, agent_state)
        }
    
    async def _analyze_process_reflection(self, data: Optional[Dict]) -> Dict[str, Any]:
        """分析过程反思"""
        agent_state = self.get_agent_state()
        
        return {
            "process_assessment": {
                "steps_taken": agent_state.get("step_count", 0),
                "efficiency": "good" if agent_state.get("step_count", 0) < 10 else "needs_improvement",
                "error_rate": self._calculate_error_rate(agent_state)
            },
            "process_insights": self._extract_process_insights(agent_state)
        }
    
    async def _analyze_decision_reflection(self, data: Optional[Dict]) -> Dict[str, Any]:
        """分析决策反思"""
        return {
            "decision_assessment": {
                "rationale": data.get("rationale", "") if data else "",
                "alternatives_considered": len(data.get("alternatives", [])) if data else 0,
                "confidence": data.get("confidence", "medium") if data else "unknown"
            },
            "decision_quality": self._assess_decision_quality(data)
        }
    
    async def _analyze_overall_reflection(self, data: Optional[Dict]) -> Dict[str, Any]:
        """分析整体反思"""
        agent_state = self.get_agent_state()
        
        return {
            "overall_assessment": {
                "session_length": agent_state.get("step_count", 0),
                "goal_achievement": self._assess_goal_achievement(agent_state),
                "learning_occurred": len(self.reflection_history) > 0
            },
            "session_insights": self._extract_session_insights(agent_state)
        }
    
    def _get_reflection_context(self) -> Dict[str, Any]:
        """获取反思上下文"""
        context = {}
        
        # Agent状态
        agent_state = self.get_agent_state()
        if agent_state:
            context["current_step"] = agent_state.get("step_count", 0)
            context["has_errors"] = any("error" in str(h).lower() for h in agent_state.get("history", []))
        
        # Brain状态
        brain = self.get_brain()
        if brain:
            context["brain_tools_count"] = len(getattr(brain, "tools", []))
        
        return context
    
    def _assess_data_quality(self, data: Optional[Dict]) -> str:
        """评估数据质量"""
        if not data:
            return "no_data"
        elif len(data) < 2:
            return "minimal"
        elif len(data) < 5:
            return "adequate"
        else:
            return "comprehensive"
    
    def _assess_completeness(self, data: Optional[Dict], agent_state: Dict) -> str:
        """评估完整性"""
        if not data:
            return "unknown"
        
        # 简单启发式评估
        if agent_state.get("step_count", 0) > 5 and data.get("final_answer"):
            return "high"
        elif agent_state.get("step_count", 0) > 2:
            return "medium"
        else:
            return "low"
    
    def _assess_accuracy(self, data: Optional[Dict], agent_state: Dict) -> str:
        """评估准确性"""
        # 基于错误率的简单评估
        error_rate = self._calculate_error_rate(agent_state)
        if error_rate < 0.1:
            return "high"
        elif error_rate < 0.3:
            return "medium"
        else:
            return "low"
    
    def _assess_efficiency(self, data: Optional[Dict], agent_state: Dict) -> str:
        """评估效率"""
        step_count = agent_state.get("step_count", 0)
        if step_count <= 3:
            return "high"
        elif step_count <= 7:
            return "medium"
        else:
            return "low"
    
    def _calculate_error_rate(self, agent_state: Dict) -> float:
        """计算错误率"""
        history = agent_state.get("history", [])
        if not history:
            return 0.0
        
        error_count = sum(1 for h in history if "error" in str(h).lower() or "exception" in str(h).lower())
        return error_count / len(history)
    
    def _identify_improvement_areas(self, data: Optional[Dict], agent_state: Dict) -> List[str]:
        """识别改进领域"""
        areas = []
        
        if self._calculate_error_rate(agent_state) > 0.2:
            areas.append("error_handling")
        
        if agent_state.get("step_count", 0) > 10:
            areas.append("efficiency")
        
        if not data or not data.get("final_answer"):
            areas.append("task_completion")
        
        return areas
    
    def _extract_process_insights(self, agent_state: Dict) -> List[str]:
        """提取过程洞察"""
        insights = []
        
        step_count = agent_state.get("step_count", 0)
        if step_count > 0:
            insights.append(f"Completed {step_count} reasoning steps")
        
        if self._calculate_error_rate(agent_state) == 0:
            insights.append("No errors encountered - good execution")
        
        return insights
    
    def _assess_decision_quality(self, data: Optional[Dict]) -> str:
        """评估决策质量"""
        if not data:
            return "unknown"
        
        quality_score = 0
        
        if data.get("rationale"):
            quality_score += 2
        if data.get("alternatives"):
            quality_score += 1
        if data.get("confidence") == "high":
            quality_score += 1
        
        if quality_score >= 3:
            return "high"
        elif quality_score >= 2:
            return "medium"
        else:
            return "low"
    
    def _assess_goal_achievement(self, agent_state: Dict) -> str:
        """评估目标达成"""
        # 简单的启发式评估
        if agent_state.get("is_final_answer"):
            return "achieved"
        elif agent_state.get("step_count", 0) > 0:
            return "in_progress"
        else:
            return "not_started"
    
    def _extract_session_insights(self, agent_state: Dict) -> List[str]:
        """提取会话洞察"""
        insights = []
        
        step_count = agent_state.get("step_count", 0)
        if step_count > 0:
            insights.append(f"Session involved {step_count} decision points")
        
        if len(self.reflection_history) > 1:
            insights.append("Multiple reflections show good self-awareness")
        
        return insights
    
    async def _process_reflection_questions(self, 
                                          questions: List[str], 
                                          data: Optional[Dict]) -> List[Dict[str, str]]:
        """处理反思问题"""
        responses = []
        
        for question in questions:
            response = await self._answer_reflection_question(question, data)
            responses.append({
                "question": question,
                "response": response
            })
        
        return responses
    
    async def _answer_reflection_question(self, question: str, data: Optional[Dict]) -> str:
        """回答反思问题"""
        # 简单的问题回答逻辑
        question_lower = question.lower()
        
        if "what went well" in question_lower:
            return "Task execution proceeded without major errors"
        elif "what could be improved" in question_lower:
            return "Could optimize step efficiency and error handling"
        elif "what did you learn" in question_lower:
            return "Gained insights into problem-solving patterns"
        else:
            return "Reflection noted, requires deeper analysis"
    
    def _extract_learning_points(self, analysis: Dict[str, Any]) -> List[str]:
        """提取学习点"""
        learning_points = []
        
        # 从分析中提取学习点
        if "improvement_areas" in analysis:
            for area in analysis["improvement_areas"]:
                learning_points.append(f"Focus on improving {area.replace('_', ' ')}")
        
        if analysis.get("result_assessment", {}).get("efficiency") == "needs_improvement":
            learning_points.append("Work on improving execution efficiency")
        
        return learning_points[:3]  # 最多3个学习点
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        # 基于分析生成建议
        if "improvement_areas" in analysis:
            areas = analysis["improvement_areas"]
            if "efficiency" in areas:
                recommendations.append("Consider planning ahead to reduce step count")
            if "error_handling" in areas:
                recommendations.append("Implement better validation and error checking")
            if "task_completion" in areas:
                recommendations.append("Ensure all requirements are fully addressed")
        
        return recommendations[:3]  # 最多3个建议
    
    async def _update_reflection_memory(self, reflection_entry: Dict):
        """更新反思记忆"""
        brain = self.get_brain()
        if not brain or not hasattr(brain, 'mem') or not brain.mem:
            return
        
        try:
            memory_content = f"Reflection on {reflection_entry['subject']}: {len(reflection_entry['learning_points'])} learning points identified"
            
            metadata = {
                "type": "reflection",
                "subject": reflection_entry["subject"],
                "timestamp": reflection_entry["timestamp"],
                "learning_points": reflection_entry["learning_points"]
            }
            
            brain.mem.add(memory_content, metadata=metadata)
        except Exception:
            pass  # 静默失败