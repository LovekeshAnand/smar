import re

test_queries = [
    "can you tell me the mean of salaries of from employee id 30 to 40 like i want the mean of salary not the employee id",
    "can you tell me the mean of the salaries from the range of employee id 30 to 40 like i want the mean",
    "mean of salary for employees from 30 to 40",
    "average salary between employee id 50 and 60",
    "sum of salary from 1 to 10",
    "average price of products from range 100 to 200",
    "total salary for employee id 30"
]

for q in test_queries:
    # Look for range: 2 numbers separated by to / and / - with range/from/between prefix or just numbers
    rm = re.search(r'(?:range\s+(?:of\s+)?|between\s+|from\s+)?(?:[a-z_]+\s+)*?(\d+)\s*(?:to|and|-)\s*(\d+)\b', q)
    if rm:
        print(f'MATCH: [{rm.group(1)} to {rm.group(2)}] in: "{q[:60]}..."')
    else:
        print(f'NO RANGE in: "{q[:60]}..."')
