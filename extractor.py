
import os
import json
import time
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from preprocessing import process_pdf, PreprocessingConfig
from model_chain import run_model_chain
from pdf_chunker import split_pdf

logger = logging.getLogger("legal_extractor.extractor")
logging.basicConfig(level=logging.INFO)

MAX_PAGE_THRESHOLD = 20  # Max pages before chunking

class ExtractionResult:
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.results = []
        self._processing_time = 0
        self.model_used = "Unknown"
        self.output_files = {}

    def add_page_result(self, page_num: int, text: str):
        self.results.append({
            "page_number": page_num,
            "text": text.strip(),
            "char_count": len(text)
        })
        
    @property
    def processing_time(self):
        return self._processing_time
        
    @processing_time.setter
    def processing_time(self, value):
        self._processing_time = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "processing_time": f"{self._processing_time:.2f}s",
            "model_used": self.model_used,
            "page_count": len(self.results),
            "total_characters": sum(r["char_count"] for r in self.results),
            "results": self.results
        }

def save_results(document_id: str, results: dict, output_dir: str) -> Dict[str, str]:
    output_paths = {}
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        json_path = output_dir_path / f"{document_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        output_paths["json"] = str(json_path)

        excel_path = output_dir_path / f"{document_id}.xlsx"
        df = pd.DataFrame(results["results"])
        df.to_excel(excel_path, index=False)
        output_paths["excel"] = str(excel_path)

        txt_path = output_dir_path / f"{document_id}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for page in results["results"]:
                f.write(f"\n=== PAGE {page['page_number']} ===\n")
                f.write(page["text"])
        output_paths["txt"] = str(txt_path)

    except Exception as e:
        logger.error(f"Failed to save results: {str(e)}", exc_info=True)

    return output_paths

def run_extraction(pdf_file: str, input_dir: str, output_dir: str) -> Dict[str, Any]:
    logger.info(f"Starting extraction for {pdf_file}")
    start_time = time.time()

    result = {
        "document_id": Path(pdf_file).stem,
        "success": False,
        "processing_time": 0,
        "model_used": "None",
        "output_files": {}
    }

    try:
        full_path = str(Path(input_dir) / pdf_file)
        # Chunk if PDF is over threshold
        chunks = split_pdf(full_path, output_dir + "/chunks")

        if not chunks:
            raise RuntimeError("Chunking failed or produced no valid pages")

        extraction_result = ExtractionResult(Path(pdf_file).stem)

        # Process each chunk
        for idx, chunk_path in enumerate(chunks):
            single_page_name = os.path.basename(chunk_path)
            processing_result = process_pdf(single_page_name, output_dir + "/chunks", output_dir)
            if not processing_result.get("success"):
                logger.warning(f"Skipping failed chunk {single_page_name}")
                continue

            for page_result in processing_result.get("results", []):
                prompt = page_result["text"]
                model_output, model_name = run_model_chain(prompt)
                extraction_result.add_page_result(idx + 1, model_output)
                extraction_result.model_used = model_name

        extraction_result.processing_time = time.time() - start_time
        output_paths = save_results(
            extraction_result.document_id,
            extraction_result.to_dict(),
            output_dir
        )

        result.update({
            "success": True,
            "document_id": extraction_result.document_id,
            "processing_time": f"{extraction_result.processing_time:.2f}s",
            "model_used": extraction_result.model_used,
            "output_files": output_paths
        })

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Extraction failed: {str(e)}", exc_info=True)

    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Legal Document Extraction CLI")
    parser.add_argument("--input", default="input_pdfs", help="PDF input folder")
    parser.add_argument("--output", default="output_results", help="Results output folder")
    parser.add_argument("--pdf", required=True, help="PDF filename to process")
    args = parser.parse_args()

    result = run_extraction(args.pdf, args.input, args.output)
    print(json.dumps(result, indent=2))
