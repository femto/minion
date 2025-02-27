import asyncio

from mem0 import MemoryClient

from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion import config
from examples.agents.customer_service import CustomerServiceAgent
from minion.providers import create_llm_provider


async def main():
    # Create Customer Service Agent
    python_env_config = {"port": 3007}
    
    # Get mem0 configuration from config
    memory_config = config.mem0

    model = "gpt-4o"
    # model = "deepseek-r1"
    # model = "phi-4"
    # model = "llama3.2"
    llm_config = config.models.get(model)

    llm = create_llm_provider(llm_config)
    
    brain = Brain(
        python_env=RpycPythonEnv(port=python_env_config.get("port", 3007)),
        #memory=MemoryClient(api_key="m0-yCXYU9soW9FGC9iNg3j1uy8OSeRcELvqpdbAx9Yu"),
        memory_config=memory_config,
        llm=llm
    )
    agent = CustomerServiceAgent(brain=brain, user_id="@test")

    # Add user order memory
    agent.add_memory([
        {
            "role": "user",
            "content": "User Order Information: Order ID ORD001, containing Product A (2 units, unit price $99.99) and Product B (1 unit, unit price $199.99), "
                      "total price $399.97. Order created on 2024-02-01 10:00 and delivered on 2024-02-03 14:30."
        }
    ], metadata={
        "type": "order",
        "order_id": "ORD001",
        "user_id": "USR001",
        "status": "delivered",
        "items": [
            {"name": "Product A", "quantity": 2, "price": 99.99},
            {"name": "Product B", "quantity": 1, "price": 199.99}
        ],
        "total": 399.97,
        "created_at": "2024-02-01T10:00:00Z",
        "delivered_at": "2024-02-03T14:30:00Z"
    })
    
    # Retrieve memories by metadata
    order_memories = agent.get_all_memories(filter={"type": "order"})
    print("\nRetrieved Order Memories:")
    for memory in order_memories:
        print(f"Memory ID: {memory.id}")
        print(f"Content: {memory.messages[0]['content']}")
        print(f"Metadata: {memory.metadata}")

    # Search memories semantically
    search_results = agent.search_memories(query="order delivery status", top_k=5)
    print("\nSemantic Search Results:")
    for result in search_results:
        # Handle the case where result might be a string
        if isinstance(result, str):
            print(f"Content: {result}")
        else:
            # Try to access attributes if result is an object
            try:
                print(f"Score: {result.score}")
                print(f"Content: {result.messages[0]['content']}")
            except AttributeError:
                print(f"Result: {result}")

    # Get conversation history
    conversation_history = agent.get_conversation_history()
    print("\nConversation History from Memory:")
    for message in conversation_history:
        print(f"Role: {message['role']}, Content: {message['content']}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 