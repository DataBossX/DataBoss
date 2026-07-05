"""File inventory system for scanning and cataloging source documents."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from .models import SourceDocument
from .utils import format_file_size, detect_file_relevance, is_likely_runsheet, is_likely_template


class InventoryScanner:
    """Scans directories and catalogs relevant files."""
    
    # File extensions to scan
    RELEVANT_EXTENSIONS = {
        '.xlsx', '.xls', '.csv',  # Spreadsheets
        '.docx', '.doc',  # Word documents
        '.pdf',  # PDFs
        '.txt', '.md',  # Text files
        '.json',  # JSON data
    }
    
    def __init__(self, logger):
        """Initialize inventory scanner.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.documents: List[SourceDocument] = []
    
    def scan_directory(self, directory: Path, recursive: bool = True) -> List[SourceDocument]:
        """Scan a directory for relevant files.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            
        Returns:
            List of discovered source documents
        """
        if not directory.exists():
            self.logger.warning(f"Directory does not exist: {directory}")
            return []
        
        self.logger.info(f"Scanning directory: {directory}")
        discovered = []
        
        pattern = "**/*" if recursive else "*"
        for path in directory.glob(pattern):
            if not path.is_file():
                continue
            
            # Check if extension is relevant
            if path.suffix.lower() not in self.RELEVANT_EXTENSIONS:
                continue
            
            # Skip temporary files
            if path.name.startswith('~$') or path.name.startswith('.~'):
                continue
            
            # Create source document
            doc = self._create_source_document(path)
            discovered.append(doc)
            self.logger.debug(f"Found: {path.name} ({doc.relevance})")
        
        self.logger.info(f"Discovered {len(discovered)} relevant files")
        return discovered
    
    def _create_source_document(self, path: Path) -> SourceDocument:
        """Create a SourceDocument from a file path.
        
        Args:
            path: File path
            
        Returns:
            SourceDocument instance
        """
        stat = path.stat()
        
        doc = SourceDocument(
            path=path,
            file_type=path.suffix.lower(),
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            relevance=detect_file_relevance(path)
        )
        
        # Add warnings for specific cases
        if doc.size == 0:
            doc.warnings.append("File is empty")
        
        if doc.size > 50 * 1024 * 1024:  # > 50 MB
            doc.warnings.append("Large file - may take time to process")
        
        if path.suffix.lower() == '.pdf':
            doc.warnings.append("PDF - may require OCR if image-based")
        
        return doc
    
    def scan_multiple(self, directories: List[Path]) -> List[SourceDocument]:
        """Scan multiple directories.
        
        Args:
            directories: List of directories to scan
            
        Returns:
            Combined list of source documents
        """
        all_docs = []
        for directory in directories:
            docs = self.scan_directory(directory)
            all_docs.extend(docs)
        
        # Remove duplicates based on path
        seen_paths = set()
        unique_docs = []
        for doc in all_docs:
            if doc.path not in seen_paths:
                seen_paths.add(doc.path)
                unique_docs.append(doc)
        
        self.documents = unique_docs
        return unique_docs
    
    def categorize_documents(self) -> Dict[str, List[SourceDocument]]:
        """Categorize documents by type.
        
        Returns:
            Dictionary mapping category to list of documents
        """
        categories = {
            "runsheets": [],
            "templates": [],
            "ownership_reports": [],
            "deeds": [],
            "leases": [],
            "other_spreadsheets": [],
            "other_documents": [],
            "other_pdfs": [],
        }
        
        for doc in self.documents:
            name_lower = doc.path.name.lower()
            
            if is_likely_runsheet(doc.path):
                categories["runsheets"].append(doc)
            elif is_likely_template(doc.path):
                categories["templates"].append(doc)
            elif 'ownership' in name_lower or 'title' in name_lower:
                categories["ownership_reports"].append(doc)
            elif 'deed' in name_lower:
                categories["deeds"].append(doc)
            elif 'lease' in name_lower:
                categories["leases"].append(doc)
            elif doc.file_type in ['.xlsx', '.xls', '.csv']:
                categories["other_spreadsheets"].append(doc)
            elif doc.file_type == '.pdf':
                categories["other_pdfs"].append(doc)
            else:
                categories["other_documents"].append(doc)
        
        return categories
    
    def generate_inventory_report(self, output_path: Path, report_date: str) -> None:
        """Generate inventory report in markdown and JSON.
        
        Args:
            output_path: Directory to write reports
            report_date: Report date string
        """
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate markdown report
        md_path = output_path / f"system_inventory_{report_date}.md"
        self._generate_markdown_report(md_path, report_date)
        
        # Generate JSON report
        json_path = output_path / f"system_inventory_{report_date}.json"
        self._generate_json_report(json_path, report_date)
        
        self.logger.info(f"Inventory reports generated:")
        self.logger.info(f"  Markdown: {md_path}")
        self.logger.info(f"  JSON: {json_path}")
    
    def _generate_markdown_report(self, output_path: Path, report_date: str) -> None:
        """Generate markdown inventory report.
        
        Args:
            output_path: Output file path
            report_date: Report date string
        """
        categories = self.categorize_documents()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Horizon System Inventory\n\n")
            f.write(f"**Date:** {report_date}\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- **Total Files:** {len(self.documents)}\n")
            for category, docs in categories.items():
                if docs:
                    f.write(f"- **{category.replace('_', ' ').title()}:** {len(docs)}\n")
            f.write("\n")
            
            # Detailed listings by category
            for category, docs in categories.items():
                if not docs:
                    continue
                
                f.write(f"## {category.replace('_', ' ').title()}\n\n")
                
                for doc in docs:
                    f.write(f"### {doc.path.name}\n\n")
                    f.write(f"- **Path:** `{doc.path}`\n")
                    f.write(f"- **Type:** {doc.file_type}\n")
                    f.write(f"- **Size:** {format_file_size(doc.size)}\n")
                    f.write(f"- **Modified:** {doc.modified_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"- **Relevance:** {doc.relevance}\n")
                    
                    if doc.warnings:
                        f.write(f"- **Warnings:**\n")
                        for warning in doc.warnings:
                            f.write(f"  - ⚠️ {warning}\n")
                    
                    f.write("\n")
            
            # Warnings summary
            all_warnings = [doc for doc in self.documents if doc.warnings]
            if all_warnings:
                f.write("## Files with Warnings\n\n")
                for doc in all_warnings:
                    f.write(f"- **{doc.path.name}**\n")
                    for warning in doc.warnings:
                        f.write(f"  - {warning}\n")
                f.write("\n")
    
    def _generate_json_report(self, output_path: Path, report_date: str) -> None:
        """Generate JSON inventory report.
        
        Args:
            output_path: Output file path
            report_date: Report date string
        """
        categories = self.categorize_documents()
        
        report_data = {
            "report_date": report_date,
            "generated_at": datetime.now().isoformat(),
            "total_files": len(self.documents),
            "categories": {
                category: len(docs)
                for category, docs in categories.items()
            },
            "documents": [doc.to_dict() for doc in self.documents],
            "categorized": {
                category: [doc.to_dict() for doc in docs]
                for category, docs in categories.items()
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)
