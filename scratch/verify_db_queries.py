from server import smart_data_engine

test_queries = [
    "hamare db mai kitne stores present hai",
    "what tables are in the database",
    "hamare database me kya kya hai",
    "show all tables",
    "kitne products hai hamare paas",
    "total kitne orders hai",
    "how many stores do we have",
    "database me kitne customers hai",
]

for q in test_queries:
    res = smart_data_engine.process_query(q)
    print(f"Q: {q}")
    print(f"   Intent: {res.get('intent')}")
    print(f"   Spoken: {res.get('spoken_confirmation')}")
    print("-" * 50)
