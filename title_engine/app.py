"""
DataBoss Title Engine — Streamlit Application
Section 27-11N-25W, Beckham County, Oklahoma

Screens:
  1. API Setup
  2. Dry-Run Search
  3. Cost Estimate & Approval
  4. Download Documents
  5. OCR / Extraction
  6. Chain Dashboard
  7. Missing Documents
  8. Export Workbook / Report
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Allow "from title_engine.xxx import" regardless of working directory
_here = Path(__file__).resolve().parent
_parent = _here.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
from dotenv import load_dotenv

# ── Bootstrap ─────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Must be first Streamlit call
st.set_page_config(
    page_title="DataBoss Title Engine",
    page_icon="🛢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Lazy imports (after streamlit is initialized) ─────────────────────────────

@st.cache_resource
def _get_db_path() -> Path:
    out = Path(os.getenv("OUTPUT_DIR", "output"))
    out.mkdir(parents=True, exist_ok=True)
    return out / "title_engine.db"


def _init_db():
    from title_engine import db as DB  # noqa: PLC0415
    DB.init_db(_get_db_path())
    return DB


# ── Constants ─────────────────────────────────────────────────────────────────

COUNTY      = os.getenv("COUNTY", "Beckham")
SECTION     = "27"
TOWNSHIP    = "11N"
RANGE_      = "25W"
OUTPUT_DIR  = Path(os.getenv("OUTPUT_DIR", "output"))
PDF_DIR     = OUTPUT_DIR / "pdfs"
REPORT_DIR  = OUTPUT_DIR / "reports"
PRICE_PER_IMAGE = 0.10   # USD per downloaded image (estimate)

SCREEN_NAMES = [
    "1. API Setup",
    "2. Dry-Run Search",
    "3. Cost Estimate",
    "4. Download Documents",
    "5. OCR / Extraction",
    "6. Chain Dashboard",
    "7. Missing Documents",
    "8. Export",
]

# ── Session state helpers ─────────────────────────────────────────────────────

def _ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _set(key, value):
    st.session_state[key] = value


# ── Sidebar navigation ────────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Oklahoma_state_seal.svg/240px-Oklahoma_state_seal.svg.png",
                 width=60)
        st.markdown("## DataBoss Title Engine")
        st.caption(f"Section {SECTION}-{TOWNSHIP}-{RANGE_} | {COUNTY} Co., OK")
        st.markdown("---")

        current = _ss("screen", 0)
        for i, name in enumerate(SCREEN_NAMES):
            if st.button(name, key=f"nav_{i}",
                         type="primary" if current == i else "secondary",
                         use_container_width=True):
                _set("screen", i)
                st.rerun()

        st.markdown("---")
        # Show live stats if DB is available
        try:
            DB = _init_db()
            stats = DB.get_stats()
            st.metric("Instruments", stats["total"])
            st.metric("Downloaded", stats["dl_done"])
            st.metric("Total Cost", f"${stats['total_cost']:.4f}")
        except Exception:
            st.caption("DB not initialized")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 1 — API Setup
# ══════════════════════════════════════════════════════════════════════════════

def screen_api_setup():
    st.title("API Setup")
    st.markdown("""
