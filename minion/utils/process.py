import sys
import subprocess
import tempfile
import os
import re
from typing import NamedTuple
from dataclasses import dataclass


@dataclass
class ProcessResult:
    """Result of running code in a separate process."""
    stdout: str
    stderr: str
    return_code: int

    @property
    def success(self) -> bool:
        """Whether the process executed successfully."""
        return self.return_code == 0


def _has_main_structure(code: str) -> tuple[bool, bool]:
    """Check if code already has main function and/or main guard.
    
    Returns:
        Tuple of (has_main_func, has_main_guard)
    """
    # Simple pattern matching for main function and guard
    has_main_func = bool(re.search(r'def\s+main\s*\(', code))
    has_main_guard = 'if __name__ == "__main__":' in code or "if __name__ == '__main__':" in code
    return has_main_func, has_main_guard


def run_code_in_separate_process(
    code: str,
    input_data: str = "",
    timeout: int = 120,
    indent: str = "    "  # Default indentation for the code
) -> ProcessResult:
    """Run Python code in a separate process with the given input data.
    
    Args:
        code: The Python code to execute
        input_data: Input data to feed to the process's stdin
        timeout: Maximum execution time in seconds
        indent: Indentation to use for the code in the main function
    
    Returns:
        ProcessResult containing stdout, stderr, and return code
        
    Raises:
        TimeoutError: If the code execution exceeds the timeout
        subprocess.SubprocessError: If there's an error running the subprocess
    """
    has_main_func, has_main_guard = _has_main_structure(code)
    
    # If code already has both main structures, use it as is
    if has_main_func and has_main_guard:
        wrapper_code = code
    # If code has main function but no guard, add the guard
    elif has_main_func:
        wrapper_code = f'''{code}

if __name__ == "__main__":
    main()'''
    # If code has neither, wrap it in both
    else:
        # Indent the code
        indented_code = "\n".join(indent + line if line.strip() else line 
                                 for line in code.splitlines())
        
        wrapper_code = f'''
import sys

def main():
{indented_code}

if __name__ == "__main__":
    main()
'''
    
    # Create a temporary Python file with the code
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(wrapper_code)
        temp_file = f.name

    try:
        # Run the code in a separate process
        process = subprocess.Popen(
            [sys.executable, temp_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send input and get output with timeout
        try:
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            return ProcessResult(
                stdout=stdout,
                stderr=stderr,
                return_code=process.returncode
            )
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError("Code execution timed out")
            
    finally:
        # Clean up the temporary file
        os.unlink(temp_file) 