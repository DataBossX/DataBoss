"""
Document type detection with ML-enhanced pattern matching
"""

import re
from typing import Tuple, List, Dict
from ..models.document import DocumentType


class DocumentTypeDetector:
    """
    Advanced document type detector using pattern matching and scoring
    """

    # Pattern signatures for each document type
    PATTERNS = {
        DocumentType.DEED: {
            "required": [
                r"\b(warranty deed|quit[ -]?claim deed|special warranty deed)\b",
                r"\b(grantor|grantee)\b",
            ],
            "strong": [
                r"\b(convey|grant|bargain|sell)\b",
                r"\b(consideration|purchase price)\b",
                r"\b(notary|acknowledged)\b",
            ],
            "weak": [
                r"\b(legal description|lot|block)\b",
                r"\b(county|state of)\b",
            ],
        },
        DocumentType.MINERAL_DEED: {
            "required": [
                r"\b(mineral|minerals)\b",
                r"\b(grantor|grantee)\b",
            ],
            "strong": [
                r"\b(mineral deed|mineral rights|mineral interest)\b",
                r"\b(oil|gas|petroleum)\b",
                r"\b(royalty|working interest)\b",
                r"\b(depth|formation|horizon)\b",
            ],
            "weak": [
                r"\b(convey|grant)\b",
                r"\b(acres|section|township|range)\b",
            ],
        },
        DocumentType.LEASE: {
            "required": [
                r"\b(lease|lessor|lessee)\b",
            ],
            "strong": [
                r"\b(oil and gas lease|mineral lease)\b",
                r"\b(primary term|secondary term)\b",
                r"\b(royalty|bonus|rental)\b",
                r"\b(drilling|production)\b",
            ],
            "weak": [
                r"\b(extend|renewal|option)\b",
                r"\b(assignment|transfer)\b",
            ],
        },
        DocumentType.ASSIGNMENT: {
            "required": [
                r"\b(assignment|assignor|assignee)\b",
            ],
            "strong": [
                r"\b(assign|transfer|convey)\b",
                r"\b(working interest|overriding royalty)\b",
                r"\b(lease|leasehold)\b",
            ],
            "weak": [
                r"\b(consideration|effective date)\b",
                r"\b(interest|rights)\b",
            ],
        },
        DocumentType.AFFIDAVIT: {
            "required": [
                r"\b(affidavit)\b",
                r"\b(sworn|subscribed|notary)\b",
            ],
            "strong": [
                r"\b(affiant|deponent)\b",
                r"\b(personally appeared|being duly sworn)\b",
                r"\b(under oath|under penalty)\b",
            ],
            "weak": [
                r"\b(statement|declare|certify)\b",
            ],
        },
        DocumentType.POOLING: {
            "required": [
                r"\b(pool|pooling|unit|unitization)\b",
            ],
            "strong": [
                r"\b(pooling agreement|pooling declaration)\b",
                r"\b(participating|non-participating)\b",
                r"\b(proration|allocation)\b",
                r"\b(spacing|drilling unit)\b",
            ],
            "weak": [
                r"\b(well|production|operator)\b",
                r"\b(interest|share)\b",
            ],
        },
        DocumentType.PROBATE: {
            "required": [
                r"\b(estate|probate|heir|intestate)\b",
            ],
            "strong": [
                r"\b(last will|testament|executor|administrator)\b",
                r"\b(deceased|decedent|death)\b",
                r"\b(beneficiary|inheritance|devise)\b",
                r"\b(probate court|surrogate)\b",
            ],
            "weak": [
                r"\b(distribute|succession)\b",
                r"\b(personal representative)\b",
            ],
        },
        DocumentType.ROYALTY_DEED: {
            "required": [
                r"\b(royalty)\b",
                r"\b(grantor|grantee)\b",
            ],
            "strong": [
                r"\b(royalty deed|royalty interest)\b",
                r"\b(non-participating|participating)\b",
                r"\b(override|overriding)\b",
                r"\b(production|proceeds)\b",
            ],
            "weak": [
                r"\b(convey|grant)\b",
                r"\b(oil|gas|minerals)\b",
            ],
        },
    }

    def __init__(self):
        self.compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency"""
        for doc_type, pattern_dict in self.PATTERNS.items():
            self.compiled_patterns[doc_type] = {
                "required": [
                    re.compile(pattern, re.IGNORECASE) for pattern in pattern_dict["required"]
                ],
                "strong": [
                    re.compile(pattern, re.IGNORECASE) for pattern in pattern_dict["strong"]
                ],
                "weak": [
                    re.compile(pattern, re.IGNORECASE) for pattern in pattern_dict["weak"]
                ],
            }

    def calculate_score(self, text: str, doc_type: DocumentType) -> float:
        """
        Calculate confidence score for a document type

        Scoring:
        - Required patterns: Must match at least one, or score is 0
        - Strong patterns: +0.15 per match
        - Weak patterns: +0.05 per match
        - Base score: 0.3 if all required patterns match
        """
        patterns = self.compiled_patterns[doc_type]

        # Check required patterns
        required_matches = sum(
            1 for pattern in patterns["required"] if pattern.search(text)
        )
        if required_matches == 0:
            return 0.0

        # Base score for meeting requirements
        score = 0.3

        # Add points for strong patterns
        strong_matches = sum(
            1 for pattern in patterns["strong"] if pattern.search(text)
        )
        score += min(strong_matches * 0.15, 0.6)

        # Add points for weak patterns
        weak_matches = sum(
            1 for pattern in patterns["weak"] if pattern.search(text)
        )
        score += min(weak_matches * 0.05, 0.15)

        return min(score, 1.0)

    async def detect(self, text: str) -> Tuple[DocumentType, float]:
        """
        Detect document type from text

        Args:
            text: Document text content

        Returns:
            Tuple of (DocumentType, confidence_score)
        """
        if not text or len(text) < 50:
            return DocumentType.UNKNOWN, 0.0

        # Calculate scores for all document types
        scores: List[Tuple[DocumentType, float]] = []
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
            score = self.calculate_score(text, doc_type)
            if score > 0:
                scores.append((doc_type, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores:
            return DocumentType.UNKNOWN, 0.0

        # Return highest scoring type
        best_type, best_score = scores[0]

        # If score is too low, return UNKNOWN
        if best_score < 0.4:
            return DocumentType.UNKNOWN, best_score

        return best_type, best_score

    def get_detection_details(self, text: str) -> Dict[DocumentType, float]:
        """
        Get scores for all document types

        Args:
            text: Document text content

        Returns:
            Dictionary mapping DocumentType to score
        """
        scores = {}
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
            scores[doc_type] = self.calculate_score(text, doc_type)
        return scores
