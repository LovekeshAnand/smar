# Read Models & Hot Data Cache Layer: Technical Specifications & Smart Data Layer Integration

> **Author**: Vedika (Senior Backend/Data Engineer - SMAR v2 Project)  
> **Source of Truth**: Primary SQLite Database (`data/smar_inventory.db`)  
> **Target Consumer**: Smart Data Layer (Entity Resolution, Voice Intent Classifiers, Cognitive Context Engine)

---

## 1. Executive Summary

This subsystem implements the final two components of the **Structured Data Layer**:
1. **Read Models & Materialized Views**: Accelerated, pre-aggregated database projections for category stock values, SKU counts, and reorder alerts.
2. **Hot Data Cache Layer**: High-performance Cache-Aside engine with data-classification TTL policies, thread-safe LRU eviction, and automatic cache invalidation to protect against serving stale volatile stock information.

---

## 2. Architecture & Data Flow

```
                      ┌─────────────────────────────┐
                      │    Smart Data Layer Engine  │
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │    StructuredDataService    │
                      └──────────────┬──────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │ (1) Cache Lookup              │
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │   Hot Data Cache Layer    │   │ Cache MISS Fallback       │
       │   (Cache HIT -> Return)   │   └─────────────┬─────────────┘
       └───────────────────────────┘                 │
                                                     ▼
                                       ┌───────────────────────────┐
                                       │ Read Models / Primary DB  │
                                       │ (Materialized Views)      │
                                       └───────────────────────────┘
```

---

## 3. Read Models & Materialized Views

### 3.1 `mv_category_summary` (Materialized Category Aggregations Table)
- **Purpose**: Pre-aggregates stock values, total SKUs, active SKUs, and low-stock counts per category.
- **Columns**: `category` (PK), `total_skus`, `active_skus`, `total_quantity`, `low_stock_count`, `total_stock_value_mrp`, `total_stock_value_cost`, `last_updated_at`.
- **Why It Exists**: Eliminates standard dynamic `SUM(quantity * unit_price) GROUP BY category` full table scans over 100,000 items when Kirana owners ask category inventory summary questions.
- **Refresh Strategy**: Refreshed automatically on inventory updates or via `read_models.refresh_all_materialized_views()`.

### 3.2 `mv_low_stock_alerts` (Materialized Reorder Alerts Table)
- **Purpose**: Pre-aggregates active inventory items where available quantity is at or below the reorder threshold (`quantity <= reorder_level`).
- **Columns**: `item_id` (PK), `canonical_name`, `category`, `brand`, `quantity`, `reorder_level`, `deficit_quantity`, `unit_price`, `updated_at`.
- **Why It Exists**: Enables instantaneous sorting and retrieval of critical stock replenishment alerts.

---

## 4. Hot Data Cache Layer Design

### 4.1 Cache Key Standards
- **Static Item Data**: `smar:item:static:{item_id}`
- **Full Item Data**: `smar:item:full:{item_id}`
- **Volatile Stock & Price**: `smar:item:volatile:{item_id}`
- **Barcode Scan Lookup**: `smar:barcode:{barcode}`
- **Category Summary**: `smar:category:summary:{category_name}`
- **Low Stock List**: `smar:low_stock:list`

### 4.2 TTL & Classification Strategy

| Classification | Attributes | TTL Policy | Rationale |
| :--- | :--- | :--- | :--- |
| **Static Data** | `canonical_name`, `category`, `brand`, `unit_of_measure`, `hsn_code` | **3,600 sec** (1 Hour) | Product identity metadata changes rarely. |
| **Volatile Data** | `quantity`, `unit_price`, `cost_price`, `reorder_level` | **15 sec** + Invalidation | Primary DB remains source of truth; prevents serving stale stock. |
| **Barcode Index** | `barcode` -> `item_id` | **3,600 sec** (1 Hour) | Barcode mappings are immutable trade numbers. |
| **Category Summary** | Aggregated category metrics | **60 sec** | Category totals change with bulk sales. |
| **Low Stock Alerts** | Reorder list prioritization | **30 sec** | Changes as stock decreases. |

