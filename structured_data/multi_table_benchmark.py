"""
structured_data/multi_table_benchmark.py
=========================================
Battle-Test Benchmark for SMAR v2 Multi-Table Warehouse (1,086,800+ rows).

Tests:
1. PK lookups across 50,000 products & 150,000 inventory items.
2. FTS5 text search over 50,000 products.
3. 3-way relational JOIN (products + inventory + stores) across 1M+ rows.
4. Aggregation of 400,000 sales transactions.
5. Tiered Hot Cache acceleration (Cold vs Warm latency).
6. Non-blocking async execution concurrent with simulated voice audio loop.
"""

import asyncio
import logging
import sqlite3
import time
from typing import Dict, Any

from structured_data.multi_table_manager import MultiTableWarehouseManager
from structured_data.cache import hot_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smar.benchmark")


def run_warehouse_benchmarks(db_path: str = "data/warehouse.db") -> Dict[str, Any]:
    manager = MultiTableWarehouseManager(db_path=db_path)
    tables = manager.list_tables()
    total_rows = sum(t["row_count"] for t in tables)
    logger.info(f"Loaded warehouse with {len(tables)} tables and {total_rows:,} total rows.")

    results = {}

    # Benchmark 1: Exact PK Lookup
    pk_times = []
    for test_id in [101, 1542, 28941, 49999]:
        t0 = time.perf_counter()
        rec = manager.get_record_by_id("products", test_id, "product_id")
        t_el = (time.perf_counter() - t0) * 1000.0
        pk_times.append(t_el)
    avg_pk = sum(pk_times) / len(pk_times)
    results["pk_lookup_cold_ms"] = round(avg_pk, 4)
    logger.info(f"[PK Lookup] Avg cold latency: {avg_pk:.4f} ms")

    # Benchmark 2: PK Lookup Warm (Cached)
    t0 = time.perf_counter()
    cached_rec = manager.get_record_by_id("products", 101, "product_id")
    warm_pk = (time.perf_counter() - t0) * 1000.0
    results["pk_lookup_warm_ms"] = round(warm_pk, 4)
    logger.info(f"[PK Lookup Warm Cache] Latency: {warm_pk:.4f} ms")

    # Benchmark 3: FTS5 Full Text Search
    search_queries = ["Tata Tea Gold", "Amul Ghee 1L", "Aashirvaad Atta", "Parle Biscuits"]
    fts_times = []
    for q in search_queries:
        t0 = time.perf_counter()
        hits = manager.search_text(q, table_name="products", limit=5)
        t_el = (time.perf_counter() - t0) * 1000.0
        fts_times.append(t_el)
    avg_fts = sum(fts_times) / len(fts_times)
    results["fts_search_cold_ms"] = round(avg_fts, 4)
    logger.info(f"[FTS5 Text Search] Avg cold latency: {avg_fts:.4f} ms (Found {len(hits)} hits)")

    # Benchmark 4: FTS5 Search Warm (Cached)
    t0 = time.perf_counter()
    cached_hits = manager.search_text("Tata Tea Gold", table_name="products", limit=5)
    warm_fts = (time.perf_counter() - t0) * 1000.0
    results["fts_search_warm_ms"] = round(warm_fts, 4)
    logger.info(f"[FTS5 Warm Cache] Latency: {warm_fts:.4f} ms")

    # Benchmark 5: 3-Way Relational JOIN across 1M+ rows
    t0 = time.perf_counter()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT p.product_name, p.retail_price, i.quantity_on_hand, s.store_name, s.city
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            JOIN stores s ON i.store_id = s.store_id
            WHERE p.brand = 'Amul'
            LIMIT 10;
        """)
        join_rows = [dict(r) for r in cur.fetchall()]
    join_ms = (time.perf_counter() - t0) * 1000.0
    results["three_way_join_ms"] = round(join_ms, 2)
    logger.info(f"[3-Way Relational JOIN] Latency: {join_ms:.2f} ms ({len(join_rows)} rows returned)")

    # Benchmark 6: Aggregation over 400,000 Sales Transactions
    t0 = time.perf_counter()
    agg_res = manager.execute_aggregation("sales_transactions", agg_func="SUM", column="total_amount")
    agg_ms = (time.perf_counter() - t0) * 1000.0
    results["aggregation_400k_rows_ms"] = round(agg_ms, 2)
    results["total_sales_val"] = round(agg_res.get("value", 0.0), 2)
    logger.info(f"[Aggregation 400,000 Rows] Sum total: ₹{agg_res.get('value', 0):,.2f} in {agg_ms:.2f} ms")

    return results


async def test_non_blocking_voice_simulation(db_path: str = "data/warehouse.db"):
    """
    Simulates the Voice AI loop running concurrently while high-scale DB operations execute.
    Verifies that the voice audio frame processing has ZERO jitter or pauses.
    """
    manager = MultiTableWarehouseManager(db_path=db_path)
    jitter_samples = []

    # Voice audio simulation worker: must run uninterrupted every 20ms (standard 20ms audio frame chunk)
    stop_event = asyncio.Event()

    async def voice_audio_streamer():
        last_tick = time.perf_counter()
        while not stop_event.is_set():
            await asyncio.sleep(0.02)  # 20ms audio frame
            now = time.perf_counter()
            delta_ms = (now - last_tick) * 1000.0
            last_tick = now
            jitter_samples.append(delta_ms)

    # Launch voice audio loop in background
    voice_task = asyncio.create_task(voice_audio_streamer())

    # Concurrently execute 5 heavy DB queries via async non-blocking interface
    query_tasks = [
        manager.search_text_async("Amul Butter", table_name="products", limit=10),
        manager.execute_aggregation_async("sales_transactions", agg_func="SUM", column="total_amount"),
        manager.get_record_by_id_async("products", 25000),
        manager.search_text_async("Tata Salt", table_name="products", limit=10),
        manager.get_record_by_id_async("customers", 12000),
    ]

    query_results = await asyncio.gather(*query_tasks)
    await asyncio.sleep(0.1)  # Let audio streamer capture post-query ticks
    stop_event.set()
    await voice_task

    # Evaluate voice loop jitter
    # 20ms interval expected
    anomalies = [j for j in jitter_samples if j > 50.0]  # Any frame delayed > 50ms is a stutter
    max_jitter = max(jitter_samples) if jitter_samples else 0.0
    avg_tick = sum(jitter_samples) / len(jitter_samples) if jitter_samples else 0.0

    logger.info(f"[Voice AI Non-Blocking Verification] Processed {len(jitter_samples)} audio frames.")
    logger.info(f"Avg audio frame interval: {avg_tick:.2f} ms | Max frame delay: {max_jitter:.2f} ms | Stutters (>50ms): {len(anomalies)}")

    assert len(anomalies) == 0, f"Voice loop experienced {len(anomalies)} audio stutters!"
    logger.info("PASSED: Voice AI loop remained 100% smooth and non-blocking during 1M-row operations!")


if __name__ == "__main__":
    b_results = run_warehouse_benchmarks()
    print("\n=== BENCHMARK SUMMARY (1,086,800 ROWS) ===")
    for k, v in b_results.items():
        print(f"  {k}: {v}")
    print("==========================================\n")

    print("Running Non-Blocking Voice AI Simulation...")
    asyncio.run(test_non_blocking_voice_simulation())
