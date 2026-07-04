"""Validation gates package."""
from __future__ import annotations

from .base import Validator, ValidatorSuite
from .chain_of_title import ChainOfTitleValidator
from .instrument_line_audit import InstrumentLineAuditValidator
from .interest_conservation import InterestConservationValidator
from .ogl_register_audit import OGLRegisterAuditValidator
from .pro_rata_footing import ProRataFootingValidator


def default_suite() -> ValidatorSuite:
    """The canonical five-gate suite in fixed order."""
    return ValidatorSuite(
        [
            InterestConservationValidator(),
            ProRataFootingValidator(),
            ChainOfTitleValidator(),
            InstrumentLineAuditValidator(),
            OGLRegisterAuditValidator(),
        ]
    )


__all__ = [
    "Validator",
    "ValidatorSuite",
    "default_suite",
    "InterestConservationValidator",
    "ProRataFootingValidator",
    "ChainOfTitleValidator",
    "InstrumentLineAuditValidator",
    "OGLRegisterAuditValidator",
]
