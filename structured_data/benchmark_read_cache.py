"""
structured_data/benchmark_read_cache.py
========================================
Performance Benchmark Suite for Read Models & Hot Data Cache Layer.
Measures and compares query latencies across 100,000+ Kirana inventory records for:
- Cold DB Lookup vs. Hot Cache HIT
- Dynamic Group-By SQL Aggregation vs. Materialized Read Model Query
- Barcode Cache HIT vs. MISS
- Selective Invalidation & Re-fetch Overhead
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
        logger.info(f"Database has {count:,} items. Generating & loading {total_items:,} items...")
        gen = KiranaInventoryDataGenerator()
        pipeline = InventoryETLPipeline(db_manager=db)
        pipeline.run_pipeline(gen.generate_records(total_records=total_items), chunk_size=10000)
        count = db.get_total_count()

    read_models = ReadModelManager(db_manager=db)
    cache = HotDataCacheManager()
    service = StructuredDataService(db_manager=db, read_model_manager=read_models, cache_manager=cache)

    logger.info(f"\n=================================================================")
    logger.info(f"  READ MODEL & HOT CACHE PERFORMANCE BENCHMARK ({count:,} ITEMS)")
    logger.info(f"=================================================================\n")

    test_item_id = "INV-005000"

    # --- BENCHMARK 1: Cold DB Lookup (Cache MISS) vs Hot Cache (Cache HIT) ---
    logger.info("--- Benchmark 1: Item Lookup (Cache MISS vs. Cache HIT) ---")
    cache.clear()
    
    # 1A. Cache MISS (DB Query)
    t0 = time.perf_counter()
    for _ in range(100):
        item_miss = service.get_item(test_item_id)
        cache.clear()  # Force miss each time
    t1 = time.perf_counter()
    miss_latency_ms = ((t1 - t0) / 100.0) * 1000.0

    # 1B. Cache HIT
    cache.clear()
    _ = service.get_item(test_item_id)  # Warm up cache once
    t0 = time.perf_counter()
    for _ in range(100):
        item_hit = service.get_item(test_item_id)
    t1 = time.perf_counter()
    hit_latency_ms = ((t1 - t0) / 100.0) * 1000.0

    speedup_item = miss_latency_ms / max(hit_latency_ms, 0.0001)
    logger.info(f"Cache MISS Latency (DB Search) : {miss_latency_ms:.4f} ms")
    logger.info(f"Cache HIT Latency (In-Memory)   : {hit_latency_ms:.4f} ms")
    logger.info(f"Speedup Ratio                   : {speedup_item:.1f}x Faster!\n")

    # --- BENCHMARK 2: Dynamic SQL Aggregation vs Materialized View ---
    logger.info("--- Benchmark 2: Dynamic Aggregation vs. Materialized Read Model ---")
    category = "Spices & Cooking Essentials"

    # 2A. Dynamic SQL Group By Aggregation over 100,000 rows
    conn = db.get_connection()
    try:
        t0 = time.perf_counter()
        for _ in range(20):
            conn.execute("""
            SELECT category, COUNT(*), SUM(quantity), SUM(quantity * unit_price)
            FROM inventory_items WHERE category = ? GROUP BY category;
            """, (category,)).fetchall()
        t1 = time.perf_counter()
        dynamic_agg_ms = ((t1 - t0) / 20.0) * 1000.0
    finally:
        conn.close()

    # 2B. Materialized View Query
    t0 = time.perf_counter()
    for _ in range(20):
        _ = read_models.get_category_summary(category)
    t1 = time.perf_counter()
    materialized_ms = ((t1 - t0) / 20.0) * 1000.0

    speedup_agg = dynamic_agg_ms / max(materialized_ms, 0.0001)
    logger.info(f"Dynamic SQL GROUP BY Latency  : {dynamic_agg_ms:.4f} ms")
    logger.info(f"Materialized Read Model Query : {materialized_ms:.4f} ms")
    logger.info(f"Speedup Ratio                 : {speedup_agg:.1f}x Faster!\n")

    # --- BENCHMARK 3: Cache Invalidation Cycle ---
    logger.info("--- Benchmark 3: Item Mutation & Invalidation Safety ---")
    original_qty = item_miss["quantity"]
    new_qty = original_qty + 50.0

    # Mutate item stock
    success = service.update_item_stock_or_price(test_item_id, new_quantity=new_qty)
    updated_item = service.get_item(test_item_id)
    
    logger.info(f"Mutation Success : {success}")
    logger.info(f"Old Quantity     : {original_qty}")
    logger.info(f"New Live Quantity: {updated_item['quantity']}")
    assert updated_item["quantity"] == new_qty, "Stale volatile stock served!"
    logger.info("Verified: Mutation correctly invalidated cache and served live updated stock!\n")

    # Revert stock back
    service.update_item_stock_or_price(test_item_id, new_quantity=original_qty)

    stats = cache.get_stats()
    logger.info("--- Final Cache Health Statistics ---")
    logger.info(f"Cache Hits   : {stats['hits']}")
    logger.info(f"Cache Misses : {stats['misses']}")
    logger.info(f"Hit Ratio    : {stats['hit_ratio_pct']}%")
    logger.info("=================================================================\n")

    return {
        "miss_latency_ms": miss_latency_ms,
        "hit_latency_ms": hit_latency_ms,
        "item_speedup": speedup_item,
        "dynamic_agg_ms": dynamic_agg_ms,
        "materialized_ms": materialized_ms,
        "agg_speedup": speedup_agg,
        "cache_stats": stats
    }


if __name__ == "__main__":
    run_cache_and_read_model_benchmark()
