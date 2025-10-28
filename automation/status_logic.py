from typing import List, Dict

TARGET_SEC = "SEC 1"
TARGET_T = "T7N"
TARGET_R = "R63W"

def _hits_target(legal_short: str) -> bool:
    if not legal_short: return False
    s = legal_short.upper().replace(".", "").replace(",", "")
    return ("SEC 1" in s or "SECTION 1" in s) and "T7N" in s and "R63W" in s

def decide_status_rule_based(owner: str, docs: List[Dict]) -> Dict:
    docs_sorted = sorted(docs, key=lambda d: (d.get("recording_date") or "0000-00-00"))
    target_docs = [d for d in docs_sorted if _hits_target((d.get("legal_short") or ""))]
    if not target_docs:
        return {"status":"Unknown—needs manual","confidence":0.6,"explanation":"No Sec 1 T7N R63W hits."}

    last = target_docs[-1]
    instr = (last.get("instrument") or "").upper()
    grantor = (last.get("grantor") or "").upper()
    grantees = [g.upper() for g in last.get("grantee") or []]
    o = owner.upper()

    if "LEASE" in instr and o == grantor:
        return {"status":"Leased HBP","confidence":0.7,"explanation":"Owner is lessor on O&G lease for Sec 1; no later deed out recorded."}
    if o == grantor:
        return {"status":"Assigned out","confidence":0.85,"explanation":"Latest affecting doc shows owner as grantor/assignor in Sec 1."}
    if o in grantees:
        return {"status":"Current owner of record","confidence":0.85,"explanation":"Latest affecting doc shows owner as grantee for Sec 1 with no later conveyance out."}

    return {"status":"Unknown—needs manual","confidence":0.6,"explanation":"Docs ambiguous relative to owner."}
