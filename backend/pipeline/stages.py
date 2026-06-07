"""Five pipeline stages: Ingest → OCR → Extract → Reason → Report."""

import json
import os
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from .models import ChainLink, ChainOfTitle, Instrument, Job
from .ocr import extract_text, pdf_to_images


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_prompt(name: str) -> str:
    base = Path(__file__).parent.parent.parent / "prompts" / name
    if base.exists():
        return base.read_text()
    return ""


def _openai_client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY", "")
    return OpenAI(api_key=key) if key else None


def _anthropic_client():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=key) if key else None


def _gemini_model(model_name: str = "gemini-1.5-pro"):
    import google.generativeai as genai
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel(model_name)


def _call_extractor_llm(ocr_text: str) -> dict:
    """Call Claude or GPT with the canonical extractor prompt. Returns parsed JSON dict."""
    system_prompt = _load_prompt("canonical_extractor.md")
    user_msg = f"Document text:\n\n{ocr_text[:8000]}"

    # Try Claude first (best at structured extraction)
    client = _anthropic_client()
    if client:
        try:
            resp = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text
            input_tokens = resp.usage.input_tokens
            output_tokens = resp.usage.output_tokens
            # claude-opus-4-8: $15/M input, $75/M output (approximate)
            cost = (input_tokens * 15.0 + output_tokens * 75.0) / 1_000_000
            return {"parsed": json.loads(text), "cost": cost, "model": "claude-opus-4-8"}
        except Exception as e:
            logger.warning(f"Claude extractor failed: {e}")

    # Fall back to GPT-4o
    oai = _openai_client()
    if oai:
        try:
            resp = oai.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            text = resp.choices[0].message.content
            usage = resp.usage
            cost = (usage.prompt_tokens * 2.50 + usage.completion_tokens * 10.0) / 1_000_000
            return {"parsed": json.loads(text), "cost": cost, "model": "gpt-4o"}
        except Exception as e:
            logger.warning(f"GPT-4o extractor failed: {e}")

    return {"parsed": {}, "cost": 0.0, "model": "none", "error": "No LLM available"}


def _call_chain_analyzer_llm(instruments: list[Instrument], tract: Optional[str]) -> dict:
    """Send full instrument list to Gemini for chain-of-title analysis."""
    system_prompt = _load_prompt("chain_of_title_analyzer.md")
    if tract:
        system_prompt = f"Target tract: {tract}\n\n" + system_prompt

    instruments_json = json.dumps([i.to_dict() for i in instruments], indent=2)
    user_msg = f"Instruments (chronological):\n\n{instruments_json}"

    # Gemini 1.5 Pro — best for long-context chain analysis
    model = _gemini_model("gemini-1.5-pro")
    if model:
        try:
            resp = model.generate_content(
                [system_prompt, user_msg],
                generation_config={"response_mime_type": "application/json"},
            )
            return {"parsed": json.loads(resp.text), "cost": 0.002, "model": "gemini-1.5-pro"}
        except Exception as e:
            logger.warning(f"Gemini chain analyzer failed: {e}")

    # Fall back to Claude
    client = _anthropic_client()
    if client:
        try:
            resp = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text
            input_tokens = resp.usage.input_tokens
            output_tokens = resp.usage.output_tokens
            cost = (input_tokens * 15.0 + output_tokens * 75.0) / 1_000_000
            return {"parsed": json.loads(text), "cost": cost, "model": "claude-opus-4-8"}
        except Exception as e:
            logger.warning(f"Claude chain analyzer failed: {e}")

    return {"parsed": {}, "cost": 0.0, "model": "none", "error": "No LLM available"}


# ── rule-based reasoning (fast, no LLM cost) ──────────────────────────────────

