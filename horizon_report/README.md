# Horizon Ownership Report Generator

A production-grade tool for generating ownership reports from source documents. Reads runsheets, templates, and source files to produce comprehensive ownership reports in DOCX, XLSX, and PDF formats with built-in quality assurance and optional Google Drive synchronization.

## Features

✅ **Real File Processing** - Scans and parses XLSX, CSV, DOCX, and PDF files
✅ **Multiple Output Formats** - Generates DOCX, XLSX, and PDF reports
✅ **Quality Assurance** - Built-in QA checks with confidence scoring
✅ **Google Drive Sync** - Optional sync to Google Drive (local or API)
✅ **Comprehensive Logging** - Detailed logs for every operation
✅ **Secure Configuration** - Environment-based settings with secret protection
✅ **No Fabrication** - Only uses data from actual source files

## Quick Start (Non-Technical Users)

### Step 1: Install Python

1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation by opening Terminal (Mac/Linux) or Command Prompt (Windows) and typing:
   ```
   python --version
   ```

### Step 2: Set Up the Tool

1. Open Terminal/Command Prompt
2. Navigate to the Horizon folder:
   ```
   cd /path/to/workspace
   ```
   (Replace `/path/to/workspace` with the actual path)

3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

4. Activate the virtual environment:
   - **Windows:**
     ```
     venv\Scripts\activate
     ```
   - **Mac/Linux:**
     ```
     source venv/bin/activate
     ```

5. Install required packages:
   ```bash
   pip install -r horizon_report/requirements.txt
   ```

### Step 3: Add Your Files

1. Place your source files (runsheets, ownership documents, etc.) in the `inputs/` folder
2. Supported file types:
   - Excel files (.xlsx, .xls)
   - CSV files (.csv)
   - Word documents (.docx)
   - PDF files (.pdf)

### Step 4: Generate Reports

