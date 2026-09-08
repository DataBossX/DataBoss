#!/usr/bin/env python3
"""
Section 15 page-setup repair — byte-faithful reimplementation of the ACCEPTED
Section 2 donor recipe (add_xlsx_page_setup.ps1, Drive id 1oOBt9YHxfZBm810VmC98AEo3_lq59knl).

Donor law, reproduced exactly:
  * Only xl/worksheets/sheet1.xml is touched. Every other zip entry is copied verbatim.
  * Injection happens ONLY if no <pageSetup> (any namespace prefix) already exists.
  * Mode FitWidth  -> <x:pageSetup orientation="portrait" fitToWidth="1" fitToHeight="0"/>
  * Mode Checklist -> <x:pageSetup scale="34"/>
  * Inserted immediately before </x:worksheet>.
  * Refuses to overwrite an existing output.
No other metadata is added. Nothing is invented beyond the donor.
"""
import re, shutil, sys, zipfile, os

SHEET = "xl/worksheets/sheet1.xml"
HAS_PAGESETUP = re.compile(r'<(?:[A-Za-z]+:)?pageSetup(?:\s|/)')
FITWIDTH  = '<x:pageSetup orientation="portrait" fitToWidth="1" fitToHeight="0"/>'
CHECKLIST = '<x:pageSetup scale="34"/>'

def repair(src, dst, mode):
    if os.path.exists(dst):
        raise SystemExit(f"Refusing to overwrite existing output: {dst}")
    setup = FITWIDTH if mode == "FitWidth" else CHECKLIST
    injected = False
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == SHEET:
                text = data.decode("utf-8")
                if not HAS_PAGESETUP.search(text):
                    text = text.replace("</x:worksheet>", setup + "</x:worksheet>")
                    injected = True
                data = text.encode("utf-8")
            zout.writestr(item, data)
    return injected

def audit(path):
    with zipfile.ZipFile(path) as z:
        s = z.read(SHEET).decode()
        w = z.read("xl/workbook.xml").decode()
    return {
        "pageSetup":   len(HAS_PAGESETUP.findall(s)),
        "pageMargins": s.count("<x:pageMargins"),
        "sheetPr":     s.count("<x:sheetPr"),
        "fitToPage":   s.count('fitToPage="1"'),
        "definedName": w.count("definedName"),
    }

def main(argv):
    if len(argv) == 3 and argv[1] == "--audit":
        print(argv[2], audit(argv[2]))
        return 0
    if len(argv) != 4:
        print(__doc__)
        print("usage: xlsx_pagesetup_repair.py <in.xlsx> <out.xlsx> <FitWidth|Checklist>")
        print("       xlsx_pagesetup_repair.py --audit <file.xlsx>")
        return 2
    src, dst, mode = argv[1], argv[2], argv[3]
    if mode not in ("FitWidth", "Checklist"):
        raise SystemExit("mode must be FitWidth or Checklist")
    print("BEFORE:", audit(src))
    print("injected:", repair(src, dst, mode))
    print("AFTER :", audit(dst))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
