"""
structured_data/multi_table_generator.py
=========================================
Generates a realistic 12-table retail data warehouse dataset with over 1,000,000+ rows
matching the Kaggle retail data warehouse schema specification:
https://www.kaggle.com/datasets/datarspectrum/retail-data-warehouse-12-table-1m-rows-dataset/data

Tables generated (Total > 1,086,000 rows):
1.  products (50,000 rows)
2.  stores (200 rows)
3.  suppliers (500 rows)
4.  customers (50,000 rows)
5.  inventory (150,000 rows)
6.  sales_transactions (400,000 rows)
7.  order_details (400,000 rows)
8.  purchase_orders (10,000 rows)
9.  po_items (20,000 rows)
10. promotions (1,000 rows)
11. product_categories (100 rows)
12. warehouse_locations (5,000 rows)
"""

import os
import sqlite3
import random
import time
import logging
from typing import Dict, Any

logger = logging.getLogger("smar.generator")

CATEGORIES = [
    "Grocery & Staples", "Dairy & Eggs", "Beverages", "Snacks & Confectionery",
    "Personal Care", "Household & Cleaning", "Baby Care", "Electronics & Accessories",
    "Clothing & Apparel", "Home & Kitchen", "Health & Wellness", "Stationery"
]

BRANDS = [
    "Tata", "ITC", "Amul", "Britannia", "Nestle", "Hindustan Unilever",
    "Dabur", "Parle", "Marico", "Godrej", "Patanjali", "Haldiram",
    "Cadbury", "PepsiCo", "Coca-Cola", "Colgate", "Dettol", "Aashirvaad"
]

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Chennai",
    "Kolkata", "Surat", "Pune", "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore"
]

REGIONS = ["North", "South", "East", "West", "Central"]
PAYMENT_METHODS = ["Cash", "UPI", "Credit Card", "Debit Card", "Net Banking"]
PO_STATUSES = ["Pending", "Approved", "Shipped", "Received", "Cancelled"]


