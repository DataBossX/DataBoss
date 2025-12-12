"""
PDF ingestion module.
Reads unit maps, plats, and COGCC/RRC exhibits.
Extracts tract descriptions and legal information.
"""

import logging
from typing import List, Dict, Optional, Tuple
import re
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# PDF libraries - PyPDF2 for basic extraction, pdfplumber for tables
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 not installed, PDF text extraction limited")
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    logger.warning("pdfplumber not installed, PDF table extraction limited")
    PDFPLUMBER_AVAILABLE = False


@dataclass
class PDFTractInfo:
    """Information extracted from PDF."""
    tract_id: str
    legal_description: str
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    page_number: int = 1
    confidence_score: float = 0.0
    source_file: str = ""


class PDFIngestor:
    """Ingests tract information from PDF files."""

    def __init__(self):
        """Initialize PDF ingestor."""
        self.tracts: List[PDFTractInfo] = []

    def read_pdf(self, file_path: str) -> Dict:
        """
        Read PDF file and extract information.

        Args:
            file_path: Path to PDF file

        Returns:
            Dictionary with extracted data
        """
        if not PYPDF2_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            logger.error("No PDF library available")
            return {"error": "PDF libraries not installed"}

        try:
            # Try pdfplumber first (better table extraction)
            if PDFPLUMBER_AVAILABLE:
                return self._read_with_pdfplumber(file_path)
            else:
                return self._read_with_pypdf2(file_path)

        except Exception as e:
            logger.error(f"Failed to read PDF {file_path}: {e}")
            return {"error": str(e)}

    def _read_with_pdfplumber(self, file_path: str) -> Dict:
        """Read PDF using pdfplumber."""
        import pdfplumber

        result = {
            "metadata": {},
            "text": "",
            "tables": [],
            "tracts": []
        }

        try:
            with pdfplumber.open(file_path) as pdf:
                # Extract metadata
                result["metadata"] = pdf.metadata or {}

                # Process each page
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text
                    text = page.extract_text() or ""
                    result["text"] += f"\n--- Page {page_num} ---\n{text}"

                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            result["tables"].append({
                                "page": page_num,
                                "data": table
                            })

                    # Try to extract tracts from this page
                    tracts = self._extract_tracts_from_text(text, page_num, file_path)
                    result["tracts"].extend(tracts)

            logger.info(f"Extracted {len(result['tracts'])} tracts from PDF")
            return result

        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return {"error": str(e)}

    def _read_with_pypdf2(self, file_path: str) -> Dict:
        """Read PDF using PyPDF2 (fallback)."""
        import PyPDF2

        result = {
            "metadata": {},
            "text": "",
            "tracts": []
        }

        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)

                # Extract metadata
                if reader.metadata:
                    result["metadata"] = dict(reader.metadata)

                # Extract text from all pages
                for page_num, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    result["text"] += f"\n--- Page {page_num} ---\n{text}"

                    # Try to extract tracts
                    tracts = self._extract_tracts_from_text(text, page_num, file_path)
                    result["tracts"].extend(tracts)

            return result

        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            return {"error": str(e)}

    def _extract_tracts_from_text(
        self,
        text: str,
        page_number: int,
        source_file: str
    ) -> List[PDFTractInfo]:
        """
        Extract tract information from text.

        Looks for common patterns:
        - Township/Range/Section (T1N R68W Sec 16)
        - Tract numbers (Tract 1, Tract A, etc.)
        - Acreage information

        Args:
            text: Text to parse
            page_number: Page number
            source_file: Source file path

        Returns:
            List of extracted tracts
        """
        tracts = []

        # Pattern for PLSS legal descriptions
        plss_pattern = r'(T\s*\d+[NS]\s+R\s*\d+[EW]\s+Sec\.?\s+\d+[^.]*)'

        matches = re.finditer(plss_pattern, text, re.IGNORECASE)

        for match_num, match in enumerate(matches, start=1):
            legal_desc = match.group(1).strip()

            # Try to find associated acreage
            # Look for patterns like "160 acres", "40.0 ac", etc.
            context = text[max(0, match.start() - 100):min(len(text), match.end() + 100)]
            acres = self._extract_acreage(context)

            tract_id = f"PDF_TRACT_{page_number}_{match_num}"

            tract = PDFTractInfo(
                tract_id=tract_id,
                legal_description=legal_desc,
                gross_acres=acres,
                page_number=page_number,
                confidence_score=70.0,
                source_file=source_file
            )

            tracts.append(tract)
            logger.debug(f"Extracted tract: {legal_desc}")

        return tracts

    def _extract_acreage(self, text: str) -> Optional[float]:
        """
        Extract acreage from text.

        Args:
            text: Text to parse

        Returns:
            Acreage as float or None
        """
        # Pattern for acreage: "160 acres", "40.5 ac", etc.
        acre_pattern = r'(\d+\.?\d*)\s*(?:acres?|ac\.?|Acres?|AC\.?)'

        match = re.search(acre_pattern, text, re.IGNORECASE)

        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        return None

    def extract_unit_info(self, text: str) -> Dict:
        """
        Extract unit/DSU information from PDF text.

        Looks for:
        - Unit name
        - County
        - State
        - Operator

        Args:
            text: PDF text

        Returns:
            Dictionary with unit information
        """
        info = {
            "unit_name": None,
            "county": None,
            "state": None,
            "operator": None
        }

        # Common patterns
        unit_patterns = [
            r'(?:Unit|DSU|Drilling\s+Spacing\s+Unit)[:\s]+([A-Z0-9\s\-]+)',
            r'([A-Z][A-Za-z0-9\-\s]+(?:Unit|DSU))',
        ]

        for pattern in unit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info["unit_name"] = match.group(1).strip()
                break

        # County pattern
        county_match = re.search(r'([A-Z][a-z]+)\s+County', text)
        if county_match:
            info["county"] = county_match.group(1)

        # State pattern
        state_match = re.search(r',\s*([A-Z]{2})\s+\d{5}', text)  # State in address
        if state_match:
            info["state"] = state_match.group(1)

        # Operator pattern
        operator_match = re.search(r'(?:Operator|Applicant)[:\s]+([A-Z][A-Za-z0-9\s,\.]+)', text)
        if operator_match:
            info["operator"] = operator_match.group(1).strip()

        return info

    def extract_from_table(self, table_data: List[List[str]]) -> List[PDFTractInfo]:
        """
        Extract tracts from table data.

        Assumes table has columns like:
        Tract | Legal Description | Gross Acres | Net Acres

        Args:
            table_data: 2D list of table cells

        Returns:
            List of extracted tracts
        """
        tracts = []

        if not table_data or len(table_data) < 2:
            return tracts

        # Try to identify columns
        header = table_data[0]
        header_lower = [str(h).lower() if h else "" for h in header]

        # Find column indices
        tract_col = None
        legal_col = None
        gross_col = None
        net_col = None

        for i, h in enumerate(header_lower):
            if "tract" in h:
                tract_col = i
            elif "legal" in h or "description" in h:
                legal_col = i
            elif "gross" in h:
                gross_col = i
            elif "net" in h:
                net_col = i

        # Extract data rows
        for row_num, row in enumerate(table_data[1:], start=1):
            if len(row) <= max(filter(None, [tract_col, legal_col, gross_col, net_col]) or [0]):
                continue

            tract_id = row[tract_col] if tract_col is not None else f"TABLE_TRACT_{row_num}"
            legal_desc = row[legal_col] if legal_col is not None else ""

            gross_acres = None
            if gross_col is not None and row[gross_col]:
                try:
                    gross_acres = float(str(row[gross_col]).replace(",", ""))
                except ValueError:
                    pass

            net_acres = None
            if net_col is not None and row[net_col]:
                try:
                    net_acres = float(str(row[net_col]).replace(",", ""))
                except ValueError:
                    pass

            if legal_desc:
                tract = PDFTractInfo(
                    tract_id=str(tract_id),
                    legal_description=legal_desc,
                    gross_acres=gross_acres,
                    net_acres=net_acres,
                    confidence_score=85.0,
                    source_file="table"
                )
                tracts.append(tract)

        return tracts
