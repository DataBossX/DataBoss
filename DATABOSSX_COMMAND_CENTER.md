# DataBossX Command Center — Quick Start (for Rodney)

DataBossX turns a folder of land & title files (deeds, leases, assignments,
runsheets, ownership spreadsheets, PDFs, scans) into a **client-ready report**:
a reconciled runsheet, mineral ownership, working-interest & net-revenue math,
a defect list, and an evidence/audit trail — as **Excel + PDF + a dashboard**.

It is local-first (nothing leaves your computer), it **never invents** a number
(anything the files don't support is left blank and flagged for review), and it
**never changes your source files** (every run writes to its own output folder
and backs up the previous run first).

---

## 1. Run it (the easy way — Windows)

**Double-click `DataBossX.bat`.**

The first time, it quietly sets itself up (about a minute). Then you get a menu:

```
1) Run the built-in demo (no client data needed)
2) Run one of your projects
3) Quick interest calculator (mineral / WI / NRI)
4) Self-check (doctor)
5) Open the last output folder
6) Quit
```

Start with **1) Run the built-in demo** — it proves the whole system works on
safe, made-up data and opens a real report you can look at.

When you're ready, pick **2) Run one of your projects**, type the project name
(for example `horizon`), and point it at the folder that holds that project's
files.

> Not on Windows? Use `./run_databossx.sh demo` (macOS/Linux).

---

## 2. What you get

Every run creates a `databossx_output` folder **inside your project folder**:

| File | What it is |
| --- | --- |
| `DataBossX_Report.xlsx` | The full client workbook: Summary, Runsheet, Abstract (chain of title), Mineral Ownership, Division of Interest (WI/NRI), Defects, Evidence. |
| `DataBossX_Report.pdf` | The same report as a clean, printable PDF. |
| `DataBossX_Abstract.txt` | Plain-language chain-of-title abstract — each tract's instruments in order, with review flags. |
| `dashboard.html` | A one-page status dashboard (double-click to open). Green / Yellow / Red. |
| `examiner_review_worklist_v###.csv` | The punch list — every item a person must resolve before sign-off. |
| `chain_breaks_v###.csv` | Every instrument that doesn't match across the OGL and the runsheet. |
| `run_manifest.json` | A machine record of the run (counts, status, files produced). |
| `databossx_audit.log` | An exact, timestamped log of everything the run did. |
| `_backups/` | Copies of the **previous** run's report, so you can always go back. |

**Red** means something must be fixed before release (for example, mineral
ownership that doesn't add up to 8/8, or a conveyance of more than someone owns).
**Yellow** means there are review items. **Green** means no defects were found —
but a human still signs off. Technical verification is not client release.

---

## 3. The quick calculator

You don't need a full project to check a number. From the menu pick
**3) Quick interest calculator**, or from a command line:

```bat
databossx calc --mineral 1/2 --gross 160        ->  net mineral acres
databossx calc --wi 1 --royalty 1/8             ->  net revenue interest (NRI)
databossx calc --wi 1/2 --royalty 3/16 --orri 1/32
```

All math is exact (real fractions, never rounded-off decimals).

---

## 4. If something looks wrong

Run **4) Self-check (doctor)**. It checks Python, the components, and the math
engine, and tells you in plain language what to fix. If a step ever says a
number couldn't be read, DataBossX **leaves it blank and flags it** — it will
not guess.

To completely reset the tool, delete the `.dbxvenv` folder and double-click
`DataBossX.bat` again. Your project files and outputs are untouched.

---

## 5. Projects

Built-in project names: `horizon`, `penterra`, `roger_mills`, `beckham`,
`ryder`, and `golden_demo` (the safe demo). Add more any time — a project is
just a name plus the folder its files live in. See `python dbx.py list` for the
current list and where each one points.

Full technical details are in [`databossx/README.md`](databossx/README.md).
