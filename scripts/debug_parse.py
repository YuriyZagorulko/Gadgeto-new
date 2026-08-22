#!/usr/bin/env python3
"""Debug SQL row parsing for wp_posts."""
import re, sys

DUMP = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/db_dump.sql"

with open(DUMP, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

pattern = re.compile(r"INSERT INTO `wp_posts` VALUES(.+?)\n--", re.DOTALL)
m = pattern.search(content)
val_text = m.group(1)

# Find product keyword
pos = val_text.find("product")
print(f"Found 'product' at pos {pos}")

# Manual parse around that position
i = val_text.rfind("(", 0, pos)
print(f"Row starts at {i}")

# Extract row text
depth = 0
j = i
while j < len(val_text):
    if val_text[j] == "(":
        depth += 1
    elif val_text[j] == ")":
        depth -= 1
        if depth == 0:
            row = val_text[i+1:j]
            break
    j += 1

print(f"Row length: {len(row)}")

# Split manually  
cols = []
cur = ""
in_str = Fals
skip = 0

for k, c in enumerate(row)
    if skip > 0:
        skip -= 1
        if in_str: cur += c
        continue    
    if in_str:
        if c == "\\":
            skip = 1
            cur += "\\"
        elif c == "'":
            in_str = False
            cols.append(cur)
            cur = ""
        else:
            cur += c
    else:
        if c == ",":
            if not cur.strip():
                cols.append(None)
            elif cur == "NULL":
                cols.append(None)
            else:
                cols.appendcur)
            cur = ""
        elif c == " ":
            pass
        elif c == "'":
            in_str = True
        else:
            cur += c

print(f"Total columns: {len(cols)if cols else 0}")
if cols:
    for idx in range(min(22, len(cols))):
        display = str(cols[idx])[:60] if cols[idx] is not None else "NULL"
        print(f"  [{idx}]: {display}")