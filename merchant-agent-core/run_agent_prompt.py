import sys
from app.config.settings import get_settings
from app.llm.llm_client import create_llm_client
from app.llm.prompt_manager import PromptManager
from app.tools.tool_client import ToolClient
from app.agent.merchant_agent import MerchantAgent

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_agent_prompt.py '<prompt>'")
        sys.exit(1)
        
    prompt = sys.argv[1]
    settings = get_settings()
    
    print(f"Initialising agent with LLM provider: {settings.llm_provider.value} ({settings.llm_model})")
    
    tool_client = ToolClient(settings)
    llm_client = create_llm_client(settings)
    prompt_manager = PromptManager()
    
    agent = MerchantAgent(
        llm_client=llm_client,
        tool_client=tool_client,
        prompt_manager=prompt_manager,
        max_iterations=settings.agent_max_iterations
    )
    
    print(f"\nUser Prompt: {prompt}\n")
    print("Running agent loop...")
    try:
        state = agent.run(user_request=prompt, user_id=42)
        print("\n=== Agent Response ===")
        print(f"Status: {state.status.value}")
        if state.final_response:
            print(f"Response: {state.final_response}")
        if state.error:
            print(f"Error: {state.error}")
            
        print("\n=== Tool Calls Made ===")
        for i, call in enumerate(state.tool_results):
            print(f"{i+1}. Tool: {call.tool_name} | Args: {call.arguments}")
            if call.result:
                print(f"   Success: {call.result.success} | Data: {call.result.data}")
            if call.error:
                print(f"   Transport Error: {call.error}")
    except Exception as e:
        print(f"Failed running agent: {e}")
    finally:
        tool_client.close()

if __name__ == "__main__":
    main()
