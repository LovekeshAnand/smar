def choose_target_column(clean: str, agg_name: str, columns: list, domain_dict=None) -> str:
    """
    Dynamically and intelligently selects the target column for an aggregation.
    Zero hardcoding: works across any table and column set.
    """
    col_names = [c["name"] for c in columns]
    numeric_cols = [c["name"] for c in columns if any(t in str(c.get("type", "")).upper() for t in ["INT", "REAL", "FLOAT", "DOUBLE", "NUM"])]
    
    # Partition into metric columns (non-ID numeric) vs identifier columns (ending in _id or id)
    metric_cols = [c for c in numeric_cols if not c.lower().endswith("id") and c.lower() != "id"]
    id_cols = [c for c in col_names if c.lower().endswith("id") or c.lower() == "id"]

    clean_lower = clean.lower()

    if agg_name == "COUNT":
        # For COUNT: Default to '*' (all rows) unless a specific non-ID column is explicitly requested
        for c in metric_cols:
            cname = c.lower()
            if cname in clean_lower or cname.rstrip("s") in clean_lower:
                return c
        return "*"

    # For mathematical aggregations (SUM, AVG, MIN, MAX):
    # Step 1: Check if the column is directly mentioned right after the aggregation keyword
    # e.g., "mean of salaries", "average of salary", "sum of the prices", "min of refunds"
    import re
    agg_target_m = re.search(
        r"(?:sum|total|avg|average|mean|min|minimum|max|maximum)\s+(?:of|in)?\s+(?:the\s+)?([a-z_]+)",
        clean_lower
    )
    if agg_target_m:
        word = agg_target_m.group(1).rstrip("s")  # singularize "salaries" -> "salarie", handle -ies
        if word.endswith("ie"):
            word = word[:-2] + "y"  # "salaries" -> "salary"
        for c in metric_cols:
            cname = c.lower().rstrip("s")
            if cname.endswith("ie"):
                cname = cname[:-2] + "y"
            if word == cname or word in c.lower() or c.lower() in agg_target_m.group(1):
                return c

    # Step 2: Check if any metric column (or its plural) appears anywhere in the clean query
    for c in metric_cols:
        cname = c.lower()
        plural = cname + "s" if not cname.endswith("y") else cname[:-1] + "ies"
        words = clean_lower.split()
        if cname in clean_lower or plural in clean_lower or cname.replace("_", " ") in clean_lower:
            return c

    # Step 3: Check domain synonyms (e.g. pay/wage -> salary, cost -> price)
    if domain_dict and hasattr(domain_dict, "synonyms"):
        for c in metric_cols:
            syns = domain_dict.synonyms.get(c.lower(), [])
            if any(s in clean_lower.split() for s in syns):
                return c

    # Step 4: Explicit request for ID aggregation (e.g. "average of employee id")
    # Only if user explicitly asks for the ID column itself
    for c in id_cols:
        cname = c.lower()
        c_phrase = cname.replace("_", " ")
        if f"of {cname}" in clean_lower or f"of {c_phrase}" in clean_lower or f"of the {c_phrase}" in clean_lower:
            return c

    # Step 5: Fallback: default to the first metric column (NEVER an ID column)
    if metric_cols:
        return metric_cols[0]
    return numeric_cols[0] if numeric_cols else "*"

# Test cases
emp_cols = [
    {"name": "employee_id", "type": "INTEGER", "pk": True},
    {"name": "store_id", "type": "INTEGER"},
    {"name": "salary", "type": "REAL"}
]

test_cases = [
    ("can you tell me the mean of salaries of from employee id 30 to 40 like i want the mean of salary not the employee id", "AVG", "salary"),
    ("can you tell me the mean of the salaries from the range of employee id 30 to 40 like i want the mean", "AVG", "salary"),
    ("what is the average salary per store", "AVG", "salary"),
    ("sum of all salaries", "SUM", "salary"),
    ("average of employee id", "AVG", "employee_id"),
    ("how many employees", "COUNT", "*")
]

for q, agg, expected in test_cases:
    chosen = choose_target_column(q, agg, emp_cols)
    status = "OK" if chosen == expected else "FAIL"
    print(f"[{status}] Agg={agg} Expected={expected} Got={chosen} for: '{q[:50]}...'")
