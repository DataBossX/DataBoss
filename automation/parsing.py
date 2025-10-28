import re, json, time
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_fixed
# LLM client shims (fill with your SDK of choice)
import os
OPENAI = os.getenv("OPENAI_API_KEY")
ANTHROPIC = os.getenv("ANTHROPIC_API_KEY")

def clean_text(t:str)->str:
    return re.sub(r"[ \t]+"," ", (t or "")).strip()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def extractor_llm(text:str, source_url:str)->Dict[str,Any]:
    # Call Claude or GPT in JSON mode; here we stub a minimal sanitizer
    # Replace with your actual SDK call using prompts/extractor_user.md.
    payload = {
        "doc_no": None, "instrument": None, "recording_date": None,
        "grantor": None, "grantee": [], "legal_short": None,
        "addresses": [], "source_url": source_url
    }
    # quick heuristics (backup to LLM)
    m = re.search(r"Document\s*#\s*([0-9]{7,})", text, re.I)
    if m: payload["doc_no"] = m.group(1)
    if "OIL & GAS LEASE" in text.upper(): payload["instrument"]="Oil & Gas Lease"
    m = re.search(r"(20\d{2}-\d{2}-\d{2})|(\d{2}/\d{2}/20\d{2})", text)
    if m: payload["recording_date"]=m.group(0).replace("/","-")
    m = re.search(r"Sec(tion)?\s*1.*T7N.*R63W", text, re.I)
    if m: payload["legal_short"]="Sec 1 T7N R63W"
    return payload

def ocr_if_needed(image_bytes:bytes)->str:
    # If PDFs render as images, run OCR fallback (paddle/tesseract)
    return ""
