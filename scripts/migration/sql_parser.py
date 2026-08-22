"""
SQL dump parser for WordPress mysqldump files.
"""
import re
from typing import List


def find_insert_blocks(content: str, table_name: str) -> List[str]:
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(table_name) + r"` VALUES(.+?)\n--",
        re.DOTALL
    )
    return [m.group(1) for m in pattern.finditer(content)]


def extract_all_rows(content: str, table_name: str) -> List[str]:
    blocks = find_insert_blocks(content, table_name)
    rows = []
    for block in blocks:
        rows.extend(parse_values_block(block))
    return rows


def parse_values_block(text: str) -> List[str]:
    rows = []
    depth = 0
    start = 0
    in_str = False
    for i, c in enumerate(text):
        if in_str:
            if c == "'" and (i == 0 or text[i-1] != "\\"):
                in_str = False
        else:
            if c == "'":
                in_str = True
            elif c == "(":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    rows.append(text[start:i])
    return rows


def split_row_values(text: str) -> List[str]:
    cols = []
    val = ""
    in_str = False
    for c in text:
        if in_str:
            if c == "'" and (not val or val[-1] != "\\"):
                in_str = False
                cols.append(val)
                val = ""
            else:
                val += c
        else:
            if c == "'" and (not val or val[-1] != "\\"):
                in_str = True
                val = ""
            elif c == ",":
                cols.append("")
            else:
                val += c
    if val:
        cols.append(val)
    return cols