### 4.3 Invalidation Strategy
When `service.update_item_stock_or_price(item_id, ...)` is called:
1. Primary Database (`data/smar_inventory.db`) is updated as the source of truth.
2. Materialized views (`mv_category_summary`, `mv_low_stock_alerts`) are refreshed.
3. Selective invalidation flushes `smar:item:full:{item_id}`, `smar:item:volatile:{item_id}`, `smar:barcode:{barcode}`, `smar:category:summary:{category}`, and `smar:low_stock:list`.

### 4.4 Fallback & Resilience Behavior
If the cache layer is disabled, encounters an exception, or experiences memory pressure, it logs a warning and gracefully falls back to querying the Primary DB / Materialized Views cleanly without throwing application errors.

---

## 5. Smart Data Layer Integration Contract

Downstream Smart Data Layer components can instantiate `StructuredDataService` to query inventory:

```python
from structured_data import StructuredDataService

service = StructuredDataService()

# 1. Full Item Lookup (Cache-Aside: 15s TTL)
item = service.get_item("INV-000100")

# 2. Separated Static Metadata (1h TTL) & Volatile Live Stock (Direct/Short TTL)
static_data = service.get_item_static("INV-000100")
volatile_data = service.get_item_volatile("INV-000100", use_cache=False)

# 3. Voice Assistant Inventory Info (Zero stale risk)
info = service.get_current_inventory_info("INV-000100")

# 4. Barcode Scanner Lookup (POS)
item_by_bc = service.get_item_by_barcode("8901030000100")

# 5. Sub-millisecond FTS5 Fuzzy Search
results = service.search_items(query="tata salt", limit=10)

# 6. Category Aggregations from Materialized View
summary = service.get_category_summary("Spices & Cooking Essentials")
all_summaries = service.get_all_category_summaries()

# 7. Low Stock Reorder Alerts from Materialized View
alerts = service.get_low_stock_alerts(limit=50)

# 8. Direct Cache Lookup & Population for Cognitive Layers
val = service.cache_lookup("custom:key")
service.cache_populate("custom:key", {"status": "ok"}, ttl_seconds=30)

# 9. Mutate Stock (Source of Truth Update + Materialized View Refresh + Cache Invalidation)
service.update_item_stock_or_price("INV-000100", new_quantity=75.0)
```

---

## 6. Performance Benchmarks & Query Plans (100,000 Records)

Measured directly on `data/smar_inventory.db` populated with **100,000 Kirana records**:

### 6.1 Query Plan Verification (`EXPLAIN QUERY PLAN`)
- **Exact PK Lookup**: `SEARCH inventory_items USING INDEX sqlite_autoindex_inventory_items_1 (item_id=?)`
- **Barcode Scan**: `SEARCH inventory_items USING INDEX idx_inventory_barcode (barcode=?)`
- **Category Filter**: `SEARCH inventory_items USING INDEX idx_inventory_category (category=?)`
- **Materialized Category Aggregation**: `SEARCH mv_category_summary USING INDEX sqlite_autoindex_mv_category_summary_1 (category=?)`
- **Low Stock Priority Alerts**: `SCAN mv_low_stock_alerts USING INDEX idx_mv_low_stock_deficit`

### 6.2 Latency Measurements
- **Cold Request Latency (Initial DB fetch)**: `14.68 ms`
- **Cache MISS Latency (DB search)**: `4.77 ms`
- **Cache HIT Latency (In-Memory Hot Cache)**: **`0.0023 ms`** (**~2,055x Faster**)
- **Dynamic GROUP BY Aggregation over 100k rows**: `20.17 ms`
- **Materialized Read Model Query**: **`3.64 ms`** (**~5.5x Faster**)
- **Cache Unavailable Fallback Latency**: `6.15 ms` (100% successful, zero exceptions)
- **Cache Hit Ratio**: **`98.06%`**
- **All Unit Tests**: `22 / 22 PASSED` (100% pass rate)