Run this command (replace the date with today's date in YYYY-MM-DD format):

```bash
python -m horizon_report generate --input inputs --date 2026-07-05
```

### Step 5: Find Your Reports

Generated reports will be in the `reports/generated/` folder:
- `Ownership_Report_2026-07-05.docx` - Word document
- `Ownership_Report_2026-07-05.xlsx` - Excel workbook
- `Ownership_Report_2026-07-05.pdf` - PDF document (if reportlab installed)

QA reports will be in `reports/qa/`:
- `qa_report_2026-07-05.md` - Quality assurance report

Logs will be in `logs/`:
- `run_2026-07-05.txt` - Detailed log file

## All Available Commands

### Generate Reports
```bash
python -m horizon_report generate --input inputs --date 2026-07-05
```

Optional flags:
- `--section 31-12N-24W` - Specify section identifier
- `--county "Roger Mills"` - Specify county name
- `--state Oklahoma` - Specify state name

### Run Quality Assurance Only
```bash
python -m horizon_report qa --date 2026-07-05
```

### Scan Files (Inventory)
```bash
python -m horizon_report inventory
```

### Sync to Google Drive
```bash
python -m horizon_report sync-drive --date 2026-07-05
```

### Run Everything (Full Pipeline)
```bash
python -m horizon_report build-all --input inputs --date 2026-07-05
```

This runs: inventory → generate → QA → sync (all in one command)

## Configuration (Optional)

To customize settings:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with a text editor and set your preferences:
   ```
   HORIZON_INPUT_PATH=/path/to/your/inputs
   HORIZON_REPORTS_PATH=/path/to/your/reports
   REPORT_COUNTY=Roger Mills
   REPORT_STATE=Oklahoma
   ```

3. **Never share or commit your .env file!**

## Google Drive Setup (Optional)

### Option 1: Local Sync (Easiest)

If Google Drive is installed on your computer:

1. Find your Google Drive folder path (usually `C:\Users\YourName\Google Drive` or `/Users/YourName/Google Drive`)
2. Create a folder in Google Drive called "Horizon Reports"
3. Add to `.env`:
   ```
   GOOGLE_DRIVE_SYNC_PATH=C:\Users\YourName\Google Drive\Horizon Reports
   ```

### Option 2: API Sync (Advanced)

Requires a Google service account. Steps:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project
3. Enable Google Drive API
4. Create a service account and download the JSON key
5. Share your Google Drive folder with the service account email
6. Add to `.env`:
   ```
   GOOGLE_DRIVE_FOLDER_ID=your-folder-id
   GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account-key.json
   ```

## Understanding the Output

### Confidence Score

Reports include a confidence score (0-100):

- **80-100**: High confidence - data appears reliable
- **60-79**: Medium confidence - some gaps or issues
- **0-59**: Low confidence - significant human review required

### Report Contents

**DOCX Report:**
- Report metadata and property information
- Source documents summary
- Ownership table
- Chain of title
- Missing items and exceptions
- QA summary
- Analyst notes

**XLSX Workbook:**
- Summary sheet
- Ownership data (complete with all fields)
- Chain of title
- Source documents list
- Missing items
- Exceptions
- QA checks
- Calculations (totals, variances)
- Run log

**PDF Report:**
- Summary version of the report
- Key ownership data
- QA metrics

**QA Report (Markdown):**
- Detailed quality assurance results
- List of all checks performed
- Confidence score breakdown
- Warnings and issues

## Troubleshooting

### "No source files found"
- Check that files are in the `inputs/` folder
- Supported formats: .xlsx, .xls, .csv, .docx, .pdf

### "Module not found" error
- Make sure virtual environment is activated
- Run: `pip install -r horizon_report/requirements.txt`

### PDF generation skipped
- This is normal if reportlab is not installed
- To enable PDF: `pip install reportlab`

### Google Drive sync failed
- Check your `.env` configuration
- For local sync: verify the folder path exists
- For API sync: verify service account has access

### Low confidence score
- This means the tool couldn't extract verified ownership data
- Review source files to ensure they contain ownership information
- Check QA report for specific issues

## Important Notes

### What This Tool Does:
✅ Scans and inventories files in the input folder
✅ Parses data from Excel, CSV, Word, and PDF files
✅ Generates structured ownership reports
✅ Runs quality assurance checks
✅ Syncs to Google Drive (if configured)

### What This Tool Does NOT Do:
❌ Does not fabricate or guess ownership data
❌ Does not extract data from image-only PDFs (OCR not included)
❌ Does not modify original source files
❌ Does not upload data without explicit sync configuration

### Security:
- Never commit `.env` files to version control
- Keep service account JSON files secure
- Generated reports may contain confidential data
- Review `.gitignore` to ensure sensitive files are excluded

## Support

For issues or questions:
1. Check the log file in `logs/run_YYYY-MM-DD.txt`
2. Review the QA report for specific errors
3. Ensure all source files are in supported formats
4. Verify Python and all dependencies are installed correctly

## File Structure

```
workspace/
├── horizon_report/          # Main package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration management
│   ├── models.py           # Data models
│   ├── utils.py            # Utility functions
│   ├── inventory.py        # File scanning
│   ├── parsers.py          # Document parsers
│   ├── generators.py       # Report generators
│   ├── qa.py               # Quality assurance
│   ├── drive_sync.py       # Google Drive sync
│   └── requirements.txt    # Package dependencies
├── inputs/                  # Place source files here
├── templates/               # Optional templates
├── reports/                 # Generated reports
│   ├── generated/          # DOCX, XLSX, PDF outputs
│   ├── qa/                 # QA reports
│   └── inventory/          # File inventory reports
├── logs/                    # Operation logs
├── archive/                 # Archived files
├── .env                     # Your configuration (don't commit!)
└── .env.example            # Configuration template
```

## Version

Current version: 1.0.0

---

**Remember:** This tool only extracts and reports data from your source files. It never fabricates ownership information. If the confidence score is low, review your source documents to ensure they contain the needed data.
