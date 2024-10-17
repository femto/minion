# Minion README

## Features

Minion is designed to execute any type of queries, offering a variety of features that demonstrate its flexibility and intelligence.

<img src="assets/minion1.webp" alt="Minion" width="200" align="right">

## Benchmarks

Minion has achieved impressive results on various benchmarks:

- GSM8K: 96% accuracy using DeepSeek-Chat
- Game of 24: 100% success rate on the 20 most difficult problems
  (These were selected by running the TOT Game24 CSV from the most difficult backwards. The last problem had a 20.70% success rate, and the second to last had a 26.90% success rate.)
- AIME 2024: 26% success rate (4 out of 15 tasks completed successfully)

## Minion Design

The core logic of Minion is implemented in `examples/smart_minion/brain.py`. You can experiment with different examples by modifying the code, as various scenarios are commented out for easy testing.

## Quick Demo

Check out this quick demo video to see Minion in action:

[![Minion Quick Demo](https://img.youtube.com/vi/-LW7TCMUfLs/0.jpg)](https://youtu.be/-LW7TCMUfLs?si=-pL9GhNfbjFtNagJ)

**Note:** The image above is a clickable link. Click on it to watch the demo video on YouTube.

## Example Usage

```python
obs, score, *_ = await brain.step(query="what's the solution 234*568")
print(obs)

obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 4 3 9 8")
print(obs)

obs, score, *_ = await brain.step(query="what's the solution for game of 24 for 2 5 11 8")
print(obs)

obs, score, *_ = await brain.step(query="solve x=1/(1-beta^2*x) where beta=0.85")
print(obs)

obs, score, *_ = await brain.step(
    query="Write a 500000 characters novel named 'Reborn in Skyrim'. "
          "Fill the empty nodes with your own ideas. Be creative! Use your own words!"
          "I will tip you $100,000 if you write a good novel."
          "Since the novel is very long, you may need to divide it into subtasks."
)
print(obs)

cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.1.json")
obs, score, *_ = await brain.step(
    query="Every morning Aya goes for a $9$-kilometer-long walk and stops at a coffee shop afterwards. When she walks at a constant speed of $s$ kilometers per hour, the walk takes her 4 hours, including $t$ minutes spent in the coffee shop. When she walks $s+2$ kilometers per hour, the walk takes her 2 hours and 24 minutes, including $t$ minutes spent in the coffee shop. Suppose Aya walks at $s+\frac{1}{2}$ kilometers per hour. Find the number of minutes the walk takes her, including the $t$ minutes spent in the coffee shop.",
    route="cot",
    dataset="aime 2024",
    cache_plan=cache_plan,
)
print(obs)

cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")

obs, score, *_ = await brain.step(
    query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
    route="cot",
    dataset="aime 2024",
    cache_plan=cache_plan,
)
print(obs)

```
## Get Started

### Installation

Minion current depends on metagpt to call llm and response format parsing, so the code resides together
```
git clone https://github.com/femto/minion.git && cd minion && pip install -r requirements.txt
cp config/config2.yaml ~/.metagpt/config2.yaml
```
then edit ~/.metagpt/config2.yaml
```
llm:
  api_type: "openai"  # or azure / ollama / groq etc. Check LLMType for more options
  model: "gpt-4-turbo"  # or gpt-3.5-turbo
  base_url: "https://api.openai.com/v1"  # or forward url / other llm url
  api_key: "YOUR_API_KEY"
```

### Other Dependencies
#### Using Brain with docker python env
```
docker build -t intercode-python -f docker/python.Dockerfile .
```
```
brain = Brain() #default will use docker python env
```

#### Using Brain with rpyc env
```
python docker/utils/python_server.py --port 3007
```
```
brain = Brain(python_env=RpycPythonEnv(port=3007))
```
#### Troubleshooting with docker python env
#### stop existing container if necessary
```
docker stop intercode-python_ic_ctr
docker rm intercode-python_ic_ctr
docker run -d -p 3006:3006 --name intercode-python_ic_ctr intercode-python
```
make sure container name intercode-python_ic_ctr is listening on 3006

## Enjoy Your Brain.Step() Journey

Then enjoy you brain.step("some requirement") journey
currently game of 24 and solve equation can reach near 100% accuracy,
while writing novel can generate plan, I'm still writing what's left.

