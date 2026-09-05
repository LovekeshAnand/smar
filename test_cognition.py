import asyncio
from context_layer import ContextLayerEngine, ContextConfig
from core.epsilon_bridge import EpsilonBridge
from smart_data import SmartDataLayerEngine

async def run_test():
    context_config = ContextConfig(default_user_id="lovekesh")
    context_engine = ContextLayerEngine(config=context_config)
    smart_data_engine = SmartDataLayerEngine(context_store=context_engine.store)
    bridge = EpsilonBridge()

    user_text = "i forgot what was the 1st question that i asked you and what's my name and what's your name"
    user_id = "lovekesh"

    smart_res = await smart_data_engine.process_query_async(user_text, user_id=user_id)
    inventory_context = smart_res.get("context_string")

    turn_result = context_engine.process_user_turn(
        user_id=user_id,
        user_text=user_text,
        language_hint="en-IN"
    )

    system_prompt = turn_result["system_prompt"]
    retrieval = turn_result["retrieval"]
    structured_facts = retrieval.get("structured_facts", [])
    semantic_memories = retrieval.get("semantic_memories", [])
    recent_turns = turn_result.get("recent_turns", [])

    context_blocks = []
    if inventory_context:
        context_blocks.append(inventory_context)
    if structured_facts:
        context_blocks.append("[Personal User Knowledge]:\n" + "\n".join(f"- {f}" for f in structured_facts))
    if semantic_memories:
        context_blocks.append("[Recalled Past Notes & Context]:\n" + "\n".join(f"- {m}" for m in semantic_memories))
    context_summary = "\n\n".join(context_blocks) if context_blocks else None

    prompt = bridge.format_prompt(
        user_prompt=user_text,
        context=context_summary,
        system_prompt=system_prompt,
        conversation_history=recent_turns
    )

    print("=== FORMATTED PROMPT SENT TO EPSILON ===")
    print(prompt)
    print("========================================")

if __name__ == "__main__":
    asyncio.run(run_test())
