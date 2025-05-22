"""
Preprocessing module for DataBoss
Handles document preprocessing before OCR extraction
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path

logger = logging.getLogger("legal_extractor.preprocessing")
logging.basicConfig(level=logging.INFO)

@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing steps"""
    dpi: int = 300
    contrast_adjust: bool = True
    denoise: bool = True
    deskew: bool = True
    output_format: str = "png"
    
def preprocess_image(image_path: str, config: PreprocessingConfig = PreprocessingConfig()) -> str:
    """Preprocess a single image to improve OCR quality"""
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
            
        if config.contrast_adjust:
            img = cv2.convertScaleAbs(img, alpha=1.2, beta=10)
            
        if config.denoise:
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
            
        if config.deskew:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
            
            if lines is not None:
                angles = [line[0][1] for line in lines]
                angle_counts = {}
                for angle in angles:
                    angle_deg = angle * 180 / np.pi
                    if angle_deg > 45:
                        angle_deg = angle_deg - 90
                    angle_counts[angle_deg] = angle_counts.get(angle_deg, 0) + 1
                
                dominant_angle = max(angle_counts.items(), key=lambda x: x[1])[0]
                if abs(dominant_angle) > 0.5:  # Only rotate if skew is significant
                    h, w = img.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, dominant_angle, 1.0)
                    img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
        output_path = os.path.splitext(image_path)[0] + "_processed." + config.output_format
        cv2.imwrite(output_path, img)
        return output_path
        
    except Exception as e:
        logger.error(f"Image preprocessing failed: {str(e)}", exc_info=True)
        return image_path  # Return original if processing fails

def process_pdf(pdf_name: str, input_dir: str, output_dir: str, config: PreprocessingConfig = PreprocessingConfig()) -> Dict[str, Any]:
    """Process a PDF file for OCR extraction"""
    try:
        pdf_path = Path(input_dir) / pdf_name
        if not pdf_path.exists():
            return {"success": False, "error": f"PDF file not found: {pdf_path}"}
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        images = convert_from_path(pdf_path, dpi=config.dpi)
        
        results = []
        for i, img in enumerate(images):
            temp_dir = tempfile.mkdtemp()
            temp_img_path = os.path.join(temp_dir, f"page_{i+1}.png")
            img.save(temp_img_path, "PNG")
            
            processed_img_path = preprocess_image(temp_img_path, config)
            
            text = f"Processed page {i+1} of {pdf_name}"
            
            results.append({
                "page": i+1,
                "image_path": processed_img_path,
                "text": text
            })
            
        return {
            "success": True,
            "pdf_name": pdf_name,
            "page_count": len(images),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"PDF processing failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