def _rule_based_reason(instruments: list[Instrument], owner: Optional[str]) -> ChainOfTitle:
    """Generalized rule-based chain of title reasoning."""
    sorted_instr = sorted(
        instruments,
        key=lambda i: (i.recording_date or "0000-00-00"),
    )

    chain_links = [
        ChainLink(
            link_no=idx + 1,
            doc_no=i.doc_no,
            instrument_type=i.instrument_type,
            recording_date=i.recording_date,
            from_parties=i.grantors,
            to_parties=i.grantees,
            interest_conveyed=i.interest_conveyed,
        )
        for idx, i in enumerate(sorted_instr)
    ]

    encumbrances = []
    curative = []
    gaps = []
    status = "Unknown—needs manual"
    confidence = 0.6
    explanation = "Rule-based analysis."

    if not sorted_instr:
        return ChainOfTitle(
            chain=chain_links,
            status="Unknown—needs manual",
            confidence=0.5,
            explanation="No instruments to analyze.",
        )

    last = sorted_instr[-1]
    instr_upper = (last.instrument_type or "").upper()
    o_upper = (owner or "").upper()

    # Identify encumbrances (active leases, mortgages)
    for i in sorted_instr:
        t = (i.instrument_type or "").upper()
        if "LEASE" in t:
            encumbrances.append(
                f"O&G Lease recorded {i.recording_date} (Doc {i.doc_no}) — HBP status unknown"
            )
        elif "MORTGAGE" in t or "DEED OF TRUST" in t:
            encumbrances.append(
                f"Mortgage/DOT recorded {i.recording_date} (Doc {i.doc_no}) — check for release"
            )

    # Determine current status
    if o_upper and "LEASE" in instr_upper and o_upper in " ".join(last.grantors).upper():
        status = "Leased HBP"
        confidence = 0.7
        explanation = f"Most recent instrument is a lease naming {owner} as lessor; no later deed out recorded."
    elif o_upper and o_upper in " ".join(last.grantors).upper():
        status = "Assigned out"
        confidence = 0.85
        explanation = f"Most recent instrument shows {owner} as grantor/assignor with no later conveyance back."
    elif o_upper and o_upper in " ".join(last.grantees).upper():
        status = "Current owner of record"
        confidence = 0.85
        explanation = f"Most recent instrument shows {owner} as grantee with no later conveyance out."
    elif not o_upper:
        # No owner filter — just report last known grantee
        if last.grantees:
            status = "Current owner of record"
            confidence = 0.75
            explanation = f"Last recorded instrument names {', '.join(last.grantees)} as grantee(s)."

    current_owners = []
    if last.grantees:
        for g in last.grantees:
            current_owners.append({"name": g, "interest_type": "mineral", "fraction": None})

    # Flag curative needs
    if encumbrances:
        curative.append("Verify status of all active leases (HBP vs expired)")

    return ChainOfTitle(
        chain=chain_links,
        current_owners=current_owners,
        gaps=gaps,
        encumbrances=encumbrances,
        curative_needed=curative,
        status=status,
        confidence=confidence,
        explanation=explanation,
        reasoning_method="rule_based",
    )


# ── Stage 1: Ingest ────────────────────────────────────────────────────────────

async def run_ingest(job: Job) -> Job:
    """Validate and normalize input files."""
    job.status = "ingesting"
    job.log("ingest", "Starting ingest stage")

    valid = []
    for f in job.files:
        p = Path(f)
        if p.exists():
            valid.append(str(p.resolve()))
            job.log("ingest", f"Validated: {p.name}")
        else:
            job.log("ingest", f"File not found, skipping: {f}")

    if not valid:
        raise ValueError("No valid input files found. Upload files before starting the pipeline.")

    job.ingested_files = valid
    job.log("ingest", f"Ingest complete: {len(valid)} file(s) ready")
    return job


# ── Stage 2: OCR ──────────────────────────────────────────────────────────────

async def run_ocr(job: Job) -> Job:
    """Extract text from all ingested files using the multi-fallback OCR engine."""
    job.status = "ocr"
    job.log("ocr", f"Starting OCR on {len(job.ingested_files)} file(s)")

    results = []
    total_cost = 0.0

    for file_path in job.ingested_files:
        p = Path(file_path)
        image_paths: list[str] = []

        # Convert PDF to images for vision APIs
        if p.suffix.lower() == ".pdf":
            image_paths = pdf_to_images(file_path)
            if image_paths:
                job.log("ocr", f"PDF rendered: {p.name} → {len(image_paths)} pages")

        result = extract_text(file_path, image_paths or None)
        result["source_file"] = file_path
        results.append(result)
        total_cost += result.get("cost", 0.0)
        job.log(
            "ocr",
            f"{p.name}: method={result['method']} conf={result['confidence']} cost=${result.get('cost', 0):.4f}",
            cost=result.get("cost", 0.0),
        )

    job.ocr_results = results
    job.log("ocr", f"OCR complete. Total cost: ${total_cost:.4f}")
    return job


# ── Stage 3: Extract ───────────────────────────────────────────────────────────

