"""
DataBossX Title & OCR Orchestrator v9
Handles document scanning, OCR processing, and title abstract extraction
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import json

from config_databossx9 import get_config

# Configure logging
logger = logging.getLogger(__name__)


class TitleOCROrchestrator:
    """
    Orchestrates OCR processing and title abstract extraction.
    Scans input folders, processes documents, and extracts structured data.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize Title OCR Orchestrator.

        Args:
            db_path: Path to SQLite database
        """
        config = get_config()
        self.db_path = db_path or config.get('paths', 'database_path', 'databossx.db')
        self.input_folder = Path(config.get('paths', 'input_folder', 'input'))
        self.output_folder = Path(config.get('paths', 'output_folder', 'output'))
        self.penterra_folder = Path(config.get('paths', 'penterra_folder', 'penterra_docs'))
        self.supported_formats = config.get('ocr', 'supported_formats', ['.pdf', '.png', '.jpg'])

        # Ensure folders exist
        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.penterra_folder.mkdir(parents=True, exist_ok=True)

        logger.info("TitleOCROrchestrator initialized")

    def scan_for_documents(self, folder: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Scan folder for documents to process.

        Args:
            folder: Folder to scan (defaults to input_folder)

        Returns:
            List of document dictionaries
        """
        scan_folder = folder or self.input_folder
        documents = []

        try:
            for file_path in scan_folder.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                    doc_info = {
                        'path': str(file_path),
                        'filename': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        'extension': file_path.suffix.lower(),
                        'processed': self._is_document_processed(str(file_path))
                    }
                    documents.append(doc_info)

            logger.info(f"Scanned {scan_folder}: Found {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Error scanning documents: {e}")
            return []

    def _is_document_processed(self, file_path: str) -> bool:
        """
        Check if document has been processed.

        Args:
            file_path: Path to document

        Returns:
            True if processed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if file exists in documents table with completed status
            cursor.execute("""
                SELECT COUNT(*) FROM documents
                WHERE filename = ? AND status = 'completed'
            """, (Path(file_path).name,))

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"Error checking document status: {e}")
            return False

    def get_document_stats(self) -> Dict[str, Any]:
        """
        Get statistics about documents.

        Returns:
            Statistics dictionary
        """
        stats = {
            'input_folder': {
                'total': 0,
                'processed': 0,
                'unprocessed': 0
            },
            'penterra_folder': {
                'total': 0,
                'processed': 0,
                'unprocessed': 0
            },
            'total_processed': 0,
            'by_status': {}
        }

        try:
            # Scan input folder
            input_docs = self.scan_for_documents(self.input_folder)
            stats['input_folder']['total'] = len(input_docs)
            stats['input_folder']['processed'] = sum(1 for d in input_docs if d['processed'])
            stats['input_folder']['unprocessed'] = sum(1 for d in input_docs if not d['processed'])

            # Scan Penterra folder
            penterra_docs = self.scan_for_documents(self.penterra_folder)
            stats['penterra_folder']['total'] = len(penterra_docs)
            stats['penterra_folder']['processed'] = sum(1 for d in penterra_docs if d['processed'])
            stats['penterra_folder']['unprocessed'] = sum(1 for d in penterra_docs if not d['processed'])

            # Get database stats
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM documents")
            stats['total_processed'] = cursor.fetchone()[0]

            cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
            stats['by_status'] = dict(cursor.fetchall())

            conn.close()

            return stats

        except Exception as e:
            logger.error(f"Error getting document stats: {e}")
            return stats

    def extract_title_data(self, ocr_text: str) -> Dict[str, Any]:
        """
        Extract structured title data from OCR text.

        Args:
            ocr_text: Raw OCR text

        Returns:
            Extracted data dictionary
        """
        # This is a simplified extraction
        # In production, use LLM or advanced parsing
        extracted = {
            'document_type': self._extract_document_type(ocr_text),
            'grantor': self._extract_party(ocr_text, 'grantor'),
            'grantee': self._extract_party(ocr_text, 'grantee'),
            'book_page': self._extract_book_page(ocr_text),
            'date': self._extract_date(ocr_text),
            'legal_description': self._extract_legal_desc(ocr_text),
            'county': self._extract_county(ocr_text),
            'state': self._extract_state(ocr_text)
        }

        return extracted

    def _extract_document_type(self, text: str) -> str:
        """Extract document type from text"""
        doc_types = [
            'Deed', 'Mortgage', 'Lease', 'Release', 'Assignment',
            'Affidavit', 'Easement', 'Mineral Deed', 'Royalty Deed',
            'Quit Claim', 'Warranty Deed', 'Oil and Gas Lease'
        ]

        text_lower = text.lower()
        for doc_type in doc_types:
            if doc_type.lower() in text_lower:
                return doc_type

        return "Unknown"

    def _extract_party(self, text: str, party_type: str) -> str:
        """Extract grantor or grantee from text"""
        # Simplified extraction - use LLM for better results
        markers = {
            'grantor': ['grantor', 'from', 'seller'],
            'grantee': ['grantee', 'to', 'buyer', 'purchaser']
        }

        lines = text.split('\n')
        for i, line in enumerate(lines):
            if any(marker in line.lower() for marker in markers.get(party_type, [])):
                # Try to extract name from next line or same line
                if i + 1 < len(lines):
                    return lines[i + 1].strip()[:100]

        return "Not found"

    def _extract_book_page(self, text: str) -> str:
        """Extract book and page reference"""
        import re

        # Look for patterns like "Book 123 Page 456" or "Bk 123 Pg 456"
        patterns = [
            r'Book\s+(\d+)\s+Page\s+(\d+)',
            r'Bk\.?\s+(\d+)\s+Pg\.?\s+(\d+)',
            r'Volume\s+(\d+)\s+Page\s+(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"Book {match.group(1)} Page {match.group(2)}"

        return "Not found"

    def _extract_date(self, text: str) -> str:
        """Extract date from text"""
        import re

        # Look for date patterns
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'[A-Za-z]+\s+\d{1,2},\s+\d{4}'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return "Not found"

    def _extract_legal_desc(self, text: str) -> str:
        """Extract legal description"""
        # Look for common legal description markers
        markers = ['legal description', 'described as', 'lot', 'section', 'township', 'range']

        text_lower = text.lower()
        for marker in markers:
            if marker in text_lower:
                start_idx = text_lower.find(marker)
                # Extract up to 200 characters after marker
                return text[start_idx:start_idx + 200].strip()

        return "Not found"

    def _extract_county(self, text: str) -> str:
        """Extract county name"""
        # Look for "County" keyword
        import re

        pattern = r'([A-Z][a-z]+)\s+County'
        match = re.search(pattern, text)
        if match:
            return match.group(1)

        return "Unknown"

    def _extract_state(self, text: str) -> str:
        """Extract state"""
        states = ['Oklahoma', 'Texas', 'Kansas', 'Arkansas', 'Missouri']

        for state in states:
            if state.lower() in text.lower():
                return state

        return "Unknown"

    def process_document_with_llm(self, ocr_text: str, document_name: str) -> Dict[str, Any]:
        """
        Process document using LLM for better extraction.

        Args:
            ocr_text: OCR text
            document_name: Document filename

        Returns:
            Extracted data dictionary
        """
        try:
            # Try to use LLM for extraction
            from agents_manager9 import AgentsManager

            agents_mgr = AgentsManager()

            prompt = f"""
            Extract structured data from this title document:

            Document: {document_name}

            Text:
            {ocr_text[:2000]}  # Limit text size

            Please extract and return JSON with these fields:
            - document_type: Type of legal document
            - grantor: Party transferring property
            - grantee: Party receiving property
            - book_page: Book and page reference
            - date: Document date
            - legal_description: Legal property description
            - county: County name
            - state: State name

            Return only valid JSON.
            """

            task_id = agents_mgr.queue_task(
                "title_ocr_agent",
                f"Extract data from {document_name}",
                prompt,
                task_type="extraction"
            )

            # Process immediately
            agents_mgr.process_task(task_id)

            # Get result
            tasks = agents_mgr.get_agent_tasks("title_ocr_agent", status="completed", limit=1)
            if tasks and tasks[0]['id'] == task_id:
                result_text = tasks[0]['result']
                # Try to parse JSON from result
                try:
                    extracted_data = json.loads(result_text)
                    return extracted_data
                except:
                    # Fallback to basic extraction
                    pass

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")

        # Fallback to basic extraction
        return self.extract_title_data(ocr_text)

    def get_extraction_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent extraction results.

        Args:
            limit: Maximum number of results

        Returns:
            List of extraction result dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get documents with their OCR and LLM results
            cursor.execute("""
                SELECT
                    d.id,
                    d.filename,
                    d.status,
                    d.upload_time,
                    o.cleaned_text,
                    o.confidence_score,
                    l.analysis_result
                FROM documents d
                LEFT JOIN ocr_results o ON d.id = o.document_id
                LEFT JOIN llm_analysis l ON d.id = l.document_id
                WHERE d.status = 'completed'
                ORDER BY d.upload_time DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                result = {
                    'id': row[0],
                    'filename': row[1],
                    'status': row[2],
                    'upload_time': row[3],
                    'confidence_score': row[5] if row[5] else 0.0,
                }

                # Extract structured data
                if row[4]:  # OCR text available
                    result['extracted_data'] = self.extract_title_data(row[4])

                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error getting extraction results: {e}")
            return []

    def run_ocr_tournament(self, document_path: str) -> Dict[str, Any]:
        """
        Run OCR mutation tournament (use multiple OCR engines and compare).

        Args:
            document_path: Path to document

        Returns:
            Tournament results
        """
        logger.info(f"Running OCR tournament for {document_path}")

        # This is a placeholder for the OCR tournament feature
        # In production, this would run multiple OCR engines and compare results

        results = {
            'document': document_path,
            'engines_tested': ['tesseract', 'paddle_ocr', 'google_vision'],
            'winner': 'paddle_ocr',
            'best_confidence': 0.94,
            'processing_time': 2.5,
            'text_preview': "Sample OCR output from tournament winner..."
        }

        return results


if __name__ == "__main__":
    # Test the TitleOCROrchestrator
    orchestrator = TitleOCROrchestrator()

    # Get document stats
    stats = orchestrator.get_document_stats()
    print("Document Statistics:")
    print(json.dumps(stats, indent=2))

    # Scan for documents
    docs = orchestrator.scan_for_documents()
    print(f"\nFound {len(docs)} documents to process")
