import openpyxl, sys
path, sheets = sys.argv[1], sys.argv[2:]
wb = openpyxl.load_workbook(path, data_only=False)
for ws in wb.worksheets:
    if sheets and ws.title not in sheets: continue
    print("\n"+"#"*60); print("# SHEET:", ws.title); print("#"*60)
    for row in ws.iter_rows():
        cells=[]
        for c in row:
            if c.value is not None and str(c.value).strip()!="":
                cells.append(f"{c.coordinate}={repr(c.value)}")
        if cells: print(" | ".join(cells))
