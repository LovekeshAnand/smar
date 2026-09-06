import sys, os
sys.path.insert(0, os.path.abspath('.'))
import asyncio
from context_layer import ContextLayerEngine, ContextConfig
from core.epsilon_bridge import EpsilonBridge

async def test():
    config = ContextConfig(default_user_id='lovekesh')
    context_engine = ContextLayerEngine(config=config)
    bridge = EpsilonBridge()

    for query in ["can you pronounce my name again", "no my name not yours"]:
        turn_res = context_engine.process_user_turn(user_id='lovekesh', user_text=query, language_hint='en-IN')
        system_prompt = turn_res['system_prompt']
        reply = await bridge.generate_reply(user_prompt=query, system_prompt=system_prompt, max_tokens=150)
        print(f"\n=== QUERY: {query} ===")
        print("Reply:", reply)

asyncio.run(test())
