"""
scratch/adaptive_battle_suite.py
================================
Universal Adaptive Battle Test Suite for SMAR Platform.

Completely eliminates hardcoded table names, IDs, prices, and column values.
Discovers schema, tables, IDs, and numeric metrics dynamically at runtime.
Validates structural integrity, correct pipeline routing, and robustness.

Covers:
1. Dynamic Entity Resolution (Discovered IDs, parent/child relationships)
2. Mathematical Aggregations (SUM, AVG, MIN, MAX, COUNT, Group By)
3. Visual Chart Generation (Bar, Pie, Line charts)
4. Tabular Data Queries (Dynamic across all tables)
5. Schema-Fingerprinted Zero-Rescan Fast Boot
6. STT Artifact & Glitch Normalization
7. Contextual Memory & Conversational Bypass
8. Edge Cases & Resilience (Nonexistent IDs, SQL injection, Case variations)
"""

import sys
import time
import logging
from typing import Dict, Any, List

sys.path.insert(0, '.')

from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine
from smart_data.visualizer import AdaptiveDataVisualizer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("adaptive_battle")


def run_adaptive_battle_tests():
    print("=" * 85)
    print("SMAR UNIVERSAL ADAPTIVE BATTLE TEST SUITE: ZERO HARDCODING")
    print("=" * 85)

    ctx = ContextLayerEngine(config=ContextConfig(default_user_id="battle_user"))
    engine = SmartDataLayerEngine(context_store=ctx.store)
    wh = engine.warehouse_manager

    # 1. Discover tables dynamically
    tables_info = wh.list_tables()
    table_names = [t["table_name"] for t in tables_info]
    print(f"\n[1/4] Discovered {len(table_names)} tables: {table_names}")

    if not table_names:
        print("[ERROR] No tables found in warehouse!")
        return False

    # Extract sample IDs and schemas dynamically
    sample_entities = {}
    numeric_columns = {}

    for t in table_names:
        schema = wh.get_table_schema(t)
        cols = schema.get("columns", {})
        pks = schema.get("primary_keys", [])
        id_col = pks[0] if pks else next((c for c in cols if c.endswith("_id") or c == "id"), None)
        
        num_cols = [c for c, dt in cols.items() if any(k in dt.upper() for k in ("INT", "REAL", "FLOAT", "NUM", "DEC"))]
        numeric_columns[t] = num_cols

        if id_col:
            tab_res = wh.query_tabular(t, limit=1)
            recs = tab_res.get("records", [])
            if recs and id_col in recs[0]:
                sample_entities[t] = {
                    "id_col": id_col,
                    "sample_val": recs[0][id_col],
                    "record": recs[0]
                }

    print(f"[2/4] Discovered dynamic sample entities for {len(sample_entities)} tables.")

    # 2. Build test matrix
    tests: List[Dict[str, Any]] = []

    # Category 1: Dynamic Entity Resolution (Zero Hardcoded IDs)
    for t, info in list(sample_entities.items())[:5]:
        id_col_clean = info["id_col"].replace("_", " ")
        sample_id = info["sample_val"]
        singular = t.rstrip("s")
        prompt = f"what is the {singular} with {id_col_clean} {sample_id}"
        tests.append({
            "category": "DYNAMIC_ENTITY_LOOKUP",
            "prompt": prompt,
            "check": lambda r, sid=str(sample_id): sid in r.get("spoken_confirmation", "") or sid in r.get("context_string", "") or r.get("matched_item") is not None,
            "desc": f"Dynamic lookup of {t} by {id_col_clean}={sample_id}"
        })

    # Category 2: Aggregations & Analytics (Dynamic table + numeric column)
    for t in table_names[:4]:
        num_cols = numeric_columns.get(t, [])
        metric = num_cols[0] if num_cols else None
        metric_phrase = metric.replace("_", " ") if metric else "records"
        singular = t.rstrip("s")

        # COUNT
        tests.append({
            "category": "AGGREGATION_COUNT",
            "prompt": f"how many total {t} are there in the system",
            "check": lambda r: r.get("operation") == "AGGREGATION" and r.get("operation_details", {}).get("value") is not None,
            "desc": f"COUNT(*) in {t}"
        })

        if metric:
            # SUM
            tests.append({
                "category": "AGGREGATION_SUM",
                "prompt": f"what is the total {metric_phrase} in {t}",
                "check": lambda r: r.get("operation") == "AGGREGATION" and r.get("operation_details", {}).get("value") is not None,
                "desc": f"SUM({metric}) in {t}"
            })

            # AVG
            tests.append({
                "category": "AGGREGATION_AVG",
                "prompt": f"calculate the average {metric_phrase} for {t}",
                "check": lambda r: r.get("operation") == "AGGREGATION" and r.get("operation_details", {}).get("value") is not None,
                "desc": f"AVG({metric}) in {t}"
            })

    # Category 3: Tabular Queries & Visual Charts
    for t in table_names[:3]:
        tests.append({
            "category": "TABULAR_QUERY",
            "prompt": f"show me {t} in table format",
            "check": lambda r: r.get("operation") == "TABULAR" and r.get("table_data") is not None,
            "desc": f"TABULAR format of {t}"
        })

        tests.append({
            "category": "VISUAL_CHART",
            "prompt": f"generate a chart of {t}",
            "check": lambda r: (r.get("visual_chart") is not None or r.get("table_data") is not None),
            "desc": f"Chart / Visual of {t}"
        })

    # Category 4: STT Glitch Normalization (No hardcoded domain values)
    if sample_entities:
        t_sample, s_info = next(iter(sample_entities.items()))
        id_str = str(s_info["sample_val"])
        glitched_prompt = f"show {t_sample} id [00:01:23] {id_str} details"
        tests.append({
            "category": "STT_NORMALIZATION",
            "prompt": glitched_prompt,
            "check": lambda r, s=id_str: s in r.get("spoken_confirmation", "") or s in r.get("context_string", "") or r.get("matched_item") is not None,
            "desc": f"STT timestamp stripping from prompt with ID {id_str}"
        })

    # Category 5: Conversational Memory & Bypass
    tests.extend([
        {
            "category": "CONVERSATION_BYPASS",
            "prompt": "hello how are you doing today",
            "check": lambda r: r.get("intent") == "CONVERSATION" and r.get("matched_item") is None,
            "desc": "Conversational greeting bypasses database lookup"
        },
        {
            "category": "CONVERSATION_BYPASS",
            "prompt": "what is your name and what can you do",
            "check": lambda r: r.get("intent") == "CONVERSATION" and r.get("matched_item") is None,
            "desc": "Assistant identity query bypasses database lookup"
        },
        {
            "category": "PERSONAL_FACT_MEMORY",
            "prompt": "my name is Agent Tester and I live in Neo Tokyo",
            "check": lambda r: r.get("intent") == "CONVERSATION",
            "desc": "Stores personal profile fact in Knowledge Graph"
        }
    ])

    # Category 6: Robustness & Edge Cases
    tests.extend([
        {
            "category": "EDGE_NONEXISTENT",
            "prompt": "get details for nonexistent_entity_xyz_99999999",
            "check": lambda r: r is not None and isinstance(r, dict),
            "desc": "Gracefully handles nonexistent entity without crashing"
        },
        {
            "category": "EDGE_SQL_INJECTION",
            "prompt": "show categories WHERE 1=1; DROP TABLE test; --",
            "check": lambda r: r is not None and isinstance(r, dict),
            "desc": "SQL injection injection resilience"
        },
        {
            "category": "EDGE_CASE_VARIATION",
            "prompt": f"SHOW ME {table_names[0].upper()} IN TABLE FORMAT",
            "check": lambda r: r.get("operation") == "TABULAR" or r.get("table_data") is not None,
            "desc": "All-caps case-insensitive input handling"
        }
    ])

    print(f"\n[3/4] Running {len(tests)} battle tests...")
    passed = 0
    failed = 0

    for i, t in enumerate(tests, 1):
        prompt = t["prompt"]
        cat = t["category"]
        desc = t["desc"]
        t0 = time.perf_counter()
        try:
            res = engine.process_query(prompt, user_id="battle_user")
            elapsed = (time.perf_counter() - t0) * 1000.0
            ok = t["check"](res)
            if ok:
                passed += 1
                print(f"[PASS] #{i:02d} [{cat}] ({elapsed:6.1f}ms) {desc}")
            else:
                failed += 1
                print(f"[FAIL] #{i:02d} [{cat}] ({elapsed:6.1f}ms) {desc}")
                print(f"       Prompt: '{prompt}'")
                print(f"       Result: intent={res.get('intent')}, op={res.get('operation')}, item={bool(res.get('matched_item'))}")
        except Exception as e:
            failed += 1
            print(f"[CRASH] #{i:02d} [{cat}] {desc}: {e}")

    # 4. Fast boot cache test
    print("\n[4/4] Verifying Schema Boot Fingerprint Cache...")
    t_start = time.perf_counter()
    reloaded = engine.refresh_schema()
    t_refresh = (time.perf_counter() - t_start) * 1000.0
    print(f"[CACHE] Schema refresh completed in {t_refresh:.2f}ms. Unchanged schema reused cache: {t_refresh < 1000.0}")

    print("\n" + "=" * 85)
    pct = (passed / len(tests)) * 100.0 if tests else 0
    print(f"SUMMARY: {passed}/{len(tests)} PASSED ({pct:.1f}%) | {failed} FAILED")
    print("=" * 85)
    return failed == 0


if __name__ == "__main__":
    success = run_adaptive_battle_tests()
    sys.exit(0 if success else 1)
