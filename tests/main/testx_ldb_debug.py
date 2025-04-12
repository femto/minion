from LLMDebugger.programming.generators import PyGenerator, model_factory
from LLMDebugger.programming.executors import PyExecutor

class MockModel:
    def generate(self, prompt):
        return "Mock model response"
    
    def generate_completion(self, messages, stop=None, temperature=0):
        return "[debug]\nMock debug explanation\n[/debug]"
    
    @property
    def is_chat(self):
        return False

def process_numbers(numbers):
    """Process a list of numbers and return sum of even numbers"""
    result = 0
    for num in numbers:
        if num % 2 == 0:
            result += num
    return result

def main():
    # Initialize components with mock model but real generator
    gen = PyGenerator()
    model = MockModel()
    exe = PyExecutor()
    
    # Test case that will fail - now at top level
    test_case = """
result = process_numbers([1, 2, 3, 4])
assert result == 0, f"Expected 0 but got {result}"
"""
    
    # Prepare the function implementation
    func_impl = inspect.getsource(process_numbers)
    
    # Execute test to get failure
    tests = [test_case]
    is_passing, failed_tests, _ = exe.execute(func_impl, tests)
    
    print(f"is_passing: {is_passing}")
    print(f"failed_tests: {failed_tests}")
    
    if not failed_tests:
        print("No failed tests!")
        return
        
    # Call ldb_debug with real generator but mock model
    messages = gen.ldb_debug(
        prompt=func_impl,
        prev_func_impl=func_impl,
        failed_test=failed_tests[0],
        entry="process_numbers",
        model=model,
        messages="",
        dataset_type="HumanEval",
        level="block"
    )
    
    print("\nDebug Messages:")
    print(messages)

if __name__ == "__main__":
    import inspect
    main() 