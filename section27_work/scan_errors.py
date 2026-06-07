import openpyxl
wb=openpyxl.load_workbook("11N 25W 27 Diversified Cursory Report 6-6-2026.xlsx", data_only=False)
errs=['#REF!','#VALUE!','#NAME?','#DIV/0!','#N/A','#NULL!','#NUM!']
found=0
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value,str):
                for e in errs:
                    if e in c.value:
                        print(f"{ws.title}!{c.coordinate}: {c.value[:80]}"); found+=1
print("TOTAL error-token cells (in stored strings/formulas):", found)
# Also check defined names and external links
print("Defined names:", list(wb.defined_names)[:20] if hasattr(wb,'defined_names') else 'n/a')
