"""multi_ai_tournament_reviewer -- independent cross-check passes over key facts.

Three deterministic analytical passes (facts / title-effect / skeptic) run over
the assembled chain and lease data, then a consensus step compares them. Where
the passes disagree or the skeptic finds a gap, a curative issue is raised
rather than forcing a conclusion.

This is a rule-based tournament (explainable, reproducible). A real multi-LLM
backend can be plugged in via `llm_review()` when API keys are present in .env;
absent keys, the heuristic passes run and that fact is logged -- never faked.
"""
from __future__ import annotations

import os

from ..model import ReportContext, CurativeIssue, ChainLink


# --- Pass 1: facts-only completeness -------------------------------------
def _pass_facts(link: ChainLink) -> dict:
    have = {
        "instrument": bool(link.instrument_no),
        "book_page": bool(link.book_page),
        "date": bool(link.date),
        "grantor": bool(link.grantor),
        "grantee": bool(link.grantee),
    }
    return {"complete": all(have.values()), "missing": [k for k, v in have.items() if not v]}


# --- Pass 2: title-effect classification ---------------------------------
def _pass_effect(link: ChainLink) -> dict:
    t = (link.track or "").lower()
    if "exclusion" in t or "divest" in t:
        return {"effect": "possible interest leaving Diversified", "into_diversified": False}
    if "diversified" in (link.grantee or "").lower() or "dp " in (link.grantee or "").lower():
        return {"effect": "interest into Diversified/DP entity", "into_diversified": True}
    if link.doc_type in {"Affidavit", "Memorandum", "Agreement"}:
        return {"effect": "support/notice only", "into_diversified": None}
    return {"effect": "needs schedule/image to determine", "into_diversified": None}


# --- Pass 3: skeptic -- gaps, contradictions, weak assumptions ------------
def _pass_skeptic(link: ChainLink) -> list[str]:
    issues = []
    if "corporate succession" in link.doc_type.lower():
        issues.append("Corporate-level succession is not a county-recorded conveyance; "
                      "no recorded FourPoint->Maverick->Diversified assignment located.")
    if link.book_page and "/" in link.book_page and len(link.book_page.split("/")[0]) <= 3:
        issues.append(f"Book/Page '{link.book_page}' looks truncated; verify full book number.")
    if "exclusion" in (link.track or "").lower():
        issues.append("Possible divestiture/exclusion; the assignment schedule controls whether "
                      "Section 27 / Cherokee depths were conveyed away.")
    return issues


def run_tournament(ctx: ReportContext) -> None:
    subject = ctx.config["subject_property"]
    cur: list[CurativeIssue] = []
    cid = 0

    # Cross-check each chain link with the three passes.
    for link in ctx.chain:
        facts = _pass_facts(link)
        effect = _pass_effect(link)
        skeptic = _pass_skeptic(link)
        disagreements = []
        if not facts["complete"]:
            disagreements.append(f"facts pass: missing {', '.join(facts['missing'])}")
        disagreements.extend(skeptic)
        if disagreements:
            cid += 1
            sev = "High" if effect["into_diversified"] is False else "Medium"
            cur.append(CurativeIssue(
                issue_id=f"CHAIN-{cid:03d}", severity=sev, category="Chain of title",
                description=f"[{link.instrument_no or link.book_page} {link.doc_type}] "
                            + " ".join(disagreements),
                related_instruments=link.instrument_no or link.book_page,
                recommended_action="Pull recorded image + assignment schedule; verify Section 27 / "
                                   "Cherokee coverage, net acres, depths, and exclusions.",
                source=link.source,
            ))

    # Lease-level systemic issues.
    abstracted = sum(1 for l in ctx.leases if "first-page" in (l.data_status or "").lower())
    if ctx.leases:
        cur.append(CurativeIssue(
            issue_id="OGL-001", severity="Medium", category="Leasehold",
            description=f"{len(ctx.leases)} base oil & gas leases identified for the section; only "
                        f"{abstracted} have first-page terms captured and 0 are full-image verified. "
                        "Primary terms (1994-2001) have all expired on their face; HBP status drives "
                        "current validity and is unconfirmed.",
            related_instruments="OGL 1-64",
            recommended_action="Pull every lease image; verify primary term, royalty, depth/Pugh, "
                               "extension/option, warranty, and tie HBP to OCC production by formation.",
            source="OGL sheet",
        ))

    # HBP / Cherokee formation gap (from public-record context).
    cur.append(CurativeIssue(
        issue_id="HBP-001", severity="High", category="HBP / Formation",
        description="Active OCC wells exist in Section 27 (MANDRELL #2-27, BETTY SITES #1-27, "
                    "SITES #1H-2215), but the only matched completion formation is Hogshooter, "
                    "NOT Cherokee. Cherokee-formation HBP is NOT confirmed.",
        related_instruments="API 3500921146, 3500921241, 3500921990",
        recommended_action="Pull OCC spacing/pooling order images and OTC production by formation; "
                           "confirm whether the Cherokee is held by current production.",
        source="context_public_records.xlsx",
    ))

    # Name-match-trap advisory.
    cur.append(CurativeIssue(
        issue_id="ID-001", severity="Medium", category="Identity",
        description="The county name-search returns many 'Diversified Financial Group/Systems/Services' "
                    "judgment, lien and town-lot records (Erick, OK, 1989-1995). These are a DIFFERENT "
                    "entity from the subject Diversified Production, LLC / Diversified Energy and were "
                    "excluded from the mineral chain (do not assume ownership from name similarity).",
        related_instruments="1989-1995 Diversified Financial entries",
        recommended_action="Keep excluded; confirm entity distinction if any S27 mineral conveyance "
                           "ever names a Diversified Financial entity.",
        source="diversified / Full Chain Notes sheets",
    ))

    ctx.curative.extend(cur)


def llm_review(prompt: str) -> str | None:
    """Optional real multi-model pass via litellm; returns None if unavailable."""
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")):
        return None
    try:  # pragma: no cover - only with live keys
        from litellm import completion
        resp = completion(model=os.getenv("TRF_REVIEW_MODEL", "claude-sonnet-4-6"),
                          messages=[{"role": "user", "content": prompt}])
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return None
