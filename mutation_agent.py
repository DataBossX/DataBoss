"""
Mutation Agent for DataBoss
Monitors and fixes system issues automatically
"""

import os
import sys
import re
import ast
import json
import time
import logging
import importlib
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import subprocess

logger = logging.getLogger("databoss.mutation_agent")
logging.basicConfig(level=logging.INFO)

class MutationAgent:
    def __init__(self, scan_interval: int = 3600):
        self.scan_interval = scan_interval
        self.issues_log = []
        self.fixed_issues = []
        self.running = False
        
    def start(self):
        """Start the mutation agent monitoring"""
        self.running = True
        logger.info("Mutation Agent started")
        
        while self.running:
            self.scan_system()
            time.sleep(self.scan_interval)
            
    def stop(self):
        """Stop the mutation agent"""
        self.running = False
        logger.info("Mutation Agent stopped")
        
    def scan_system(self):
        """Scan the system for issues"""
        logger.info("Starting system scan")
        
        self.scan_for_broken_imports()
        self.scan_for_runtime_crashes()
        self.scan_for_hallucination_risk()
        
        self.log_scan_results()
        
    def scan_for_broken_imports(self):
        """Scan for broken imports in Python files"""
        logger.info("Scanning for broken imports")
        
        python_files = list(Path('.').glob('**/*.py'))
        for file_path in python_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                try:
                    tree = ast.parse(content)
                    
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                imports.append(name.name)
                        elif isinstance(node, ast.ImportFrom):
                            imports.append(node.module)
                    
                    for module_name in imports:
                        if module_name and not self._is_import_valid(module_name):
                            issue = {
                                "type": "broken_import",
                                "file": str(file_path),
                                "module": module_name,
                                "timestamp": time.time()
                            }
                            self.issues_log.append(issue)
                            logger.warning(f"Broken import in {file_path}: {module_name}")
                            
                except SyntaxError:
                    issue = {
                        "type": "syntax_error",
                        "file": str(file_path),
                        "timestamp": time.time()
                    }
                    self.issues_log.append(issue)
                    logger.warning(f"Syntax error in {file_path}")
                    
            except Exception as e:
                logger.error(f"Error scanning {file_path}: {str(e)}")
                
    def scan_for_runtime_crashes(self):
        """Scan for potential runtime crashes"""
        logger.info("Scanning for potential runtime crashes")
        
        python_files = list(Path('.').glob('**/*.py'))
        for file_path in python_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                if 'def ' in content and 'try:' not in content:
                    issue = {
                        "type": "missing_exception_handling",
                        "file": str(file_path),
                        "severity": "medium",
                        "timestamp": time.time()
                    }
                    self.issues_log.append(issue)
                    logger.warning(f"Missing exception handling in {file_path}")
                    
            except Exception as e:
                logger.error(f"Error scanning {file_path}: {str(e)}")
                
    def scan_for_hallucination_risk(self):
        """Scan for potential AI hallucination risks"""
        logger.info("Scanning for hallucination risks")
        
        if os.path.exists('model_chain.py'):
            try:
                with open('model_chain.py', 'r') as f:
                    content = f.read()
                    
                if 'def is_valid' not in content or 'def validate' not in content:
                    issue = {
                        "type": "hallucination_risk",
                        "file": "model_chain.py",
                        "description": "Missing validation logic for AI responses",
                        "severity": "high",
                        "timestamp": time.time()
                    }
                    self.issues_log.append(issue)
                    logger.warning("Hallucination risk: Missing validation in model_chain.py")
                    
            except Exception as e:
                logger.error(f"Error scanning model_chain.py: {str(e)}")
                
    def _is_import_valid(self, module_name: str) -> bool:
        """Check if an import is valid"""
        try:
            base_module = module_name.split('.')[0]
            if base_module in sys.modules:
                return True
            try:
                __import__(base_module)
                return True
            except ImportError:
                return False
        except (ImportError, AttributeError):
            return False
            
    def log_scan_results(self):
        """Log scan results to file"""
        try:
            log_dir = Path("self_healing_system")
            log_dir.mkdir(exist_ok=True)
            
            log_data = {
                "timestamp": time.time(),
                "issues_found": len(self.issues_log),
                "issues": self.issues_log,
                "fixed_issues": self.fixed_issues
            }
            
            log_path = log_dir / f"mutation_scan_{int(time.time())}.json"
            with open(log_path, "w") as f:
                json.dump(log_data, f, indent=2)
                
            logger.info(f"Scan results logged to {log_path}")
            
        except Exception as e:
            logger.error(f"Failed to log scan results: {str(e)}")
