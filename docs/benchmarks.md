# Benchmarks

Minion has achieved impressive results on various benchmarks:

## Summary

| Benchmark | Score | Model |
|-----------|-------|-------|
| GSM8K | 96% accuracy | DeepSeek-Chat |
| Game of 24 | 100% success rate | - |
| AIME 2024 | 26% (4/15 tasks) | - |
| Humaneval | 98.2% pass@1 | GPT-4o |

## GSM8K

- **96% accuracy** using DeepSeek-Chat

## Game of 24

- **100% success rate** on the 20 most difficult problems
- These were selected by running the TOT Game24 CSV from the most difficult backwards
- The last problem had a 20.70% success rate
- The second to last had a 26.90% success rate

## AIME 2024

- **26% success rate** (4 out of 15 tasks completed successfully)

## Humaneval

- **98.2% pass@1** rate using GPT-4o

## Running Benchmarks

Minion supports processing various benchmarks through configurable workflows. You can find examples in:

- `examples/smart_minion/gsm8k/`: Math word problem solving
- `examples/smart_minion/code_contests/`: Code competition problem solving

### Configuration-based Workflow

Each benchmark can be configured using a JSON configuration file that defines the processing pipeline. For example, `examples/smart_minion/code_contests/code_contests_config.json` demonstrates an ensemble approach:

```json
{
  "type": "ensemble",
  "pre_processing": ["problem_reflect", "example_reasoning"],
  "workers": [
    {
      "name": "python",
      "count": 3,
      "check": 1,
      "check_route": "codium_check",
      "post_processing": "extract_python"
    }
  ],
  "result_strategy": {
    "name": "majority_voting"
  }
}
```

This configuration allows you to define:
- Pre-processing steps for problem analysis
- Multiple worker configurations for ensemble solutions
- Verification and post-processing steps
- Result aggregation strategies

You can create similar configurations for your own benchmarks by following these examples.
