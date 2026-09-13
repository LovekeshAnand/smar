import sys
sys.path.insert(0, '.')
from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine

ctx = ContextLayerEngine(config=ContextConfig(default_user_id='test_user'))
engine = SmartDataLayerEngine(context_store=ctx.store)

test_queries = [
    'hamare db mai kitne stores present hai',
    'what tables are in the database',
    'what is in the database',
    'hamare database me kya kya hai',
    'show me all tables',
    'list all tables',
    'db me kitne stores hai',
    'how many stores do we have',
    'kitne products hai hamare paas',
    'total kitne orders hai'
]

for q in test_queries:
    res = engine.process_query(q)
    print(f"Query: '{q}'")
    print(f"  intent: {res.get('intent')}, op: {res.get('operation')}")
    print(f"  spoken: {res.get('spoken_confirmation')}")
    print(f"  context: {res.get('context_string')[:100] if res.get('context_string') else None}")
    print()
