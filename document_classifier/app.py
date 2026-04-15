"""
app.py — Document Classifier
=============================
Streamlit application entry point.

Pipeline
--------
  1. User uploads a PDF or DOCX via the file uploader.
  2. Text is extracted by ``document_parser``.
  3. Claude classifies the document via ``classifier``.
  4. The result is appended to an Excel log by ``excel_manager``.
  5. The result is rendered in the UI with colour-coded confidence.

Run
---
  cd document_classifier
  streamlit run app.py

Environment
-----------
  ANTHROPIC_API_KEY   (required)
  LOG_LEVEL           (optional, default "INFO")
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# ── Logging — configure once at import time ────────────────────────────────────
from config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Config.LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Lazy imports (after logging is set up) ─────────────────────────────────────
from classifier import classify_document        # noqa: E402
from document_parser import extract_text        # noqa: E402
from excel_manager import append_result         # noqa: E402

# ── UI constants ───────────────────────────────────────────────────────────────

_CONF_ICON = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}
_CONF_BADGE = {
    "High":   "background:#d6ead7;color:#2d6a30;padding:3px 10px;border-radius:12px;font-weight:600",
    "Medium": "background:#fff3cd;color:#856404;padding:3px 10px;border-radius:12px;font-weight:600",
    "Low":    "background:#fadadd;color:#842029;padding:3px 10px;border-radius:12px;font-weight:600",
}

# ── Page config — must be first Streamlit call ─────────────────────────────────
st.set_page_config(
    page_title="Document Classifier",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ── Helper functions ───────────────────────────────────────────────────────────


def _check_api_key() -> bool:
    """Return True when the API key is configured; show an error otherwise."""
    if not Config.ANTHROPIC_API_KEY:
        st.error(
            "**ANTHROPIC_API_KEY is not set.**\n\n"
            "Export it before starting the app:\n"
            "```bash\nexport ANTHROPIC_API_KEY=sk-ant-...\nstreamlit run app.py\n```"
        )
        return False
    return True


def _render_header() -> None:
    st.title("📄 Document Classifier")
    st.markdown(
        "Upload a **PDF** or **DOCX** and the app will use **Claude AI** to "
        "identify the document type, summarise its content, and append the "
        "result to an Excel log automatically."
    )
    st.divider()


def _process_file(uploaded_file) -> tuple[dict, str, Path]:
    """
    Run the full extraction → classification → save pipeline.

    Args:
        uploaded_file: Streamlit ``UploadedFile`` object.

    Returns:
        ``(classification, extracted_text, excel_path)``
    """
    file_bytes: bytes = uploaded_file.read()
    filename: str = uploaded_file.name
    file_ext: str = Path(filename).suffix.lstrip(".")

    logger.info(
        "Processing upload: '%s'  size=%d bytes", filename, len(file_bytes)
    )

    with st.status("Processing document…", expanded=True) as status:

        # ── Step 1: text extraction ────────────────────────────────────────────
        st.write("🔍 **Extracting text…**")
        text: str = extract_text(file_bytes, filename)

        if not text.strip():
            raise ValueError(
                "No readable text found.  The document may be entirely "
                "image-based, password-protected, or blank."
            )

        word_count = len(text.split())
        st.write(
            f"✅ Extracted **{len(text):,}** characters "
            f"(**{word_count:,}** words)."
        )

        # ── Step 2: AI classification ──────────────────────────────────────────
        st.write("🤖 **Classifying with Claude AI…**")
        classification: dict = classify_document(text, filename)
        st.write(
            f"✅ Classified as **{classification['category']}** "
            f"({classification['confidence']} confidence)."
        )

        # ── Step 3: Excel logging ──────────────────────────────────────────────
        st.write("💾 **Appending to Excel log…**")
        excel_path: Path = append_result(filename, file_ext, classification)
        st.write(f"✅ Saved to `{excel_path}`.")

        status.update(label="Done!", state="complete", expanded=False)

    return classification, text, excel_path


def _render_results(classification: dict, text: str, excel_path: Path) -> None:
    """Render the classification results in the Streamlit UI."""

    st.subheader("Classification Results")

    # ── Metric row ─────────────────────────────────────────────────────────────
    col_category, col_confidence = st.columns([3, 2])

    with col_category:
        st.metric("Document Type", classification["category"])

    with col_confidence:
        conf = classification.get("confidence", "Unknown")
        icon = _CONF_ICON.get(conf, "⚪")
        badge_css = _CONF_BADGE.get(conf, "")
        st.markdown("**Confidence**")
        st.markdown(
            f'<span style="{badge_css}">{icon} {conf}</span>',
            unsafe_allow_html=True,
        )

    st.markdown("")  # vertical spacer

    # ── Summary ────────────────────────────────────────────────────────────────
    st.markdown("#### Summary")
    st.info(classification.get("summary", "—"))

    # ── Key topics ─────────────────────────────────────────────────────────────
    topics: list = classification.get("key_topics", [])
    if topics:
        st.markdown("#### Key Topics")
        topic_pills = "  ".join(f"`{t}`" for t in topics)
        st.markdown(topic_pills)

    # ── Reasoning (collapsible) ────────────────────────────────────────────────
    with st.expander("Classification Reasoning"):
        st.write(classification.get("reasoning", "—"))

    # ── Extracted text preview (collapsible) ──────────────────────────────────
    with st.expander("Extracted Text Preview (first 2 000 chars)"):
        preview = text[:2_000]
        st.text_area(
            label="extracted_text",
            value=preview,
            height=240,
            disabled=True,
            label_visibility="collapsed",
        )

    st.divider()
    st.success(f"Result appended to **{excel_path}**")


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    _render_header()

    if not _check_api_key():
        st.stop()

    uploaded_file = st.file_uploader(
        "Choose a document",
        type=["pdf", "docx"],
        help="Supported formats: PDF, DOCX",
    )

    if uploaded_file is None:
        st.info("⬆️ Upload a PDF or DOCX above to get started.")
        return

    try:
        classification, text, excel_path = _process_file(uploaded_file)
        _render_results(classification, text, excel_path)

    except ValueError as exc:
        # Expected user errors (bad file, no text, etc.)
        logger.warning("Validation error for '%s': %s", uploaded_file.name, exc)
        st.error(f"**Document error:** {exc}")

    except RuntimeError as exc:
        # API / IO errors with a user-friendly message
        logger.error(
            "Runtime error for '%s': %s", uploaded_file.name, exc, exc_info=True
        )
        st.error(f"**Processing error:** {exc}")

    except Exception as exc:
        # Catch-all — log full trace, show brief message
        logger.critical("Unexpected error: %s", exc, exc_info=True)
        st.error(
            f"**Unexpected error:** {exc}\n\n"
            f"Check `{Config.LOG_FILE}` for the full stack trace."
        )


if __name__ == "__main__":
    main()
