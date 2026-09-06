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

    query = "can you tell me what's the price of order id 520580"
    res = await smart_engine.process_query_async(query, user_id='lovekesh')
    print('Intent:', res.get('intent'))
    print('Matched item:', res.get('matched_item'))
    print('Spoken confirmation:', res.get('spoken_confirmation'))
    print('Context string:', res.get('context_string'))

asyncio.run(test())
