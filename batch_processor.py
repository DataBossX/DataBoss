
"""
Batch Processing Module for Legal Document Processing

Handles batch processing of multiple PDF documents with robust error handling.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from extractor import run_extraction

# Configure logging
logging.basicConfig(
    filename="batch_processor.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("legal_extractor.batch_processor")

def batch_process(input_dir: str, output_dir: str, skip_existing: bool = True, 
                 max_workers: int = 4, timeout: int = 300):
    """
    Process all PDF files in the input directory using run_extraction().
    
    Args:
        input_dir: Path to folder containing PDF files
        output_dir: Path to folder where results will be saved
        skip_existing: Skip PDFs already processed
        max_workers: Maximum number of parallel workers
        timeout: Maximum time in seconds for processing each PDF
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    input_path.mkdir(exist_ok=True)
    output_path.mkdir(exist_ok=True)

    pdf_files = list(input_path.glob("*.pdf"))
    total_files = len(pdf_files)
    logger.info(f"Found {total_files} PDF(s) to process")
    
    if total_files == 0:
        logger.warning(f"No PDF files found in {input_dir}")
        return []
    
    results = []
    failed = []
    skipped = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pdf = {}
        
        for pdf_file in pdf_files:
            doc_id = pdf_file.stem
            json_out = output_path / f"{doc_id}.json"

            if skip_existing and json_out.exists():
                logger.info(f"Skipping already processed file: {pdf_file.name}")
                skipped.append(pdf_file.name)
                continue

            logger.info(f"Submitting file for processing: {pdf_file.name}")
            future = executor.submit(
                process_file_with_timeout, 
                pdf_file.name, 
                str(input_path), 
                str(output_path),
                timeout
            )
            future_to_pdf[future] = pdf_file.name
        
        for future in as_completed(future_to_pdf):
            pdf_name = future_to_pdf[future]
            try:
                result = future.result()
                results.append(result)
                
                if result.get("success"):
                    logger.info(f"✔ Success: {pdf_name} in {result['processing_time']}")
                else:
                    logger.warning(f"❌ Failed: {pdf_name} - {result.get('error', 'Unknown error')}")
                    failed.append(pdf_name)
                    
            except Exception as e:
                logger.error(f"Unhandled exception while processing {pdf_name}: {str(e)}", exc_info=True)
                failed.append(pdf_name)
    
    completion_rate = (len(results) - len(failed)) / total_files if total_files > 0 else 0
    logger.info(f"Batch processing complete. Success rate: {completion_rate:.1%}")
    logger.info(f"Processed: {len(results)}, Failed: {len(failed)}, Skipped: {len(skipped)}")
    
    return results

def process_file_with_timeout(pdf_name: str, input_dir: str, output_dir: str, 
                             timeout: int = 300) -> Dict[str, Any]:
    """
    Process a single file with timeout protection.
    
    Args:
        pdf_name: Name of the PDF file
        input_dir: Directory containing the PDF
        output_dir: Directory to save results
        timeout: Maximum processing time in seconds
        
    Returns:
        Processing result dictionary
    """
    result = {
        "pdf_name": pdf_name,
        "success": False,
        "error": "Timeout occurred"
    }
    
    def target():
        nonlocal result
        try:
            result = run_extraction(pdf_name, input_dir, output_dir)
        except Exception as e:
            result = {
                "pdf_name": pdf_name,
                "success": False,
                "error": str(e)
            }
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        logger.warning(f"Processing timed out after {timeout}s for {pdf_name}")
        return result
    
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch processor for legal document PDFs")
    parser.add_argument("--input", default="input_pdfs", help="Input folder path")
    parser.add_argument("--output", default="output_results", help="Output folder path")
    parser.add_argument("--skip_existing", action="store_true", help="Skip files already processed")
    args = parser.parse_args()

    batch_process(args.input, args.output, args.skip_existing)
