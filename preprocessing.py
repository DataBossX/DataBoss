"""
Preprocessing Module for Legal Document Processing

Handles document preprocessing, OCR, and text extraction.
"""

import os
import logging
import fitz  # PyMuPDF
from PIL import Image, ImageFilter
import pytesseract
from pathlib import Path
from typing import Dict, Any, List, Optional
import pdf2image
import numpy as np

logger = logging.getLogger("legal_extractor.preprocessing")

class PreprocessingConfig:
    """Configuration for preprocessing options"""
    def __init__(self, 
                ocr_enabled: bool = True,
                language: str = "eng",
                dpi: int = 300,
                contrast_enhancement: bool = True,
                noise_reduction: bool = True):
        self.ocr_enabled = ocr_enabled
        self.language = language
        self.dpi = dpi
        self.contrast_enhancement = contrast_enhancement
        self.noise_reduction = noise_reduction

def enhance_image(image: Image.Image, config: PreprocessingConfig) -> Image.Image:
    """Apply image enhancements for better OCR results"""
    img_array = np.array(image)
    
    if config.contrast_enhancement:
        p2, p98 = np.percentile(img_array, (2, 98))
        img_array = np.clip((img_array - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
    
    if config.noise_reduction:
        image = Image.fromarray(img_array)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
    return image

def extract_text_with_ocr(image: Image.Image, config: PreprocessingConfig) -> str:
    """Extract text from image using OCR"""
    try:
        enhanced_image = enhance_image(image, config)
        text = pytesseract.image_to_string(enhanced_image, lang=config.language)
        return text
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}", exc_info=True)
        return ""

def process_pdf(pdf_name: str, input_dir: str, output_dir: str, 
               config: Optional[PreprocessingConfig] = None) -> Dict[str, Any]:
    """
    Process a PDF file for text extraction, with optional OCR.
    
    Args:
        pdf_name: Name of the PDF file
        input_dir: Directory containing the PDF
        output_dir: Directory to save results
        config: Preprocessing configuration
        
    Returns:
        Dictionary with processing results
    """
    if config is None:
        config = PreprocessingConfig()
        
    result = {
        "success": False,
        "pdf_name": pdf_name,
        "results": []
    }
    
    try:
        pdf_path = os.path.join(input_dir, pdf_name)
        logger.info(f"Processing PDF: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            text = page.get_text()
            
            if len(text.strip()) < 50 and config.ocr_enabled:
                logger.info(f"Using OCR for page {page_num+1} of {pdf_name}")
                pix = page.get_pixmap(dpi=config.dpi)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                ocr_text = extract_text_with_ocr(img, config)
                
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            
            result["results"].append({
                "page_number": page_num + 1,
                "text": text.strip(),
                "char_count": len(text)
            })
        
        result["success"] = True
        
    except Exception as e:
        logger.error(f"Failed to process {pdf_name}: {str(e)}", exc_info=True)
        result["error"] = str(e)
    
    return result
