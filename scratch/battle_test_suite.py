"""
scratch/battle_test_suite.py
============================
End-to-End Battle Test Suite for SMAR Platform:
1. Dynamic Entity Resolution (Order Item vs Order, Prices, Quantities)
2. Complex Aggregations (COUNT, SUM, AVG, MIN, MAX, Group By)
3. Visual Chart Generation (Bar, Pie, Line charts)
4. Tabular Data Queries (Stores, Customers, Suppliers, Products)
5. Dynamic Introspection & Zero Hardcoding
6. STT Glitch Normalization (Timestamp artifacts)
7. Personal Context Memory & Conversational Continuity
8. Robustness & Edge Cases (Nonexistent IDs, Case variations, Special chars)
"""

import sys
import json
import time
from typing import Dict, Any

sys.path.insert(0, '.')

from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine
from smart_data.visualizer import AdaptiveDataVisualizer

def run_battle_tests():
    print("=" * 80)
    print("SMAR BATTLE TEST SUITE: ZERO-HARDCODING & DEEP VERIFICATION")
    print("=" * 80)

    config = ContextConfig(default_user_id="lovekesh")
    ctx = ContextLayerEngine(config=config)
    engine = SmartDataLayerEngine(context_store=ctx.store)

    test_cases = [
        # --- Category 1: Disambiguation & Precise Math ---
        {
            "category": "DISAMBIGUATION",
            "prompt": "can you tell me what is the price of order id 520580",
            "check": lambda res: (
                "520580" in res.get("spoken_confirmation", "") and
                "2812" in res.get("spoken_confirmation", "") and
                "11248" in res.get("spoken_confirmation", "") and
                "292487" in res.get("spoken_confirmation", "")
            ),
            "expected_desc": "Identifies 520580 as Order Item, Unit price 2812, Qty 4, Total 11248, parent order 292487"
        },
        {
            "category": "DISAMBIGUATION",
            "prompt": "what is the total price for order id 292487",
            "check": lambda res: (
                "18166" in res.get("spoken_confirmation", "") and
                "292487" in res.get("spoken_confirmation", "")
            ),
            "expected_desc": "Sums items for parent Order 292487 to yield total order value 18166"
        },

        # --- Category 2: STT Normalization ---
        {
            "category": "STT_NORMALIZATION",
            "prompt": "what happened to order 05:02 580",
            "check": lambda res: "502580" in res.get("spoken_confirmation", ""),
            "expected_desc": "Normalizes '05:02 580' timestamp glitch to 502580"
        },

        # --- Category 3: Aggregations without hardcoding ---
        {
            "category": "AGGREGATION",
            "prompt": "can you tell me the mean of salaries of from employee id 30 to 40 like i want the mean of salary not the employee id",
            "check": lambda res: (
                res.get("operation") == "AGGREGATION" and
                "salary" in res.get("spoken_confirmation", "").lower() and
                "52,061.27" in res.get("spoken_confirmation", "")
            ),
            "expected_desc": "AVG(salary) WHERE employee_id BETWEEN 30 AND 40 returns 52,061.27"
        },
        {
            "category": "AGGREGATION",
            "prompt": "can you tell me the mean of the salaries from the range of employee id 30 to 40 like i want the mean",
            "check": lambda res: (
                res.get("operation") == "AGGREGATION" and
                "salary" in res.get("spoken_confirmation", "").lower() and
                "52,061.27" in res.get("spoken_confirmation", "")
            ),
            "expected_desc": "AVG(salary) from range of employee id 30 to 40 returns 52,061.27"
        },
        {
            "category": "AGGREGATION",
            "prompt": "how many orders are in the database",
            "check": lambda res: res.get("operation") == "AGGREGATION" and "300,000" in res.get("spoken_confirmation", ""),
            "expected_desc": "COUNT(*) on orders returns 300,000"
        },
        {
            "category": "AGGREGATION",
            "prompt": "show me the sum of salaries of all employees",
            "check": lambda res: res.get("operation") == "AGGREGATION" and "49,420,829" in res.get("spoken_confirmation", ""),
            "expected_desc": "SUM(salary) on employees returns 49,420,829"
        },
        {
            "category": "AGGREGATION",
            "prompt": "what is the average salary per store in a bar chart",
            "check": lambda res: (
                res.get("operation") == "AGGREGATION" and
                res.get("visual_chart") is not None and
                res.get("visual_chart", {}).get("chart_type") in ("bar", "column", "donut")
            ),
            "expected_desc": "AVG(salary) GROUP BY store_id with visual bar chart"
        },

        # --- Category 4: Visual Chart Generation ---
        {
            "category": "VISUALIZATION",
            "prompt": "show me total orders grouped by store in a chart",
            "check": lambda res: (
                res.get("visual_chart") is not None and
                "image_base64" in res.get("visual_chart", {}) and
                "chart_type" in res.get("visual_chart", {})
            ),
            "expected_desc": "Generates chart PNG and metadata"
        },

        # --- Category 5: Tabular Data Retrieval ---
        {
            "category": "TABULAR",
            "prompt": "show me all stores in a table",
            "check": lambda res: (
                res.get("operation") == "TABULAR" and
                res.get("table_data") is not None and
                len(res.get("table_data", {}).get("records", [])) > 0
            ),
            "expected_desc": "TABULAR query on stores returning records"
        },
        {
            "category": "TABULAR",
            "prompt": "list all customers in table format",
            "check": lambda res: (
                res.get("operation") == "TABULAR" and
                res.get("table_data", {}).get("table") == "customers"
            ),
            "expected_desc": "TABULAR query dynamically mapping to customers table"
        },
        {
            "category": "TABULAR",
            "prompt": "show me suppliers in a table",
            "check": lambda res: (
                res.get("operation") == "TABULAR" and
                res.get("table_data", {}).get("table") == "suppliers"
            ),
            "expected_desc": "TABULAR query on suppliers table"
        },

        # --- Category 6: Single-Entity Lookups & Mutations ---
        {
            "category": "ENTITY_LOOKUP",
            "prompt": "what is the salary of employee 877",
            "check": lambda res: "877" in res.get("spoken_confirmation", "") and "50000" in res.get("spoken_confirmation", ""),
            "expected_desc": "Retrieves employee 877 salary accurately"
        },
        {
            "category": "MUTATION",
            "prompt": "update the salary of employee 877 to 52000",
            "check": lambda res: res.get("operation") == "UPDATE" and "52000" in res.get("spoken_confirmation", ""),
            "expected_desc": "Executes SQL UPDATE on employees table"
        },
        {
            "category": "ENTITY_LOOKUP",
            "prompt": "what is the salary of employee 877",
            "check": lambda res: "52000" in res.get("spoken_confirmation", ""),
            "expected_desc": "Verifies updated salary (52000) persists immediately"
        },

        # --- Category 7: Conversational Bypass ---
        {
            "category": "CONVERSATION",
            "prompt": "can you pronounce my name please",
            "check": lambda res: res.get("intent") == "CONVERSATION" and res.get("operation") is None,
            "expected_desc": "Conversational intent without touching database"
        },

        # --- Category 8: Edge Cases ---
        {
            "category": "EDGE_CASE",
            "prompt": "what is the price of order item 99999999",
            "check": lambda res: (
                "No matching records found" in res.get("spoken_confirmation", "") or
                res.get("matched_item") is None
            ),
            "expected_desc": "Non-existent item gracefully returns clean 'no records found'"
        },
        {
            "category": "EDGE_CASE",
            "prompt": "SHOW ME ALL PRODUCTS IN A TABLE",
            "check": lambda res: res.get("operation") == "TABULAR",
            "expected_desc": "Case-insensitive query handling"
        }
    ]

    passed = 0
    failed = 0

    for i, tc in enumerate(test_cases, 1):
        prompt = tc["prompt"]
        category = tc["category"]
        expected = tc["expected_desc"]
        
        t0 = time.perf_counter()
        res = engine.process_query(prompt, user_id="lovekesh")
        elapsed = (time.perf_counter() - t0) * 1000.0

        ok = False
        try:
            ok = tc["check"](res)
        except Exception as e:
            ok = False

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
            print(f"[{status}] #{i} [{category}] '{prompt}' ({elapsed:.1f}ms)")
            print(f"        -> {res.get('spoken_confirmation', '')[:100]}")
        else:
            failed += 1
            print(f"[{status}] #{i} [{category}] '{prompt}'")
            print(f"        Expected: {expected}")
            print(f"        Got Intent: {res.get('intent')}, Op: {res.get('operation')}")
            print(f"        Spoken: {res.get('spoken_confirmation')}")

    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {passed}/{len(test_cases)} PASSED ({(passed/len(test_cases))*100:.1f}%) | {failed} FAILED")
    print("=" * 80)

    # Restore employee 877 salary to 50000
    engine.process_query("update the salary of employee 877 to 50000", user_id="lovekesh")

if __name__ == "__main__":
    run_battle_tests()
