"""
Main entity extractor - coordinates all specialized extractors
"""

import uuid
from datetime import datetime
from typing import List

from ..models.entity import EntityExtraction
from .grantor_extractor import GrantorExtractor
from .grantee_extractor import GranteeExtractor
from .legal_desc_extractor import LegalDescriptionExtractor
from .depth_clause_extractor import DepthClauseExtractor
from .acreage_extractor import AcreageExtractor


class EntityExtractor:
    """
    Main entity extractor that coordinates all specialized extractors
    """

    def __init__(self):
        self.grantor_extractor = GrantorExtractor()
        self.grantee_extractor = GranteeExtractor()
        self.legal_desc_extractor = LegalDescriptionExtractor()
        self.depth_clause_extractor = DepthClauseExtractor()
        self.acreage_extractor = AcreageExtractor()

    async def extract(self, document_id: str, text: str) -> EntityExtraction:
        """
        Extract all entities from document text

        Args:
            document_id: Document ID
            text: Document text content

        Returns:
            EntityExtraction object with all extracted entities
        """
        # Extract grantors
        grantors = await self.grantor_extractor.extract(text)

        # Extract grantees
        grantees = await self.grantee_extractor.extract(text)

        # Extract legal descriptions
        legal_descriptions = await self.legal_desc_extractor.extract(text)

        # Extract depth clauses
        depth_clauses = await self.depth_clause_extractor.extract(text)

        # Extract acreage info
        acreage_info = await self.acreage_extractor.extract(text)

        # Collect rules used
        rules_used = (
            self.grantor_extractor.get_rules_used()
            + self.grantee_extractor.get_rules_used()
            + self.legal_desc_extractor.get_rules_used()
            + self.depth_clause_extractor.get_rules_used()
            + self.acreage_extractor.get_rules_used()
        )

        # Calculate overall confidence
        all_confidences = []
        all_confidences.extend([g.confidence for g in grantors])
        all_confidences.extend([g.confidence for g in grantees])
        all_confidences.extend([ld.confidence for ld in legal_descriptions])
        all_confidences.extend([dc.confidence for dc in depth_clauses])
        if acreage_info:
            all_confidences.append(acreage_info.confidence)

        overall_confidence = (
            sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        )

        return EntityExtraction(
            id=str(uuid.uuid4()),
            document_id=document_id,
            grantors=grantors,
            grantees=grantees,
            legal_descriptions=legal_descriptions,
            depth_clauses=depth_clauses,
            acreage_info=acreage_info,
            extraction_rules_used=rules_used,
            overall_confidence=overall_confidence,
            created_at=datetime.utcnow().isoformat(),
        )
