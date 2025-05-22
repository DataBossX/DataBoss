"""
Database connector for DataBoss
Handles database connections and operations
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger("databoss.db_connector")
logging.basicConfig(level=logging.INFO)

DEFAULT_DB_PATH = "databoss.db"

class DBConnector:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.initialize_db()
        
    def initialize_db(self):
        """Initialize database with required tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS mineral_rights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                grantor TEXT,
                grantee TEXT,
                agreement_type TEXT,
                effective_date TEXT,
                section TEXT,
                township TEXT,
                range TEXT,
                county TEXT,
                state TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                page_count INTEGER,
                processed BOOLEAN DEFAULT 0,
                processing_time REAL,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                page_number INTEGER,
                text TEXT,
                char_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
            
    def insert_mineral_rights(self, data: Dict[str, Any]) -> bool:
        """Insert mineral rights data into database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO mineral_rights 
            (document_id, grantor, grantee, agreement_type, effective_date, 
             section, township, range, county, state, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('document_id', ''),
                data.get('grantor', ''),
                data.get('grantee', ''),
                data.get('agreement_type', ''),
                data.get('effective_date', ''),
                data.get('section', ''),
                data.get('township', ''),
                data.get('range', ''),
                data.get('county', ''),
                data.get('state', ''),
                data.get('description', '')
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Inserted mineral rights data for document {data.get('document_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert mineral rights data: {str(e)}", exc_info=True)
            return False
            
    def track_document(self, document_id: str, filename: str, file_path: str, 
                      file_type: str, page_count: int) -> bool:
        """Track document in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO documents
            (document_id, filename, file_path, file_type, page_count)
            VALUES (?, ?, ?, ?, ?)
            ''', (document_id, filename, file_path, file_type, page_count))
            
            conn.commit()
            conn.close()
            logger.info(f"Tracked document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track document: {str(e)}", exc_info=True)
            return False
