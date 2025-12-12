"""
Excel output writer.
Creates XLSX with exactly two sheets:
1. UNIT_NOTICE_LIST
2. OFFSET_NOTICE_LIST

Format is exactly how landmen expect it - no junk, no extras.
"""

import logging
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ExcelWriter:
    """Writes notice lists to Excel format."""

    # Exact column order and names (non-negotiable)
    NOTICE_COLUMNS = [
        "OWNER_NAME",
        "MAILING_ADDRESS",
        "TRACT_ID",
        "LEGAL_DESCRIPTION",
        "GROSS_ACRES",
        "NET_ACRES",
        "LEASE_STATUS",  # UMI, ROY, or WI
        "OWNERSHIP_TYPE",  # MINERAL, LEASEHOLD, WORKING_INTEREST
        "INTEREST",
        "OFFSET_METHOD",  # polygon, centroid, str_grid
        "ADDRESS_SOURCE",
        "ADDRESS_DATE",
        "CONFIDENCE_SCORE",
        "DISTANCE_TO_UNIT_MILES",  # Only for offset tracts
        "EVIDENCE"  # JSON list of evidence records
    ]

    def __init__(self):
        """Initialize Excel writer."""
        self.unit_data: List[Dict] = []
        self.offset_data: List[Dict] = []

    def add_unit_row(
        self,
        owner_name: str,
        mailing_address: str,
        tract_id: str,
        legal_description: str,
        lease_status: str,
        ownership_type: str,
        gross_acres: Optional[float] = None,
        net_acres: Optional[float] = None,
        interest: Optional[str] = None,
        offset_method: str = "unknown",
        address_source: str = "unknown",
        address_date: Optional[datetime] = None,
        confidence_score: float = 0.0,
        evidence: Optional[List] = None
    ) -> None:
        """
        Add a row to UNIT_NOTICE_LIST.

        Args:
            owner_name: Owner name
            mailing_address: Full mailing address
            tract_id: Tract identifier
            legal_description: Legal description
            lease_status: UMI, ROY, or WI
            ownership_type: MINERAL, LEASEHOLD, or WORKING_INTEREST
            gross_acres: Gross acres
            net_acres: Net acres
            interest: Interest fraction or decimal
            address_source: Source of address
            address_date: Date of address source
            confidence_score: Confidence score (0-100)
        """
        import json

        row = {
            "OWNER_NAME": owner_name,
            "MAILING_ADDRESS": mailing_address,
            "TRACT_ID": tract_id,
            "LEGAL_DESCRIPTION": legal_description,
            "GROSS_ACRES": gross_acres,
            "NET_ACRES": net_acres,
            "LEASE_STATUS": lease_status,
            "OWNERSHIP_TYPE": ownership_type,
            "INTEREST": interest,
            "OFFSET_METHOD": offset_method,
            "ADDRESS_SOURCE": address_source,
            "ADDRESS_DATE": address_date.strftime("%Y-%m-%d") if address_date else "",
            "CONFIDENCE_SCORE": round(confidence_score, 1),
            "DISTANCE_TO_UNIT_MILES": "",  # Empty for unit tracts
            "EVIDENCE": json.dumps(evidence or [], indent=2)
        }

        self.unit_data.append(row)

    def add_offset_row(
        self,
        owner_name: str,
        mailing_address: str,
        tract_id: str,
        legal_description: str,
        lease_status: str,
        ownership_type: str,
        distance_to_unit_miles: Optional[float] = None,
        gross_acres: Optional[float] = None,
        net_acres: Optional[float] = None,
        interest: Optional[str] = None,
        offset_method: str = "unknown",
        address_source: str = "unknown",
        address_date: Optional[datetime] = None,
        confidence_score: float = 0.0,
        evidence: Optional[List] = None
    ) -> None:
        """
        Add a row to OFFSET_NOTICE_LIST.

        Same as add_unit_row but includes distance to unit.
        """
        import json

        row = {
            "OWNER_NAME": owner_name,
            "MAILING_ADDRESS": mailing_address,
            "TRACT_ID": tract_id,
            "LEGAL_DESCRIPTION": legal_description,
            "GROSS_ACRES": gross_acres,
            "NET_ACRES": net_acres,
            "LEASE_STATUS": lease_status,
            "OWNERSHIP_TYPE": ownership_type,
            "INTEREST": interest,
            "OFFSET_METHOD": offset_method,
            "ADDRESS_SOURCE": address_source,
            "ADDRESS_DATE": address_date.strftime("%Y-%m-%d") if address_date else "",
            "CONFIDENCE_SCORE": round(confidence_score, 1),
            "DISTANCE_TO_UNIT_MILES": round(distance_to_unit_miles, 2) if distance_to_unit_miles else "",
            "EVIDENCE": json.dumps(evidence or [], indent=2)
        }

        self.offset_data.append(row)

    def write_excel(self, output_path: str, unit_name: Optional[str] = None) -> bool:
        """
        Write Excel file with both sheets.

        Args:
            output_path: Path for output file
            unit_name: Optional unit name for filename

        Returns:
            True if successful
        """
        try:
            # Create DataFrames
            unit_df = pd.DataFrame(self.unit_data, columns=self.NOTICE_COLUMNS)
            offset_df = pd.DataFrame(self.offset_data, columns=self.NOTICE_COLUMNS)

            # Sort by owner name
            unit_df = unit_df.sort_values("OWNER_NAME", na_position='last')
            offset_df = offset_df.sort_values("OWNER_NAME", na_position='last')

            # Write to Excel with exact sheet names
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                unit_df.to_excel(writer, sheet_name="UNIT_NOTICE_LIST", index=False)
                offset_df.to_excel(writer, sheet_name="OFFSET_NOTICE_LIST", index=False)

                # Format worksheets
                self._format_worksheet(writer.sheets["UNIT_NOTICE_LIST"], len(unit_df))
                self._format_worksheet(writer.sheets["OFFSET_NOTICE_LIST"], len(offset_df))

            logger.info(f"Wrote Excel file: {output_path}")
            logger.info(f"  - UNIT_NOTICE_LIST: {len(unit_df)} rows")
            logger.info(f"  - OFFSET_NOTICE_LIST: {len(offset_df)} rows")

            return True

        except Exception as e:
            logger.error(f"Failed to write Excel file: {e}")
            return False

    def _format_worksheet(self, worksheet, num_rows: int) -> None:
        """
        Format worksheet for readability.

        Args:
            worksheet: openpyxl worksheet
            num_rows: Number of data rows
        """
        from openpyxl.styles import Font, Alignment, PatternFill

        # Header formatting
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")

        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Column widths
        column_widths = {
            "A": 30,  # OWNER_NAME
            "B": 40,  # MAILING_ADDRESS
            "C": 15,  # TRACT_ID
            "D": 50,  # LEGAL_DESCRIPTION
            "E": 12,  # GROSS_ACRES
            "F": 12,  # NET_ACRES
            "G": 12,  # LEASE_STATUS
            "H": 18,  # OWNERSHIP_TYPE
            "I": 12,  # INTEREST
            "J": 20,  # ADDRESS_SOURCE
            "K": 15,  # ADDRESS_DATE
            "L": 15,  # CONFIDENCE_SCORE
            "M": 18,  # DISTANCE_TO_UNIT_MILES
        }

        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width

        # Freeze header row
        worksheet.freeze_panes = "A2"

    def validate_output(self) -> Dict:
        """
        Validate output data before writing.

        Returns:
            Validation results
        """
        errors = []
        warnings = []

        # Check for empty output
        if not self.unit_data and not self.offset_data:
            errors.append("No data to write")

        # Check for required fields
        for row in self.unit_data + self.offset_data:
            if not row.get("OWNER_NAME"):
                warnings.append("Row missing OWNER_NAME")
            if not row.get("LEGAL_DESCRIPTION"):
                warnings.append("Row missing LEGAL_DESCRIPTION")
            if not row.get("LEASE_STATUS"):
                warnings.append("Row missing LEASE_STATUS")

        # Check lease status values
        valid_statuses = {"UMI", "ROY", "WI", "UNKNOWN"}
        for row in self.unit_data + self.offset_data:
            status = row.get("LEASE_STATUS", "").upper()
            if status and status not in valid_statuses:
                warnings.append(f"Invalid lease status: {status}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "unit_rows": len(self.unit_data),
            "offset_rows": len(self.offset_data)
        }

    def get_summary(self) -> Dict:
        """
        Get summary statistics for output.

        Returns:
            Summary dictionary
        """
        unit_df = pd.DataFrame(self.unit_data)
        offset_df = pd.DataFrame(self.offset_data)

        summary = {
            "total_unit_rows": len(self.unit_data),
            "total_offset_rows": len(self.offset_data),
            "total_rows": len(self.unit_data) + len(self.offset_data)
        }

        # Count by lease status
        if not unit_df.empty:
            summary["unit_by_status"] = unit_df["LEASE_STATUS"].value_counts().to_dict()
        if not offset_df.empty:
            summary["offset_by_status"] = offset_df["LEASE_STATUS"].value_counts().to_dict()

        # Count unique owners
        all_owners = set()
        if not unit_df.empty:
            all_owners.update(unit_df["OWNER_NAME"].dropna().unique())
        if not offset_df.empty:
            all_owners.update(offset_df["OWNER_NAME"].dropna().unique())

        summary["unique_owners"] = len(all_owners)

        return summary

    def clear(self) -> None:
        """Clear all data (for running multiple times)."""
        self.unit_data = []
        self.offset_data = []
