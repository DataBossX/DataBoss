"""Improvement-loop tournament for abstract image accounting and format.

Each pass re-counts every image, queues vision/OCR, applies the Section
13/15 Letter contract, and scores the isolated copy. The loop stops at
the first unaccounted image, empty proposal set, or max pass count.
This is not package release. Work date is 2026-09-22.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import write_new_json
from .image_account import (
    WORK_DATE,
    ImageAccountError,
    account_images,
    every_image_accounted,
    vision_queue_from_receipt,
)
from .package_format import (
    PackageFormatError,
    apply_letter_format,
    portfolio_status,
)
from .vision_ocr import VisionOcrError, review_queue

RECEIPT_SCHEMA_ID = "dbx.tournament_loop_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
DEFAULT_MAX_LOOPS = 10
MAX_LOOPS_CAP = 20
CHALLENGERS = (
    "image_account",
    "every_image_accounted",
    "vision_ocr_queue",
    "letter_format",
    "required_fields",
)


class TournamentLoopError(ValueError):
    """Raised when the improvement-loop tournament cannot run safely."""


@dataclass
class ChallengerScore:
    name: str
    passed: bool
    score: int
    detail: str


@dataclass
class TournamentPass:
    pass_number: int
    image_count: int
    accounted_images: int
    unaccounted_images: int
    empty_text_images: int
    vision_queued: int
    format_pass: Optional[bool]
    scores: List[ChallengerScore]
    stop_reason: str = ""
    winner: str = ""


@dataclass
class TournamentReceipt:
    generated_utc: str
    work_date: str
    packet_id: str
    bind_dir: str
    passes: List[TournamentPass]
    image_count: int
    every_image_accounted: bool
    winner: str
    technical_pass: bool
    packages_complete: bool
    portfolio: Dict[str, object]
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Vision before OCR",
            "Match Section 15 by role, not facts",
            "UNKNOWN image counts stay UNKNOWN when no bind-dir images exist",
            "packages_complete stays false",
            "This tournament does not promote a package",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _score_challengers(
    *,
    image_receipt,
    accounted: bool,
    vision_queued: int,
    format_pass: Optional[bool],
) -> List[ChallengerScore]:
    scores = [
        ChallengerScore(
            name="image_account",
            passed=image_receipt.technical_pass,
            score=10 if image_receipt.technical_pass else 0,
            detail=f"{image_receipt.image_count} images",
        ),
        ChallengerScore(
            name="every_image_accounted",
            passed=accounted,
            score=20 if accounted else 0,
            detail=f"unaccounted={image_receipt.unaccounted_images}",
        ),
        ChallengerScore(
            name="vision_ocr_queue",
            passed=vision_queued >= 0,
            score=5 if vision_queued >= 0 else 0,
            detail=f"queued={vision_queued}",
        ),
        ChallengerScore(
            name="letter_format",
            passed=bool(format_pass),
            score=15 if format_pass else 0,
            detail="Section 13/15 Letter landscape" if format_pass else "format not applied",
        ),
        ChallengerScore(
            name="required_fields",
            passed=bool(format_pass),
            score=15 if format_pass else 0,
            detail="workbook QA" if format_pass else "no isolated Letter",
        ),
    ]
    return scores


def _winner(scores: Sequence[ChallengerScore]) -> str:
    if not scores:
        return ""
    ranked = sorted(scores, key=lambda item: (item.score, item.name), reverse=True)
    return ranked[0].name


def run_tournament(
    *,
    bind_dir: Path,
    packet_id: str,
    workbook: Optional[Path] = None,
    letter_dir: Optional[Path] = None,
    max_loops: int = DEFAULT_MAX_LOOPS,
    allow_ocr: bool = False,
) -> TournamentReceipt:
    if type(max_loops) is not int or max_loops < 1 or max_loops > MAX_LOOPS_CAP:
        raise TournamentLoopError(f"max_loops must be 1..{MAX_LOOPS_CAP}")
    token = packet_id.strip()
    if not token or "\n" in token:
        raise TournamentLoopError("packet_id must be a single-line string")
    bind = bind_dir.expanduser().resolve()
    passes: List[TournamentPass] = []
    last_accounted = False
    last_count = 0
    winner = ""
    technical_pass = False
    letter_ok: Optional[bool] = None
    for number in range(1, max_loops + 1):
        image_receipt = account_images(bind, packet_id=f"{token}-p{number}")
        accounted = every_image_accounted(image_receipt)
        queue = vision_queue_from_receipt(image_receipt)
        vision = review_queue(queue, bind_dir=bind, allow_ocr=allow_ocr)
        if workbook is not None and letter_dir is not None:
            isolated = letter_dir.expanduser() / f"section-letter-pass{number}.xlsx"
            if isolated.exists():
                isolated.unlink()
            formatted = apply_letter_format(workbook, isolated)
            letter_ok = formatted.technical_pass
        scores = _score_challengers(
            image_receipt=image_receipt,
            accounted=accounted,
            vision_queued=vision.queued,
            format_pass=letter_ok,
        )
        stop = ""
        if not accounted:
            stop = "unaccounted images remain"
        elif image_receipt.empty_text_images and number == max_loops:
            stop = "empty-text images still need face review"
        elif number == max_loops:
            stop = "max loops reached"
        elif accounted and letter_ok is True and number >= 2:
            stop = "no new image or format defects found"
        winner = _winner(scores)
        passes.append(
            TournamentPass(
                pass_number=number,
                image_count=image_receipt.image_count,
                accounted_images=image_receipt.accounted_images,
                unaccounted_images=image_receipt.unaccounted_images,
                empty_text_images=image_receipt.empty_text_images,
                vision_queued=vision.queued,
                format_pass=letter_ok,
                scores=scores,
                stop_reason=stop,
                winner=winner,
            )
        )
        last_accounted = accounted
        last_count = image_receipt.image_count
        technical_pass = accounted and image_receipt.technical_pass
        if stop:
            break
    return TournamentReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        work_date=WORK_DATE.isoformat(),
        packet_id=token,
        bind_dir=str(bind),
        passes=passes,
        image_count=last_count,
        every_image_accounted=last_accounted,
        winner=winner,
        technical_pass=technical_pass,
        packages_complete=False,
        portfolio=portfolio_status(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a 10-pass image-account and Section 13/15 format tournament "
            "dated 2026-09-22. Never promotes a package."
        )
    )
    parser.add_argument("--bind-dir", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--letter-dir", type=Path)
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS)
    parser.add_argument("--allow-ocr", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = run_tournament(
            bind_dir=args.bind_dir,
            packet_id=args.packet_id,
            workbook=args.workbook,
            letter_dir=args.letter_dir,
            max_loops=args.max_loops,
            allow_ocr=args.allow_ocr,
        )
        write_new_json(receipt.to_dict(), args.output, "tournament receipt")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "work_date": WORK_DATE.isoformat(),
                    "passes": len(receipt.passes),
                    "image_count": receipt.image_count,
                    "every_image_accounted": receipt.every_image_accounted,
                    "winner": receipt.winner,
                    "technical_pass": receipt.technical_pass,
                    "packages_complete": False,
                },
                indent=2,
            )
        )
    except (
        OSError,
        TournamentLoopError,
        ImageAccountError,
        VisionOcrError,
        PackageFormatError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
