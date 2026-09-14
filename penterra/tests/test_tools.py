"""Deterministic tests. All fixtures are synthetic; no canonical source is touched."""
import sys, os, zipfile, hashlib, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.stable_key import stable_key, normalize_bookpage, TractEntry, dedupe, StableKeyError
from tools.identity import SourceFile, key_from_filename, candidate_keys, match_sources
from tools.pdf_census import census, parse_part, parse_serial, is_srp, count_pages
from tools.dupe_pages import find_duplicate_pages
from tools import blanks
from tools.parity import compare, ParityViolation
from tools.package import verify_package
from tools.replay import Rejection, check as replay_check, ReplayDetected
from tools.lease import LeaseStore, CollisionError, LeaseError

FAILED = []
def ok(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond: FAILED.append(label)

print("== stable_key ==")
ok(stable_key("1063795", "3269-0038") == "1063795|3269-0038", "doc+bookpage")
ok(stable_key("2023-00118", None) == "2023-00118|", "doc only (modern, no book/page)")
ok(stable_key(None, "0098-0131") == "|0098-0131", "bookpage only")
ok(stable_key("#0407085", "25MR-0347") == "407085|25MR-0347", "strips # and leading zeros")
ok(normalize_bookpage("005M-0119") == "005M-0119", "alpha book suffix preserved")
try:
    stable_key(None, None); ok(False, "rejects empty identity")
except StableKeyError: ok(True, "rejects empty identity")
ok(stable_key("1218", "005M-0119") == "1218|005M-0119", "legacy pair")

print("== stable_key dedupe (461-universe shape) ==")
raw = ([TractEntry(page=1, row=i, docno=str(1000+i)) for i in range(1, 46)] +
       [TractEntry(page=12, row=1, docno="1001", source="typed"),
        TractEntry(page=12, row=2, docno="1002", source="typed"),
        TractEntry(page=12, row=3, docno="9999", source="typed")])
by_key, overlaps = dedupe(raw)
ok(len(raw) == 48, "raw rows = 48")
ok(len(by_key) == 46, "unique keys = 46")
ok(overlaps == ["1001|", "1002|"], f"names the 2 overlaps: {overlaps}")
ok(len(raw) - len(by_key) == len(overlaps), "raw - unique == overlap count")

print("== identity ==")
ok(key_from_filename("#2023-00118.pdf") == "2023-00118|", "modern filename")
ok(key_from_filename("3305-0366.pdf") == "|3305-0366", "bookpage filename (book 3305 is not a year)")
ok(key_from_filename("25MR-0347.pdf") == "|25MR-0347", "alpha-suffixed book filename")
ok(candidate_keys("2023-0366.pdf") == ["2023-0366|", "|2023-0366"], "dddd-dddd with a year-like book emits BOTH candidates")
_amb = match_sources([SourceFile("2023-0366.pdf")], {"2023-0366|", "|2023-0366"})
ok(_amb["unmatched"][0]["disposition"] == "AMBIGUOUS", "index holding both readings -> AMBIGUOUS, never guessed")
_res = match_sources([SourceFile("3305-0366.pdf"), SourceFile("#2023-00118.pdf")], {"|3305-0366", "2023-00118|"})
ok(_res["matched_count"] == 2 and not _res["unmatched"], "ambiguous shape resolved by index membership")
ok(key_from_filename("1063795.pdf") == "1063795|", "legacy filename")
ok(key_from_filename("random_notes.pdf") is None, "unparseable filename -> None")
idx = {"2023-00118|", "1063795|3269-0038", "|0098-0131", "555|"}
r = match_sources([SourceFile("#2023-00118.pdf"), SourceFile("1063795.pdf"),
                   SourceFile("junk.pdf"), SourceFile("#2099-00001.pdf"),
                   SourceFile("1063795.pdf")], idx)
ok(r["matched_count"] == 2, f"matched 2 ({r['matched_count']})")
d = {u["disposition"] for u in r["unmatched"]}
ok(d == {"UNDETERMINED", "NON_INDEX", "DUPLICATE"}, f"three dispositions: {sorted(d)}")
ok(r["index_keys_without_source"] == ["555|", "|0098-0131"], "names index keys lacking a source")

print("== pdf_census ==")
ok(parse_part("WYW-51704 Part 3 of 6.pdf") == (3, 6), "part parse")
ok(parse_serial("WYW-5955.pdf") == "WYW-005955", "serial zero-pads")
ok(parse_serial("WYW-47318 Part 1 of 4.pdf") == "WYW-047318", "serial from part file")
ok(is_srp("Serial Register Page WYW-5955 (8.4.2026).pdf"), "SRP detected")
ok(not is_srp("WYW-5955.pdf"), "casefile not SRP")
FED = [('WYW-5955.pdf',243),('Serial Register Page WYW-5955 (8.4.2026).pdf',3),
 ('WYW-47318 Part 1 of 4.pdf',189),('WYW-47318 Part 2 of 4.pdf',177),
 ('WYW-47318 Part 3 of 4.pdf',94),('WYW-47318 Part 4 of 4.pdf',2),
 ('Serial Register Page WYW-47318 (8.04.2026).pdf',5),
 ('WYW-51704 Part 1 of 6.pdf',225),('WYW-51704 Part 2 of 6.pdf',184),
 ('WYW-51704 Part 3 of 6.pdf',239),('WYW-51704 Part 4 of 6.pdf',168),
 ('WYW-51704 Part 5 of 6.pdf',131),('WYW-51704 Part 6 of 6.pdf',2),
 ('Serial Register Page WYW-51704 (8.04.2026).pdf',11)]
c = census(FED)
ok(c["by_serial"]["WYW-005955"].casefile_files == 1 and c["by_serial"]["WYW-005955"].casefile_pages == 243, "WYW-005955 = 1 casefile / 243 pages")
ok(c["by_serial"]["WYW-047318"].casefile_files == 4 and c["by_serial"]["WYW-047318"].casefile_pages == 462, "WYW-047318 = 4 parts / 462 pages")
ok(c["by_serial"]["WYW-051704"].casefile_files == 6 and c["by_serial"]["WYW-051704"].casefile_pages == 949, "WYW-051704 = 6 parts / 949 pages")
ok((c["casefile_files"], c["casefile_pages"]) == (11, 1654), "casefile total = 11 files / 1,654 pages")
ok((c["srp_files"], c["srp_pages"]) == (3, 19), "SRP total = 3 files / 19 pages")
ok((c["total_files"], c["total_pages"]) == (14, 1673), "broader total = 14 files / 1,673 pages")
ok(c["problems"] == [], "no duplicate/missing parts, no double-counted SRP")
bad = census(FED + [('WYW-51704 Part 3 of 6.pdf', 239)])
ok(any("duplicate Part 3" in p.get("problem","") for p in bad["problems"]), "detects a duplicated Part")
gap = census([('WYW-47318 Part 1 of 4.pdf',189), ('WYW-47318 Part 3 of 4.pdf',94)])
ok(any("missing Part" in p.get("problem","") for p in gap["problems"]), "detects a missing Part")

print("== pdf_census.count_pages on a real generated PDF ==")
with tempfile.TemporaryDirectory() as td:
    pdf = Path(td)/"t.pdf"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>"] + \
           ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"]*3
    body, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(body)); body += f"{i} 0 obj\n{o}\nendobj\n"
    start = len(body)
    body += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    body += "".join(f"{o:010d} 00000 n \n" for o in offs)
    body += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n"
    pdf.write_text(body)
    cp = count_pages(pdf)
    ok(cp["pages"] == 3 and cp["declared"] == 3 and cp["agree"], f"counts 3 pages, agrees with /Count: {cp}")

