"""Regression tests for IT-Link importer."""
import ast
import importlib.util
import sys
from pathlib import Path

_ITLINK_PATH = str(Path(__file__).resolve().parents[2] / "backend/app/imports/itlink.py")


def test_category_path_assigned_before_use():
    with open(_ITLINK_PATH, "r") as f:
        tree = ast.parse(f.read())

    parse_offers = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "parse_offers":
            parse_offers = node
            break

    assert parse_offers is not None, "parse_offers method not found"

    # Collect all name references in parse_offers
    names_in_body = set()
    for node in ast.walk(parse_offers):
        if isinstance(node, ast.Name):
            names_in_body.add(node.id)

    assert "category_path" in names_in_body,         "category_path must be referenced in parse_offers"

    # Now check ordering: find the resolve_category_path CALL
    # and verify it comes BEFORE the first usage in calculate_price/find_markup_multiplier
    # We do this by checking the AST line numbers
    assign_line = None
    first_calculate_price_use = None

    for node in ast.walk(parse_offers):
        # Find assignment to category_path via resolve_category_path
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "category_path":
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        func_name = None
                        if isinstance(func, ast.Attribute):
                            func_name = func.attr
                        elif isinstance(func, ast.Name):
                            func_name = func.id
                        if func_name and "resolve_category_path" in func_name:
                            assign_line = node.lineno

        # Find usage of category_path as Name (not target)
        if isinstance(node, ast.Name) and node.id == "category_path":
            # Check it's not a target of an assignment
            is_target = False
            for parent in ast.walk(tree):
                if isinstance(parent, ast.Assign):
                    for t in parent.targets:
                        if isinstance(t, ast.Name) and t.id == "category_path" and t.lineno == node.lineno:
                            is_target = True
            if not is_target:
                # This is a usage
                if first_calculate_price_use is None or node.lineno < first_calculate_price_use:
                    first_calculate_price_use = node.lineno

    assert assign_line is not None,         "category_path must be assigned via resolve_category_path() in parse_offers"
    assert first_calculate_price_use is not None,         "category_path must be used in parse_offers"
    assert assign_line < first_calculate_price_use,         f"BUG: category_path assigned at line {assign_line} but "         f"first used at line {first_calculate_price_use}. "         "Move resolve_category_path() BEFORE price calculation."


def test_itlink_import_stats_alias():
    """IT-Link ImportStats is an alias of shared ImportStats."""
    _stats_path = str(Path(_ITLINK_PATH).parent / "import_stats.py")
    _spec = importlib.util.spec_from_file_location("import_stats", _stats_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ImportStats = _mod.ImportStats
    s = ImportStats()
    s.record_unmapped_category("Test")
    assert s.has_unmapped is True
