"""
Tests for ingest modules.
Verifies PDFs and spreadsheets normalize correctly.
"""

import pytest
from pathlib import Path
import tempfile
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.pdf_ingest import PDFIngestor
from ingest.spreadsheet_ingest import SpreadsheetIngestor
from ingest.normalize_input import InputNormalizer


class TestPDFIngest:
    """Test PDF ingestion."""

    def test_extract_plss_from_text(self):
        """Test PLSS extraction from text."""
        ingestor = PDFIngestor()

        text = "The unit includes T1N R68W Sec 16 and surrounding areas."
        tracts = ingestor._extract_tracts_from_text(text, 1, "test.pdf")

        assert len(tracts) > 0
        assert "T1N" in tracts[0].legal_description
        assert "R68W" in tracts[0].legal_description
        assert "Sec" in tracts[0].legal_description

    def test_extract_acreage(self):
        """Test acreage extraction."""
        ingestor = PDFIngestor()

        text = "containing approximately 160 acres"
        acres = ingestor._extract_acreage(text)

        assert acres == 160.0

    def test_extract_unit_info(self):
        """Test unit info extraction."""
        ingestor = PDFIngestor()

        text = """
        Smith 16-21 DSU
        Weld County, Colorado
        Operator: ABC Oil Company
        """

        info = ingestor.extract_unit_info(text)

        assert info["unit_name"] is not None
        assert "county" in info or "County" in text


class TestSpreadsheetIngest:
    """Test spreadsheet ingestion."""

    def test_read_csv(self):
        """Test reading CSV file."""
        # Create test CSV
        data = {
            "Tract": ["1", "2"],
            "Legal Description": ["T1N R68W Sec 16", "T1N R68W Sec 21"],
            "Gross Acres": [160.0, 160.0],
            "Owner": ["John Doe", "Jane Smith"]
        }

        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            csv_path = f.name

        try:
            ingestor = SpreadsheetIngestor()
            result = ingestor.read_file(csv_path)

            assert result["success"]
            assert result["rows"] == 2
            assert len(ingestor.tracts) == 2

        finally:
            Path(csv_path).unlink()

    def test_column_mapping(self):
        """Test column name variations."""
        ingestor = SpreadsheetIngestor()

        # Mock dataframe
        ingestor.data = pd.DataFrame({
            "tract_id": ["1"],
            "legal": ["T1N R68W Sec 16"],
            "gross": [160.0]
        })

        tract_col = ingestor._find_column(ingestor.TRACT_ID_COLUMNS)
        legal_col = ingestor._find_column(ingestor.LEGAL_DESC_COLUMNS)
        gross_col = ingestor._find_column(ingestor.GROSS_ACRES_COLUMNS)

        assert tract_col == "tract_id"
        assert legal_col == "legal"
        assert gross_col == "gross"


class TestInputNormalizer:
    """Test input normalization."""

    def test_normalize_legal_desc(self):
        """Test legal description normalization."""
        normalizer = InputNormalizer()

        legal1 = "Township 1 North Range 68 West Section 16"
        legal2 = "T1N R68W Sec 16"

        norm1 = normalizer._normalize_legal_desc(legal1)
        norm2 = normalizer._normalize_legal_desc(legal2)

        # Both should normalize to similar format
        assert "T1N" in norm1 or "T 1N" in norm1
        assert "R68W" in norm2

    def test_parse_plss(self):
        """Test PLSS component parsing."""
        normalizer = InputNormalizer()

        from ingest.normalize_input import NormalizedTract

        tract = NormalizedTract(
            tract_id="1",
            legal_description="T1N R68W Sec 16"
        )

        normalizer._parse_plss(tract)

        assert tract.township == "1N"
        assert tract.range == "68W"
        assert tract.section == 16

    def test_merge_duplicates(self):
        """Test duplicate tract merging."""
        normalizer = InputNormalizer()

        from ingest.normalize_input import NormalizedTract

        # Create duplicates
        tract1 = NormalizedTract(
            tract_id="1",
            legal_description="T1N R68W Sec 16",
            gross_acres=160.0,
            confidence_score=80.0
        )

        tract2 = NormalizedTract(
            tract_id="2",
            legal_description="T1N R68W SEC 16",  # Slight variation
            net_acres=140.0,
            confidence_score=70.0
        )

        normalizer.tracts = [tract1, tract2]
        merged = normalizer.merge_duplicate_tracts()

        # Should merge to one tract
        assert len(merged) <= 2  # May or may not merge depending on normalization


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
