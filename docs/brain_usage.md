# Brain Usage Guide

Brain is the core reasoning engine of Minion. This document covers how to use `brain.step()` for various tasks.

## Basic Usage

```python
from minion.main.brain import Brain

brain = Brain()

# Simple math
obs, score, *_ = await brain.step(query="what's the solution 234*568")
print(obs)
```

## Example Queries

### Math Problems

```python
# Basic arithmetic
obs, score, *_ = await brain.step(query="what's the solution 234*568")
print(obs)

# Game of 24
obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 4 3 9 8")
print(obs)

obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 2 5 11 8")
print(obs)

# Equation solving
obs, score, *_ = await brain.step(query="solve x=1/(1-beta^2*x) where beta=0.85")
print(obs)
```

### Long-form Content Generation

```python
obs, score, *_ = await brain.step(
    query="Write a 500000 characters novel named 'Reborn in Skyrim'. "
          "Fill the empty nodes with your own ideas. Be creative! Use your own words!"
          "I will tip you $100,000 if you write a good novel."
          "Since the novel is very long, you may need to divide it into subtasks."
)
print(obs)
```

### Competition Problems (AIME)

```python
import os

current_file_dir = os.path.dirname(__file__)

# AIME Problem 1
cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.1.json")
obs, score, *_ = await brain.step(
    query="Every morning Aya goes for a $9$-kilometer-long walk and stops at a coffee shop afterwards. When she walks at a constant speed of $s$ kilometers per hour, the walk takes her 4 hours, including $t$ minutes spent in the coffee shop. When she walks $s+2$ kilometers per hour, the walk takes her 2 hours and 24 minutes, including $t$ minutes spent in the coffee shop. Suppose Aya walks at $s+\frac{1}{2}$ kilometers per hour. Find the number of minutes the walk takes her, including the $t$ minutes spent in the coffee shop.",
    route="cot",
    dataset="aime 2024",
    cache_plan=cache_plan,
)
print(obs)

# AIME Problem 7
cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")
obs, score, *_ = await brain.step(
    query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
    route="cot",
    dataset="aime 2024",
    cache_plan=cache_plan,
)
print(obs)
```

## Routes

The `route` parameter controls the reasoning strategy:

- `"cot"` - Chain of Thought reasoning
- `"code"` - Code-based reasoning (uses CodeMinion)
- `"direct"` - Direct answer without complex reasoning

See [Route Parameter Guide](agent_route_parameter_guide.md) for more details.

## Python Environment Options

### Docker Python Environment (Recommended)

```bash
docker build -t intercode-python -f docker/python.Dockerfile .
```

```python
brain = Brain()  # Default uses docker python env
```

## Related Documentation

- [CodeAgent Documentation](merged_code_agent.md) - For the newer Agent-based API
- [Route Parameter Guide](agent_route_parameter_guide.md) - Detailed route options
- [Brain Python Environment](brain_python_env.md) - Python environment configuration
