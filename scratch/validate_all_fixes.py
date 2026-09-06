import sys, os, asyncio
sys.path.insert(0, '.')
from structured_data.adapters import AdapterRegistry, SQLiteStorageAdapter
from context_layer import ContextLayerEngine, ContextConfig
from smart_data import SmartDataLayerEngine

async def test():
    config = ContextConfig(default_user_id='lovekesh')
    context_engine = ContextLayerEngine(config=config)
    adapter_registry = AdapterRegistry()
    adapter_registry.register('primary_sqlite', SQLiteStorageAdapter(), set_as_primary=True)
    smart_engine = SmartDataLayerEngine(adapter_registry=adapter_registry, context_store=context_engine.store)

    tests = [
        "can you tell me what is the price of order id 520580",
        "what is the total price for order id 292487",
        "what happened to order 05:02 580",
        "can you pronounce my name please",
        "how many orders are in the database",
        "show me the sum of salaries of all employees",
        "what is the average salary per store in a bar chart",
        "what is the salary of employee 877",
        "update the salary of employee 877 to 50000",
        "show me all stores in a table",
    ]

    for q in tests:
        res = await smart_engine.process_query_async(q, user_id='lovekesh')
        intent = res.get("intent", "?")
        operation = res.get("operation", "")
        ctx = res.get("context_string", "")
        spoken = res.get("spoken_confirmation", "")
        print(f"Q: {q}")
        print(f"  intent={intent}  op={operation}")
        print(f"  spoken={spoken[:150]}")
        print(f"  context={ctx[:200]}")
        print()

asyncio.run(test())