Configure your API credentials. The key is **never hardcoded** — it is read from
your `.env` file or entered below and stored only in this session.
""")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("OKCountyRecords API")
        env_key = os.getenv("OKCOUNTYRECORDS_API_KEY", "")
        key_display = (env_key[:4] + "..." + env_key[-4:]) if len(env_key) > 8 else ("SET" if env_key else "NOT SET")
        st.info(f"Key from .env: **{key_display}**")

        manual_key = st.text_input(
            "Override API Key (session only, not saved to disk)",
            type="password",
            placeholder="Leave blank to use .env key",
        )
        if manual_key:
            _set("okcr_api_key", manual_key)
            st.success("Session key set.")
        elif env_key:
            _set("okcr_api_key", env_key)

        st.markdown("**Test connection:**")
        if st.button("Test OKCR Connection"):
            api_key = _ss("okcr_api_key") or env_key
            if not api_key:
                st.error("No API key configured.")
            else:
                with st.spinner("Testing…"):
                    try:
                        from title_engine.okcr_api import OKCRClient
                        client = OKCRClient(api_key)
                        hits = client.search(q="27-11N-25W", county=COUNTY, max_results=1)
                        st.success(f"Connected — got {len(hits)} result(s) on test query.")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")

    with col2:
        st.subheader("Claude AI (optional)")
        env_ai = os.getenv("ANTHROPIC_API_KEY", "")
        ai_display = ("SET" if env_ai else "NOT SET")
        st.info(f"Anthropic key from .env: **{ai_display}**")
        st.caption("Used for Claude-vision OCR fallback and AI-enhanced field extraction.")

        auto_approve = st.checkbox(
            "AUTO_APPROVE_COST (skip manual approval gate)",
            value=os.getenv("AUTO_APPROVE_COST", "false").lower() == "true",
        )
        _set("auto_approve", auto_approve)

        max_cost = st.number_input(
            "MAX_COST_USD (auto-approve only if cost ≤ this)",
            min_value=0.0, max_value=10000.0,
            value=float(os.getenv("MAX_COST_USD", "50.0")),
            step=5.0,
        )
        _set("max_cost_usd", max_cost)

    st.markdown("---")
    st.subheader("Output Directory")
    st.code(str(OUTPUT_DIR.resolve()))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if st.button("Initialize Database", type="primary"):
        try:
            DB = _init_db()
            st.success(f"Database ready: {_get_db_path()}")
            st.json(DB.get_stats())
        except Exception as e:
            st.error(f"DB init failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 2 — Dry-Run Search
# ══════════════════════════════════════════════════════════════════════════════

def screen_dry_run():
    st.title("Dry-Run Search")
    st.markdown("""
Run **all** configured searches against the OKCountyRecords index without
downloading any images. Results are saved to the local database.

