"""
Spreadsheet ingestion module.
Reads XLSX/CSV files with tract and owner information.
"""

import logging
from typing import List, Dict, Optional, Union
import pandas as pd
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SpreadsheetTract:
    """Tract information from spreadsheet."""
    tract_id: str
    legal_description: str
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    owner_name: Optional[str] = None
    ownership_type: Optional[str] = None
    interest: Optional[str] = None
    row_number: int = 0
    source_file: str = ""


class SpreadsheetIngestor:
    """Ingests tract and owner information from spreadsheets."""

    # Common column name variations
    TRACT_ID_COLUMNS = ["tract_id", "tract", "tract_no", "tract_number", "id"]
    LEGAL_DESC_COLUMNS = ["legal", "legal_description", "description", "str", "location"]
    GROSS_ACRES_COLUMNS = ["gross_acres", "gross", "acres", "total_acres"]
    NET_ACRES_COLUMNS = ["net_acres", "net", "nma"]
    OWNER_NAME_COLUMNS = ["owner", "owner_name", "name", "lessor", "mineral_owner"]
    OWNERSHIP_TYPE_COLUMNS = ["type", "ownership_type", "interest_type", "owner_type"]
    INTEREST_COLUMNS = ["interest", "decimal_interest", "fraction", "share"]

    def __init__(self):
        """Initialize spreadsheet ingestor."""
        self.data: Optional[pd.DataFrame] = None
        self.tracts: List[SpreadsheetTract] = []

    def read_file(self, file_path: str) -> Dict:
        """
        Read spreadsheet file (XLSX or CSV).

        Args:
            file_path: Path to file

        Returns:
            Dictionary with status and data
        """
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return {"error": "File not found"}

        try:
            # Detect file type and read
            if path.suffix.lower() in ['.xlsx', '.xls']:
                self.data = pd.read_excel(file_path)
                logger.info(f"Read Excel file: {path.name}")

            elif path.suffix.lower() == '.csv':
                # Try different encodings
                for encoding in ['utf-8', 'latin1', 'cp1252']:
                    try:
                        self.data = pd.read_csv(file_path, encoding=encoding)
                        logger.info(f"Read CSV file with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    return {"error": "Failed to read CSV with any encoding"}

            else:
                return {"error": f"Unsupported file type: {path.suffix}"}

            # Extract tracts
            self.tracts = self._extract_tracts(file_path)

            return {
                "success": True,
                "rows": len(self.data),
                "columns": list(self.data.columns),
                "tracts_extracted": len(self.tracts)
            }

        except Exception as e:
            logger.error(f"Failed to read spreadsheet: {e}")
            return {"error": str(e)}

    def _find_column(self, possible_names: List[str]) -> Optional[str]:
        """
        Find column name from list of possibilities.

        Args:
            possible_names: List of possible column names

        Returns:
            Actual column name or None
        """
        if self.data is None:
            return None

        # Convert all column names to lowercase for comparison
        columns_lower = {col.lower(): col for col in self.data.columns}

        for name in possible_names:
            if name.lower() in columns_lower:
                return columns_lower[name.lower()]

        return None

    def _extract_tracts(self, source_file: str) -> List[SpreadsheetTract]:
        """
        Extract tracts from loaded dataframe.

        Args:
            source_file: Source file path

        Returns:
            List of SpreadsheetTract objects
        """
        if self.data is None:
            return []

        tracts = []

        # Find column mappings
        tract_id_col = self._find_column(self.TRACT_ID_COLUMNS)
        legal_col = self._find_column(self.LEGAL_DESC_COLUMNS)
        gross_col = self._find_column(self.GROSS_ACRES_COLUMNS)
        net_col = self._find_column(self.NET_ACRES_COLUMNS)
        owner_col = self._find_column(self.OWNER_NAME_COLUMNS)
        type_col = self._find_column(self.OWNERSHIP_TYPE_COLUMNS)
        interest_col = self._find_column(self.INTEREST_COLUMNS)

        logger.info(f"Column mapping: tract_id={tract_id_col}, legal={legal_col}, "
                   f"gross={gross_col}, net={net_col}, owner={owner_col}")

        # Process each row
        for idx, row in self.data.iterrows():
            # Skip if no legal description
            if legal_col and pd.notna(row.get(legal_col)):
                legal_desc = str(row[legal_col]).strip()
            else:
                continue

            # Generate tract ID if not present
            if tract_id_col and pd.notna(row.get(tract_id_col)):
                tract_id = str(row[tract_id_col]).strip()
            else:
                tract_id = f"TRACT_{idx + 1}"

            # Parse numeric fields
            gross_acres = self._safe_float(row.get(gross_col)) if gross_col else None
            net_acres = self._safe_float(row.get(net_col)) if net_col else None

            # Parse text fields
            owner_name = str(row[owner_col]).strip() if owner_col and pd.notna(row.get(owner_col)) else None
            ownership_type = str(row[type_col]).strip() if type_col and pd.notna(row.get(type_col)) else None
            interest = str(row[interest_col]).strip() if interest_col and pd.notna(row.get(interest_col)) else None

            tract = SpreadsheetTract(
                tract_id=tract_id,
                legal_description=legal_desc,
                gross_acres=gross_acres,
                net_acres=net_acres,
                owner_name=owner_name,
                ownership_type=ownership_type,
                interest=interest,
                row_number=idx + 2,  # Excel row number (1-indexed + header)
                source_file=source_file
            )

            tracts.append(tract)

        logger.info(f"Extracted {len(tracts)} tracts from spreadsheet")
        return tracts

    def _safe_float(self, value) -> Optional[float]:
        """
        Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value or None
        """
        if pd.isna(value):
            return None

        try:
            # Remove commas if present
            if isinstance(value, str):
                value = value.replace(",", "")
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_summary(self) -> Dict:
        """
        Get summary of spreadsheet data.

        Returns:
            Summary dictionary
        """
        if self.data is None:
            return {"error": "No data loaded"}

        return {
            "total_rows": len(self.data),
            "total_columns": len(self.data.columns),
            "columns": list(self.data.columns),
            "tracts_extracted": len(self.tracts),
            "has_owner_data": any(t.owner_name for t in self.tracts),
            "has_acreage_data": any(t.gross_acres or t.net_acres for t in self.tracts)
        }

    def validate_data(self) -> Dict:
        """
        Validate spreadsheet data.

        Returns:
            Validation results
        """
        if not self.tracts:
            return {
                "valid": False,
                "errors": ["No tracts extracted"],
                "warnings": []
            }

        errors = []
        warnings = []

        # Check for required fields
        missing_legal = sum(1 for t in self.tracts if not t.legal_description)
        if missing_legal > 0:
            errors.append(f"{missing_legal} tracts missing legal description")

        # Check for duplicate tract IDs
        tract_ids = [t.tract_id for t in self.tracts]
        duplicates = len(tract_ids) - len(set(tract_ids))
        if duplicates > 0:
            warnings.append(f"{duplicates} duplicate tract IDs found")

        # Check for missing acreage
        missing_acres = sum(1 for t in self.tracts if not t.gross_acres and not t.net_acres)
        if missing_acres > 0:
            warnings.append(f"{missing_acres} tracts missing acreage data")

        # Check for missing owner data
        missing_owner = sum(1 for t in self.tracts if not t.owner_name)
        if missing_owner == len(self.tracts):
            warnings.append("No owner data found in spreadsheet")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_tracts": len(self.tracts)
        }
