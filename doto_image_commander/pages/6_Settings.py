"""Page 6 – API key management, path configuration, and diagnostics."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from core.config import config, ensure_dirs
from core.security import encrypt, decrypt

st.set_page_config(page_title="Settings — DOTO Image Commander", layout="wide")
st.title("⚙️ Settings")

st.info(
    "API keys entered here are written to environment variables for the current session. "
    "To persist across restarts, add them to your `.env` file in the project root. "
    "Keys are never logged or displayed in plain text after entry."
)

# ── OKCountyRecords ──────────────────────────────────────────────────────────
st.header("OKCountyRecords API")

current_ok = os.getenv("OKCOUNTY_API_KEY", "")
ok_configured = bool(current_ok and current_ok != "your_api_key_here")

col1, col2 = st.columns([3, 1])
with col1:
    new_ok_key = st.text_input(
        "OKCountyRecords API Key",
        type="password",
        placeholder="Enter API key...",
        help="Obtain from your OKCountyRecords account dashboard.",
    )
with col2:
    st.write("")
    st.write("")
    st.write("Status:", "✅ Configured" if ok_configured else "❌ Not set")

col_a, col_b, col_c = st.columns(3)
with col_a:
    new_base_url = st.text_input(
        "API Base URL",
        value=config.OKCOUNTY_API_BASE_URL,
        help="Override if using a staging environment.",
    )
with col_b:
    new_cost_image = st.number_input(
        "Cost per Image ($)",
        value=config.OKCOUNTY_COST_PER_IMAGE,
        min_value=0.0, step=0.01, format="%.2f",
    )
with col_c:
    new_cost_search = st.number_input(
        "Cost per Search ($)",
        value=config.OKCOUNTY_COST_PER_SEARCH,
        min_value=0.0, step=0.01, format="%.2f",
    )

if st.button("Save OKCountyRecords Settings", type="primary"):
    if new_ok_key.strip():
        os.environ["OKCOUNTY_API_KEY"] = new_ok_key.strip()
        from api.okcounty import client as ok_client
        ok_client.reload_key()
    os.environ["OKCOUNTY_API_BASE_URL"] = new_base_url.strip()
    os.environ["OKCOUNTY_COST_PER_IMAGE"] = str(new_cost_image)
    os.environ["OKCOUNTY_COST_PER_SEARCH"] = str(new_cost_search)
    config.OKCOUNTY_API_BASE_URL = new_base_url.strip()
    config.OKCOUNTY_COST_PER_IMAGE = new_cost_image
    config.OKCOUNTY_COST_PER_SEARCH = new_cost_search
    st.success("OKCountyRecords settings saved for this session.")
    st.code(
        f"# Add to your .env file to persist:\n"
        f"OKCOUNTY_API_KEY=<your key>\n"
        f"OKCOUNTY_API_BASE_URL={new_base_url}\n"
        f"OKCOUNTY_COST_PER_IMAGE={new_cost_image}\n"
        f"OKCOUNTY_COST_PER_SEARCH={new_cost_search}"
    )

st.divider()

# ── OpenAI ────────────────────────────────────────────────────────────────────
st.header("OpenAI API")

openai_configured = bool(os.getenv("OPENAI_API_KEY", ""))

col1, col2 = st.columns([3, 1])
with col1:
    new_openai_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="Obtain from platform.openai.com",
    )
with col2:
    st.write("")
    st.write("")
    st.write("Status:", "✅ Configured" if openai_configured else "❌ Not set")

col_d, col_e = st.columns(2)
with col_d:
    new_model = st.selectbox(
        "Model",
        ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision-preview"],
        index=0,
    )
with col_e:
    new_max_tokens = st.number_input(
        "Max Tokens per Call",
        value=config.OPENAI_MAX_TOKENS,
        min_value=512, max_value=16384, step=256,
    )

if st.button("Save OpenAI Settings", type="primary"):
    if new_openai_key.strip():
        os.environ["OPENAI_API_KEY"] = new_openai_key.strip()
        from api.openai_client import analyzer
        analyzer.reload_key()
    os.environ["OPENAI_MODEL"] = new_model
    os.environ["OPENAI_MAX_TOKENS"] = str(new_max_tokens)
    config.OPENAI_MODEL = new_model
    config.OPENAI_MAX_TOKENS = new_max_tokens
    st.success("OpenAI settings saved for this session.")
    st.code(
        f"# Add to your .env file to persist:\n"
        f"OPENAI_API_KEY=<your key>\n"
        f"OPENAI_MODEL={new_model}\n"
        f"OPENAI_MAX_TOKENS={new_max_tokens}"
    )

st.divider()

# ── Storage paths ─────────────────────────────────────────────────────────────
st.header("Storage Paths")

col1, col2, col3 = st.columns(3)
with col1:
    st.text_input("Downloads Directory", value=str(config.DOWNLOADS_DIR), disabled=True)
with col2:
    st.text_input("Images Directory", value=str(config.IMAGES_DIR), disabled=True)
with col3:
    st.text_input("Reports Directory", value=str(config.REPORTS_DIR), disabled=True)

st.caption(
    "To change paths, update `DOWNLOADS_DIR`, `IMAGES_DIR`, `REPORTS_DIR` in your `.env` file "
    "and restart the app."
)

if st.button("Create/Verify Directories"):
    ensure_dirs()
    for d in (config.DOWNLOADS_DIR, config.IMAGES_DIR, config.REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
        exists = "✅" if d.exists() else "❌"
        st.write(f"{exists} `{d}`")

st.divider()

# ── .env file helper ──────────────────────────────────────────────────────────
st.header(".env File Helper")
st.write("Download a pre-filled `.env` template based on current settings:")

env_content = f"""# DOTO Image Commander – paste into .env in project root
OKCOUNTY_API_KEY=
OKCOUNTY_API_BASE_URL={config.OKCOUNTY_API_BASE_URL}
OKCOUNTY_COST_PER_IMAGE={config.OKCOUNTY_COST_PER_IMAGE}
OKCOUNTY_COST_PER_SEARCH={config.OKCOUNTY_COST_PER_SEARCH}