Includes:
- 6 legal description queries
- 20 quarter / quarter-quarter queries
- 28 named-entity queries (both grantor and grantee sides)
- Dynamic follow-up for every discovered party
""")

    api_key = _ss("okcr_api_key") or os.getenv("OKCOUNTYRECORDS_API_KEY", "")
    if not api_key:
        st.error("Set your API key on the **API Setup** screen first.")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Search Configuration")
        run_legal   = st.checkbox("Legal description queries",  value=True)
        run_quarter = st.checkbox("Quarter / Quarter-quarter",  value=True)
        run_entity  = st.checkbox("Named entity queries",       value=True)
        run_dynamic = st.checkbox("Dynamic chaining (follow-up per party)", value=True)

    with col2:
        st.subheader("Stats")
        try:
            DB = _init_db()
            stats = DB.get_stats()
            st.metric("Instruments", stats["total"])
            st.metric("Searches done", stats["searches_done"])
            st.metric("Entity queue", stats["entity_pending"])
        except Exception:
            st.caption("DB not ready")

    if st.button("Run Dry-Run Search", type="primary"):
        DB = _init_db()
        from title_engine.okcr_api import OKCRClient
        from title_engine.search_matrix import (
            LEGAL_QUERIES, QUARTER_QUERIES, ENTITY_QUERIES, build_dynamic_query
        )

        client = OKCRClient(api_key)
        queries: List[Dict] = []
        if run_legal:   queries += LEGAL_QUERIES
        if run_quarter: queries += QUARTER_QUERIES
        if run_entity:  queries += ENTITY_QUERIES

        progress_bar = st.progress(0)
        log_box = st.empty()
        status_box = st.empty()
        new_total = 0
        log_lines: List[str] = []

        def _log(msg: str):
            log_lines.append(msg)
            log_box.code("\n".join(log_lines[-40:]))

        for i, qd in enumerate(queries):
            q_text = qd.get("q") or str(qd)
            if DB.search_already_done(q_text, COUNTY):
                _log(f"SKIP (already done): {q_text[:60]}")
                progress_bar.progress((i + 1) / max(len(queries), 1))
                continue

            try:
                hits = client.search_all(
                    q=qd.get("q"),
                    county=COUNTY,
                    grantor=qd.get("grantor"),
                    grantee=qd.get("grantee"),
                    section=qd.get("section"),
                    township=qd.get("township"),
                    range_=qd.get("range_"),
                )
                count = 0
                for h in hits:
                    _, is_new = DB.upsert_instrument(h.to_dict())
                    if is_new:
                        count += 1
                        new_total += 1
                        # Queue grantor/grantee for dynamic follow-up
                        if run_dynamic:
                            for pname in (h.grantor_names or []):
                                DB.add_to_entity_queue(pname, "grantor", h.dedup_key)
                            for pname in (h.grantee_names or []):
                                DB.add_to_entity_queue(pname, "grantee", h.dedup_key)

                DB.mark_search_done(q_text, COUNTY, qd.get("type", ""), len(hits))
                DB.log_research("search", f"{qd.get('type','')} | {q_text[:60]} | {len(hits)} hits ({count} new)")
                _log(f"OK [{qd.get('type','')}] {q_text[:55]} → {len(hits)} hits, {count} new")
            except Exception as e:
                _log(f"ERROR: {q_text[:55]} — {e}")

            progress_bar.progress((i + 1) / max(len(queries), 1))

        # Dynamic chaining
        if run_dynamic:
            pending = DB.fetch_all(
                "SELECT entity_name, entity_type FROM entity_queue WHERE search_status='pending' LIMIT 500"
            )
            _log(f"\nDynamic chaining: {len(pending)} entities queued…")
            for ent in pending:
                dqs = build_dynamic_query(ent["entity_name"], ent["entity_type"])
                for dq in dqs:
                    q_text = dq.get("q") or str(dq)
                    if DB.search_already_done(q_text, COUNTY):
                        continue
                    try:
                        hits = client.search_all(
                            q=dq.get("q"),
                            county=COUNTY,
                            grantor=dq.get("grantor"),
                            grantee=dq.get("grantee"),
                        )
                        count = sum(1 for h in hits if DB.upsert_instrument(h.to_dict())[1])
                        new_total += count
                        DB.mark_search_done(q_text, COUNTY, "dynamic", len(hits))
                        if count:
                            _log(f"  DYN [{ent['entity_name'][:30]}] → {len(hits)} hits, {count} new")
                    except Exception as e:
                        _log(f"  DYN ERROR [{ent['entity_name'][:30]}]: {e}")

                DB.execute(
                    "UPDATE entity_queue SET search_status='done' WHERE entity_name=?",
                    (ent["entity_name"],)
                )

        status_box.success(f"Dry-run complete. {new_total} new instruments added to database.")
        _set("dry_run_done", True)

    # Show current index
    try:
        DB = _init_db()
        rows = DB.fetch_all(
            "SELECT instrument_type, doc_date, recording_date, grantor, grantee, "
            "book, page, instrument_number, download_status "
            "FROM instruments ORDER BY recording_date DESC LIMIT 200"
        )
        if rows:
            st.subheader(f"Index — {len(rows)} most recent instruments")
            st.dataframe(rows, use_container_width=True)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Screen 3 — Cost Estimate & Approval
# ══════════════════════════════════════════════════════════════════════════════

def screen_cost_estimate():
    st.title("Cost Estimate")
    st.markdown("""
Before downloading any images, review the cost estimate and approve or cancel.

