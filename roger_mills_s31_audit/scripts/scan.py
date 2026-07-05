import openpyxl
wb = openpyxl.load_workbook("sources/CURRENT_BROKEN.xlsx", data_only=False)
targets = ["No final owners","Needs Verification","Needs Examiner","placeholder","TODO","TBD","No final","not calculated"]
for ws in wb.worksheets:
    hits={}
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value,str):
                for t in targets:
                    if t.lower() in c.value.lower():
                        hits[t]=hits.get(t,0)+1
    if hits:
        print(f"{ws.title}: {hits}")
