"""
Tests for Excel output.
Verifies XLSX structure, headers, and row counts.
"""

import pytest
from pathlib import Path
import tempfile
import pandas as pd
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from output.excel_writer import ExcelWriter
from title.lease_classifier import LeaseStatus
from title.owner_resolver import OwnershipType


class TestExcelWriter:
    """Test Excel output generation."""

    def test_add_unit_row(self):
        """Test adding unit row."""
        writer = ExcelWriter()

        writer.add_unit_row(
            owner_name="John Doe",
            mailing_address="123 Main St, Denver, CO 80202",
            tract_id="TRACT-1",
            legal_description="T1N R68W Sec 16",
            lease_status="UMI",
            ownership_type="MINERAL",
            gross_acres=160.0,
            net_acres=140.0,
            interest="1/8",
            address_source="county_tax_roll",
            address_date=datetime(2024, 1, 1),
            confidence_score=85.0
        )

        assert len(writer.unit_data) == 1
        assert writer.unit_data[0]["OWNER_NAME"] == "John Doe"
        assert writer.unit_data[0]["LEASE_STATUS"] == "UMI"

    def test_add_offset_row(self):
        """Test adding offset row."""
        writer = ExcelWriter()

        writer.add_offset_row(
            owner_name="Jane Smith",
            mailing_address="456 Oak Ave, Boulder, CO 80301",
            tract_id="TRACT-2",
            legal_description="T1N R68W Sec 21",
            lease_status="ROY",
            ownership_type="MINERAL",
            distance_to_unit_miles=0.3,
            gross_acres=160.0,
            confidence_score=80.0
        )

        assert len(writer.offset_data) == 1
        assert writer.offset_data[0]["DISTANCE_TO_UNIT_MILES"] == 0.3

    def test_write_excel(self):
        """Test writing Excel file."""
        writer = ExcelWriter()

        # Add some data
        writer.add_unit_row(
            owner_name="John Doe",
            mailing_address="123 Main St, Denver, CO 80202",
            tract_id="TRACT-1",
            legal_description="T1N R68W Sec 16",
            lease_status="UMI",
            ownership_type="MINERAL"
        )

        writer.add_offset_row(
            owner_name="Jane Smith",
            mailing_address="456 Oak Ave, Boulder, CO 80301",
            tract_id="TRACT-2",
            legal_description="T1N R68W Sec 21",
            lease_status="ROY",
            ownership_type="MINERAL",
            distance_to_unit_miles=0.4
        )

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            output_path = tmp.name

        try:
            success = writer.write_excel(output_path)
            assert success

            # Verify file exists
            assert Path(output_path).exists()

            # Verify sheets
            excel_file = pd.ExcelFile(output_path)
            assert "UNIT_NOTICE_LIST" in excel_file.sheet_names
            assert "OFFSET_NOTICE_LIST" in excel_file.sheet_names

            # Verify data
            unit_df = pd.read_excel(output_path, sheet_name="UNIT_NOTICE_LIST")
            offset_df = pd.read_excel(output_path, sheet_name="OFFSET_NOTICE_LIST")

            assert len(unit_df) == 1
            assert len(offset_df) == 1

            # Verify columns
            expected_cols = writer.NOTICE_COLUMNS
            assert list(unit_df.columns) == expected_cols
            assert list(offset_df.columns) == expected_cols

        finally:
            Path(output_path).unlink()

    def test_validate_output(self):
        """Test output validation."""
        writer = ExcelWriter()

        # Empty output should fail validation
        validation = writer.validate_output()
        assert not validation["valid"]
        assert "No data to write" in validation["errors"]

        # Add valid data
        writer.add_unit_row(
            owner_name="John Doe",
            mailing_address="123 Main St",
            tract_id="TRACT-1",
            legal_description="T1N R68W Sec 16",
            lease_status="UMI",
            ownership_type="MINERAL"
        )

        validation = writer.validate_output()
        assert validation["valid"]
        assert validation["unit_rows"] == 1

    def test_column_order(self):
        """Test that columns are in exact order."""
        writer = ExcelWriter()

        writer.add_unit_row(
            owner_name="Test",
            mailing_address="Test Address",
            tract_id="1",
            legal_description="Test Legal",
            lease_status="UMI",
            ownership_type="MINERAL"
        )

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            output_path = tmp.name

        try:
            writer.write_excel(output_path)

            df = pd.read_excel(output_path, sheet_name="UNIT_NOTICE_LIST")

            # Verify exact column order
            assert list(df.columns) == writer.NOTICE_COLUMNS

        finally:
            Path(output_path).unlink()

    def test_summary_statistics(self):
        """Test summary statistics."""
        writer = ExcelWriter()

        # Add diverse data
        writer.add_unit_row(
            owner_name="Owner 1",
            mailing_address="Address 1",
            tract_id="1",
            legal_description="Legal 1",
            lease_status="UMI",
            ownership_type="MINERAL"
        )

        writer.add_unit_row(
            owner_name="Owner 2",
            mailing_address="Address 2",
            tract_id="2",
            legal_description="Legal 2",
            lease_status="ROY",
            ownership_type="MINERAL"
        )

        writer.add_offset_row(
            owner_name="Owner 3",
            mailing_address="Address 3",
            tract_id="3",
            legal_description="Legal 3",
            lease_status="WI",
            ownership_type="WORKING_INTEREST",
            distance_to_unit_miles=0.2
        )

        summary = writer.get_summary()

        assert summary["total_unit_rows"] == 2
        assert summary["total_offset_rows"] == 1
        assert summary["total_rows"] == 3
        assert summary["unique_owners"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
