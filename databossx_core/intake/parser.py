"""
Document parser for structured data files
"""

import io
import csv
from typing import Dict, List, Any
import pandas as pd


class DocumentParser:
    """
    Parser for structured data files (CSV, XLSX)
    """

    async def parse(self, file_type: str, content: bytes) -> Dict[str, Any]:
        """
        Parse structured data file

        Args:
            file_type: Type of file (csv, xlsx, xls)
            content: File content as bytes

        Returns:
            Parsed data as dictionary
        """
        if file_type == "csv":
            return await self.parse_csv(content)
        elif file_type in ["xlsx", "xls"]:
            return await self.parse_excel(content)
        else:
            raise ValueError(f"Unsupported file type for parsing: {file_type}")

    async def parse_csv(self, content: bytes) -> Dict[str, Any]:
        """
        Parse CSV file

        Args:
            content: CSV file content

        Returns:
            Dictionary with parsed data
        """
        try:
            # Decode content
            text = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))

            # Read rows
            rows = []
            headers = None
            for row in reader:
                if headers is None:
                    headers = list(row.keys())
                rows.append(row)

            return {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "format": "csv",
            }
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {str(e)}")

    async def parse_excel(self, content: bytes) -> Dict[str, Any]:
        """
        Parse Excel file

        Args:
            content: Excel file content

        Returns:
            Dictionary with parsed data
        """
        try:
            # Read Excel file
            df = pd.read_excel(io.BytesIO(content), sheet_name=None)

            # Process all sheets
            sheets = {}
            for sheet_name, sheet_df in df.items():
                sheets[sheet_name] = {
                    "headers": sheet_df.columns.tolist(),
                    "rows": sheet_df.to_dict("records"),
                    "row_count": len(sheet_df),
                }

            return {
                "sheets": sheets,
                "sheet_count": len(sheets),
                "format": "excel",
            }
        except Exception as e:
            raise ValueError(f"Failed to parse Excel: {str(e)}")