async def run_extract(job: Job) -> Job:
    """Extract structured instrument data from OCR text using canonical LLM prompt."""
    job.status = "extracting"
    job.log("extract", f"Extracting fields from {len(job.ocr_results)} OCR result(s)")

    instruments: list[Instrument] = []
    total_cost = 0.0

    for ocr in job.ocr_results:
        text = ocr.get("text", "")
        if not text.strip():
            job.log("extract", f"Skipping {ocr.get('source_file', '?')} — empty OCR text")
            continue

        result = _call_extractor_llm(text)
        cost = result.get("cost", 0.0)
        total_cost += cost

        parsed = result.get("parsed", {})
        if not parsed:
            job.log("extract", f"LLM returned empty result for {ocr.get('source_file', '?')}")
            continue

        instr = Instrument(
            doc_no=parsed.get("doc_no"),
            instrument_type=parsed.get("instrument_type"),
            book=parsed.get("book"),
            page=parsed.get("page"),
            recording_date=parsed.get("recording_date"),
            instrument_date=parsed.get("instrument_date"),
            grantors=parsed.get("grantors") or [],
            grantees=parsed.get("grantees") or [],
            legal_description=parsed.get("legal_description"),
            section=parsed.get("section"),
            township=parsed.get("township"),
            range_val=parsed.get("range"),
            county=parsed.get("county") or job.county,
            state=parsed.get("state") or job.state,
            interest_conveyed=parsed.get("interest_conveyed"),
            lease_royalty_terms=parsed.get("lease_royalty_terms"),
            consideration=parsed.get("consideration"),
            reservations=parsed.get("reservations"),
            notes=parsed.get("notes"),
            confidence_score=parsed.get("confidence_score", 0.0),
            needs_review=parsed.get("needs_review", False),
            source_file=ocr.get("source_file"),
            source_url=parsed.get("source_url"),
            raw_ocr_text=text[:2000],
            ocr_method=ocr.get("method"),
            extract_cost=cost,
        )
        instruments.append(instr)
        job.log(
            "extract",
            f"Extracted: {instr.instrument_type or 'unknown'} | "
            f"Doc {instr.doc_no} | conf={instr.confidence_score:.2f} | model={result.get('model')}",
            cost=cost,
        )

    job.instruments = instruments
    job.log("extract", f"Extract complete: {len(instruments)} instrument(s). Cost: ${total_cost:.4f}")
    return job


# ── Stage 4: Reason ────────────────────────────────────────────────────────────

async def run_reason(job: Job) -> Job:
    """Build chain of title and determine ownership status."""
    job.status = "reasoning"
    job.log("reason", f"Reasoning over {len(job.instruments)} instrument(s)")

    if not job.instruments:
        job.chain = ChainOfTitle(
            status="Unknown—needs manual",
            confidence=0.0,
            explanation="No instruments extracted — cannot determine chain of title.",
        )
        job.log("reason", "No instruments — defaulting to Unknown")
        return job

    # Start with fast rule-based reasoning
    chain = _rule_based_reason(job.instruments, job.owner_name)
    job.log("reason", f"Rule-based result: {chain.status} (conf={chain.confidence})")

    # Escalate to Gemini LLM if confidence is low or too many instruments
    should_escalate = chain.confidence < 0.75 or len(job.instruments) >= 5

    if should_escalate:
        job.log("reason", "Escalating to Gemini chain analyzer (low confidence or complex chain)")
        result = _call_chain_analyzer_llm(job.instruments, job.tract_description)
        cost = result.get("cost", 0.0)

        if result.get("parsed"):
            p = result["parsed"]
            # Rebuild chain from LLM result
            llm_chain_links = [
                ChainLink(
                    link_no=lnk.get("link_no", i + 1),
                    doc_no=lnk.get("doc_no"),
                    instrument_type=lnk.get("instrument_type"),
                    recording_date=lnk.get("recording_date"),
                    from_parties=lnk.get("from", []),
                    to_parties=lnk.get("to", []),
                    interest_conveyed=lnk.get("interest_conveyed"),
                    fraction=lnk.get("fraction"),
                )
                for i, lnk in enumerate(p.get("chain", []))
            ]
            chain = ChainOfTitle(
                chain=llm_chain_links,
                current_owners=p.get("current_owners", chain.current_owners),
                gaps=p.get("gaps", []),
                encumbrances=p.get("encumbrances", chain.encumbrances),
                curative_needed=p.get("curative_needed", chain.curative_needed),
                status=p.get("status", chain.status),
                confidence=p.get("confidence", chain.confidence),
                explanation=p.get("explanation", chain.explanation),
                title_opinion_notes=p.get("title_opinion_notes"),
                reasoning_method=f"llm:{result.get('model', 'gemini')}",
                reasoning_cost=cost,
            )
            job.log(
                "reason",
                f"LLM result: {chain.status} (conf={chain.confidence}) model={result.get('model')}",
                cost=cost,
            )
        else:
            job.log("reason", "LLM chain analyzer returned no result — using rule-based output")

    job.chain = chain
    job.log("reason", f"Reasoning complete: {chain.status}")
    return job


# ── Stage 5: Report ────────────────────────────────────────────────────────────

async def run_report(job: Job) -> Job:
    """Generate landman run sheet (JSON + Excel)."""
    from ..reports.landman_report import generate_report

    job.status = "reporting"
    job.log("report", "Generating landman report")

    report_json, report_path = generate_report(job)
    job.report_json = report_json
    job.report_path = report_path
    job.log("report", f"Report saved: {report_path}")
    return job
