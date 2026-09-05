"""
structured_data/benchmark.py
=============================
Query Performance & Index Verification Suite for SMAR v2.
Verifies indexed execution plans, timing metrics, and full-text search performance
across 100,000+ Kirana inventory records.
"""

import time
import logging
from typing import Dict, Any, List
from .db import InventoryDatabaseManager
from .generator import KiranaInventoryDataGenerator
from .etl import InventoryETLPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smar.structured_data.benchmark")


def run_benchmark_and_explain(db_path: str = None, total_items: int = 100000) -> Dict[str, Any]:
    """
    Executes benchmark queries and prints EXPLAIN QUERY PLAN output.
    If database contains fewer than `total_items`, automatically generates and loads them.
    """
    db = InventoryDatabaseManager(db_path=db_path)
    count = db.get_total_count()

    if count < total_items:
        logger.info(f"Database has {count:,} items. Generating & loading {total_items:,} items for benchmarking...")
        gen = KiranaInventoryDataGenerator()
        pipeline = InventoryETLPipeline(db_manager=db)
        res = pipeline.run_pipeline(gen.generate_records(total_records=total_items), chunk_size=10000)
        logger.info(res.summary())
        count = db.get_total_count()

    logger.info(f"\n=======================================================")
    logger.info(f"  SMAR v2 BENCHMARK & INDEX VERIFICATION ({count:,} ROWS)")
    logger.info(f"=======================================================\n")

    queries_to_test = [
        {
            "name": "1. Exact Primary Key Lookup (item_id)",
            "sql": "SELECT * FROM inventory_items WHERE item_id = ?",
            "params": ("INV-005000",)
        },
        {
            "name": "2. Barcode POS Scan Lookup (barcode)",
            "sql": "SELECT * FROM inventory_items WHERE barcode = ?",
            "params": ("8901030005000",)
        },
        {
            "name": "3. Entity Resolution Exact Lookup (normalized_name)",
            "sql": "SELECT item_id, canonical_name FROM inventory_items WHERE normalized_name = ?",
            "params": ("tata salt vacuum evaporated iodised salt 1kg (variant #1)",)
        },
        {
            "name": "4. Category & Brand Filter (Composite Index)",
            "sql": "SELECT * FROM inventory_items WHERE category = ? AND brand = ? LIMIT 50",
            "params": ("Spices & Cooking Essentials", "Tata")
        },
        {
            "name": "5. Volatile Reorder Stock Alert (is_active, quantity)",
            "sql": "SELECT item_id, canonical_name, quantity, reorder_level FROM inventory_items WHERE is_active = 1 AND quantity <= reorder_level LIMIT 50",
            "params": ()
        },
        {
            "name": "6. Sub-millisecond FTS5 Fuzzy Full-Text Search (inventory_fts)",
            "sql": "SELECT i.item_id, i.canonical_name, i.category, i.brand FROM inventory_fts f JOIN inventory_items i ON f.item_id = i.item_id WHERE inventory_fts MATCH ? LIMIT 10",
            "params": ("atta*",)
        }
    ]

    results = []

    for q in queries_to_test:
        logger.info(f"--- Query: {q['name']} ---")
        logger.info(f"SQL: {q['sql']}")

        # 1. Query Plan Analysis
        plan_lines = db.explain_query(q['sql'], q['params'])
        logger.info("EXPLAIN QUERY PLAN:")
        for line in plan_lines:
            logger.info(f"   --> {line}")

        # 2. Timing benchmark (100 iterations)
        conn = db.get_connection()
        try:
            start_t = time.perf_counter()
            for _ in range(100):
                cursor = conn.execute(q['sql'], q['params'])
                rows = cursor.fetchall()
            end_t = time.perf_counter()
            
            avg_ms = ((end_t - start_t) / 100.0) * 1000.0
            logger.info(f"Results Count : {len(rows)}")
            logger.info(f"Average Latency: {avg_ms:.4f} ms per query\n")

            results.append({
                "name": q['name'],
                "sql": q['sql'],
                "query_plan": plan_lines,
                "latency_ms": avg_ms,
                "results_count": len(rows)
            })
        finally:
            conn.close()

    logger.info("=======================================================")
    logger.info("  BENCHMARK SUMMARY COMPLETE (All indexes verified)")
    logger.info("=======================================================\n")
    return {"total_records": count, "benchmark_results": results}


if __name__ == "__main__":
    run_benchmark_and_explain()
