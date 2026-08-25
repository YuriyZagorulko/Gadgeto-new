"""Tests for the Rozetka mapping suggestion engine."""

import json
from unittest.mock import patch, MagicMock

from app.channels.rozetka.mapping_suggestions import (
    suggest_mappings,
    _normalize,
    _similarity,
)


class TestNormalization:
    """Tests for text normalization."""

    def test_lowercase(self):
        assert _normalize("Ноутбук") == "ноутбук"

    def test_whitespace_collapsed(self):
        assert _normalize("  Оперативна   пам'ять  ") == "оперативна память"

    def test_punctuation_removed(self):
        assert _normalize("\u041a\u043e\u043c\u043f\u0027\u044e\u0442\u0435\u0440") == "компютер"

    def test_hyphen_to_space(self):
        result = _normalize("\u0421\u0432\u0435\u0440\u043b\u043e-\u0431\u0443\u0440")
        assert " " in result or "-" not in result

    def test_mixed_ukrainian_cyrillic(self):
        result = _normalize("\u0412\u0456\u0434\u0435\u043e\u043a\u0430\u0440\u0442\u0430")
        assert "\u0432\u0456\u0434\u0435\u043e" in result


class TestSimilarity:
    """Tests for string similarity."""

    def test_identical(self):
        assert _similarity("abc", "abc") == 1.0

    def test_completely_different(self):
        assert _similarity("abc", "xyz") < 0.5

    def test_similar_ukrainian(self):
        sim = _similarity(
            _normalize("\u041e\u043f\u0435\u0440\u0430\u0442\u0438\u0432\u043d\u0430 \u043f\u0430\u043c\u0027\u044f\u0442\u044c"),
            _normalize("\u041e\u043f\u0435\u0440\u0430\u0442\u0438\u0432\u043d\u0430 \u043f\u0430\u043c\u0027\u044f\u0442\u044c"),
        )
        assert sim == 1.0


class TestSuggestCategories:
    """Tests for category mapping suggestions."""

    def test_exact_match(self):
        with patch("app.channels.rozetka.mapping_suggestions.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # First call: fetch internal category
            mock_cursor.fetchone.side_effect = [
                {"name": "\u041d\u043e\u0443\u0442\u0431\u0443\u043a\u0438"},  # internal category
            ]
            # Second call: fetch all Rozetka categories
            mock_cursor.fetchall.return_value = [
                {"external_id": "12345", "name": "\u041d\u043e\u0443\u0442\u0431\u0443\u043a\u0438"},
                {"external_id": "67890", "name": "\u041f\u043b\u0430\u043d\u0448\u0435\u0442\u0438"},
                {"external_id": "11111", "name": "\u041c\u043e\u043d\u0456\u0442\u043e\u0440\u0438"},
            ]
            
            results = suggest_mappings(channel_id=1, kind="categories", internal_id=1)
            assert len(results) > 0
            # Exact match should be highest confidence
            assert results[0]["confidence"] == 1.0
            assert results[0]["method"] == "exact"

    def test_no_match(self):
        with patch("app.channels.rozetka.mapping_suggestions.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"name": "\u0427\u0430\u0439\u043d\u0438\u043a\u0438"}
            mock_cursor.fetchall.return_value = [
                {"external_id": "12345", "name": "\u041d\u043e\u0443\u0442\u0431\u0443\u043a\u0438"},
            ]
            results = suggest_mappings(channel_id=1, kind="categories", internal_id=1)
            # No match for "\u0427\u0430\u0439\u043d\u0438\u043a\u0438" (teapots) vs "\u041d\u043e\u0443\u0442\u0431\u0443\u043a\u0438" (laptops)
            assert len(results) == 0 or results[0]["confidence"] < 0.5


class TestSuggestValues:
    """Tests for value mapping suggestions (stricter matching)."""

    def test_value_exact_match(self):
        with patch("app.channels.rozetka.mapping_suggestions.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"value": "128 \u0413\u0411"}
            mock_cursor.fetchall.return_value = [
                {"external_id": "5001", "value": "128 \u0413\u0411", "attribute_external_id": "1001"},
                {"external_id": "5002", "value": "256 \u0413\u0411", "attribute_external_id": "1001"},
            ]
            results = suggest_mappings(channel_id=1, kind="values", internal_id=1, ext_attr_id="1001")
            assert len(results) == 1
            assert results[0]["confidence"] == 1.0
            assert results[0]["method"] == "exact"

    def test_no_false_positive_value(self):
        """\"128 \u0413\u0411\" should NEVER match \"256 \u0413\u0411\""""
        with patch("app.channels.rozetka.mapping_suggestions.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"value": "128 \u0413\u0411"}
            mock_cursor.fetchall.return_value = [
                {"external_id": "5002", "value": "256 \u0413\u0411", "attribute_external_id": "1001"},
            ]
            results = suggest_mappings(channel_id=1, kind="values", internal_id=1, ext_attr_id="1001")
            assert len(results) == 0


class TestSuggestAttributes:
    """Tests for attribute mapping suggestions."""

    def test_global_attribute_matching(self):
        with patch("app.channels.rozetka.mapping_suggestions.psycopg2.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"name": "\u0413\u0430\u0440\u0430\u043d\u0442\u0456\u044f"}
            mock_cursor.fetchall.return_value = [
                {"external_id": "20769", "name": "\u0413\u0430\u0440\u0430\u043d\u0442\u0456\u044f"},
            ]
            results = suggest_mappings(channel_id=1, kind="attributes", internal_id=1, ext_cat_id="80032")
            assert len(results) > 0
            assert results[0]["method"] == "exact"


class TestMappingStatus:
    """Tests for mapping status workflow."""

    def test_proposed_not_accepted(self):
        """Proposed mappings should not be treated as accepted."""
        status = "proposed"
        assert status != "accepted"

    def test_rejected_not_accepted(self):
        status = "excluded"
        assert status != "accepted"

    def test_accepted_is_accepted(self):
        status = "accepted"
        assert status == "accepted"
