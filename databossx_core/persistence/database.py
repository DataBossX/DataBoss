"""
Database manager for DataBossX
"""

import json
import aiosqlite
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.document import Document
from ..models.ocr import OCRResult, OCRFusionResult
from ..models.entity import EntityExtraction
from ..models.chain import ChainGraph


class DatabaseManager:
    """
    Database manager for all CRUD operations
    """

    def __init__(self, db_path: str = "./databossx_land_intel.db"):
        self.db_path = db_path

    async def save_document(self, document: Document):
        """Save document to database"""
        async with aiosqlite.connect(self.db_path) as db:
            metadata_json = json.dumps(document.metadata.dict() if document.metadata else None)
            await db.execute(
                """
                INSERT INTO documents (
                    id, filename, file_hash, file_type, file_size, uploaded_at,
                    document_type, document_type_confidence, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.filename,
                    document.file_hash,
                    document.file_type,
                    document.file_size,
                    document.uploaded_at.isoformat(),
                    document.document_type.value,
                    document.document_type_confidence,
                    document.status,
                    metadata_json,
                ),
            )
            await db.commit()

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                # Convert row to Document (simplified)
                return None  # Implement full conversion

    async def update_document_status(
        self, document_id: str, status: str, error_message: Optional[str] = None
    ):
        """Update document status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE documents
                SET status = ?, error_message = ?, processing_completed_at = ?
                WHERE id = ?
                """,
                (status, error_message, datetime.utcnow().isoformat(), document_id),
            )
            await db.commit()

    async def save_ocr_result(self, ocr_result: OCRResult):
        """Save OCR result"""
        async with aiosqlite.connect(self.db_path) as db:
            metadata_json = json.dumps(ocr_result.metadata)
            await db.execute(
                """
                INSERT INTO ocr_results (
                    id, document_id, engine, raw_text, overall_confidence,
                    processing_time, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ocr_result.id,
                    ocr_result.document_id,
                    ocr_result.engine.value,
                    ocr_result.raw_text,
                    ocr_result.overall_confidence,
                    ocr_result.processing_time,
                    ocr_result.created_at.isoformat(),
                    metadata_json,
                ),
            )
            await db.commit()

    async def save_ocr_fusion(self, fusion: OCRFusionResult):
        """Save OCR fusion result"""
        async with aiosqlite.connect(self.db_path) as db:
            metadata_json = json.dumps(fusion.metadata)
            await db.execute(
                """
                INSERT INTO ocr_fusion_results (
                    id, document_id, fused_text, overall_confidence,
                    fusion_method, llm_model_used, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fusion.id,
                    fusion.document_id,
                    fusion.fused_text,
                    fusion.overall_confidence,
                    fusion.fusion_method,
                    fusion.llm_model_used,
                    fusion.created_at.isoformat(),
                    metadata_json,
                ),
            )
            await db.commit()

    async def save_extraction(self, extraction: EntityExtraction):
        """Save entity extraction"""
        async with aiosqlite.connect(self.db_path) as db:
            # Save extraction record
            metadata_json = json.dumps(extraction.metadata)
            await db.execute(
                """
                INSERT INTO entity_extractions (
                    id, document_id, overall_confidence, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    extraction.id,
                    extraction.document_id,
                    extraction.overall_confidence,
                    extraction.created_at,
                    metadata_json,
                ),
            )

            # Save grantors
            for grantor in extraction.grantors:
                await db.execute(
                    """
                    INSERT INTO grantors (
                        id, extraction_id, name, normalized_name, entity_type,
                        confidence, source_text, marital_status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        grantor.id,
                        extraction.id,
                        grantor.name,
                        grantor.normalized_name,
                        grantor.entity_type.value,
                        grantor.confidence,
                        grantor.source_text,
                        grantor.marital_status,
                        json.dumps(grantor.metadata),
                    ),
                )

            # Save grantees
            for grantee in extraction.grantees:
                await db.execute(
                    """
                    INSERT INTO grantees (
                        id, extraction_id, name, normalized_name, entity_type,
                        confidence, source_text, percentage_interest, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        grantee.id,
                        extraction.id,
                        grantee.name,
                        grantee.normalized_name,
                        grantee.entity_type.value,
                        grantee.confidence,
                        grantee.source_text,
                        str(grantee.percentage_interest) if grantee.percentage_interest else None,
                        json.dumps(grantee.metadata),
                    ),
                )

            await db.commit()

    async def save_chain(self, chain: ChainGraph):
        """Save chain-of-title graph"""
        async with aiosqlite.connect(self.db_path) as db:
            # Save chain
            await db.execute(
                """
                INSERT INTO chain_graphs (
                    id, property_description, interest_type,
                    created_at, last_updated, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chain.id,
                    chain.property_description,
                    chain.interest_type.value,
                    chain.created_at.isoformat(),
                    chain.last_updated.isoformat(),
                    json.dumps(chain.metadata),
                ),
            )

            # Save nodes
            for node in chain.nodes:
                await db.execute(
                    """
                    INSERT INTO chain_nodes (
                        id, chain_id, entity_name, normalized_name,
                        is_current_owner, is_original_grantor, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.id,
                        chain.id,
                        node.entity_name,
                        node.normalized_name,
                        node.is_current_owner,
                        node.is_original_grantor,
                        json.dumps(node.metadata),
                    ),
                )

            # Save links
            for link in chain.links:
                await db.execute(
                    """
                    INSERT INTO chain_links (
                        id, chain_id, from_node_id, to_node_id, document_id,
                        transaction_date, transaction_type, interest_transferred, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link.id,
                        chain.id,
                        link.from_node_id,
                        link.to_node_id,
                        link.document_id,
                        link.transaction_date.isoformat() if link.transaction_date else None,
                        link.transaction_type,
                        link.interest_transferred.value,
                        json.dumps(link.metadata),
                    ),
                )

            await db.commit()

    async def get_all_documents(self) -> List[Dict]:
        """Get all documents"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM documents ORDER BY uploaded_at DESC") as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def log_event(self, level: str, message: str, component: str, details: Optional[Dict] = None):
        """Log system event"""
        async with aiosqlite.connect(self.db_path) as db:
            import uuid
            await db.execute(
                """
                INSERT INTO system_logs (id, level, message, component, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    level,
                    message,
                    component,
                    json.dumps(details) if details else None,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
