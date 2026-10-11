#!/usr/bin/env python3
"""Build Overtime-format abstract-package deliverables for the Penterra sections.

Layout parity is taken from the two finished Overtime packages:
  Section 11 final package  (45N-76W-11)  <- primary template (richest checklist)
  Section 15 Example Final Package (45N-76W-15)

Per section this emits:
  Abstract_Checklist_<sec>-<twp>-<rng>.xlsx      3-block Overtime checklist
  <sec>-<twp>-<rng>_Certification_Letter.docx    Overtime preparation/certification letter

Counts written into these files come from counts.json, which is derived by
counter.py from the actual index workbooks. Nothing here is invented: where a
source value is absent it is carried through as "Unknown"/"N/A" and the
qualification block says so.
"""
import json, os, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "build")
CFG = json.load(open(os.path.join(BASE, "sections.json")))
META = CFG["project_meta"]

HDR_FILL = PatternFill("solid", fgColor="D9D9D9")
TITLE_FILL = PatternFill("solid", fgColor="BFBFBF")
THIN = Side(style="thin", color="808080")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def _long(datestr):
    """m/d/Y or Y-m-d -> 'March 15, 2017'."""
    if not datestr:
        return None
    for f in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(datestr, f).strftime("%B %-d, %Y")
        except ValueError:
            continue
    return datestr

def _serial_phrase(serials):
    if not serials:
        return None
    if len(serials) == 1:
        return serials[0]
    return ", ".join(serials[:-1]) + " and " + serials[-1]

def _mdY(datestr):
    if not datestr:
        return None
    for f in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            d = datetime.datetime.strptime(datestr, f)
            return f"{d.month}/{d.day}/{d.year}"
        except ValueError:
            continue
    return datestr

# ---------------------------------------------------------------- checklist
def build_checklist(s):
    tag = f"{s['sec']}-{s['twp']}-{s['rng']}"
    wb = Workbook(); ws = wb.active; ws.title = "Abstract Checklist"
    serials = s["federals"]
    sp = _serial_phrase(serials)
    prepared = _mdY(META["prepared_date"])

    fed_file = sp if sp else "N/A - no federal lease index accepted for this section"
    srp = (f"{sp} SRP; posted-through date not established (UNKNOWN)" if sp
           else "N/A")
    county_contents = (f"County index from {s['starting']} through last indexed instrument "
                       f"recorded {_mdY(s['latest_rec'])}, {s['county_entries']} entries; "
                       f"no certified search cutoff established")
    fed_counts = json.load(open(os.path.join(BASE, "counts.json")))["penterra"][s["sec"]]["federals"]
    fed_contents = ("  ".join(f"{k}: {v}" for k, v in fed_counts.items())
                    if fed_counts else "N/A")

    blocks = [
        ("Abstract checklist",
         ["County Index", "County Documents", "Plat", "STR online search",
          "Compare index to Uploads", "BLM File", "SRP", "State File",
          "Lease Report if applicable", "Reviewed SRP vs BLM file or State file",
          "Certification Letter"],
         ["Partial - see qualifications", "Partial - see qualifications",
          (f"{s['blm_plat_rows']} BLM survey/plat record" + ("s" if s["blm_plat_rows"] != 1 else "") + " in index") if s["blm_plat_rows"] else "N/A",
          "Yes", "Partial - see qualifications",
          fed_file, srp, "N/A", "N/A",
          "Partial - see qualifications" if serials else "N/A",
          "Unsigned - qualified"]),
        ("Abstract Excel Sheet",
         ["County", "Lands Covered", "Date Prepared", "Starting Date",
          "Date Reviewed", "Landman Name", "Project / Prospect"],
         [META["county"], s["lands_covered"], prepared, s["starting"],
          prepared, META["landman"], s["project"]]),
        ("Certification Letter",
         ["Client", "STR & County", "Contents for County Records",
          "Contents for BLM / State", "SRP Info", "Preparation Date"],
         [META["client"],
          f"T{s['twp']}-R{s['rng']} {s['lands_line']}, {META['county']} County, {META['state']}",
          county_contents, fed_contents, srp, prepared]),
    ]

    r = 1
    for title, heads, vals in blocks:
        c = ws.cell(row=r, column=1, value=title)
        c.font = Font(bold=True, size=11); c.fill = TITLE_FILL; c.border = BOX
        for j, h in enumerate(heads, start=2):
            c = ws.cell(row=r, column=j, value=h)
            c.font = Font(bold=True, size=10); c.fill = HDR_FILL; c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="center")
        r += 1
        c = ws.cell(row=r, column=1, value="Yes")
        c.font = Font(size=10); c.border = BOX
        for j, v in enumerate(vals, start=2):
            c = ws.cell(row=r, column=j, value=v)
            c.font = Font(size=10); c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 2

    ws.cell(row=r, column=1, value="Qualifications").font = Font(bold=True, size=11)
    r += 1
    for q in s["quals"]:
        ws.cell(row=r, column=1, value="•")
        c = ws.cell(row=r, column=2, value=q)
        c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = Font(size=10)
        r += 1

    ws.column_dimensions["A"].width = 22
    for col in "BCDEFGHIJKL":
        ws.column_dimensions[col].width = 26
    ws.freeze_panes = "B2"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = f"A1:L{r}"

    path = os.path.join(OUT, f"Abstract_Checklist_{tag}.xlsx")
    wb.save(path)
    return path

