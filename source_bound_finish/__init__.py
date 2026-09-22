"""Public-safe, fail-closed source-bound finish toolkit.

This package never invents title facts. Missing evidence stays blank or
UNRESOLVED. It does not write to canonical client packages.
"""

from .access import AccessReceipt, probe_access
from .dates import DateRoleError, check_date_roles
from .format_qa import FormatFinding, check_format
from .hashing import sha256_bytes, sha256_file
from .identity import StableKey, reconcile_populations, stable_key
from .ledger import DISPOSITIONS, PageRecord, build_ledger
from .package import verify_package
from .pdf_census import PdfCensus, count_pdf_pages
from .purity import PurityFinding, check_purity
from .tournament import CycleResult, run_tournament

__all__ = [
    "AccessReceipt",
    "CycleResult",
    "DateRoleError",
    "DISPOSITIONS",
    "FormatFinding",
    "PageRecord",
    "PdfCensus",
    "PurityFinding",
    "StableKey",
    "build_ledger",
    "check_date_roles",
    "check_format",
    "check_purity",
    "count_pdf_pages",
    "probe_access",
    "reconcile_populations",
    "run_tournament",
    "sha256_bytes",
    "sha256_file",
    "stable_key",
    "verify_package",
]

__version__ = "2026.09.22"