print("== dupe_pages ==")
dp = find_duplicate_pages([("a.pdf",1,b"X"), ("b.pdf",1,b"X"), ("a.pdf",2,b"Y"),
                           ("a.pdf",3,b"Y"), ("c.pdf",1,b"Z")])
ok(len(dp["cross_file_duplicates"]) == 1, "one cross-file duplicate")
ok(len(dp["intra_file_duplicates"]) == 1, "one intra-file duplicate")
ok(dp["unique_pages"] == 3 and dp["total_pages"] == 5, "unique 3 of 5 pages")

print("== blanks ==")
k, why = blanks.classify("Book-Page", "Corner Record", docno="2026-00020")
ok(k == blanks.INAPPLICABLE, f"modern doc-no-only book/page -> INAPPLICABLE")
k, _ = blanks.classify("Grantor", "Corner Record", docno="2026-00020")
ok(k == blanks.INAPPLICABLE, "corner record has no grantor -> INAPPLICABLE")
k, _ = blanks.classify("Legal Description", "UCC Financing Statement", docno="700000")
ok(k == blanks.INTENTIONAL, "UCC general collateral -> INTENTIONAL")
k, _ = blanks.classify("Legal Description", "Warranty Deed", docno="700000", has_source=False)
ok(k == blanks.SOURCE_MISSING, "no custody -> SOURCE_MISSING")
k, _ = blanks.classify("Date of Doc", "Warranty Deed", docno="700000", legible=False)
ok(k == blanks.UNREADABLE, "illegible face -> UNREADABLE")
k, _ = blanks.classify("Date of Doc", "Warranty Deed", docno="700000")
ok(k == blanks.TRUE_HOLD, "read but indeterminate -> TRUE_HOLD")
cen = blanks.census([{"field":"Grantor","doc_type":"Corner Record","docno":"2026-00020"},
                     {"field":"Date of Doc","doc_type":"Warranty Deed","docno":"1","legible":False}])
