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
        # Handle memory as a dictionary
        if isinstance(memory, dict):
            print(f"Memory ID: {memory.get('id')}")
            # Check if 'messages' exists and is a list with at least one item
            if 'messages' in memory and isinstance(memory['messages'], list) and memory['messages']:
                print(f"Content: {memory['messages'][0].get('content', 'No content')}")
            elif 'memory' in memory:  # Some memory objects might have a 'memory' field instead
                print(f"Content: {memory.get('memory', 'No content')}")
            else:
                print("Content: No content available")
            print(f"Metadata: {memory.get('metadata', {})}")
        else:
            # Try to handle as an object with attributes (fallback)
            try:
                print(f"Memory ID: {memory.id}")
                print(f"Content: {memory.messages[0]['content']}")
                print(f"Metadata: {memory.metadata}")
            except AttributeError as e:
                print(f"Error accessing memory attributes: {e}")
                print(f"Memory object: {memory}")

    # Search memories semantically (without relations)
    search_results = agent.search_memories(query="order delivery status", top_k=5)
    print("\nSemantic Search Results (without relations):")
    for result in search_results:
        # Handle the case where result might be a string
        if isinstance(result, str):
            print(f"Content: {result}")
        elif isinstance(result, dict):
            # Handle result as a dictionary
            print(f"Score: {result.get('score', 'N/A')}")
            if 'messages' in result and isinstance(result['messages'], list) and result['messages']:
                print(f"Content: {result['messages'][0].get('content', 'No content')}")
            elif 'memory' in result:
                print(f"Content: {result.get('memory', 'No content')}")
            else:
                print("Content: No content available")
        else:
            # Try to access attributes if result is an object
            try:
                print(f"Score: {result.score}")
                print(f"Content: {result.messages[0]['content']}")
            except AttributeError:
                print(f"Result: {result}")
    
    # Search memories semantically (with relations)
    search_with_relations = agent.search_memories(query="order delivery status", top_k=5, include_relations=True)
    print("\nSemantic Search Results (with relations):")
    if isinstance(search_with_relations, dict) and 'results' in search_with_relations:
        # Print vector results
        print("Vector Results:")
        for result in search_with_relations.get('results', []):
            if isinstance(result, dict):
                print(f"  Memory: {result.get('memory', 'N/A')}")
                print(f"  Metadata: {result.get('metadata', {})}")
        
        # Print graph relations if available
        if 'relations' in search_with_relations:
            print("\nGraph Relations:")
            for relation in search_with_relations.get('relations', []):
                if isinstance(relation, dict):
                    print(f"  Relation: {relation}")
    else:
        # Handle case where relations are not available
        print("Relations not available in the response or API version doesn't support relations.")
        print(f"Response type: {type(search_with_relations)}")
        if isinstance(search_with_relations, list):
            print(f"Number of results: {len(search_with_relations)}")

    # Get conversation history
    conversation_history = agent.get_conversation_history()
    print("\nConversation History from Memory:")
    for message in conversation_history:
        # Handle different message formats
        if isinstance(message, dict):
            role = message.get('role', 'unknown')
            content = message.get('content', 'No content')
            print(f"Role: {role}, Content: {content}")
        else:
            # Try to handle as an object with attributes
            try:
                print(f"Role: {message.role}, Content: {message.content}")
            except AttributeError:
                print(f"Message format not recognized: {message}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 