OPENAI_API_KEY=
OPENAI_MODEL={config.OPENAI_MODEL}
OPENAI_MAX_TOKENS={config.OPENAI_MAX_TOKENS}

DOWNLOADS_DIR={config.DOWNLOADS_DIR}
IMAGES_DIR={config.IMAGES_DIR}
REPORTS_DIR={config.REPORTS_DIR}
DB_PATH={config.DB_PATH}
AUDIT_LOG_PATH={config.AUDIT_LOG_PATH}
"""

st.download_button(
    label="Download .env template",
    data=env_content,
    file_name=".env",
    mime="text/plain",
)

st.divider()

# ── Diagnostics ───────────────────────────────────────────────────────────────
st.header("Diagnostics")

if st.button("Run System Check"):
    checks = []

    # Python packages
    for pkg, mod in [
        ("pandas", "pandas"), ("openpyxl", "openpyxl"), ("PyMuPDF", "fitz"),
        ("Pillow", "PIL"), ("openai", "openai"), ("cryptography", "cryptography"),
        ("requests", "requests"),
    ]:
        try:
            __import__(mod)
            checks.append(("✅", pkg, "Installed"))
        except ImportError:
            checks.append(("❌", pkg, "Not installed — run: pip install -r requirements.txt"))

    # API keys
    checks.append(("✅" if ok_configured else "⚠️", "OKCounty API Key",
                   "Set" if ok_configured else "Not configured"))
    checks.append(("✅" if openai_configured else "⚠️", "OpenAI API Key",
                   "Set" if openai_configured else "Not configured"))

    # Directories
    for label, path in [
        ("Downloads dir", config.DOWNLOADS_DIR),
        ("Images dir", config.IMAGES_DIR),
        ("Reports dir", config.REPORTS_DIR),
    ]:
        path.mkdir(parents=True, exist_ok=True)
        checks.append(("✅", label, str(path)))

    for icon, name, detail in checks:
        st.write(f"{icon} **{name}**: {detail}")
