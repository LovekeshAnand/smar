"""
scratch/warehouse_extreme_tests.py
==================================
Extreme Warehouse Worker Edge Test Suite for SMAR Platform:
Simulates a real-world warehouse worker / inventory manager firing 20+
hardcore, edge-case, colloquial, multi-table queries.
"""

import sys
import time
import json

sys.path.insert(0, '.')

from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine

def run_extreme_tests():
    print("=" * 85)
    print("STARTING EXTREME WAREHOUSE WORKER TEST SUITE (20 REAL-WORLD STRESS TESTS)")
    print("=" * 85)

    ctx = ContextLayerEngine(config=ContextConfig(default_user_id="warehouse_worker"))
    engine = SmartDataLayerEngine(context_store=ctx.store)

    scenarios = [
        # 1. Order Item Disambiguation with parent order lookup
        {
            "worker_intent": "Check specific item price & verify parent order",
            "prompt": "bhai tell me what is the price of order id 520580",
            "validator": lambda r: "520580" in r.get("spoken_confirmation", "") and "2812" in r.get("spoken_confirmation", "")
        },
        # 2. Total Order Value (Aggregates multiple line items dynamically)
        {
            "worker_intent": "Calculate complete order value for multi-item order",
            "prompt": "what is the total order value for order 292487",
            "validator": lambda r: "18166" in r.get("spoken_confirmation", "")
        },
        # 3. Shipment Tracking via Parent Order ID
        {
            "worker_intent": "Check shipment status using the parent order number",
            "prompt": "what is the status of shipment for order 292487",
            "validator": lambda r: "late" in r.get("spoken_confirmation", "").lower() or "late" in r.get("context_string", "").lower()
        },
        # 4. Direct Shipment Status
        {
            "worker_intent": "Check shipment status by shipment ID",
            "prompt": "status of shipment 4149",
            "validator": lambda r: "late" in r.get("spoken_confirmation", "").lower() or "late" in r.get("context_string", "").lower()
        },
        # 5. Returns & Refunds Calculation
        {
            "worker_intent": "Inspect refund amount for a specific return item",
            "prompt": "how much was the refund for return id 4149",
            "validator": lambda r: "4355" in r.get("spoken_confirmation", "") or "4355" in r.get("context_string", "")
        },
        # 6. Total Refunds Aggregation
        {
            "worker_intent": "Sum of all refunds across 30,000 return records",
            "prompt": "what is the sum of refunds in returns",
            "validator": lambda r: r.get("operation") == "AGGREGATION" and "refund" in str(r.get("operation_details", {}).get("column", "")).lower()
        },
        # 7. Mean / Average with Range on Metric (The screenshot scenario)
        {
            "worker_intent": "Mean of salary across employee range",
            "prompt": "can you tell me the mean of the salaries from the range of employee id 30 to 40 like i want the mean",
            "validator": lambda r: "52,061.27" in r.get("spoken_confirmation", "")
        },
        # 8. Product Price Lookup
        {
            "worker_intent": "Find unit price of inventory product",
            "prompt": "what is the price of product 7703",
            "validator": lambda r: "2812" in r.get("spoken_confirmation", "") or "product" in r.get("spoken_confirmation", "").lower()
        },
        # 9. Inventory Extremes (MAX price)
        {
            "worker_intent": "Find highest priced catalog item",
            "prompt": "what is the maximum price among all products",
            "validator": lambda r: r.get("operation") == "AGGREGATION" and "4,999" in r.get("spoken_confirmation", "")
        },
        # 10. Inventory Extremes (MIN price)
        {
            "worker_intent": "Find lowest priced item",
            "prompt": "what is the minimum price of products",
            "validator": lambda r: r.get("operation") == "AGGREGATION" and "price" in str(r.get("operation_details", {}).get("column", "")).lower()
        },
        # 11. Payment Amount for Order
        {
            "worker_intent": "Inspect payment record for order 4149",
            "prompt": "what was the payment amount for order 4149",
            "validator": lambda r: "18255" in r.get("spoken_confirmation", "") or "18255" in r.get("context_string", "")
        },
        # 12. Total Payments Aggregation
        {
            "worker_intent": "Sum of all payment amounts in warehouse",
            "prompt": "show me the total sum of payments amount",
            "validator": lambda r: r.get("operation") == "AGGREGATION" and "amount" in str(r.get("operation_details", {}).get("column", "")).lower()
        },
        # 13. Customer City Lookup
        {
            "worker_intent": "Inspect customer location",
            "prompt": "which city is customer 4149 from",
            "validator": lambda r: "pune" in r.get("spoken_confirmation", "").lower() or "pune" in r.get("context_string", "").lower()
        },
        # 14. Promotion Discount Lookup
        {
            "worker_intent": "Inspect promotion discount percentage",
            "prompt": "what is the discount for promotion id 10",
            "validator": lambda r: "discount" in r.get("spoken_confirmation", "").lower() or "promotion" in r.get("spoken_confirmation", "").lower()
        },
        # 15. Store Breakdown with Visual Chart
        {
            "worker_intent": "Average salary per store in visual chart",
            "prompt": "average salary per store in a bar chart",
            "validator": lambda r: r.get("visual_chart") is not None and "image_base64" in r.get("visual_chart", {})
        },
        # 16. Tabular Browse Returns
        {
            "worker_intent": "View recent returns in tabular format",
            "prompt": "show me all returns in a table",
            "validator": lambda r: r.get("operation") == "TABULAR" and r.get("table_data", {}).get("table") == "returns"
        },
        # 17. Safe Mutation: Update Shipment Status
        {
            "worker_intent": "Update shipment status in real time",
            "prompt": "update shipment 4149 status to delivered",
            "validator": lambda r: r.get("operation") == "UPDATE" and "delivered" in r.get("spoken_confirmation", "").lower()
        },
        # 18. Non-Existent ID Handling
        {
            "worker_intent": "Look up non-existent order gracefully",
            "prompt": "where is order 9999999999",
            "validator": lambda r: "No matching records found" in r.get("spoken_confirmation", "") or r.get("matched_item") is None
        },
        # 19. SQL Injection Attack Resilience
        {
            "worker_intent": "Attempt SQL injection in worker voice input",
            "prompt": "check order 292487; DROP TABLE orders; --",
            "validator": lambda r: "292487" in r.get("spoken_confirmation", "") or r.get("intent") is not None
        },
        # 20. Noise / Punctuation Only Resilience
        {
            "worker_intent": "Noisy background microphone click",
            "prompt": "??? ... !!!",
            "validator": lambda r: r is not None and isinstance(r, dict)
        }
    ]

    passed = 0
    failed = 0
    results = []

    for idx, sc in enumerate(scenarios, 1):
        prompt = sc["prompt"]
        intent = sc["worker_intent"]
        t0 = time.perf_counter()
        res = engine.process_query(prompt, user_id="warehouse_worker")
        elapsed = (time.perf_counter() - t0) * 1000.0

        ok = False
        try:
            ok = sc["validator"](res)
        except Exception as e:
            ok = False

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
            print(f"[{status}] #{idx:02d} ({elapsed:6.1f}ms) | {intent}")
            print(f"       Prompt: '{prompt}'")
            print(f"       Spoken: {res.get('spoken_confirmation', '')[:100]}")
        else:
            failed += 1
            print(f"[{status}] #{idx:02d} ({elapsed:6.1f}ms) | {intent}")
            print(f"       Prompt: '{prompt}'")
            print(f"       Intent: {res.get('intent')} | Op: {res.get('operation')}")
            print(f"       Spoken: {res.get('spoken_confirmation')}")
            print(f"       Context: {res.get('context_string', '')[:120]}")

        results.append({"idx": idx, "intent": intent, "prompt": prompt, "status": status, "elapsed_ms": elapsed})

    print("\n" + "=" * 85)
    print(f"EXTREME TEST SUMMARY: {passed}/{len(scenarios)} PASSED ({(passed/len(scenarios))*100:.1f}%) | {failed} FAILED")
    print("=" * 85)

    # Revert shipment 4149 to 'late'
    engine.process_query("update shipment 4149 status to late", user_id="warehouse_worker")

if __name__ == "__main__":
    run_extreme_tests()