**NO images are downloaded until you explicitly click Approve.**
""")

    try:
        DB = _init_db()
        stats = DB.get_stats()
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    api_key = _ss("okcr_api_key") or os.getenv("OKCOUNTYRECORDS_API_KEY", "")
    if not api_key:
        st.error("Set your API key on the **API Setup** screen first.")
        return

    pending = DB.fetch_all(
        "SELECT id, instrument_type, doc_date, grantor, grantee, book, page, instrument_number, image_url "
        "FROM instruments WHERE download_status='pending' AND image_url IS NOT NULL"
    )

    n_pending = len(pending)

    try:
        from title_engine.okcr_api import OKCRClient
        client = OKCRClient(api_key)
        est = client.estimate_cost(n_pending)
    except Exception:
        est = {"count": n_pending, "estimated_usd": n_pending * PRICE_PER_IMAGE}

    col1, col2, col3 = st.columns(3)
    col1.metric("Images with download URLs", n_pending)
    col2.metric("Estimated cost", f"${est['estimated_usd']:.2f}")
    col3.metric("Already spent", f"${stats['okcr_cost']:.4f}")

    auto_approve = _ss("auto_approve", False)
    max_cost = _ss("max_cost_usd", 50.0)

    if auto_approve and est["estimated_usd"] <= max_cost:
        st.success(
            f"AUTO-APPROVE: cost ${est['estimated_usd']:.2f} is within limit ${max_cost:.2f}."
        )
        _set("download_approved", True)
    else:
        if auto_approve:
            st.warning(
                f"AUTO-APPROVE configured, but estimated cost ${est['estimated_usd']:.2f} "
                f"exceeds limit ${max_cost:.2f}. Manual approval required."
            )
        st.info("Review the breakdown below, then approve or cancel.")

    with st.expander("Show pending download list"):
        st.dataframe(pending[:100], use_container_width=True)
        if len(pending) > 100:
            st.caption(f"… and {len(pending) - 100} more")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("APPROVE DOWNLOADS", type="primary", use_container_width=True):
            _set("download_approved", True)
            st.success("Downloads approved. Go to **Download Documents** screen.")
    with c2:
        if st.button("CANCEL — Do not download", type="secondary", use_container_width=True):
            _set("download_approved", False)
            st.info("Downloads cancelled.")

    if _ss("download_approved"):
        st.success("Downloads are currently APPROVED.")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 4 — Download Documents
# ══════════════════════════════════════════════════════════════════════════════

def screen_download():
    st.title("Download Documents")

    if not _ss("download_approved"):
        st.warning("Downloads not yet approved. Go to **Cost Estimate** screen and approve first.")
        return

    api_key = _ss("okcr_api_key") or os.getenv("OKCOUNTYRECORDS_API_KEY", "")
    if not api_key:
        st.error("Set your API key on the **API Setup** screen first.")
        return

    DB = _init_db()

    pending = DB.fetch_all(
        "SELECT id, instrument_number, book, page, instrument_type, image_url "
        "FROM instruments WHERE download_status='pending' AND image_url IS NOT NULL"
    )

    st.metric("Images to download", len(pending))

    if not pending:
        st.success("No pending downloads — all images already downloaded or no image URLs found.")
        return

    batch_size = st.number_input("Batch size per run", min_value=1, max_value=500, value=50)

    if st.button("Start Downloading", type="primary"):
        from title_engine.okcr_api import OKCRClient
        from title_engine.excel_writer import clean_filename

        client = OKCRClient(api_key)
        PDF_DIR.mkdir(parents=True, exist_ok=True)

        progress = st.progress(0)
        log_box  = st.empty()
        log_lines: List[str] = []

        def _log(msg: str):
            log_lines.append(msg)
            log_box.code("\n".join(log_lines[-40:]))

        batch = pending[:batch_size]
        ok = skipped = failed = 0

        for i, row in enumerate(batch):
            fname = clean_filename(
                inst_type=row.get("instrument_type", "UNKNOWN"),
                grantor="",
                grantee="",
                book=row.get("book", ""),
                page=row.get("page", ""),
                inst_no=row.get("instrument_number", ""),
            )
            dest = PDF_DIR / fname

            if dest.exists():
                DB.execute(
                    "UPDATE instruments SET download_status='downloaded', local_pdf=? WHERE id=?",
                    (str(dest), row["id"])
                )
                skipped += 1
                _log(f"SKIP (exists): {fname}")
            else:
                try:
                    result = client.download_image(row["image_url"], dest)
                    if result.success:
                        DB.execute(
                            "UPDATE instruments SET download_status='downloaded', "
                            "local_pdf=?, local_pdf_size=? WHERE id=?",
                            (str(result.local_path), result.file_size, row["id"])
                        )
                        DB.log_cost("okcr", PRICE_PER_IMAGE, f"Download {fname}")
                        ok += 1
                        _log(f"OK: {fname} ({result.file_size:,} bytes)")
                    else:
                        DB.execute(
                            "UPDATE instruments SET download_status='failed' WHERE id=?",
                            (row["id"],)
                        )
                        failed += 1
                        _log(f"FAIL: {fname} — {result.error}")
                except Exception as e:
                    failed += 1
                    _log(f"ERROR: {row.get('instrument_number','')} — {e}")

            progress.progress((i + 1) / len(batch))
            time.sleep(0.05)  # gentle rate limiting

        st.success(f"Done: {ok} downloaded, {skipped} skipped, {failed} failed.")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 5 — OCR / Extraction
# ══════════════════════════════════════════════════════════════════════════════

def screen_ocr():
    st.title("OCR / Extraction")
    st.markdown("""
