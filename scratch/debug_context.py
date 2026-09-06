import sys, os
sys.path.insert(0, os.path.abspath('.'))
import asyncio
from structured_data.adapters import AdapterRegistry, SQLiteStorageAdapter
from context_layer import ContextLayerEngine, ContextConfig
from smart_data import SmartDataLayerEngine

async def test():
    config = ContextConfig(default_user_id='lovekesh')
    context_engine = ContextLayerEngine(config=config)
    adapter_registry = AdapterRegistry()
    adapter_registry.register('primary_sqlite', SQLiteStorageAdapter(), set_as_primary=True)
    smart_engine = SmartDataLayerEngine(adapter_registry=adapter_registry, context_store=context_engine.store)

    user_text = "can you tell me what's the price of order id 520580"
    smart_res = await smart_engine.process_query_async(user_text, user_id='lovekesh')
    inventory_context = smart_res.get("context_string")

    turn_result = context_engine.process_user_turn(user_id='lovekesh', user_text=user_text, language_hint='en-IN')
    retrieval = turn_result["retrieval"]
    structured_facts = retrieval.get("structured_facts", [])
    semantic_memories = retrieval.get("semantic_memories", [])

    print("=== INVENTORY CONTEXT ===")
    print(inventory_context)

    print("\n=== SEMANTIC MEMORIES ===")
    for m in semantic_memories:
        print("  -", m.encode('ascii', 'backslashreplace').decode('ascii'))

asyncio.run(test())
