
import os
import time
import logging
from pathlib import Path
from extractor import run_extraction

# Configure logging
logging.basicConfig(
    filename="batch_processor.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def batch_process(input_dir: str, output_dir: str, skip_existing: bool = True):
    """
    Process all PDF files in the input directory using run_extraction().
    
    Args:
        input_dir (str): Path to folder containing PDF files.
        output_dir (str): Path to folder where results will be saved.
        skip_existing (bool): Skip PDFs already processed.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    input_path.mkdir(exist_ok=True)
    output_path.mkdir(exist_ok=True)

    pdf_files = list(input_path.glob("*.pdf"))
    logging.info(f"Found {len(pdf_files)} PDF(s) to process.")

    for pdf_file in pdf_files:
        try:
            doc_id = pdf_file.stem
            json_out = output_path / f"{doc_id}.json"

            if skip_existing and json_out.exists():
                logging.info(f"Skipping already processed file: {pdf_file.name}")
                continue

            logging.info(f"Processing file: {pdf_file.name}")
            result = run_extraction(pdf_file.name, str(input_path), str(output_path))

            if result.get("success"):
                logging.info(f"✔ Success: {pdf_file.name} in {result['processing_time']}")
            else:
                logging.warning(f"❌ Failed: {pdf_file.name} - {result.get('error', 'Unknown error')}")

        except Exception as e:
            logging.error(f"Unhandled exception while processing {pdf_file.name}: {str(e)}", exc_info=True)

    logging.info("Batch processing complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch processor for legal document PDFs")
    parser.add_argument("--input", default="input_pdfs", help="Input folder path")
    parser.add_argument("--output", default="output_results", help="Output folder path")
    parser.add_argument("--skip_existing", action="store_true", help="Skip files already processed")
    args = parser.parse_args()

    batch_process(args.input, args.output, args.skip_existing)
