import sys
sys.path.insert(0, '.')
import re
from structured_data.multi_table_manager import MultiTableWarehouseManager

wm = MultiTableWarehouseManager()
tables = wm.list_tables()
emp_table = next(t for t in tables if t["table_name"] == "employees")
columns = emp_table["columns"]

def parse_agg_test(clean: str, agg_name: str = "AVG"):
    # Metric vs ID columns
    numeric_cols = [c["name"] for c in columns if any(t in str(c.get("type", "")).upper() for t in ["INT", "REAL", "FLOAT", "DOUBLE", "NUM"])]
    metric_cols = [c for c in numeric_cols if not c.lower().endswith("id") and c.lower() != "id"]
    id_cols = [c["name"] for c in columns if c["name"].lower().endswith("id") or c["name"].lower() == "id"]

    clean_lower = clean.lower()

    # Column selection
    target_col = None
    if agg_name == "COUNT":
        for c in metric_cols:
            if c.lower() in clean_lower:
                target_col = c
                break
        if not target_col:
            target_col = "*"
    else:
        # Step 1: Explicit target after agg word
        agg_target_m = re.search(
            r"(?:sum|total|avg|average|mean|min|minimum|max|maximum)\s+(?:of|in)?\s+(?:the\s+)?([a-z_]+)",
            clean_lower
        )
        if agg_target_m:
            word = agg_target_m.group(1).rstrip("s")
            if word.endswith("ie"):
                word = word[:-2] + "y"
            for c in metric_cols:
                cname = c.lower().rstrip("s")
                if cname.endswith("ie"):
                    cname = cname[:-2] + "y"
                if word == cname or word in c.lower() or c.lower() in agg_target_m.group(1):
                    target_col = c
                    break

        # Step 2: Metric column mention
        if not target_col:
            for c in metric_cols:
                cname = c.lower()
                plural = cname + "s" if not cname.endswith("y") else cname[:-1] + "ies"
                if cname in clean_lower or plural in clean_lower or cname.replace("_", " ") in clean_lower:
                    target_col = c
                    break

        # Step 3: Explicit ID request
        if not target_col:
            for c in id_cols:
                cname = c.lower()
                c_phrase = cname.replace("_", " ")
                if f"of {cname}" in clean_lower or f"of {c_phrase}" in clean_lower:
                    target_col = c
                    break

        # Step 4: Fallback
        if not target_col:
            target_col = metric_cols[0] if metric_cols else (numeric_cols[0] if numeric_cols else "*")

    # Filter parsing
    pk_col = next((c["name"] for c in columns if c.get("pk")), None)
    if not pk_col:
        pk_col = next((c["name"] for c in columns if c["name"].lower().endswith("id")), columns[0]["name"])

    filter_cond = None
    filter_params = None
    filter_desc = None

    # 1. Range filter first
    range_m = re.search(r'(?:range\s+(?:of\s+)?|between\s+|from\s+)?(?:[a-z_]+\s+)*?(\d+)\s*(?:to|and|-)\s*(\d+)\b', clean_lower)
    if range_m:
        start_val, end_val = int(range_m.group(1)), int(range_m.group(2))
        range_col = pk_col
        text_before_range = clean_lower[:range_m.start() + len(range_m.group(0))]
        for c in columns:
            cname = c["name"].lower()
            c_phrase = cname.replace("_", " ")
            if cname in text_before_range or c_phrase in text_before_range:
                range_col = c["name"]
                break
        filter_cond = f'"{range_col}" BETWEEN ? AND ?'
        filter_params = [start_val, end_val]
        filter_desc = f"{range_col} from {start_val} to {end_val}"

    return {
        "table": "employees",
        "column": target_col,
        "function": agg_name,
        "filter_condition": filter_cond,
        "filter_params": filter_params,
        "filter_description": filter_desc
    }

queries = [
    "can you tell me the mean of salaries of from employee id 30 to 40 like i want the mean of salary not the employee id",
    "can you tell me the mean of the salaries from the range of employee id 30 to 40 like i want the mean",
    "what is the average salary per store in a bar chart",
    "how many orders are in the database"
]

for q in queries:
    agg = "COUNT" if "how many" in q else "AVG"
    res = parse_agg_test(q, agg)
    print(f"\nQ: {q[:70]}...")
    print(f"   Col: {res['column']} | Func: {res['function']} | Filter: {res['filter_condition']} | Params: {res['filter_params']}")