Extract text from downloaded PDFs (pdfplumber → Tesseract → Claude vision),
then run field extraction to populate the title chain.
""")

    DB = _init_db()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    use_claude = st.checkbox("Use Claude vision for scanned fallback", value=bool(anthropic_key))
    use_ai_extract = st.checkbox("Use Claude AI for enhanced field extraction", value=bool(anthropic_key))

    stats = DB.get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Downloaded", stats["dl_done"])
    col2.metric("OCR done",   stats["ocr_done"])
    col3.metric("Extracted",  stats["ext_done"])

    if st.button("Run OCR + Extraction", type="primary"):
        from title_engine.ocr_engine import ocr_pdf
        from title_engine.title_extractor import extract_from_text, extract_with_claude

        pending_ocr = DB.fetch_all(
            "SELECT id, local_pdf, instrument_number FROM instruments "
            "WHERE download_status='downloaded' AND ocr_status='pending'"
        )

        st.info(f"{len(pending_ocr)} instruments queued for OCR…")
        progress = st.progress(0)
        log_box = st.empty()
        log_lines: List[str] = []

        def _log(msg):
            log_lines.append(msg)
            log_box.code("\n".join(log_lines[-40:]))

        for i, row in enumerate(pending_ocr):
            pdf_path = Path(row["local_pdf"])
            if not pdf_path.exists():
                DB.execute("UPDATE instruments SET ocr_status='failed' WHERE id=?", (row["id"],))
                _log(f"MISSING PDF: {pdf_path.name}")
                continue
            try:
                text, method = ocr_pdf(
                    pdf_path,
                    anthropic_key=anthropic_key if use_claude else None,
                )
                DB.execute(
                    "UPDATE instruments SET ocr_status='done', ocr_text_path=? WHERE id=?",
                    (str(pdf_path.with_suffix(".txt")), row["id"])
                )
                _log(f"OCR [{method}]: {pdf_path.name[:50]}")
            except Exception as e:
                DB.execute("UPDATE instruments SET ocr_status='failed' WHERE id=?", (row["id"],))
                _log(f"OCR ERROR: {pdf_path.name[:50]} — {e}")
            progress.progress((i + 1) / max(len(pending_ocr), 1))

        # Extraction pass
        pending_ext = DB.fetch_all(
            "SELECT id, ocr_text_path, instrument_type, instrument_number "
            "FROM instruments WHERE ocr_status='done' AND extraction_status='pending'"
        )
        _log(f"\n{len(pending_ext)} instruments queued for field extraction…")

        for i, row in enumerate(pending_ext):
            txt_path = Path(row["ocr_text_path"] or "")
            if not txt_path.exists():
                continue
            text = txt_path.read_text(encoding="utf-8", errors="replace")
            try:
                if use_ai_extract and anthropic_key:
                    ext = extract_with_claude(text, anthropic_key)
                else:
                    ext = extract_from_text(text)

                DB.execute(
                    "UPDATE instruments SET extraction_status='done', extracted_json=?, "
                    "confidence=?, section_27=?, aol_flag=? WHERE id=?",
                    (
                        json.dumps(ext.__dict__),
                        ext.confidence,
                        1 if ext.section_27 else 0,
                        1 if ext.aol_flag else 0,
                        row["id"],
                    )
                )
                _log(f"EXT: {row.get('instrument_number','?')} conf={ext.confidence:.2f}")
            except Exception as e:
                DB.execute("UPDATE instruments SET extraction_status='failed' WHERE id=?", (row["id"],))
                _log(f"EXT ERROR: {row.get('instrument_number','?')} — {e}")

        st.success("OCR and extraction pass complete.")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 6 — Chain Dashboard
# ══════════════════════════════════════════════════════════════════════════════

def screen_chain_dashboard():
    st.title("Chain Dashboard")

    try:
        DB = _init_db()
        instruments = DB.fetch_all("SELECT * FROM instruments ORDER BY recording_date")
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not instruments:
        st.warning("No instruments in database. Run Dry-Run Search first.")
        return

    from title_engine.chain_builder import ChainBuilder

    builder = ChainBuilder(instruments).build()

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Leases",      len(builder.lease_rows))
    col2.metric("Assignments", len(builder.asgn_rows))
    col3.metric("Mineral",     len(builder.mineral_rows))
    col4.metric("Gaps",        len(builder.gaps),   delta_color="inverse")
    col5.metric("Diversified", len(builder.diversified_rows))

    chain_ok = len(builder.gaps) == 0 and len(builder.missing) == 0
    if chain_ok:
        st.success("No chain gaps detected.")
    else:
        st.error(f"{len(builder.gaps)} chain gap(s) and {len(builder.missing)} missing instrument(s) detected. See Missing Documents screen.")

    tab1, tab2, tab3, tab4 = st.tabs(["Lease Chain", "Assignments", "Mineral Deeds", "Diversified"])

    def _rows_df(rows):
        return [
            {
                "Instrument #": r.instrument_number,
                "Type": r.instrument_type,
                "Date": r.recording_date,
                "Grantor/Lessor": r.grantor if r.grantor != "UNKNOWN" else r.lessor,
                "Grantee/Lessee": r.grantee if r.grantee != "UNKNOWN" else r.lessee,
                "Book": r.book,
                "Page": r.page,
                "Royalty": r.royalty,
                "Acres": r.gross_acres,
                "Status": r.chain_status,
                "Confidence": r.confidence,
            }
            for r in rows
        ]

    with tab1:
        df = _rows_df(builder.lease_rows)
        if df:
            st.dataframe(df, use_container_width=True)
        else:
            st.caption("No lease instruments.")

    with tab2:
        df = _rows_df(builder.asgn_rows)
        if df:
            st.dataframe(df, use_container_width=True)
        else:
            st.caption("No assignment instruments.")

    with tab3:
        df = _rows_df(builder.mineral_rows)
        if df:
            st.dataframe(df, use_container_width=True)
        else:
            st.caption("No mineral deed instruments.")

    with tab4:
        df = _rows_df(builder.diversified_rows)
        if df:
            st.dataframe(df, use_container_width=True)
        else:
            st.caption("No Diversified Energy instruments identified.")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 7 — Missing Documents
# ══════════════════════════════════════════════════════════════════════════════

def screen_missing_docs():
    st.title("Missing Documents")

    try:
        DB = _init_db()
        instruments = DB.fetch_all("SELECT * FROM instruments")
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not instruments:
        st.warning("No instruments in database yet.")
        return

    from title_engine.chain_builder import ChainBuilder

    builder = ChainBuilder(instruments).build()

    st.subheader("Chain Gaps")
    if builder.gaps:
        st.error(f"{len(builder.gaps)} gap(s) identified")
        gap_data = [
            {
                "Instrument": g["instrument_number"],
                "Book": g["book"],
                "Page": g["page"],
                "Assignor": g["assignor"],
                "Problem": g["problem"],
                "Curative Action": g["curative"],
            }
            for g in builder.gaps
        ]
        st.dataframe(gap_data, use_container_width=True)
    else:
        st.success("No chain gaps detected.")

    st.subheader("Referenced but Missing Instruments")
    if builder.missing:
        st.warning(f"{len(builder.missing)} missing instrument(s)")
        miss_data = [
            {
                "Missing Instrument": m.get("missing_instrument", ""),
                "Referenced In": m.get("referenced_in", ""),
                "Type": m.get("type", ""),
                "Priority": m.get("priority", ""),
                "Action": m.get("curative", ""),
            }
            for m in builder.missing
        ]
        st.dataframe(miss_data, use_container_width=True)
    else:
        st.success("No missing instrument references detected.")

    st.subheader("Instruments Needing Review")
    needs_review = DB.fetch_all(
        "SELECT instrument_number, instrument_type, doc_date, grantor, grantee, "
        "confidence, download_status, extraction_status "
        "FROM instruments WHERE needs_review=1"
    )
    if needs_review:
        st.dataframe(needs_review, use_container_width=True)
    else:
        st.success("No instruments flagged for manual review.")


# ══════════════════════════════════════════════════════════════════════════════
# Screen 8 — Export
# ══════════════════════════════════════════════════════════════════════════════

def screen_export():
    st.title("Export Workbook & Report")

    try:
        DB = _init_db()
        instruments = DB.fetch_all("SELECT * FROM instruments")
        stats = DB.get_stats()
        research_log = DB.fetch_all("SELECT action, detail, created_at FROM research_log ORDER BY id")
        search_matrix = DB.fetch_all("SELECT search_type, query, county, result_count, status, ran_at FROM search_log")
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not instruments:
        st.warning("No instruments to export. Run the search pipeline first.")
        return

    from title_engine.chain_builder import ChainBuilder

    builder = ChainBuilder(instruments).build()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total instruments", len(instruments))
    col2.metric("Chain rows", len(builder.all_rows))
    col3.metric("Curative items", len(builder.curative_rows))

    # Excel export
    st.subheader("Excel Workbook (13 sheets)")
    today = __import__("datetime").date.today().strftime("%Y-%m-%d")
    xlsx_name = f"Beckham_27_11N_25W_TitleChain_{today}.xlsx"
    xlsx_path = REPORT_DIR / xlsx_name

    if st.button("Generate Excel Workbook", type="primary"):
        with st.spinner("Writing workbook…"):
            try:
                from title_engine.excel_writer import write_workbook
                write_workbook(
                    out_path=xlsx_path,
                    instruments=instruments,
                    chain=builder,
                    stats=stats,
                    log_entries=research_log,
                    search_log=search_matrix,
                )
                st.success(f"Workbook written: {xlsx_path}")
                _set("xlsx_path", str(xlsx_path))
            except Exception as e:
                st.error(f"Excel error: {e}")
                import traceback
                st.code(traceback.format_exc())

    if _ss("xlsx_path") and Path(_ss("xlsx_path")).exists():
        with open(_ss("xlsx_path"), "rb") as f:
            st.download_button(
                "Download Excel File",
                data=f,
                file_name=xlsx_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.markdown("---")

    # Narrative report
    st.subheader("Narrative Title Report (TXT)")
    report_name = f"Beckham_27_11N_25W_Report_{today}.txt"
    report_path = REPORT_DIR / report_name

    if st.button("Generate Narrative Report"):
        with st.spinner("Writing report…"):
            try:
                from title_engine.report_writer import write_report
                write_report(builder, stats, report_path)
                st.success(f"Report written: {report_path}")
                _set("report_path", str(report_path))
            except Exception as e:
                st.error(f"Report error: {e}")

    if _ss("report_path") and Path(_ss("report_path")).exists():
        report_text = Path(_ss("report_path")).read_text(encoding="utf-8")
        with st.expander("Preview report"):
            st.text(report_text[:5000] + ("\n…[truncated]" if len(report_text) > 5000 else ""))
        st.download_button(
            "Download Report TXT",
            data=report_text,
            file_name=report_name,
            mime="text/plain",
        )

    st.markdown("---")
    st.subheader("Research Log")
    if research_log:
        st.dataframe(research_log[-100:], use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# Main router
# ══════════════════════════════════════════════════════════════════════════════

SCREENS = [
    screen_api_setup,
    screen_dry_run,
    screen_cost_estimate,
    screen_download,
    screen_ocr,
    screen_chain_dashboard,
    screen_missing_docs,
    screen_export,
]


def main():
    _sidebar()
    screen_idx = _ss("screen", 0)
    SCREENS[screen_idx]()


if __name__ == "__main__":
    main()
