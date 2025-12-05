"""
Core data models for DataBossX Land Intelligence System
"""

from .document import (
    Document,
    DocumentType,
    DocumentMetadata,
    UploadedFile,
)
from .ocr import (
    OCRResult,
    OCREngine,
    OCRLineResult,
    OCRFusionResult,
)
from .entity import (
    LegalEntity,
    EntityType,
    Grantor,
    Grantee,
    LegalDescription,
    AliquotPart,
    DepthClause,
    AcreageInfo,
)
from .chain import (
    ChainGraph,
    ChainNode,
    Ownership,
    OwnershipType,
    InterestType,
    ChainLink,
    ChainGap,
)
from .evolution import (
    ExtractionRule,
    RuleMutation,
    MutationScore,
    EvolutionHistory,
)
from .analytics import (
    PredictiveInsight,
    HeirshipPrediction,
    MissingFilingPrediction,
    ConfidenceMetrics,
)

__all__ = [
    # Document models
    "Document",
    "DocumentType",
    "DocumentMetadata",
    "UploadedFile",
    # OCR models
    "OCRResult",
    "OCREngine",
    "OCRLineResult",
    "OCRFusionResult",
    # Entity models
    "LegalEntity",
    "EntityType",
    "Grantor",
    "Grantee",
    "LegalDescription",
    "AliquotPart",
    "DepthClause",
    "AcreageInfo",
    # Chain models
    "ChainGraph",
    "ChainNode",
    "Ownership",
    "OwnershipType",
    "InterestType",
    "ChainLink",
    "ChainGap",
    # Evolution models
    "ExtractionRule",
    "RuleMutation",
    "MutationScore",
    "EvolutionHistory",
    # Analytics models
    "PredictiveInsight",
    "HeirshipPrediction",
    "MissingFilingPrediction",
    "ConfidenceMetrics",
]
