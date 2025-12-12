# Notice List Maker

**Production-grade oil & gas notice list generator**

Upload → Run → Download. That's it.

## What It Does

This app has exactly **one job**: Generate proper notice lists for oil & gas drilling permits.

**Input:**
- PDF unit maps (plats, COGCC/RRC exhibits, DSU maps)
- XLSX/CSV tract spreadsheets (STRs, aliquots, legal descriptions)
- Optional manual inputs (unit name, county, state)

**Output:**
- One clean XLSX file with **exactly two sheets**:
  1. `UNIT_NOTICE_LIST` - Owners within the unit boundary
  2. `OFFSET_NOTICE_LIST` - Owners within ½ mile of unit boundary

**Processing:**
1. Identifies unit tracts from uploaded files
2. Builds true geometric ½-mile buffer (NOT "neighboring sections")
3. Resolves mineral owners (UMI/ROY) and working interest owners (WI)
4. Determines current mailing addresses with source tracking
5. Classifies lease status using hard rules (no guessing)

## Installation

### Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

### Setup

```bash
cd apps/Notice_List_Maker

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## How to Use

1. **Upload files**
   - Upload one or more PDF unit maps
   - Upload one or more XLSX/CSV tract spreadsheets
   - At least one file is required

2. **Enter unit information**
   - Unit Name (required)
   - County (optional)
   - State (optional)

3. **Click "RUN NOTICE LIST"**
   - Processing typically takes 10-30 seconds
   - Progress bar shows current step

4. **Download XLSX**
   - Click "DOWNLOAD XLSX" button
   - Open in Excel
   - Review `UNIT_NOTICE_LIST` and `OFFSET_NOTICE_LIST` sheets

## Output Format

### Column Structure

Both sheets contain these columns:

| Column | Description |
|--------|-------------|
| `OWNER_NAME` | Owner name |
| `MAILING_ADDRESS` | Current mailing address |
| `TRACT_ID` | Tract identifier |
| `LEGAL_DESCRIPTION` | Legal description (Township/Range/Section) |
| `GROSS_ACRES` | Gross acreage |
| `NET_ACRES` | Net mineral acres |
| `LEASE_STATUS` | UMI, ROY, or WI |
| `OWNERSHIP_TYPE` | MINERAL, LEASEHOLD, or WORKING_INTEREST |
| `INTEREST` | Fractional or decimal interest |
| `ADDRESS_SOURCE` | Source of address (recent_instrument, county_tax_roll, etc.) |
| `ADDRESS_DATE` | Date of address source |
| `CONFIDENCE_SCORE` | Confidence score (0-100) |
| `DISTANCE_TO_UNIT_MILES` | Distance to unit (offset sheet only) |

### Lease Status Rules (Hard Rules)

- **UMI** = Unleased Mineral Interest
  - Owner owns minerals AND no active lease exists

- **ROY** = Royalty Interest (Leased Mineral)
  - Owner owns minerals AND active lease exists

- **WI** = Working Interest
  - Leasehold / Operator / Non-op working interest

- **UNKNOWN** = Cannot determine
  - Insufficient data to classify
  - Flagged for manual review

## Architecture

```
Notice_List_Maker/
├─ app.py                      # Streamlit UI
├─ config/                     # Configuration
├─ ingest/                     # PDF & spreadsheet readers
├─ geospatial/                 # Unit builder & buffer engine
├─ title/                      # Owner, lease, address resolution
├─ output/                     # Excel writer
├─ db/                         # SQLite cache
├─ tests/                      # Tests
└─ logs/                       # Log files
```

### Key Modules

**Ingest:**
- `pdf_ingest.py` - Reads PDF maps, extracts legal descriptions
- `spreadsheet_ingest.py` - Reads XLSX/CSV tract lists
- `normalize_input.py` - Normalizes various formats

**Geospatial:**
- `unit_builder.py` - Builds unit polygon from tracts
- `buffer_engine.py` - Creates true ½-mile geometric buffer
- `tract_selector.py` - Classifies tracts as UNIT or OFFSET

**Title:**
- `owner_resolver.py` - Resolves mineral & WI owners
- `lease_classifier.py` - Classifies lease status (UMI/ROY/WI)
- `address_resolver.py` - Resolves current mailing addresses

**Output:**
- `excel_writer.py` - Generates final XLSX with exact format

## Testing

Run tests to verify correctness:

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_buffer.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Coverage

- `test_ingest.py` - Verifies PDF/spreadsheet parsing
- `test_buffer.py` - Verifies geometric buffer creation
- `test_notice_output.py` - Verifies Excel structure

## Configuration

Edit `config/settings.yaml` to adjust:

- Buffer distance (default 0.5 miles)
- Address source priority
- Output column requirements
- Logging level

## Logging

Logs are written to `logs/notice_list.log`

Log entries include:
- Tract ingestion counts
- Geometry building success/failures
- Owner resolution results
- Output statistics

## Database Cache

SQLite cache at `db/local_cache.sqlite` stores:
- Tract information
- Owner data
- Address history
- Processing logs

Cache reduces redundant lookups for repeated operations.

## Limitations & Future Enhancements

**Current Limitations:**
- PLSS coordinate conversion is approximate (uses simple lat/lon calc)
- No integration with county records APIs (manual data entry required)
- Address parsing is basic (should use proper validation service)

**Production Enhancements:**
- Use real PLSS grid shapefiles for accurate coordinates
- Integrate county recorder APIs
- Add USPS address validation
- Support more file formats (DXF, SHP, KML)
- Add batch processing for multiple units

## Troubleshooting

### No tracts extracted from PDF
- Ensure PDF is text-based (not scanned image)
- Check if legal descriptions follow standard format (T#N R#W Sec #)

### Buffer creation fails
- Verify at least one tract has valid geometry
- Check tract legal descriptions are parseable

### Missing owner data
- Provide spreadsheet with owner information
- Or add manual owner entry feature

### Excel download fails
- Check disk space
- Verify write permissions in temp directory

## Support

For issues or questions:
1. Check logs at `logs/notice_list.log`
2. Run tests: `pytest tests/ -v`
3. Review validation warnings in app output

## License

Internal use only - DataBossX

## Version

v1.0.0 - Production Release
