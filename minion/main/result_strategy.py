from typing import Dict, Any, List
from collections import Counter
from minion.main.minion import Minion, register_result_strategy

class ResultStrategy(Minion):
    """Base class for result processing strategies"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workers = kwargs.get('workers', [])  # List of actual worker instances
        
    async def execute(self) -> str:
        """Process the results according to the strategy
        
        Returns:
            The processed final result
        """
        raise NotImplementedError

@register_result_strategy
class MajorityVotingStrategy(ResultStrategy):
    """Strategy that selects result with highest vote count"""
    
    async def execute(self) -> str:
        if not self.workers:
            return ""
            
        # Count answers from workers
        results = Counter(worker.answer for worker in self.workers)
        total_count = len(self.workers)
        majority_count = total_count // 2 + 1
        
        # Check for majority
        for result, count in results.items():
            if count >= majority_count:
                return result
                
        # No majority reached, return most common
        return results.most_common(1)[0][0]

@register_result_strategy
class BestOfNStrategy(ResultStrategy):
    """Strategy that selects the best result based on a scoring function"""
    
    async def execute(self) -> str:
        if not self.workers:
            return ""
            
        # Score each worker's answer
        scores = {}
        for worker in self.workers:
            result = worker.answer
            # Score could be based on worker configuration and state
            check_count = worker.worker_config.get("check", 0) if worker.worker_config else 0
            # Add more sophisticated scoring logic here
            if result in scores:
                scores[result] = max(scores[result], check_count)
            else:
                scores[result] = check_count
            
        if not scores:
            return self.workers[0].answer if self.workers else ""
            
        return max(scores.items(), key=lambda x: x[1])[0]

@register_result_strategy
class UscStrategy(ResultStrategy):
    """Strategy that combines self-consistent results"""
    
    async def execute(self) -> str:
        if not self.workers:
            return ""
            
        # Count answers for now, but could implement more sophisticated
        # consistency checking in the future
        results = Counter(worker.answer for worker in self.workers)
        return results.most_common(1)[0][0]


@register_result_strategy
class UsccStrategy(ResultStrategy):
    """Strategy that combines self-consistent results"""

    async def execute(self) -> str:
        if not self.workers:
            return ""

        # Count answers for now, but could implement more sophisticated
        # consistency checking in the future
        results = Counter(worker.answer for worker in self.workers)
        return results.most_common(1)[0][0]

@register_result_strategy
class CodiumStrategy(ResultStrategy):
    """Strategy that implements Codium's solution ranking and improvement process"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.solid_test_cases = {
            'public': [],  # todo: bootstrap a List of verified public test cases
            'ai': []      # todo: bootstrap a  List of verified AI-generated test cases
        }
        self.max_improvement_attempts = 3

    def _process_test_cases(self, test_cases, entry_point="main"):
        """Process test cases from metadata format to internal format"""
        if not test_cases or not isinstance(test_cases, dict):
            return []

        inputs = test_cases.get('input', [])
        outputs = test_cases.get('output', [])

        # Ensure we have matching input/output pairs
        return list(zip(inputs, outputs))

    async def rank_solutions(self):
        """Rank solutions based on initial quality metrics"""
        ranked_solutions = []
        for worker in self.workers:
            score = 0
            # Add scoring logic here - could be based on:
            # - Code complexity
            # - Test case coverage
            # - Worker's confidence score
            # - Previous success rate
            score += worker.worker_config.get("check", 0) if worker.worker_config else 0
            ranked_solutions.append((worker, score))
            
        return sorted(ranked_solutions, key=lambda x: x[1], reverse=True)
        
    async def verify_test_case(self, test_case, solution):
        """Verify if a test case is solid by checking if solution passes it"""
        try:
            # Implementation would depend on your test execution framework
            # This is a placeholder for the actual test execution logic
            result = await self.execute_test(test_case, solution)
            return result.success
        except Exception as e:
            return False
            
    async def improve_solution(self, worker, iteration=0):
        """Improve a solution using public tests and AI-generated tests"""
        # First, ensure solution passes all solid test cases
        for test_type, test_cases in self.solid_test_cases.items():
            for test_case in test_cases:
                if not await self.verify_test_case(test_case, worker.answer):
                    return False
                    
        # Try to improve the solution
        if not await worker.improve():
            return False
            
        # Verify and add passing public tests to solid test cases
        for test in worker.input.metadata.get("test_cases", []):
            if await self.verify_test_case(test, worker.answer):
                if test not in self.solid_test_cases['public']:
                    self.solid_test_cases['public'].append(test)
                    
        # Verify and add passing AI tests to solid test cases
        for test in worker.input.metadata.get("ai_test_cases", []):
            if await self.verify_test_case(test, worker.answer):
                if test not in self.solid_test_cases['ai']:
                    self.solid_test_cases['ai'].append(test)
                    
        return True
        
    async def execute(self) -> str:
        if not self.workers:
            return ""
            
        # Rank initial solutions
        ranked_solutions = await self.rank_solutions()
        
        # Try solutions in ranked order
        for worker, score in ranked_solutions:
            for attempt in range(self.max_improvement_attempts):
                if await self.improve_solution(worker, attempt):
                    return worker.answer
                    
        # If no solution passes all tests, return the highest ranked solution
        return ranked_solutions[0][0].answer