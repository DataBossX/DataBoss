"""Bind allowlisted public BLM township plats.

These are published cadastral plats, not client abstracts. The module only
fetches two known township URLs, hashes the bytes, and writes a receipt.
It never treats a plat as a finished section package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

RECEIPT_SCHEMA_ID = "dbx.public_cadastral_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
_MAX_BYTES = 40 * 1024 * 1024
_ALLOWED: Dict[tuple[str, str, str], str] = {
    ("campbell", "45n", "76w"): (
        "https://wy.blm.gov/cadastral/countyplats/campbell/t45nr76w.pdf"
    ),
    ("johnson", "47n", "77w"): (
        "https://wy.blm.gov/cadastral/countyplats/johnson/t47nr77w.pdf"
    ),
}


class PublicCadastralError(ValueError):
    """Raised when a public plat request is unsafe or incomplete."""


@dataclass(frozen=True)
class PlatBinding:
    county: str
    township: str
    range_: str
    url: str
    sha256: str
    size_bytes: int
    source: str


@dataclass
class CadastralReceipt:
    generated_utc: str
    plats: list[PlatBinding]
    issues: list[str]
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: list[str] = field(default_factory=lambda: [
        "A public plat hash is not a section abstract package",
        "technical_pass is not package release",
    ])

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def plat_url(county: str, township: str, range_: str) -> str:
    key = (county.casefold(), township.casefold(), range_.casefold())
    if key not in _ALLOWED:
        raise PublicCadastralError(
            f"Township plat is not on the public allowlist: {county} {township} {range_}"
        )
    return _ALLOWED[key]


def _hash_stream(handle, *, limit: int = _MAX_BYTES) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = handle.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise PublicCadastralError("Public plat exceeds the size limit")
        digest.update(chunk)
    if size == 0:
        raise PublicCadastralError("Public plat is empty")
    return digest.hexdigest(), size


def hash_local_plat(path: Path) -> tuple[str, int]:
    with path.open("rb") as handle:
        return _hash_stream(handle)


def fetch_plat(county: str, township: str, range_: str) -> PlatBinding:
    url = plat_url(county, township, range_)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "wy.blm.gov":
        raise PublicCadastralError(f"Refusing non-allowlisted host: {url}")
    request = Request(
        url,
        headers={"User-Agent": "DataBossX-horizon-public-cadastral/1.0"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.netloc != "wy.blm.gov":
                raise PublicCadastralError(
                    f"Redirect left the allowlisted host: {response.geturl()}"
                )
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.casefold():
                raise PublicCadastralError(
                    f"Public plat is not a PDF: {content_type}"
                )
            digest, size = _hash_stream(response)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PublicCadastralError(f"Cannot fetch {url}: {exc}") from exc
    return PlatBinding(
        county=county.casefold(),
        township=township.casefold(),
        range_=range_.casefold(),
        url=url,
        sha256=digest,
        size_bytes=size,
        source="https_fetch",
    )


def bind_local_plat(
    county: str,
    township: str,
    range_: str,
    path: Path,
) -> PlatBinding:
    url = plat_url(county, township, range_)
    digest, size = hash_local_plat(path)
    return PlatBinding(
        county=county.casefold(),
        township=township.casefold(),
        range_=range_.casefold(),
        url=url,
        sha256=digest,
        size_bytes=size,
        source="local_file",
    )


def build_receipt(plats: Sequence[PlatBinding]) -> CadastralReceipt:
    issues = []
    if not plats:
        issues.append("No public plats were bound")
    return CadastralReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        plats=list(plats),
        issues=issues,
        technical_pass=bool(plats) and not issues,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hash allowlisted public BLM township plats."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--plat",
        action="append",
        required=True,
        metavar="COUNTY,TOWNSHIP,RANGE[,LOCAL_PDF]",
        help="Example: campbell,45n,76w or johnson,47n,77w,/tmp/plat.pdf",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        plats = []
        for raw in args.plat:
            parts = [part.strip() for part in raw.split(",")]
            if len(parts) == 3:
                plats.append(fetch_plat(parts[0], parts[1], parts[2]))
            elif len(parts) == 4:
                plats.append(
                    bind_local_plat(parts[0], parts[1], parts[2], Path(parts[3]))
                )
            else:
                raise PublicCadastralError(
                    "Each --plat must be county,township,range[,local_pdf]"
                )
        receipt = build_receipt(plats)
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, PublicCadastralError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "plats": [
                    {
                        "county": plat.county,
                        "township": plat.township,
                        "range": plat.range_,
                        "sha256": plat.sha256,
                        "size_bytes": plat.size_bytes,
                    }
                    for plat in receipt.plats
                ],
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
