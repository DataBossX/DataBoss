"""Multi-AI tournament reviewer.

For each material document we run (at least) three independent passes:
  1. facts        -- extract facts only, no interpretation
  2. title_effect -- analyze the effect on title
  3. red_team     -- hunt for missing links, contradictions, weak assumptions

Each pass runs first as a deterministic heuristic. When the LLM is enabled, an
LLM variant of each pass also runs and is compared. We then form a consensus:
where passes agree we raise confidence; where they disagree we DO NOT force a
conclusion -- we flag it.
"""
from __future__ import annotations

from typing import List

from .models import Document, ReviewConsensus, ReviewPass
from .llm import complete_json, llm_available
from .utils import LOG


# --------------------------- heuristic passes -----------------------------
def _facts_pass(doc: Document) -> ReviewPass:
    findings = {
        "document_type": doc.document_type,
        "instrument_no": doc.instrument_no,
        "book_page": doc.book_page,
        "grantors": doc.grantors,
        "grantees": doc.grantees,
        "recording_date": doc.recording_date,
        "legal_match": bool(doc.legal.section),
    }
    present = sum(1 for v in findings.values() if v not in ("", [], None, False))
    conf = min(95.0, 30.0 + present * 9.0)
    return ReviewPass(name="facts-heuristic", role="facts",
                      document_id=doc.doc_id, findings=findings, confidence=conf)


def _title_effect_pass(doc: Document) -> ReviewPass:
    dt = doc.document_type.lower()
    effect = "Needs Review"
    if "lease" in dt and "assignment" not in dt:
        effect = "Creates leasehold/working interest in lessee; mineral owner retains royalty."
    elif "assignment" in dt:
        effect = "Transfers leasehold/ORRI from assignor to assignee."
    elif "mineral deed" in dt:
        effect = "Conveys mineral interest from grantor to grantee."
    elif "royalty deed" in dt:
        effect = "Conveys royalty interest only; no executive/working rights."
    elif "warranty" in dt or "quitclaim" in dt:
        effect = "Conveys grantor's interest (surface and/or minerals) to grantee."
    elif "release" in dt:
        effect = "Releases/extinguishes a prior lease or mortgage encumbrance."
    elif "mortgage" in dt:
        effect = "Creates a lien/encumbrance against the described interest."
    elif "probate" in dt:
        effect = "Passes decedent's interest to heirs/devisees per estate proceeding."
    conf = 70.0 if effect != "Needs Review" else 35.0
    return ReviewPass(name="title-effect-heuristic", role="title_effect",
                      document_id=doc.doc_id,
                      findings={"title_effect": effect}, confidence=conf)


def _red_team_pass(doc: Document) -> ReviewPass:
    issues: List[str] = []
    if not doc.legal.section:
        issues.append("No machine-readable legal description -- cannot confirm subject lands.")
    if not doc.grantors and not doc.grantees:
        issues.append("No parties extracted -- chain linkage uncertain.")
    if not doc.recording_date:
        issues.append("No recording date -- priority/order uncertain.")
    if not doc.instrument_no and not doc.book_page:
        issues.append("No instrument number or book/page -- cannot cross-reference index.")
    if doc.ocr_used and (doc.ocr_confidence or 0) < 60:
        issues.append(f"Low OCR confidence ({doc.ocr_confidence:.0f}); text may be unreliable.")
    if "lease" in doc.document_type.lower():
        issues.append("Do not assume lease is held by production without well/production data.")
    conf = 80.0 if issues else 60.0
    return ReviewPass(name="red-team-heuristic", role="red_team",
                      document_id=doc.doc_id,
                      findings={"issues": issues}, confidence=conf)


# ------------------------------ LLM passes --------------------------------
_LLM_SYS = (
    "You are a meticulous Oklahoma oil-and-gas title examiner. Respond ONLY "
    "with strict JSON. Never invent instrument numbers, parties, or dates. If "
    "something is not present in the text, use null. Unknown is better than wrong."
)


def _llm_pass(doc: Document, role: str) -> ReviewPass | None:
    if not llm_available():
        return None
    prompts = {
        "facts": "Extract ONLY facts present in the text. JSON keys: "
                 "document_type, instrument_no, book_page, grantors (array), "
                 "grantees (array), recording_date, execution_date, legal_description.",
        "title_effect": "Describe the effect on title in one sentence. JSON key: title_effect.",
        "red_team": "List missing links, contradictions, and weak assumptions. "
                    "JSON key: issues (array of strings).",
    }
    text = (doc.text or "")[:6000]
    data = complete_json(_LLM_SYS, f"{prompts[role]}\n\nDOCUMENT TEXT:\n{text}")
    if data is None:
        return None
    return ReviewPass(name=f"{role}-llm", role=role, document_id=doc.doc_id,
                      findings=data, confidence=72.0, engine="llm")


# ------------------------------ consensus ---------------------------------
def review_document(doc: Document) -> ReviewConsensus:
    passes: List[ReviewPass] = [
        _facts_pass(doc), _title_effect_pass(doc), _red_team_pass(doc),
    ]
    for role in ("facts", "title_effect", "red_team"):
        lp = _llm_pass(doc, role)
        if lp:
            passes.append(lp)

    disagreements: List[str] = []
    consensus: dict = {}

    # Title effect: compare heuristic vs LLM if both exist.
    te = [p for p in passes if p.role == "title_effect"]
    if len(te) > 1:
        vals = {str(p.findings.get("title_effect", "")).strip().lower() for p in te}
        if len([v for v in vals if v]) > 1:
            disagreements.append("Title-effect passes disagree -- flagged for review.")
    if te:
        consensus["title_effect"] = te[0].findings.get("title_effect", "Needs Review")

    # Facts: prefer non-empty agreement.
    facts = [p for p in passes if p.role == "facts"]
    if facts:
        consensus["facts"] = facts[0].findings

    # Issues: union of all red-team findings.
    issues: List[str] = []
    for p in passes:
        if p.role == "red_team":
            issues.extend(p.findings.get("issues", []) or [])
    consensus["issues"] = sorted(set(issues))

    agreed = not disagreements
    mean_conf = sum(p.confidence for p in passes) / len(passes)
    # Penalize confidence when passes disagree.
    final_conf = mean_conf * (1.0 if agreed else 0.7)

    return ReviewConsensus(
        document_id=doc.doc_id,
        agreed=agreed,
        consensus=consensus,
        disagreements=disagreements,
        confidence=round(final_conf, 1),
        passes=passes,
    )


def review_all(docs: List[Document]) -> List[ReviewConsensus]:
    out = []
    for d in docs:
        try:
            out.append(review_document(d))
        except Exception as exc:  # pragma: no cover
            LOG.error("Review failed for %s: %s", d.doc_id, exc)
    return out
