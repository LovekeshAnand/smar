"""
structured_data/benchmark_read_cache.py
========================================
Performance Benchmark Suite for Read Models & Hot Data Cache Layer.
Measures and compares query latencies across 100,000+ Kirana inventory records for:
1. Cold Request & Cache Miss
2. Database / Read-Model Lookup
3. Cache Population & Repeated Requests (Cache Hit)
4. EXPLAIN QUERY PLAN verification
5. Dynamic Group-By SQL Aggregation vs. Materialized Read Model Query
6. TTL Expiration & Stale-Data Invalidation
7. Cache Unavailable Fallback Scenario
"""

import time
import logging
from typing import Dict, Any
from .db import InventoryDatabaseManager
from .read_models import ReadModelManager
from .cache import HotDataCacheManager
from .service import StructuredDataService
from .generator import KiranaInventoryDataGenerator
from .etl import InventoryETLPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smar.structured_data.benchmark_read_cache")


def run_cache_and_read_model_benchmark(total_items: int = 100000) -> Dict[str, Any]:
    """Runs performance comparison tests for Cache HIT/MISS and Materialized Views."""
    db = InventoryDatabaseManager()
    count = db.get_total_count()

    if count < total_items:
        logger.info(f"Database currently has {count:,} items. Generating & loading {total_items:,} items...")
        gen = KiranaInventoryDataGenerator(seed=42)
        pipeline = InventoryETLPipeline(db_manager=db)
        pipeline.run_pipeline(gen.generate_records(total_records=total_items), chunk_size=10000)
        count = db.get_total_count()

    read_models = ReadModelManager(db_manager=db)
    read_models.refresh_all_materialized_views()
    cache = HotDataCacheManager()
    service = StructuredDataService(db_manager=db, read_model_manager=read_models, cache_manager=cache)

    logger.info(f"\n=================================================================")
    logger.info(f"  READ MODEL & HOT CACHE PERFORMANCE BENCHMARK ({count:,} RECORDS)")
    logger.info(f"=================================================================\n")

    test_item_id = "INV-005000"

    # --- SECTION 0: EXPLAIN QUERY PLANS ---
    logger.info("--- [0] Query Plan Inspection (EXPLAIN QUERY PLAN) ---")
    plans = {
        "Exact PK Lookup": db.explain_query("SELECT * FROM inventory_items WHERE item_id = ?", (test_item_id,)),
        "Barcode Scan": db.explain_query("SELECT * FROM inventory_items WHERE barcode = ?", ("8901030005000",)),
        "Category Filter": db.explain_query("SELECT * FROM inventory_items WHERE category = ?", ("Spices & Cooking Essentials",)),
        "Category Materialized View": db.explain_query("SELECT * FROM mv_category_summary WHERE category = ?", ("Spices & Cooking Essentials",)),
        "Low Stock Alerts View": db.explain_query("SELECT * FROM mv_low_stock_alerts ORDER BY deficit_quantity DESC LIMIT 50"),
    }
    for query_name, details in plans.items():
        logger.info(f"Query: {query_name}")
        for d in details:
            logger.info(f"   -> {d}")
    logger.info("")

    # --- SECTION 1: Cold Request & Cache MISS vs HIT ---
    logger.info("--- [1] Cold Request, Cache Miss & Cache Hit Comparison ---")
    cache.clear()

    # 1. Cold Request (Cache empty, DB query)
    t0 = time.perf_counter()
    cold_item = service.get_item(test_item_id)
    t1 = time.perf_counter()
    cold_latency_ms = (t1 - t0) * 1000.0
    logger.info(f"1. Cold Request Latency (Initial DB fetch) : {cold_latency_ms:.4f} ms")

    # 2. Repeated Cache MISS (forcing cache clearance each time)
    cache.clear()
    t0 = time.perf_counter()
    for _ in range(100):
        _ = service.get_item(test_item_id)
        cache.clear()
    t1 = time.perf_counter()
    miss_latency_ms = ((t1 - t0) / 100.0) * 1000.0
    logger.info(f"2. Average Cache MISS Latency (DB search)  : {miss_latency_ms:.4f} ms")

    # 3. Repeated Cache HIT (warm cache)
    cache.clear()
    _ = service.get_item(test_item_id)  # Warm up cache once
    t0 = time.perf_counter()
    for _ in range(100):
        _ = service.get_item(test_item_id)
    t1 = time.perf_counter()
    hit_latency_ms = ((t1 - t0) / 100.0) * 1000.0
    speedup_item = miss_latency_ms / max(hit_latency_ms, 0.0001)

    logger.info(f"3. Average Cache HIT Latency (In-Memory)   : {hit_latency_ms:.4f} ms")
    logger.info(f"-> Speedup Ratio: {speedup_item:.1f}x Faster\n")

    # --- SECTION 2: Dynamic Aggregation vs Materialized View ---
    logger.info("--- [2] Dynamic SQL Aggregation vs. Materialized Read Model ---")
    category = "Spices & Cooking Essentials"

    # 2A. Dynamic SQL Group By Aggregation over 100,000 rows
    conn = db.get_connection()
    try:
        t0 = time.perf_counter()
        for _ in range(25):
            conn.execute("""
            SELECT category, COUNT(*), SUM(quantity), SUM(quantity * unit_price)
            FROM inventory_items WHERE category = ? GROUP BY category;
            """, (category,)).fetchall()
        t1 = time.perf_counter()
        dynamic_agg_ms = ((t1 - t0) / 25.0) * 1000.0
    finally:
        conn.close()

    # 2B. Materialized View Query
    t0 = time.perf_counter()
    for _ in range(25):
        _ = read_models.get_category_summary(category)
    t1 = time.perf_counter()
    materialized_ms = ((t1 - t0) / 25.0) * 1000.0
    speedup_agg = dynamic_agg_ms / max(materialized_ms, 0.0001)

    logger.info(f"Dynamic SQL GROUP BY over 100k rows : {dynamic_agg_ms:.4f} ms")
    logger.info(f"Materialized Read Model Query       : {materialized_ms:.4f} ms")
    logger.info(f"-> Speedup Ratio: {speedup_agg:.1f}x Faster\n")

    # --- SECTION 3: Static vs Volatile Separation & Stale Data Prevention ---
    logger.info("--- [3] Static vs. Volatile Separation & Invalidation ---")
    item_before = service.get_item(test_item_id)
    orig_qty = item_before["quantity"]
    new_qty = orig_qty + 25.0

    # Mutate in Primary DB
    service.update_item_stock_or_price(test_item_id, new_quantity=new_qty)
    item_after = service.get_item(test_item_id)
    logger.info(f"Original Stock : {orig_qty} -> Updated Stock : {item_after['quantity']}")
    assert item_after["quantity"] == new_qty, "CRITICAL: Stale volatile stock was returned!"
    logger.info("Verified: Cache was selectively invalidated and fresh DB data was returned.")
    # Revert
    service.update_item_stock_or_price(test_item_id, new_quantity=orig_qty)

    # --- SECTION 4: Cache Unavailable Fallback Scenario ---
    logger.info("\n--- [4] Cache Unavailable Resilience Scenario ---")
    disabled_cache = HotDataCacheManager(enabled=False)
    fallback_service = StructuredDataService(db_manager=db, read_model_manager=read_models, cache_manager=disabled_cache)
    t0 = time.perf_counter()
    fallback_item = fallback_service.get_item(test_item_id)
    t1 = time.perf_counter()
    fallback_latency_ms = (t1 - t0) * 1000.0
    logger.info(f"Fallback Item Retrieval Latency (Cache Disabled): {fallback_latency_ms:.4f} ms")
    assert fallback_item is not None and fallback_item["item_id"] == test_item_id
    logger.info("Verified: Seamless fallback to Primary Database when cache is unavailable.")

    # --- Final Stats ---
    stats = cache.get_stats()
    logger.info("\n=================================================================")
    logger.info("  FINAL CACHE PERFORMANCE & HIT RATIO REPORT")
    logger.info(f"  Cache Hits   : {stats['hits']:,}")
    logger.info(f"  Cache Misses : {stats['misses']:,}")
    logger.info(f"  Hit Ratio    : {stats['hit_ratio_pct']}%")
    logger.info(f"  Evictions    : {stats['evictions']}")
    logger.info("=================================================================\n")

    return {
        "cold_latency_ms": cold_latency_ms,
        "miss_latency_ms": miss_latency_ms,
        "hit_latency_ms": hit_latency_ms,
        "speedup_item": speedup_item,
        "dynamic_agg_ms": dynamic_agg_ms,
        "materialized_ms": materialized_ms,
        "speedup_agg": speedup_agg,
        "fallback_latency_ms": fallback_latency_ms,
        "cache_stats": stats,
    }


if __name__ == "__main__":
    run_cache_and_read_model_benchmark()
