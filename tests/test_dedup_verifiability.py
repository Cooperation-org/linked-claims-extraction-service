"""
Tests for statement deduplication and verifiability labeling
(extraction_common) and the batch-ingest manifest reader.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from extraction_common import (
    VERIFIABILITY_VALUES,
    is_new_statement,
    normalize_statement,
    normalize_verifiability,
    process_claim_data,
)


class TestNormalizeStatement:
    def test_collapses_whitespace_and_case(self):
        a = normalize_statement("Child mortality  fell by 50%\n between 2000 and 2020")
        b = normalize_statement("child mortality fell by 50% between 2000 AND 2020")
        assert a == b

    def test_strips_surrounding_quotes_and_period(self):
        assert normalize_statement('"We served 500 families."') == \
            normalize_statement("we served 500 families")

    def test_empty_and_none(self):
        assert normalize_statement(None) == ''
        assert normalize_statement('   ') == ''


class TestIsNewStatement:
    def test_first_occurrence_is_new_then_duplicate(self):
        seen = set()
        assert is_new_statement(seen, "We built 3 schools") is True
        assert is_new_statement(seen, "we built 3  schools.") is False

    def test_empty_statement_never_new(self):
        seen = set()
        assert is_new_statement(seen, "") is False
        assert is_new_statement(seen, None) is False
        assert seen == set()

    def test_distinct_statements_both_new(self):
        seen = set()
        assert is_new_statement(seen, "claim one") is True
        assert is_new_statement(seen, "claim two") is True
        assert len(seen) == 2


class TestNormalizeVerifiability:
    @pytest.mark.parametrize("value", VERIFIABILITY_VALUES)
    def test_valid_values_pass_through(self, value):
        assert normalize_verifiability(value) == value

    def test_case_and_whitespace_tolerated(self):
        assert normalize_verifiability("  Projection ") == "projection"

    @pytest.mark.parametrize("value", [None, "", "banana", "verified"])
    def test_invalid_values_coerce_to_unclear(self, value):
        assert normalize_verifiability(value) == "unclear"


class TestProcessClaimDataVerifiability:
    def _process(self, claim):
        return process_claim_data(
            claim_data=claim,
            text="page text",
            document_id="doc-1",
            public_url="https://example.org/report.pdf",
            page_num=3,
        )

    def test_verifiability_carried_into_claim_data(self):
        result = self._process({
            "subject": "https://example.org/org",
            "statement": "we did a thing",
            "verifiability": "projection",
        })
        assert result["claim_data"]["verifiability"] == "projection"

    def test_missing_verifiability_defaults_to_unclear(self):
        result = self._process({
            "subject": "https://example.org/org",
            "statement": "we did a thing",
        })
        assert result["claim_data"]["verifiability"] == "unclear"


class TestManifestReader:
    def _write(self, content):
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return f.name

    def test_valid_manifest(self, tmp_path):
        pdf = tmp_path / "r.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        path = self._write(
            "pdf_path,public_url,effective_date,subject_url\n"
            f"{pdf},https://example.org/r.pdf,2025-12-31,https://example.org\n")
        from batch_ingest import read_manifest
        rows = read_manifest(path)
        assert len(rows) == 1
        assert rows[0]["subject_url"] == "https://example.org"
        assert rows[0]["effective_date"].year == 2025

    def test_missing_column_rejected(self):
        path = self._write("pdf_path,public_url\nx,y\n")
        from batch_ingest import read_manifest
        with pytest.raises(ValueError, match="missing columns"):
            read_manifest(path)

    def test_missing_file_rejected(self):
        path = self._write(
            "pdf_path,public_url,effective_date\n"
            "/nonexistent/file.pdf,https://example.org/r.pdf,2025-12-31\n")
        from batch_ingest import read_manifest
        with pytest.raises(ValueError, match="file not found"):
            read_manifest(path)
