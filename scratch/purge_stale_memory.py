"""
Purge stale/poisoned conversation QA turns from smar_memory.db semantic_memories.
Keeps only personal user notes (e.g. "I live in X", "my name is Y").
"""
import sqlite3

DB_PATH = "data/smar_memory.db"

TRANSACTIONAL_KEYWORDS = [
    "order", "employee", "salary", "price", "stock", "product", "shipment",
    "payment", "promotion", "customer", "store", "supplier", "return",
    "category", "qty", "quantity", "amount", "sum", "count", "avg", "total",
    "item", "invoice", "bill", "receipt", "transaction"
]

def is_stale_qa_turn(content: str) -> bool:
    """Returns True if content is a QA database turn that should NOT be in semantic memory."""
    c = content.strip()
    # Classic "User: ...\nAssistant: ..." pattern
    if "User:" in c and "Assistant:" in c:
        return True
    # Single question asking about DB entities
    low = c.lower()
    if any(kw in low for kw in TRANSACTIONAL_KEYWORDS):
        # If it's a question (starts with what/how/where/when/can/could/show/tell)
        import re
        if re.match(r"^(what|how|where|when|can|could|show|tell|give|find|check|hi what|hi can|hi how|hi could|hi please)\b", low):
            return True
    return False

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("SELECT id, user_id, content FROM semantic_memories")
rows = cur.fetchall()

to_delete = []
to_keep = []
for row_id, user_id, content in rows:
    if content and is_stale_qa_turn(content):
        to_delete.append(row_id)
        print(f"  [DELETE] id={row_id}: {repr(content[:80])}")
    else:
        to_keep.append(row_id)

print(f"\nTotal: {len(rows)} rows | Deleting: {len(to_delete)} stale | Keeping: {len(to_keep)}")

if to_delete:
    cur.executemany("DELETE FROM semantic_memories WHERE id = ?", [(i,) for i in to_delete])
    con.commit()
    print("Done. Stale entries removed.")
else:
    print("Nothing to delete.")

con.close()
