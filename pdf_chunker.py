"""
PDF chunking module for DataBoss
Handles splitting large PDFs into manageable chunks
"""

import os
import logging
import tempfile
from pathlib import Path
import fitz  # PyMuPDF
from typing import List, Optional

logger = logging.getLogger("legal_extractor.pdf_chunker")
logging.basicConfig(level=logging.INFO)

def split_pdf(pdf_path: str, output_dir: str, max_pages_per_chunk: int = 5) -> List[str]:
    """
    Split a PDF into smaller chunks for better processing
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save chunks
        max_pages_per_chunk: Maximum pages per chunk
        
    Returns:
        List of paths to chunked PDFs
    """
    logger.info(f"Splitting PDF: {pdf_path}")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"Total pages: {total_pages}")
        
        if total_pages == 0:
            logger.warning("PDF has no pages")
            return []
            
        if total_pages <= max_pages_per_chunk:
            logger.info(f"PDF is small ({total_pages} pages), no chunking needed")
            chunk_path = os.path.join(output_dir, os.path.basename(pdf_path))
            doc.save(chunk_path)
            doc.close()
            return [chunk_path]
        
        chunk_paths = []
        chunk_count = (total_pages + max_pages_per_chunk - 1) // max_pages_per_chunk
        
        for i in range(chunk_count):
            start_page = i * max_pages_per_chunk
            end_page = min((i + 1) * max_pages_per_chunk, total_pages)
            
            chunk_doc = fitz.open()
            for page_num in range(start_page, end_page):
                chunk_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            chunk_path = os.path.join(output_dir, f"{base_name}_chunk{i+1}.pdf")
            chunk_doc.save(chunk_path)
            chunk_doc.close()
            
            chunk_paths.append(chunk_path)
            logger.info(f"Created chunk {i+1}/{chunk_count}: {chunk_path}")
        
        doc.close()
        return chunk_paths
        
    except Exception as e:
        logger.error(f"Failed to split PDF: {str(e)}", exc_info=True)
        return []
