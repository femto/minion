#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker minions module - re-exports from split files for backward compatibility.

This file maintains backward compatibility by importing and re-exporting all worker
minion classes from their respective modules:
- base_workers.py: WorkerMinion, RawMinion, NativeMinion
- cot_workers.py: CotMinion, DcotMinion
- plan_workers.py: PlanMinion, TaskMinion, CodeProblemMinion
- code_workers.py: PythonMinion, CodeMinion
- utility_workers.py: ModeratorMinion, IdentifyMinion, QaMinion, RouteMinion, OptillmMinion
"""

# Base workers
from minion.main.base_workers import (
    WorkerMinion,
    RawMinion,
    NativeMinion,
)

# Chain of Thought workers
from minion.main.cot_workers import (
    CotMinion,
    DcotMinion,
)

# Planning workers
from minion.main.plan_workers import (
    PlanMinion,
    TaskMinion,
    CodeProblemMinion,
)

# Code execution workers
from minion.main.code_workers import (
    PythonMinion,
    CodeMinion,
)

# Utility workers
from minion.main.utility_workers import (
    ModeratorMinion,
    IdentifyMinion,
    QaMinion,
    RouteMinion,
    OptillmMinion,
)

# Re-export registries and utilities from minion module
from minion.main.minion import (
    MINION_REGISTRY,
    WORKER_MINIONS,
    RESULT_STRATEGY_REGISTRY,
    register_worker_minion,
    register_minion_for_route,
)

# Re-export AgentResponse for convenience
from minion.types.agent_response import AgentResponse

__all__ = [
    # Base workers
    'WorkerMinion',
    'RawMinion',
    'NativeMinion',
    # COT workers
    'CotMinion',
    'DcotMinion',
    # Plan workers
    'PlanMinion',
    'TaskMinion',
    'CodeProblemMinion',
    # Code workers
    'PythonMinion',
    'CodeMinion',
    # Utility workers
    'ModeratorMinion',
    'IdentifyMinion',
    'QaMinion',
    'RouteMinion',
    'OptillmMinion',
    # Registries
    'MINION_REGISTRY',
    'WORKER_MINIONS',
    'RESULT_STRATEGY_REGISTRY',
    'register_worker_minion',
    'register_minion_for_route',
    # Types
    'AgentResponse',
]
