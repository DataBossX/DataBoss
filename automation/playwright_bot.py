import os, time, json, pathlib, re
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.sync_api import sync_playwright
from automation.parsing import extractor_llm
from automation.status_logic import decide_status_rule_based
from automation.writer import update_workbook

BASE = "https://weldrecorder.weldgov.com/web/"
WORKBOOK = "Black_Tip_Notice_List_verified_updated_20251028_v7.xlsx"
SHEET_DSU = "DSU NOTICE LIST"
SHEET_OFFSET = "OFFSET NOTICE LIST"
DELAY = 3.5

def load_owners():
    dsu = pd.read_excel(WORKBOOK, sheet_name=SHEET_DSU)
    off = pd.read_excel(WORKBOOK, sheet_name=SHEET_OFFSET)
    df = pd.concat([dsu, off], ignore_index=True)
    unk = df[df["Status"].astype(str).str.startswith("Unknown")]
    # de-dup by owner name
    return sorted(set(unk["Name (Owner)"].dropna().tolist()))

def human_check_prompt(page):
    # If page shows “I am human” checkbox, wait for a minute for manual click
    time.sleep(2)

def search_owner(page, owner:str):
    page.goto(BASE + "search/DOCSEARCH524S12", timeout=60000)
    time.sleep(DELAY)
    # Type in “Search Name as Grantor or Grantee”
    page.get_by_label("Search Name as Grantor or Grantee").click()
    page.keyboard.type(owner)
    time.sleep(1.5)
    # pick first suggestion if appears
    try:
        page.locator(".react-select__menu").locator("div").nth(0).click(timeout=2000)
    except Exception:
        pass  # no autocomplete suggestion appeared; continue with typed name
    page.get_by_role("button", name="Search").click()
    time.sleep(DELAY+1)

def parse_results(page, owner:str):
    rows = page.locator("table tbody tr")
    n = rows.count()
    docs=[]
    for i in range(min(n, 200)):  # cap per owner
        row = rows.nth(i)
        cols = row.locator("td")
        doc_no = cols.nth(1).inner_text().strip()
        instr  = cols.nth(2).inner_text().strip()
        recd   = cols.nth(3).inner_text().strip()
        # Open detail in new tab
        try:
            cols.nth(0).click()
            page.get_by_role("link", name=re.compile("View", re.I)).click(timeout=3000)
        except Exception:
            pass  # detail link not present for this row; capture current URL only
        # side panel or new tab may show details; capture URL
        source_url = page.url
        text_blob = " ".join([doc_no, instr, recd])
        doc = extractor_llm(text_blob, source_url)
        if not doc.get("doc_no"): doc["doc_no"]=doc_no
        if not doc.get("instrument"): doc["instrument"]=instr
        if not doc.get("recording_date"): doc["recording_date"]=recd or None
        docs.append(doc)
        time.sleep(1.0)
    return docs

def update_owner(owner:str, decision:dict, last_doc:dict):
    payload = {
        "verified_address": (last_doc.get("addresses") or [None])[0],
        "status": decision["status"],
        "doc_no": last_doc.get("doc_no"),
        "instrument": last_doc.get("instrument"),
        "recording_date": last_doc.get("recording_date"),
        "source_url": last_doc.get("source_url"),
        "notes": decision.get("explanation"),
        "confidence": decision.get("confidence", 0.7),
    }
    # Try DSU then OFFSET
    ok = update_workbook(WORKBOOK, SHEET_DSU, owner, payload)
    if not ok:
        update_workbook(WORKBOOK, SHEET_OFFSET, owner, payload)

def main():
    owners = load_owners()
    pathlib.Path("data/json_traces").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible so you can click CAPTCHA
        page = browser.new_page()
        page.goto(BASE, timeout=60000)
        human_check_prompt(page)
        for owner in owners:
            try:
                search_owner(page, owner)
                docs = parse_results(page, owner)
                if not docs:
                    continue
                # rule-based first
                decision = decide_status_rule_based(owner, docs)
                # pick the latest doc for workbook
                last_doc = sorted(docs, key=lambda d: (d.get("recording_date") or "0000-00-00"))[-1]
                update_owner(owner, decision, last_doc)
                safe_name = owner.replace('/', '_')
                with open(f"data/json_traces/{safe_name}.json", "w") as fh:
                    json.dump({"owner": owner, "docs": docs, "decision": decision},
                              fh, ensure_ascii=False, indent=2)
                time.sleep(DELAY)
            except Exception as e:
                safe_name = owner.replace('/', '_')
                with open(f"data/json_traces/{safe_name}_ERR.json", "w") as fh:
                    json.dump({"owner": owner, "error": str(e)}, fh)
                time.sleep(DELAY)
        browser.close()

if __name__ == "__main__":
    main()
