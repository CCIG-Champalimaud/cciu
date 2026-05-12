"""Unit tests for b-value normalisation helpers in dicom_bvalue_table."""

from unittest.mock import MagicMock

import pytest

from cciu.entrypoints.dicom_bvalue_table import (
    _extract_bvalue,
    _normalize_ge_bvalue,
    _normalize_siemens_bvalue,
)


class TestNormalizeGeBvalue:
    def test_none_returns_none(self):
        assert _normalize_ge_bvalue(None) is None

    def test_plain_integer_string(self):
        assert _normalize_ge_bvalue("800") == 800

    def test_integer_value(self):
        assert _normalize_ge_bvalue(800) == 800

    def test_bytes_input(self):
        assert _normalize_ge_bvalue(b"800") == 800

    def test_backslash_separated_returns_first(self):
        assert _normalize_ge_bvalue("0\\800\\1600") == 0

    def test_bracket_list_string_returns_first(self):
        assert _normalize_ge_bvalue("[0, 800, 1600]") == 0

    def test_bracket_list_nonzero_first(self):
        assert _normalize_ge_bvalue("[800, 0]") == 800

    def test_bytes_backslash_separated(self):
        assert _normalize_ge_bvalue(b"0\\800") == 0

    def test_invalid_string_returns_none(self):
        assert _normalize_ge_bvalue("not_a_number") is None

    def test_invalid_bracket_list_returns_none(self):
        assert _normalize_ge_bvalue("[abc, def]") is None


class TestNormalizeSiemensBvalue:
    def test_none_returns_none(self):
        assert _normalize_siemens_bvalue(None) is None

    def test_integer_passthrough(self):
        assert _normalize_siemens_bvalue(800) == 800

    def test_string_integer(self):
        assert _normalize_siemens_bvalue("800") == 800

    def test_invalid_string_returns_none(self):
        assert _normalize_siemens_bvalue("not_a_number") is None


class TestExtractBvalue:
    def _make_ds(self, tags: dict):
        """Build a minimal mock pydicom Dataset with the given tag dict."""
        def get_side_effect(tag, default=None):
            return tags.get(tag, default)

        ds = MagicMock()
        ds.get = MagicMock(side_effect=get_side_effect)
        return ds

    def test_standard_tag_takes_priority(self):
        elem = MagicMock()
        elem.value = 800
        ds = self._make_ds({("0018", "9087"): elem})
        assert _extract_bvalue(ds) == 800

    def test_siemens_tag_fallback(self):
        siemens_elem = MagicMock()
        siemens_elem.value = 400
        ds = self._make_ds({("0019", "100c"): siemens_elem})
        assert _extract_bvalue(ds) == 400

    def test_ge_tag_fallback(self):
        ge_elem = MagicMock()
        ge_elem.value = "0\\800"
        ds = self._make_ds({("0043", "1039"): ge_elem})
        assert _extract_bvalue(ds) == 0

    def test_no_bvalue_returns_none(self):
        ds = self._make_ds({})
        assert _extract_bvalue(ds) is None

    def test_standard_tag_invalid_falls_through_to_siemens(self):
        bad_elem = MagicMock()
        bad_elem.value = "not_castable"
        siemens_elem = MagicMock()
        siemens_elem.value = 50
        ds = self._make_ds(
            {("0018", "9087"): bad_elem, ("0019", "100c"): siemens_elem}
        )
        assert _extract_bvalue(ds) == 50
