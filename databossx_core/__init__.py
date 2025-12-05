"""
DataBossX Self-Evolving Land Intelligence Intake System
Version: 2.0.0
Architecture: Production-grade modular system with self-healing capabilities
"""

__version__ = "2.0.0"
__author__ = "DataBossX Engineering"
__license__ = "Proprietary"

from . import models
from . import intake
from . import ocr
from . import extraction
from . import chain
from . import evolution
from . import analytics
from . import persistence

__all__ = [
    "models",
    "intake",
    "ocr",
    "extraction",
    "chain",
    "evolution",
    "analytics",
    "persistence",
]
