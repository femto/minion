# LocalPythonEnv

`LocalPythonEnv` is a lightweight Python code execution environment for Coding Agents that doesn't require Docker or rpyc. It provides a safe and controlled environment for executing Python code locally.

## Features

- Execute Python code in a controlled local environment
- Capture stdout and stderr output
- Handle exceptions gracefully
- Support for multiline code input
- Automatic wrapping of expressions with print()
- Compatible with the IntercodeEnv interface
- **Automatic variable value display** - Shows the value of variables after assignment
- **Last expression result capture** - Stores and displays the result of the last expression
- **Variable inspection** - Type a variable name to see its value
- **Special `_` variable** - Access the last expression result, similar to Python's interactive interpreter

## Usage

### Basic Usage

```python
from minion.main.local_python_env import LocalPythonEnv

# Initialize the environment
env = LocalPythonEnv(verbose=True)

# Execute some code
observation, reward, terminated, truncated, info = env.step("print('Hello, World!')")
print(observation["output"])  # Output: Hello, World!

# Execute code with an error
observation, reward, terminated, truncated, info = env.step("1/0")
print(observation["error"])  # Output: ZeroDivisionError: division by zero

# Variable assignment will show the value
observation, reward, terminated, truncated, info = env.step("x = 42")
print(observation["output"])  # Output: x = 42

# Access the last result using the special _ variable
observation, reward, terminated, truncated, info = env.step("_")
print(observation["output"])  # Output: 42
```

## Special Features

### Variable Inspection

Simply type a variable name to see its value:

```python
# First define a variable
env.step("numbers = [1, 2, 3, 4]")

# Then inspect it by typing just the variable name
env.step("numbers")  # Output: numbers = [1, 2, 3, 4]
```

### Last Result Access

Use the special `_` variable to access the result of the last expression:

```python
env.step("2 + 2")  # Output: 4
env.step("_")      # Output: 4
env.step("_ * 2")  # Output: 8
```

### Automatic Variable Display

When you assign a value to a variable, the environment will automatically show the value:

```python
env.step("solution = solve_game_of_24([2, 4, 5, 8])")  # Output: solution = "2 * (4 + 8) - 5"
```

## Examples

Check out the example scripts in the `examples` directory:

- `local_python_env_example.py`: A simple interactive Python shell using LocalPythonEnv

## Running the Examples

```bash
# Run the simple interactive example
python examples/local_python_env_example.py

```

## Implementation Details

The `LocalPythonEnv` class implements the `IntercodeEnv` interface, making it compatible with existing code that uses the `PythonEnv` or `RpycPythonEnv` classes. It uses Python's built-in `exec()` function to execute code in a controlled environment, capturing stdout and stderr using `StringIO` and `redirect_stdout`/`redirect_stderr`.

### Key Methods

- `step(action)`: Execute the given action (Python code) and return the result
- `execute_code(code)`: Execute Python code in the local environment
- `reset_local_env()`: Reset the local execution environment
- `wrap_with_print(command)`: Wrap expressions with print() if they don't already have side effects
- `_is_variable_inspection(code)`: Check if the code is a request to inspect a variable
- `_extract_last_assigned_var(code)`: Extract the name of the last variable being assigned

## Security Considerations

The `LocalPythonEnv` executes code in the same process as your application, which can be a security risk if used with untrusted code. It's recommended to use this environment only with trusted code or in a sandboxed environment.

For production use cases with untrusted code, consider using the Docker-based `PythonEnv` implementation instead, which provides better isolation. 