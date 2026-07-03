"""Domain validator registry.

The orchestrator iterates ``DOMAIN_VALIDATORS`` for the math/logic gates
(3-10).  Structural gates (1 workbook integrity, 2 sheet classification),
source verification (11), audit completeness (12), and final certification (13)
are coordinated by the orchestrator itself because they depend on the DB / API
rather than solely on the manifest.
"""

from __future__ import annotations

from .base_validator import ValidatorBase
from .val_acreage import AcreageValidator
from .val_chain import ChainValidator
from .val_instrument import InstrumentValidator
from .val_interest import InterestValidator
from .val_ogl_wi import OglWiValidator

DOMAIN_VALIDATORS: list[ValidatorBase] = [
    InterestValidator(),
    AcreageValidator(),
    ChainValidator(),
    InstrumentValidator(),
    OglWiValidator(),
]

__all__ = [
    "ValidatorBase",
    "DOMAIN_VALIDATORS",
    "AcreageValidator",
    "InterestValidator",
    "ChainValidator",
    "InstrumentValidator",
    "OglWiValidator",
]
