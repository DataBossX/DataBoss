"""
Mineral Rights Extractor for DataBoss
Extracts mineral rights information from legal documents
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from model_chain import run_model_chain
from db_connector import DBConnector

logger = logging.getLogger("databoss.mineral_rights_extractor")
logging.basicConfig(level=logging.INFO)

class MineralRightsExtractor:
    def __init__(self, db_connector: Optional[DBConnector] = None):
        self.db_connector = db_connector or DBConnector()
        
    def extract_from_text(self, document_id: str, text: str) -> Dict[str, Any]:
        """Extract mineral rights information from document text"""
        logger.info(f"Extracting mineral rights from document {document_id}")
        
        prompt = self._create_extraction_prompt(text)
        result, model_used = run_model_chain(prompt)
        
        extracted_data = self._parse_extraction_result(result)
        extracted_data['document_id'] = document_id
        
        if not all(k in extracted_data for k in ['section', 'township', 'range']):
            self._extract_section_township_range(text, extracted_data)
            
        if self.db_connector:
            self.db_connector.insert_mineral_rights(extracted_data)
            
        self._generate_summary_log(document_id, extracted_data)
        
        return extracted_data
        
    def _create_extraction_prompt(self, text: str) -> str:
        """Create prompt for LLM extraction"""
        return f"""
        Extract the following information from this legal document in JSON format:
        - grantor (the party granting rights)
        - grantee (the party receiving rights)
        - agreement_type (type of agreement, e.g. lease, deed, assignment)
        - effective_date (date the agreement takes effect)
        - section (section number)
        - township (township number)
        - range (range number)
        - county (county name)
        - state (state name)
        - description (brief description of the property)

        Document text:
        {text[:2000]}...

        Return ONLY a valid JSON object with these fields. If a field cannot be determined, use null.
        """
        
    def _parse_extraction_result(self, result: str) -> Dict[str, Any]:
        """Parse the extraction result from LLM"""
        try:
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                return data
        except Exception as e:
            logger.error(f"Failed to parse extraction result: {str(e)}")
            
        data = {}
        patterns = {
            'grantor': r'grantor[:\s]+([^,\n]+)',
            'grantee': r'grantee[:\s]+([^,\n]+)',
            'agreement_type': r'(lease|deed|assignment|transfer)[:\s]+([^,\n]+)',
            'effective_date': r'date[:\s]+([^,\n]+)',
            'section': r'section[:\s]+(\d+)',
            'township': r'township[:\s]+(\d+\s*[NS]?)',
            'range': r'range[:\s]+(\d+\s*[EW]?)',
            'county': r'county[:\s]+([^,\n]+)',
            'state': r'state[:\s]+([^,\n]+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                data[key] = match.group(1).strip()
                
        return data
        
    def _extract_section_township_range(self, text: str, data: Dict[str, Any]) -> None:
        """Extract section/township/range from text"""
        section_pattern = r'Section\s+(\d+)'
        township_pattern = r'Township\s+(\d+\s*[NS]?)'
        range_pattern = r'Range\s+(\d+\s*[EW]?)'
        
        if 'section' not in data or not data['section']:
            section_match = re.search(section_pattern, text, re.IGNORECASE)
            if section_match:
                data['section'] = section_match.group(1)
                
        if 'township' not in data or not data['township']:
            township_match = re.search(township_pattern, text, re.IGNORECASE)
            if township_match:
                data['township'] = township_match.group(1)
                
        if 'range' not in data or not data['range']:
            range_match = re.search(range_pattern, text, re.IGNORECASE)
            if range_match:
                data['range'] = range_match.group(1)
                
        filename = data.get('document_id', '')
        if filename:
            sec_match = re.search(r'Sec(\d+)', filename, re.IGNORECASE)
            twp_match = re.search(r'T(\d+[NS]?)', filename, re.IGNORECASE)
            rng_match = re.search(r'R(\d+[EW]?)', filename, re.IGNORECASE)
            
            if 'section' not in data or not data['section']:
                if sec_match:
                    data['section'] = sec_match.group(1)
                    
            if 'township' not in data or not data['township']:
                if twp_match:
                    data['township'] = twp_match.group(1)
                    
            if 'range' not in data or not data['range']:
                if rng_match:
                    data['range'] = rng_match.group(1)
                    
    def _generate_summary_log(self, document_id: str, data: Dict[str, Any]) -> None:
        """Generate summary log for successful ingest"""
        try:
            output_dir = Path("output_results")
            output_dir.mkdir(exist_ok=True)
            
            summary_log = {
                "document_id": document_id,
                "extraction_time": data.get("extraction_time", "unknown"),
                "extracted_data": data,
                "status": "success"
            }
            
            log_path = output_dir / f"summary_log_{document_id}.json"
            with open(log_path, "w") as f:
                json.dump(summary_log, f, indent=2)
                
            logger.info(f"Generated summary log for {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate summary log: {str(e)}")