# ------------------------------------------------------------------- letter
def build_letter(s):
    tag = f"{s['sec']}-{s['twp']}-{s['rng']}"
    twp_n = s["twp"].rstrip("N"); rng_n = s["rng"].rstrip("W")
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(1.0)

    h = doc.add_paragraph()
    rr = h.add_run(f"Section {s['sec']}, T{s['twp']}-R{s['rng']} — Abstract Preparation Letter")
    rr.bold = True; rr.font.size = Pt(13)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run(f"Township {twp_n} North, Range {rng_n} West, {META['pm']}").bold = True
    p = doc.add_paragraph()
    p.add_run(f"{s['lands_line']}   {META['county']} County, {META['state']}").bold = True

    doc.add_paragraph()
    doc.add_paragraph().add_run("Contents of abstract:").bold = True
    doc.add_paragraph()

    doc.add_paragraph(
        f"Index of Documents reflecting on the entries posted in the tract indices located and "
        f"maintained by the {META['county']} County Clerk's office, from {s['starting']} to last "
        f"Indexed Instrument Recorded {_long(s['latest_rec'])} "
        f"({s['county_entries']} entries).")

    doc.add_paragraph(
        f"{META['county']} County Assessor and/or Treasurer office reports, detailing surface owner "
        f"property accounts and the state of any taxes due, N/A.")

    sp = _serial_phrase(s["federals"])
    if sp:
        doc.add_paragraph(
            f"Images of Federal Lease files {sp}; posted-through date not established (UNKNOWN).")
        doc.add_paragraph(
            f"Bureau of Land Management (MLRS) Serial Register Pages {sp}; "
            f"posted-through date not established (UNKNOWN).")
    else:
        doc.add_paragraph("Images of Federal Lease files, N/A.")
        doc.add_paragraph("Bureau of Land Management (MLRS) Serial Register Pages, N/A.")

    doc.add_paragraph("Judgement, Lien, Mortgages and Civil Suit Search not Performed.")

    doc.add_paragraph()
    doc.add_paragraph().add_run("Qualifications:").bold = True
    for q in s["quals"]:
        doc.add_paragraph(q, style="List Bullet")

    doc.add_paragraph()
    doc.add_paragraph(
        f"This abstract was prepared and made solely for the benefit of {META['client']} and is not "
        f"to be construed as a title opinion, nor a guaranty of title, and the information contained "
        f"herein is conditioned upon the accuracy of the tract indices of {META['county']} County, "
        f"including any errors or omissions contained therein. This abstract is limited to the "
        f"materials reviewed and searched and described herein. The instruments referred to have not "
        f"been examined to determine their legal sufficiency.")

    doc.add_paragraph()
    doc.add_paragraph(
        f"Prepared on {_long(META['prepared_date'])}, through the source dates shown above by: "
        f"{META['landman']}.")
    doc.add_paragraph()
    p = doc.add_paragraph("________________________________")
    doc.add_paragraph()
    for line in META["preparer_block"]:
        doc.add_paragraph(line)

    path = os.path.join(OUT, f"{tag}_Certification_Letter.docx")
    doc.save(path)
    return path

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in CFG["sections"]:
        print("checklist:", os.path.basename(build_checklist(s)))
        print("letter:   ", os.path.basename(build_letter(s)))
