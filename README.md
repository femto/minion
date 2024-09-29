# Minion README

## Features

Minion is designed to execute and analyze complex queries, offering a variety of features that demonstrate its flexibility and intelligence.

## Minion Design

The core logic of Minion is implemented in `examples/smart_minion/brain.py`. You can experiment with different examples by modifying the code, as various scenarios are commented out for easy testing.

### Example Usage

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

cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.3.json")
obs, score, *_ = await brain.step(
    query="Alice and Bob play the following game. A stack of $n$ tokens lies before them. The players take turns with Alice going first. On each turn, the player removes $1$ token or $4$ tokens from the stack. The player who removes the last token wins. Find the number of positive integers $n$ less than or equal to $2024$ such that there is a strategy that guarantees that Bob wins, regardless of Alice’s moves.",
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