def generate_1m_warehouse_db(
    db_path: str = "data/warehouse.db",
    export_samples: bool = True
) -> Dict[str, Any]:
    """Generates the 12-table warehouse database with 1,000,000+ rows."""
    start_time = time.perf_counter()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Extreme performance pragmas for massive bulk load
    cur.execute("PRAGMA journal_mode = OFF;")
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA cache_size = -128000;")  # 128MB cache
    cur.execute("PRAGMA locking_mode = EXCLUSIVE;")

    logger.info("Creating warehouse schema (12 tables)...")

    # 1. Product Categories (100 rows)
    cur.execute("""
        CREATE TABLE product_categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT NOT NULL,
            department_code TEXT NOT NULL
        );
    """)

    # 2. Stores (200 rows)
    cur.execute("""
        CREATE TABLE stores (
            store_id INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            store_size_sqft INTEGER NOT NULL
        );
    """)

    # 3. Suppliers (500 rows)
    cur.execute("""
        CREATE TABLE suppliers (
            supplier_id INTEGER PRIMARY KEY,
            supplier_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            phone TEXT NOT NULL,
            country TEXT NOT NULL
        );
    """)

    # 4. Warehouse Locations (5,000 rows)
    cur.execute("""
        CREATE TABLE warehouse_locations (
            location_id INTEGER PRIMARY KEY,
            aisle TEXT NOT NULL,
            rack TEXT NOT NULL,
            shelf TEXT NOT NULL,
            bin TEXT NOT NULL,
            max_capacity INTEGER NOT NULL
        );
    """)

    # 5. Products (50,000 rows)
    cur.execute("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            cost_price REAL NOT NULL,
            retail_price REAL NOT NULL
        );
    """)

    # 6. Customers (50,000 rows)
    cur.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            city TEXT NOT NULL,
            loyalty_tier TEXT NOT NULL
        );
    """)

    # 7. Inventory (150,000 rows)
    cur.execute("""
        CREATE TABLE inventory (
            inventory_id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            quantity_on_hand INTEGER NOT NULL,
            reorder_level INTEGER NOT NULL,
            bin_location TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        );
    """)

    # 8. Sales Transactions (400,000 rows)
    cur.execute("""
        CREATE TABLE sales_transactions (
            transaction_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            transaction_date TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        );
    """)

    # 9. Order Details (400,000 rows)
    cur.execute("""
        CREATE TABLE order_details (
            detail_id INTEGER PRIMARY KEY,
            transaction_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES sales_transactions(transaction_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)

    # 10. Purchase Orders (10,000 rows)
    cur.execute("""
        CREATE TABLE purchase_orders (
            po_id INTEGER PRIMARY KEY,
            supplier_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_cost REAL NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        );
    """)

    # 11. PO Items (20,000 rows)
    cur.execute("""
        CREATE TABLE po_items (
            po_item_id INTEGER PRIMARY KEY,
            po_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity_ordered INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)

    # 12. Promotions (1,000 rows)
    cur.execute("""
        CREATE TABLE promotions (
            promo_id INTEGER PRIMARY KEY,
            promo_name TEXT NOT NULL,
            discount_pct REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        );
    """)

    conn.commit()

    # --- POPULATING DATA IN CHUNKS ---
    random.seed(42)

    # 1. Categories (100)
    cat_rows = [(i, f"{CATEGORIES[i % len(CATEGORIES)]} Spec {i//len(CATEGORIES) + 1}", f"DEP{100 + (i%15)}") for i in range(1, 101)]
    cur.executemany("INSERT INTO product_categories VALUES (?, ?, ?);", cat_rows)

    # 2. Stores (200)
    store_rows = [(i, f"Store #{i:03d} {CITIES[i % len(CITIES)]}", CITIES[i % len(CITIES)], REGIONS[i % len(REGIONS)], random.randint(3000, 45000)) for i in range(1, 201)]
    cur.executemany("INSERT INTO stores VALUES (?, ?, ?, ?, ?);", store_rows)

    # 3. Suppliers (500)
    sup_rows = [(i, f"{BRANDS[i % len(BRANDS)]} Supply #{i}", f"orders@supplier{i}.com", f"+91-98{i:08d}"[:14], "India") for i in range(1, 501)]
    cur.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?, ?);", sup_rows)

    # 4. Warehouse Locations (5,000)
    loc_rows = [(i, f"Aisle-{chr(65 + (i//500)%26)}", f"R-{(i//50)%10 + 1}", f"S-{(i//10)%5 + 1}", f"B-{i%10 + 1}", random.choice([500, 1000, 2000])) for i in range(1, 5001)]
    cur.executemany("INSERT INTO warehouse_locations VALUES (?, ?, ?, ?, ?, ?);", loc_rows)

    # 5. Products (50,000)
    logger.info("Generating 50,000 products...")
    prod_descriptors = ["Premium", "Classic", "Gold", "Royal", "Organic", "Select", "Value", "Fresh", "Pure", "Daily"]
    prod_items = ["Atta", "Rice", "Tea", "Coffee", "Sugar", "Salt", "Ghee", "Mustard Oil", "Soap", "Shampoo", "Biscuits", "Noodles", "Toothpaste", "Detergent", "Lentils", "Spices"]
    prod_sizes = ["500g", "1kg", "2kg", "5kg", "100g", "250g", "1L", "2L", "Pack of 2", "Pack of 4"]

    prod_rows = []
    for i in range(1, 50001):
        brand = BRANDS[i % len(BRANDS)]
        cat = CATEGORIES[i % len(CATEGORIES)]
        desc = prod_descriptors[(i // 3) % len(prod_descriptors)]
        item = prod_items[i % len(prod_items)]
        sz = prod_sizes[(i // 7) % len(prod_sizes)]
        p_name = f"{brand} {desc} {item} {sz} (P-{i})"
        sku = f"SKU-{brand[:3].upper()}-{i:06d}"
        cost = round(random.uniform(15.0, 850.0), 2)
        retail = round(cost * random.uniform(1.15, 1.45), 2)
        prod_rows.append((i, sku, p_name, cat, brand, cost, retail))
        if len(prod_rows) >= 10000:
            cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?);", prod_rows)
            prod_rows = []
    if prod_rows:
        cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?);", prod_rows)

    # 6. Customers (50,000)
    logger.info("Generating 50,000 customers...")
    fnames = ["Amit", "Rahul", "Pooja", "Priya", "Vikram", "Neha", "Rohit", "Sneha", "Karan", "Anjali", "Suresh", "Ramesh"]
    lnames = ["Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Shah", "Mehta", "Joshi", "Yadav"]
    cust_rows = []
    for i in range(1, 50001):
        fn = fnames[i % len(fnames)]
        ln = lnames[(i // 2) % len(lnames)]
        cust_rows.append((i, fn, ln, f"{fn.lower()}.{ln.lower()}{i}@example.com", CITIES[i % len(CITIES)], random.choice(["Bronze", "Silver", "Gold", "Platinum"])))
        if len(cust_rows) >= 10000:
            cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?);", cust_rows)
            cust_rows = []
    if cust_rows:
        cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?);", cust_rows)

    # 7. Inventory (150,000)
    logger.info("Generating 150,000 inventory entries...")
    inv_rows = []
    for i in range(1, 150001):
        p_id = ((i - 1) % 50000) + 1
        s_id = ((i - 1) % 200) + 1
        qty = random.randint(5, 1200)
        reorder = random.randint(20, 100)
        bin_loc = f"Aisle-{chr(65 + (i % 26))}-Rack-{(i%10)+1}"
        inv_rows.append((i, p_id, s_id, qty, reorder, bin_loc))
        if len(inv_rows) >= 25000:
            cur.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?);", inv_rows)
            inv_rows = []
    if inv_rows:
        cur.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?);", inv_rows)

    # 8. Sales Transactions (400,000)
    logger.info("Generating 400,000 sales transactions...")
    tx_rows = []
    base_epoch = 1704067200  # 2024-01-01
    for i in range(1, 400001):
        c_id = ((i * 7) % 50000) + 1
        s_id = (i % 200) + 1
        tx_date = f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}"
        pm = PAYMENT_METHODS[i % len(PAYMENT_METHODS)]
        total = round(random.uniform(120.0, 4800.0), 2)
        tx_rows.append((i, c_id, s_id, tx_date, pm, total))
        if len(tx_rows) >= 25000:
            cur.executemany("INSERT INTO sales_transactions VALUES (?, ?, ?, ?, ?, ?);", tx_rows)
            tx_rows = []
    if tx_rows:
        cur.executemany("INSERT INTO sales_transactions VALUES (?, ?, ?, ?, ?, ?);", tx_rows)

    # 9. Order Details (400,000)
    logger.info("Generating 400,000 order details...")
    od_rows = []
    for i in range(1, 400001):
        t_id = i
        p_id = ((i * 13) % 50000) + 1
        qty = random.randint(1, 8)
        uprice = round(random.uniform(30.0, 600.0), 2)
        ltotal = round(qty * uprice, 2)
        od_rows.append((i, t_id, p_id, qty, uprice, ltotal))
        if len(od_rows) >= 25000:
            cur.executemany("INSERT INTO order_details VALUES (?, ?, ?, ?, ?, ?);", od_rows)
            od_rows = []
    if od_rows:
        cur.executemany("INSERT INTO order_details VALUES (?, ?, ?, ?, ?, ?);", od_rows)

    # 10. Purchase Orders (10,000)
    logger.info("Generating 10,000 purchase orders...")
    po_rows = []
    for i in range(1, 10001):
        sup_id = (i % 500) + 1
        p_date = f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}"
        status = PO_STATUSES[i % len(PO_STATUSES)]
        tot_cost = round(random.uniform(5000.0, 150000.0), 2)
        po_rows.append((i, sup_id, p_date, status, tot_cost))
    cur.executemany("INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?);", po_rows)

    # 11. PO Items (20,000)
    logger.info("Generating 20,000 po items...")
    poi_rows = []
    for i in range(1, 20001):
        po_id = ((i - 1) // 2) + 1
        p_id = ((i * 17) % 50000) + 1
        q_ord = random.randint(50, 1000)
        ucost = round(random.uniform(20.0, 450.0), 2)
        poi_rows.append((i, po_id, p_id, q_ord, ucost))
    cur.executemany("INSERT INTO po_items VALUES (?, ?, ?, ?, ?);", poi_rows)

    # 12. Promotions (1,000)
    promo_rows = [(i, f"Promo Sale #{i:04d}", round(random.uniform(5.0, 35.0), 1), "2024-01-01", "2024-12-31") for i in range(1, 1001)]
    cur.executemany("INSERT INTO promotions VALUES (?, ?, ?, ?, ?);", promo_rows)

    conn.commit()

    # Create Core Indexes
    logger.info("Building B-Tree and FTS5 search indexes...")
    cur.execute("CREATE INDEX idx_products_sku ON products (sku);")
    cur.execute("CREATE INDEX idx_products_brand ON products (brand);")
    cur.execute("CREATE INDEX idx_products_category ON products (category);")
    cur.execute("CREATE INDEX idx_inventory_product_id ON inventory (product_id);")
    cur.execute("CREATE INDEX idx_inventory_store_id ON inventory (store_id);")
    cur.execute("CREATE INDEX idx_sales_customer_id ON sales_transactions (customer_id);")
    cur.execute("CREATE INDEX idx_sales_date ON sales_transactions (transaction_date);")
    cur.execute("CREATE INDEX idx_od_transaction_id ON order_details (transaction_id);")
    cur.execute("CREATE INDEX idx_od_product_id ON order_details (product_id);")

    # Virtual table for text search on products
    cur.execute("CREATE VIRTUAL TABLE products_fts USING fts5(product_name, category, brand, content='products');")
    cur.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild');")

    conn.commit()
    conn.close()

    elapsed = time.perf_counter() - start_time
    total_records = 100 + 200 + 500 + 5000 + 50000 + 50000 + 150000 + 400000 + 400000 + 10000 + 20000 + 1000
    file_size_mb = os.path.getsize(db_path) / (1024 * 1024)

    logger.info(f"SUCCESS: Generated {total_records:,} rows across 12 tables in {elapsed:.2f}s ({file_size_mb:.1f} MB).")

    # Export sample files if requested
    if export_samples:
        import pandas as pd
        sample_conn = sqlite3.connect(db_path)
        sample_prod = pd.read_sql("SELECT * FROM products LIMIT 5000;", sample_conn)
        sample_prod.to_csv("data/retail_products_5k_sample.csv", index=False)

        sample_inv = pd.read_sql("SELECT * FROM inventory LIMIT 5000;", sample_conn)
        sample_inv.to_csv("data/retail_inventory_5k_sample.csv", index=False)

        sample_conn.close()
        logger.info("Exported sample CSV files for testing upload: data/retail_products_5k_sample.csv, data/retail_inventory_5k_sample.csv")

    return {
        "db_path": db_path,
        "total_records": total_records,
        "tables_count": 12,
        "file_size_mb": round(file_size_mb, 2),
        "generation_time_sec": round(elapsed, 2)
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_1m_warehouse_db()
    print("Warehouse Generation Completed:", res)
