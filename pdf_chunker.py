"""
PDF Chunker Module for Legal Document Processing

Handles splitting large PDFs into manageable chunks for processing.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
import fitz  # PyMuPDF

logger = logging.getLogger("legal_extractor.pdf_chunker")

def split_pdf(pdf_path: str, output_dir: str, chunk_size: int = 5) -> List[str]:
    """
    Split a PDF into smaller chunks for easier processing.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save the chunk files
        chunk_size: Number of pages per chunk
        
    Returns:
        List of paths to the created PDF chunks
    """
    logger.info(f"Splitting PDF: {pdf_path} into chunks of {chunk_size} pages")
    
    os.makedirs(output_dir, exist_ok=True)
    
    pdf_name = Path(pdf_path).stem
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"PDF has {total_pages} pages")
        
        chunk_paths = []
        
        if total_pages == 0:
            logger.warning(f"PDF {pdf_path} has no pages")
            return [pdf_path]
            
        if total_pages <= chunk_size:
            logger.info(f"PDF {pdf_path} is small, no chunking needed")
            return [pdf_path]
        
        for start_page in range(0, total_pages, chunk_size):
            end_page = min(start_page + chunk_size - 1, total_pages - 1)
            
            chunk_doc = fitz.open()
            
            for page_num in range(start_page, end_page + 1):
                chunk_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            chunk_filename = f"{pdf_name}_chunk_{start_page+1}_{end_page+1}.pdf"
            chunk_path = os.path.join(output_dir, chunk_filename)
            chunk_doc.save(chunk_path)
            chunk_doc.close()
            
            chunk_paths.append(chunk_path)
            logger.info(f"Created chunk: {chunk_path}")
        
        return chunk_paths
        
    except Exception as e:
        logger.error(f"Error splitting PDF {pdf_path}: {str(e)}", exc_info=True)
        return [pdf_path]
