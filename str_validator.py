"""
STR Validation Module for Legal Document Processing

Handles validation of Structured Text Recognition results.
"""

import os
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger("legal_extractor.str_validator")

class STRValidator:
    """Validator for Structured Text Recognition results"""
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
    
    def validate_extraction(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extraction results and flag potential issues.
        
        Args:
            extraction_result: Dictionary of extraction results
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            "document_id": extraction_result.get("document_id", "unknown"),
            "validation_passed": True,
            "issues": [],
            "stats": {
                "total_pages": len(extraction_result.get("results", [])),
                "total_chars": 0,
                "low_confidence_pages": 0
            }
        }
        
        for page in extraction_result.get("results", []):
            page_num = page.get("page_number", 0)
            text = page.get("text", "")
            char_count = page.get("char_count", 0)
            
            validation["stats"]["total_chars"] += char_count
            
            if not text.strip():
                validation["issues"].append({
                    "type": "empty_page",
                    "page": page_num,
                    "severity": "high"
                })
                validation["validation_passed"] = False
            
            if 0 < len(text.strip()) < 100:
                validation["issues"].append({
                    "type": "short_text",
                    "page": page_num,
                    "char_count": char_count,
                    "severity": "medium"
                })
            
            if self._has_ocr_artifacts(text):
                validation["issues"].append({
                    "type": "ocr_artifacts",
                    "page": page_num,
                    "severity": "medium"
                })
        
        return validation
    
    def _has_ocr_artifacts(self, text: str) -> bool:
        """Check for common OCR artifacts in text"""
        unusual_chars = ['|', '~', '#', '@', '{', '}', '\\']
        for char in unusual_chars:
            if char * 3 in text:
                return True
        
        if '  ' * 3 in text:
            return True
            
        return False
    
    def generate_report(self, validation_result: Dict[str, Any], output_dir: str) -> str:
        """Generate validation report with visualizations"""
        doc_id = validation_result.get("document_id", "unknown")
        output_path = Path(output_dir) / f"{doc_id}_validation.html"
        
        issues_df = pd.DataFrame(validation_result.get("issues", []))
        
        html = f"""
        <html>
        <head>
            <title>Validation Report: {doc_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Validation Report: {doc_id}</h1>
                <h2 class="{'passed' if validation_result.get('validation_passed') else 'failed'}">
                    Status: {'PASSED' if validation_result.get('validation_passed') else 'FAILED'}
                </h2>
            </div>
            
            <h3>Statistics</h3>
            <ul>
                <li>Total Pages: {validation_result.get('stats', {}).get('total_pages', 0)}</li>
                <li>Total Characters: {validation_result.get('stats', {}).get('total_chars', 0)}</li>
                <li>Issues Found: {len(validation_result.get('issues', []))}</li>
            </ul>
        """
        
        if not issues_df.empty:
            html += f"""
            <h3>Issues</h3>
            {issues_df.to_html(index=False)}
            """
        else:
            html += "<h3>No issues found</h3>"
            
        html += """
        </body>
        </html>
        """
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        return str(output_path)
