"""Count abstract-index entries from a flattened Drive read of a Penterra/Overtime index workbook.

Counting rule (validated against the finished Overtime packages):
  county entries = index-table rows - BLM survey/plat rows (Dependent Resurvey Plat, Corner Record)
  Overtime S11: 476 rows - 1 plat = 475  == checklist "475 entries"   OK
  Overtime S15: rows - (Dependent Resurvey Plat + Corner Record) = 151 == checklist "151 entries"

Only the FIRST index table counts. Some Penterra working drafts append a second
"Historical proposals" table (baseline proposals, not admitted entries); it is
reported separately and never added to the abstract total.
"""
import json, re, sys, collections

HDR = "Document Type,Grantor,Grantee,Doc No,Book-Page,Date of Doc,Rec Date,Legal Description,Comments"
ROW = re.compile(r',([0-9][0-9A-Za-z\-]{2,}),([0-9A-Za-z\-]*),(\d{1,2}/\d{1,2}/\d{4}|),(\d{1,2}/\d{1,2}/\d{4}),')
PLAT = re.compile(r'(Dependent Resurvey Plat|Corner Record)', re.I)
HDR_FIELDS = ["Index County", "Lands", "Date", "Starting Date", "Date Posted Thru",
              "Indexed By", "Project"]

def header(c):
    out = {}
    for f in HDR_FIELDS:
        tag = f + ":,"
        if tag in c:
            seg = c.split(tag, 1)[1]
            out[f] = seg.split(",,", 1)[0].strip().strip('"')
    return out

def tables(c):
    """Return a list of index-table spans, each bounded by the next table header."""
    occ = [m.start() for m in re.finditer(re.escape(HDR), c)]
    spans = []
    for k, o in enumerate(occ):
        start = o + len(HDR)
        end = occ[k + 1] if k + 1 < len(occ) else len(c)
        spans.append(c[start:end])
    return spans

def rows(span):
    out, prev = [], 0
    for m in ROW.finditer(span):
        out.append({"lead": span[prev:m.start()].strip(), "docno": m.group(1),
                    "bp": m.group(2), "dd": m.group(3), "rd": m.group(4)})
        prev = m.end()
    return out

def _key(s):
    m, d, y = s.split("/"); return (int(y), int(m), int(d))

def analyze(path):
    d = json.load(open(path)); c = d["fileContent"]
    spans = tables(c)
    res = {"title": d["title"], "header": header(c), "index_tables": len(spans)}
    main = rows(spans[0]) if spans else []
    plats = [r for r in main if PLAT.search(r["lead"])]
    dn = collections.Counter(r["docno"] for r in main)
    dates = [r["rd"] for r in main if r["rd"]]
    res.update({
        "index_rows": len(main),
        "blm_plat_rows": len(plats),
        "entries": len(main) - len(plats),
        "dup_docnos": {k: v for k, v in dn.items() if v > 1},
        "earliest_rec": min(dates, key=_key) if dates else None,
        "latest_rec": max(dates, key=_key) if dates else None,
    })
    if len(spans) > 1:
        res["secondary_tables"] = [len(rows(s)) for s in spans[1:]]
    return res

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(analyze(p), indent=1))
