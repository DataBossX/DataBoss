"""
DataBossX Title & OCR Orchestrator
Manages OCR workflows for title documents and lease abstracts.
Scans for PDFs, coordinates processing, and structures extracted data.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class DocumentInfo:
    """
    Represents information about a scanned document.
    """

    def __init__(self, file_path: str, file_name: str, file_size: int,
                 modified_date: str, document_type: Optional[str] = None,
                 processed: bool = False, processed_date: Optional[str] = None):
        """
        Initialize DocumentInfo.

        Args:
            file_path: Full path to document
            file_name: File name
            file_size: Size in bytes
            modified_date: Last modified date
            document_type: Type of document (Title, Lease, Abstract, etc.)
            processed: Whether document has been processed
            processed_date: When it was processed
        """
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.modified_date = modified_date
        self.document_type = document_type
        self.processed = processed
        self.processed_date = processed_date

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'modified_date': self.modified_date,
            'document_type': self.document_type,
            'processed': self.processed,
            'processed_date': self.processed_date,
        }


class ExtractedData:
    """
    Represents extracted data from a document.
    """

    def __init__(self, document_path: str, document_type: str = "Unknown",
                 grantor: str = "", grantee: str = "", book_page: str = "",
                 recorded_date: str = "", legal_description: str = "",
                 section_township_range: str = "", county: str = "",
                 state: str = "Oklahoma", additional_data: Optional[Dict] = None):
        """
        Initialize ExtractedData.

        Args:
            document_path: Source document path
            document_type: Type of document
            grantor: Grantor name
            grantee: Grantee name
            book_page: Book and page reference
            recorded_date: Recording date
            legal_description: Legal description
            section_township_range: Section, Township, Range
            county: County name
            state: State name
            additional_data: Additional extracted fields
        """
        self.document_path = document_path
        self.document_type = document_type
        self.grantor = grantor
        self.grantee = grantee
        self.book_page = book_page
        self.recorded_date = recorded_date
        self.legal_description = legal_description
        self.section_township_range = section_township_range
        self.county = county
        self.state = state
        self.additional_data = additional_data or {}
        self.extracted_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'document_path': self.document_path,
            'document_type': self.document_type,
            'grantor': self.grantor,
            'grantee': self.grantee,
            'book_page': self.book_page,
            'recorded_date': self.recorded_date,
            'legal_description': self.legal_description,
            'section_township_range': self.section_township_range,
            'county': self.county,
            'state': self.state,
            'additional_data': self.additional_data,
            'extracted_at': self.extracted_at,
        }


class TitleOCROrchestrator:
    """
    Orchestrates OCR operations for title documents.
    """

    def __init__(self, input_dirs: Optional[List[str]] = None,
                 output_dir: str = "output",
                 supported_formats: Optional[List[str]] = None):
        """
        Initialize the orchestrator.

        Args:
            input_dirs: List of directories to scan
            output_dir: Directory for output files
            supported_formats: List of supported file extensions
        """
        self.input_dirs = input_dirs or ["input", "penterra_files"]
        self.output_dir = output_dir
        self.supported_formats = supported_formats or [".pdf", ".PDF"]

        # Create output directory
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def scan_for_documents(self) -> List[DocumentInfo]:
        """
        Scan input directories for documents.

        Returns:
            List of DocumentInfo objects
        """
        documents = []

        for input_dir in self.input_dirs:
            if not os.path.exists(input_dir):
                logger.warning(f"Input directory does not exist: {input_dir}")
                continue

            try:
                for root, _, files in os.walk(input_dir):
                    for file_name in files:
                        # Check if file has supported extension
                        if any(file_name.endswith(ext) for ext in self.supported_formats):
                            file_path = os.path.join(root, file_name)

                            # Get file info
                            stats = os.stat(file_path)
                            modified_date = datetime.fromtimestamp(stats.st_mtime).isoformat()

                            doc_info = DocumentInfo(
                                file_path=file_path,
                                file_name=file_name,
                                file_size=stats.st_size,
                                modified_date=modified_date,
                                document_type=self._guess_document_type(file_name)
                            )

                            documents.append(doc_info)

                logger.info(f"Scanned {input_dir}: found {len(documents)} documents")

            except Exception as e:
                logger.error(f"Error scanning directory {input_dir}: {e}")

        return documents

    def _guess_document_type(self, file_name: str) -> str:
        """
        Guess document type from filename.

        Args:
            file_name: Name of the file

        Returns:
            Guessed document type
        """
        file_lower = file_name.lower()

        if any(keyword in file_lower for keyword in ['lease', 'oil', 'gas']):
            return "Lease"
        elif any(keyword in file_lower for keyword in ['abstract', 'title']):
            return "Title Abstract"
        elif any(keyword in file_lower for keyword in ['deed', 'warranty']):
            return "Deed"
        elif any(keyword in file_lower for keyword in ['mineral', 'royalty']):
            return "Mineral Deed"
        else:
            return "Unknown"

    def run_ocr_mutation_tournament(self, document_path: str,
                                   use_llm: bool = True) -> Dict[str, Any]:
        """
        Run OCR mutation tournament on a document.
        This is a placeholder for actual OCR processing.

        Args:
            document_path: Path to document
            use_llm: Whether to use LLM for enhancement

        Returns:
            Dictionary with results
        """
        try:
            logger.info(f"Running OCR tournament on: {document_path}")

            # Placeholder for actual OCR processing
            # In production, this would:
            # 1. Extract text with multiple OCR engines
            # 2. Compare results (tournament)
            # 3. Use LLM to pick best results and fill gaps
            # 4. Structure the data

            result = {
                'success': True,
                'document_path': document_path,
                'method': 'ocr_tournament',
                'text_extracted': True,
                'confidence': 0.85,
                'message': 'OCR tournament completed (simulated)',
                'note': 'In production, would use multiple OCR engines and LLM enhancement'
            }

            return result

        except Exception as e:
            logger.error(f"Error in OCR tournament: {e}")
            return {'success': False, 'error': str(e)}

    def parse_lease_abstract(self, document_path: str,
                           use_llm: bool = True) -> Optional[ExtractedData]:
        """
        Parse a lease or abstract document and extract structured data.

        Args:
            document_path: Path to document
            use_llm: Whether to use LLM for parsing

        Returns:
            ExtractedData object or None
        """
        try:
            logger.info(f"Parsing lease abstract: {document_path}")

            # Placeholder for actual parsing
            # In production, this would:
            # 1. Run OCR to get text
            # 2. Use LLM to extract structured fields
            # 3. Validate and clean data

            # Simulated extracted data
            extracted = ExtractedData(
                document_path=document_path,
                document_type=self._guess_document_type(os.path.basename(document_path)),
                grantor="[Simulated - Would extract from document]",
                grantee="[Simulated - Would extract from document]",
                book_page="[Book XXX, Page YYY]",
                recorded_date="[YYYY-MM-DD]",
                legal_description="[Full legal description would be extracted here]",
                section_township_range="[S-T-R]",
                county="[County Name]",
                state="Oklahoma",
                additional_data={
                    'processing_method': 'llm_parsing' if use_llm else 'basic_ocr',
                    'confidence': 0.80,
                    'note': 'Simulated extraction - production would use actual OCR + LLM'
                }
            )

            return extracted

        except Exception as e:
            logger.error(f"Error parsing lease abstract: {e}")
            return None

    def process_document(self, document_path: str, use_llm: bool = True) -> Dict[str, Any]:
        """
        Process a document end-to-end.

        Args:
            document_path: Path to document
            use_llm: Whether to use LLM

        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Processing document: {document_path}")

            # Run OCR
            ocr_result = self.run_ocr_mutation_tournament(document_path, use_llm)

            if not ocr_result.get('success'):
                return ocr_result

            # Parse and extract data
            extracted_data = self.parse_lease_abstract(document_path, use_llm)

            if not extracted_data:
                return {'success': False, 'error': 'Failed to extract data'}

            # Save results
            output_path = self._save_extracted_data(extracted_data)

            return {
                'success': True,
                'document_path': document_path,
                'extracted_data': extracted_data.to_dict(),
                'output_path': output_path,
                'message': 'Document processed successfully'
            }

        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return {'success': False, 'error': str(e)}

    def _save_extracted_data(self, extracted_data: ExtractedData) -> str:
        """
        Save extracted data to JSON file.

        Args:
            extracted_data: ExtractedData object

        Returns:
            Path to saved file
        """
        try:
            # Create output filename
            source_name = Path(extracted_data.document_path).stem
            output_filename = f"{source_name}_extracted.json"
            output_path = os.path.join(self.output_dir, output_filename)

            # Save to JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(extracted_data.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Extracted data saved to: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error saving extracted data: {e}")
            raise

    def batch_process(self, document_paths: List[str],
                     use_llm: bool = True) -> List[Dict[str, Any]]:
        """
        Process multiple documents in batch.

        Args:
            document_paths: List of document paths
            use_llm: Whether to use LLM

        Returns:
            List of processing results
        """
        results = []

        for doc_path in document_paths:
            result = self.process_document(doc_path, use_llm)
            results.append(result)

        successful = sum(1 for r in results if r.get('success'))
        logger.info(f"Batch processing complete: {successful}/{len(results)} successful")

        return results

    def get_processing_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary of processing results.

        Args:
            results: List of processing results

        Returns:
            Summary dictionary
        """
        total = len(results)
        successful = sum(1 for r in results if r.get('success'))
        failed = total - successful

        summary = {
            'total_processed': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }

        return summary


# Convenience functions
def quick_scan_pdfs(directories: Optional[List[str]] = None) -> List[DocumentInfo]:
    """
    Quickly scan for PDF documents.

    Args:
        directories: Directories to scan

    Returns:
        List of found documents
    """
    orchestrator = TitleOCROrchestrator(input_dirs=directories)
    return orchestrator.scan_for_documents()


def quick_process_document(document_path: str, use_llm: bool = True) -> Dict[str, Any]:
    """
    Quickly process a single document.

    Args:
        document_path: Path to document
        use_llm: Whether to use LLM

    Returns:
        Processing result
    """
    orchestrator = TitleOCROrchestrator()
    return orchestrator.process_document(document_path, use_llm)


if __name__ == "__main__":
    # Test the orchestrator
    print("Testing TitleOCROrchestrator...")

    orchestrator = TitleOCROrchestrator()

    # Scan for documents
    print("\nScanning for documents...")
    documents = orchestrator.scan_for_documents()
    print(f"Found {len(documents)} documents")

    if documents:
        for doc in documents[:5]:  # Show first 5
            print(f"  • {doc.file_name} ({doc.file_size} bytes) - {doc.document_type}")

    print("\nNote: This is a test run with simulated OCR processing.")
    print("In production, actual OCR engines and LLM would be used.")
