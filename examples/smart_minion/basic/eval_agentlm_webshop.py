# Evaluate AgentLM-7B on WebShop task.
# 200 data pieces, max_length=4096, max_rounds=20


import os

from agentenv.controller import Agent, Evaluator

# from agentenv.envs import WebshopTask
from agentenv.envs import AlfWorldTask
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

PYTORCH_MPS_HIGH_WATERMARK_RATIO = 0.0


os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

MODEL_PATH = "THUDM/agentlm-7b"

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, device_map="auto", trust_remote_code=True).eval()

evaluator = Evaluator(
    Agent(model, tokenizer),
    [
        AlfWorldTask(
            client_args={
                "env_server_base": "http://127.0.0.1:36001",  # If you have modified the port, modify it here.
                "data_len": 200,  # Currently, the data_len argument is of no use. It will be removed in future versions.
                "timeout": 300,
            },
            # The n_clients argument is reserved for subsequent implementations of batch generation. Please leave it at 1.
            n_clients=1,
        )
    ],
)

exps = evaluator.eval(
    generation_config=GenerationConfig(
        max_length=4096,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
    ),
    max_rounds=7,
    idxs=list(range(200)),
)

print("\n\n==== EVALUATION ====\n")
print(f"Score: {exps.score}")
print(f"Success: {exps.success}")

print("\n\n==== EXPERIENCES ====\n")
for idx, exp in enumerate(exps.experiences[:3]):
    print(f"\n\n==== EXP {idx} ====\n")
    for message in exp.conversation:
        if message["from"] == "gpt":
            print(f"\n### Agent\n{message['value']}")
        else:
            print(f"\n### Env\n{message['value']}")
