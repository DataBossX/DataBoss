"""Configuration + section/aliquot geometry. Loads .env without echoing secrets."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv optional at import time
    def load_dotenv(*_a, **_k):
        return False

# The 16 forty-acre aliquots of a standard PLSS section, ordered.
QUARTERS = ["NE", "NW", "SE", "SW"]
ALIQUOTS_16 = [f"{sub} {q}" for q in QUARTERS for sub in QUARTERS]

# Document-type vocabulary seen in OK county indexes.
DOC_TYPES = {
    "O/L": "Oil & Gas Lease", "OL": "Oil & Gas Lease", "OGL": "Oil & Gas Lease",
    "ASGT": "Assignment", "DEED": "Deed", "WD": "Warranty Deed",
    "MD": "Mineral Deed", "MIN": "Mineral Deed", "QCD": "Quit Claim Deed",
    "QCMD": "Quit Claim Mineral Deed", "PROB": "Probate", "PAT": "Patent",
    "REL": "Release", "ROW": "Right of Way", "MTG": "Mortgage",
    "AFF": "Affidavit", "RATIF": "Ratification", "FD": "Final Decree",
    "JUDG": "Judgment", "DECREE": "Decree", "DISCLAIM": "Disclaimer",
}


def load_secrets(env_path: str | os.PathLike | None = None) -> dict:
    """Load .env into the process environment. Returns ONLY which provider keys
    are present (booleans) — never the secret values."""
    if env_path and Path(env_path).exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
    return {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "lmstudio": bool(os.getenv("LMSTUDIO_BASE_URL")),
    }


@dataclass
class BuildConfig:
    project_dir: Path
    template_path: Path | None = None
    output_path: Path | None = None
    section: str = "31"
    township: str = "12N"
    range_: str = "24W"
    county: str = "Roger Mills"
    state: str = "Oklahoma"
    # tract -> list of forty-acre aliquots (defines tract geometry & footing)
    tract_aliquots: dict[int, list[str]] = field(default_factory=dict)
    dpi: int = 300
    ocr: bool = True
    recurse: bool = True

    @property
    def legal_root(self) -> str:
        return f"S{self.section} T{self.township} R{self.range_}"

    def aliquot_to_tract(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t, als in self.tract_aliquots.items():
            for a in als:
                out[a.upper()] = t
        return out
