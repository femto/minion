# ALFWorld Brain

This is an implementation of a brain that can play ALFWorld games using the minion framework.

## Overview

ALFWorld is a text-based environment for embodied AI research. It provides a way to interact with simulated household environments through text commands. This implementation uses the ALFWorldClient to communicate with the ALFWorld server and the Brain class from the minion framework to make decisions.

## Prerequisites

Before using this brain, you need to:

1. Have the ALFWorld server running (typically on http://localhost:5000)
2. Have the minion framework installed and configured
3. Have a language model configured in your minion config (e.g., GPT-4o)

## Files

- `alfworld_client.py`: A client for interacting with the ALFWorld server
- `alfworld_brain.py`: The basic brain implementation that uses the client and the minion framework
- `alfworld_planner_brain.py`: An advanced brain implementation with planning capabilities
- `alfworld_example.py`: An example script that demonstrates how to use the brains

## Usage

### Running the Example Script

The example script provides a convenient way to run the brains with various options:

```bash
# Show example tasks
python alfworld_example.py --examples

# Run with the default task from the environment
python alfworld_example.py

# Run with a custom task
python alfworld_example.py --task "find two soapbottle and put them in cabinet"

# Run with the planner brain
python alfworld_example.py --planner --task "find two soapbottle and put them in cabinet"

# Run with the planner brain and save results
python alfworld_example.py --planner --task "find two soapbottle and put them in cabinet" --save-results

# Run with a maximum number of steps
python alfworld_example.py --planner --task "find two soapbottle and put them in cabinet" --max-steps 30
```

### Using the Basic Brain

To use the basic brain in your own code:

```python
import asyncio
from alfworld_brain import alfworld_brain, run_alfworld_with_custom_task

# Run with the default task
asyncio.run(alfworld_brain())

# Run with a custom task
custom_task = "find two soapbottle and put them in cabinet"
asyncio.run(run_alfworld_with_custom_task(custom_task))
```

### Using the Planner Brain

To use the planner brain in your own code:

```python
import asyncio
from alfworld_planner_brain import run_planner_brain, ALFWorldPlannerBrain

# Run with a custom task
custom_task = "find two soapbottle and put them in cabinet"
asyncio.run(run_planner_brain(custom_task))

# Or use the class directly for more control
async def run_custom_planner():
    planner = ALFWorldPlannerBrain(model_name="gpt-4o")
    results = await planner.run(custom_task="find a knife and put it in the drawer")
    await planner.save_results(results, "my_results.json")

asyncio.run(run_custom_planner())
```

## How It Works

### Basic Brain

The basic brain follows a simple approach:

1. Initialize the ALFWorld client and connect to the server
2. Reset the environment to get the initial observation and admissible commands
3. Extract the task from the observation or use a custom task
4. For each step:
   - Use the Brain class to decide what action to take based on the current observation, admissible commands, and task
   - Extract the action from the brain's response
   - Take the action and update the state
   - Repeat until the task is completed or a maximum number of steps is reached
5. Print a summary of the game

### Planner Brain

The planner brain uses a more sophisticated approach:

1. Initialize the ALFWorld client and connect to the server
2. Reset the environment to get the initial observation and admissible commands
3. Extract the task from the observation or use a custom task
4. Create a high-level plan for completing the task
5. For each step:
   - Use the Brain class to decide what action to take based on the current plan step, observation, and admissible commands
   - Extract the action from the brain's response
   - Take the action and update the state
   - Update the progress in the plan
   - Repeat until the task is completed or a maximum number of steps is reached
6. Print a summary of the game and save the results if requested

## Customization

You can customize the brains by:

- Changing the language model used (modify the `model` variable)
- Adjusting the prompt templates to provide more or less context
- Modifying the action selection logic
- Adding additional features like memory or learning

### Customizing the Planner Brain

The planner brain is designed to be more extensible:

- You can modify the planning prompt to generate different types of plans
- You can adjust the plan progress tracking to be more or less strict
- You can add additional planning features like replanning or hierarchical planning

## Example Tasks

Here are some example tasks you can try:

- "find two soapbottle and put them in cabinet"
- "put a mug in the microwave"
- "find a knife and put it in the drawer"
- "find an apple and place it in the fridge"
- "clean the toilet with a cloth"
- "heat a pot on the stove"

## Troubleshooting

If you encounter issues:

1. Make sure the ALFWorld server is running
2. Check that your language model is properly configured
3. Verify that the Python environment is set up correctly
4. Look for error messages in the console output

### Common Issues

- **Server not running**: Make sure the ALFWorld server is running on the correct port
- **Invalid actions**: The brain might generate actions that are not in the list of admissible commands
- **Task not completed**: The brain might not be able to complete the task within the maximum number of steps
- **TypeError: sequence item 0: expected str instance, list found**: This error occurs because the ALFWorld server sometimes returns admissible_commands as a list of lists instead of a list of strings. The code has been updated to handle this case by flattening the list.

## Advanced Features

### Basic Brain Features

- History tracking to maintain context across steps
- Step-by-step reasoning to make better decisions
- Multiple action selection strategies (exact match, partial match, random)
- Game summary generation for analysis

### Planner Brain Features

- High-level planning to break down the task into steps
- Plan progress tracking to monitor completion of each step
- Results saving to analyze performance
- Customizable planning and execution strategies

## Implementation Notes

### Handling Admissible Commands

The ALFWorld server sometimes returns admissible commands as a list of lists (e.g., `[['go to bed 1', 'go to cabinet 1', ...]]`) instead of a simple list of strings. To handle this, the code checks the structure of the admissible_commands and flattens it if necessary:

```python
# Handle the case where admissible_commands is a list of lists
if admissible_commands and isinstance(admissible_commands, list) and isinstance(admissible_commands[0], list):
    admissible_commands = admissible_commands[0]
```

This check is performed in several places:
- After resetting the environment
- After each step
- Before creating a plan
- Before selecting an action
- Before updating plan progress

## Performance

The performance of the brains depends on several factors:

- The complexity of the task
- The quality of the language model
- The environment configuration
- The prompt design

In general, the planner brain tends to perform better on complex tasks that require multiple steps, while the basic brain might be sufficient for simpler tasks.

## Contributing

Feel free to contribute to this implementation by adding new features, improving the decision-making logic, or fixing bugs.

## License

This project is licensed under the same license as the minion framework. 