ok(cen["total"] == 2 and cen["counts"][blanks.UNREADABLE] == 1, "census partitions every cell")
ok(sum(cen["counts"].values()) == cen["total"], "classes partition exactly (no cell lost)")

print("== parity ==")
p = compare({"font_name":"Calibri","orientation":"landscape","print_area":"A1:J198"},
            {"font_name":"Calibri","orientation":"landscape","print_area":"A1:J198"})
ok(p["parity"] and p["compared"] == 3, "identical presentation -> parity")
p2 = compare({"font_name":"Calibri","margins":"narrow"}, {"font_name":"Arial","margins":"narrow"})
ok(not p2["parity"] and len(p2["differences"]) == 1, "detects a format difference")
p3 = compare({"orientation":"landscape"}, {"orientation":"portrait"},
             known_donor_defects={"orientation"})
ok(p3["parity"] and len(p3["skipped_donor_defects"]) == 1, "does not inherit a donor defect")
try:
    compare({"county_rows":62}, {"county_rows":155}); ok(False, "blocks fact copying")
except ParityViolation: ok(True, "blocks fact copying from Section 15")

print("== package ==")
with tempfile.TemporaryDirectory() as td:
    z = Path(td)/"pkg.zip"
    members = {"a.ods": b"AAA", "b.xlsx": b"BBB", "c.docx": b"CCC"}
    with zipfile.ZipFile(z, "w") as zf:
        for n, b in members.items(): zf.writestr(n, b)
    want = {n: hashlib.sha256(b).hexdigest() for n, b in members.items()}
    r = verify_package(z, list(members), expected_member_sha=want)
    ok(r["pass"] and r["crc_pass"] and r["member_count"] == 3, "exact-3 membership + CRC + member hashes")
    r2 = verify_package(z, ["a.ods", "b.xlsx"])
    ok(not r2["pass"] and any("unexpected members" in e for e in r2["errors"]), "detects an extra member")
    r3 = verify_package(z, list(members), expected_sha256="deadbeef")
    ok(not r3["pass"] and any("container sha mismatch" in e for e in r3["errors"]), "detects container hash drift")
    r4 = verify_package(z, ["c.docx","b.xlsx","a.ods"], ordered=True)
    ok(not r4["pass"], "detects member-order drift when ordered=True")
    ok(verify_package(Path(td)/"nope.zip", []).get("pass") is False, "missing package fails closed")

print("== replay ==")
rej = [Rejection("G11", "date", "1989-07-06", "superseded by authenticated floor", "V11.12")]
ok(replay_check({("G11","date"):"1989-07-08"}, rej)["clean"], "accepted value is not a replay")
rr = replay_check({("G11","date"):"1989-07-06"}, rej)
ok(rr["replay_count"] == 1, "detects a re-asserted rejected value")
try:
    replay_check({("G11","date"):"1989-07-06"}, rej, strict=True); ok(False, "strict raises")
except ReplayDetected: ok(True, "strict mode raises on replay")

print("== lease (one writer) ==")
with tempfile.TemporaryDirectory() as td:
    s = LeaseStore(td)
    t = "45N-76W-11_county.ods"
    l1 = s.acquire(t, "claude", preimage_sha256="df7b994b")
    ok(l1.fence == 1 and s.writer_count(t) == 1, "acquire -> fence 1, writer_count 1")
    try:
        s.acquire(t, "codex-pc"); ok(False, "second writer blocked")
    except CollisionError: ok(True, "second writer blocked (COLLISION)")
    ok(s.acquire(t, "claude").fence == 1, "same writer re-acquire renews, no fence bump")
    s.guard_commit(t, "claude", fence=1, preimage_sha256="df7b994b")
    ok(True, "guard_commit passes for the holder with matching preimage")
    try:
        s.guard_commit(t, "claude", fence=1, preimage_sha256="OTHER"); ok(False, "preimage drift blocked")
    except CollisionError: ok(True, "preimage drift blocked")
    try:
        s.guard_commit(t, "codex-pc", fence=1); ok(False, "non-holder blocked")
    except CollisionError: ok(True, "non-holder commit blocked")
    s.release(t, "claude")
    ok(s.writer_count(t) == 0, "release -> writer_count 0")
    l2 = s.acquire(t, "codex-pc")
    ok(l2.fence == 2, "fence strictly increases after handoff")
    try:
        s.guard_commit(t, "claude", fence=1); ok(False, "stale writer blocked")
    except CollisionError: ok(True, "stale writer blocked after handoff")

print()
print(f"RESULT: {'ALL PASS' if not FAILED else str(len(FAILED)) + ' FAILURES: ' + str(FAILED)}")
sys.exit(1 if FAILED else 0)
