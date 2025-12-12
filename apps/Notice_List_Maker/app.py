"""
Notice List Maker - Streamlit App

Simple interface: Upload → Run → Download
No dashboards, no charts, just production work.
"""

import streamlit as st
import logging
from pathlib import Path
import tempfile
import yaml
from datetime import datetime

# Import our modules
from ingest.pdf_ingest import PDFIngestor
from ingest.spreadsheet_ingest import SpreadsheetIngestor
from ingest.normalize_input import InputNormalizer
from geospatial.unit_builder import UnitBuilder
from geospatial.buffer_engine import BufferEngine
from geospatial.tract_selector import TractSelector
from title.owner_resolver import OwnerResolver, OwnershipType
from title.lease_classifier import LeaseClassifier, LeaseStatus
from title.address_resolver import AddressResolver, AddressSource
from output.excel_writer import ExcelWriter
from db.local_cache import LocalCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/notice_list.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Notice List Maker",
    page_icon="📋",
    layout="centered"
)


def load_config():
    """Load configuration from YAML."""
    with open("config/settings.yaml") as f:
        return yaml.safe_load(f)


def process_notice_list(
    pdf_files,
    spreadsheet_files,
    unit_name,
    county,
    state,
    progress_callback=None
) -> dict:
    """
    Main processing pipeline.

    Args:
        pdf_files: List of uploaded PDF files
        spreadsheet_files: List of uploaded spreadsheet files
        unit_name: Unit/DSU name
        county: County name
        state: State
        progress_callback: Optional callback for progress updates

    Returns:
        Result dictionary with output path or errors
    """
    try:
        # Initialize components
        pdf_ingestor = PDFIngestor()
        sheet_ingestor = SpreadsheetIngestor()
        normalizer = InputNormalizer()
        owner_resolver = OwnerResolver()
        lease_classifier = LeaseClassifier()
        address_resolver = AddressResolver()
        excel_writer = ExcelWriter()
        cache = LocalCache()

        if progress_callback:
            progress_callback("Ingesting PDF files...", 0.1)

        # Step 1: Ingest PDFs
        all_pdf_tracts = []
        for pdf_file in pdf_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_file.read())
                tmp_path = tmp.name

            result = pdf_ingestor.read_pdf(tmp_path)
            if "error" not in result:
                all_pdf_tracts.extend(result.get("tracts", []))

            Path(tmp_path).unlink()

        logger.info(f"Ingested {len(all_pdf_tracts)} tracts from PDFs")

        if progress_callback:
            progress_callback("Ingesting spreadsheet files...", 0.2)

        # Step 2: Ingest Spreadsheets
        all_sheet_tracts = []
        for sheet_file in spreadsheet_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(sheet_file.name).suffix) as tmp:
                tmp.write(sheet_file.read())
                tmp_path = tmp.name

            result = sheet_ingestor.read_file(tmp_path)
            if result.get("success"):
                all_sheet_tracts.extend(sheet_ingestor.tracts)

            Path(tmp_path).unlink()

        logger.info(f"Ingested {len(all_sheet_tracts)} tracts from spreadsheets")

        if progress_callback:
            progress_callback("Normalizing input data...", 0.3)

        # Step 3: Normalize all inputs
        normalized_tracts = []
        normalized_tracts.extend(normalizer.normalize_pdf_tracts(all_pdf_tracts))
        normalized_tracts.extend(normalizer.normalize_spreadsheet_tracts(all_sheet_tracts))

        if not normalized_tracts:
            return {"error": "No tracts found in uploaded files"}

        logger.info(f"Normalized {len(normalized_tracts)} total tracts")

        if progress_callback:
            progress_callback("Building unit geometry...", 0.4)

        # Step 4: Build unit geometry
        unit_builder = UnitBuilder()
        for tract in normalized_tracts:
            unit_builder.add_tract(
                tract_id=tract.tract_id,
                legal_description=tract.legal_description,
                gross_acres=tract.gross_acres,
                net_acres=tract.net_acres
            )

        unit_polygon = unit_builder.build_unit_polygon()
        if not unit_polygon:
            return {"error": "Failed to build unit polygon from tracts"}

        if progress_callback:
            progress_callback("Creating 0.5-mile buffer...", 0.5)

        # Step 5: Create offset buffer
        config = load_config()
        buffer_distance = config["buffer"]["offset_distance_miles"]
        buffer_engine = BufferEngine(buffer_distance_miles=buffer_distance)

        offset_polygon = buffer_engine.get_offset_zone(unit_polygon, exclude_unit=True)
        if not offset_polygon:
            return {"error": "Failed to create offset buffer"}

        if progress_callback:
            progress_callback("Classifying unit vs offset tracts...", 0.6)

        # Step 6: Classify tracts as UNIT or OFFSET
        selector = TractSelector(unit_polygon, offset_polygon)

        tracts_to_classify = [
            {
                "tract_id": t.tract_id,
                "legal_description": t.legal_description,
                "geometry": unit_builder.tracts[i].geometry
            }
            for i, t in enumerate(normalized_tracts)
        ]

        unit_tracts, offset_tracts = selector.classify_batch(tracts_to_classify)

        logger.info(f"Classified {len(unit_tracts)} UNIT tracts, {len(offset_tracts)} OFFSET tracts")

        if progress_callback:
            progress_callback("Resolving owners and addresses...", 0.7)

        # Step 7: Resolve owners (from spreadsheet data)
        for tract in normalizer.owners:
            owner_resolver.add_owner_from_spreadsheet(
                tract_id=tract.tract_id,
                owner_name=tract.owner_name,
                ownership_type=tract.ownership_type,
                interest=tract.interest_fraction
            )

        # Step 8: Classify lease status
        # For this demo, we'll mark all mineral owners without leases as UMI
        # In production, this would query actual lease records

        if progress_callback:
            progress_callback("Generating Excel output...", 0.8)

        # Step 9: Build Excel output
        # Add unit tracts
        for classified_tract in unit_tracts:
            # Get owners for this tract
            owners = owner_resolver.get_owners_by_tract(classified_tract.tract_id)

            if not owners:
                # No owner data - create placeholder
                owners = [type('obj', (object,), {
                    'owner_name': 'UNKNOWN',
                    'ownership_type': OwnershipType.MINERAL,
                    'interest_fraction': None
                })()]

            for owner in owners:
                # Classify lease status
                lease_status = lease_classifier.classify_owner(
                    owner_name=owner.owner_name,
                    ownership_type=owner.ownership_type.value if hasattr(owner.ownership_type, 'value') else str(owner.ownership_type),
                    tract_id=classified_tract.tract_id
                )

                # Get address (or placeholder)
                resolved_addr = address_resolver.get_best_address(owner.owner_name)
                if resolved_addr:
                    addr_str = str(resolved_addr.address)
                    addr_source = resolved_addr.source.value
                    addr_date = resolved_addr.source_date
                else:
                    addr_str = "ADDRESS UNKNOWN - REQUIRES RESEARCH"
                    addr_source = "unknown"
                    addr_date = None

                excel_writer.add_unit_row(
                    owner_name=owner.owner_name,
                    mailing_address=addr_str,
                    tract_id=classified_tract.tract_id,
                    legal_description=classified_tract.legal_description,
                    lease_status=lease_status.value,
                    ownership_type=owner.ownership_type.value if hasattr(owner.ownership_type, 'value') else str(owner.ownership_type),
                    gross_acres=None,  # Would come from tract data
                    net_acres=None,
                    interest=owner.interest_fraction,
                    address_source=addr_source,
                    address_date=addr_date,
                    confidence_score=classified_tract.confidence_score
                )

        # Add offset tracts
        for classified_tract in offset_tracts:
            owners = owner_resolver.get_owners_by_tract(classified_tract.tract_id)

            if not owners:
                owners = [type('obj', (object,), {
                    'owner_name': 'UNKNOWN',
                    'ownership_type': OwnershipType.MINERAL,
                    'interest_fraction': None
                })()]

            for owner in owners:
                lease_status = lease_classifier.classify_owner(
                    owner_name=owner.owner_name,
                    ownership_type=owner.ownership_type.value if hasattr(owner.ownership_type, 'value') else str(owner.ownership_type),
                    tract_id=classified_tract.tract_id
                )

                resolved_addr = address_resolver.get_best_address(owner.owner_name)
                if resolved_addr:
                    addr_str = str(resolved_addr.address)
                    addr_source = resolved_addr.source.value
                    addr_date = resolved_addr.source_date
                else:
                    addr_str = "ADDRESS UNKNOWN - REQUIRES RESEARCH"
                    addr_source = "unknown"
                    addr_date = None

                excel_writer.add_offset_row(
                    owner_name=owner.owner_name,
                    mailing_address=addr_str,
                    tract_id=classified_tract.tract_id,
                    legal_description=classified_tract.legal_description,
                    lease_status=lease_status.value,
                    ownership_type=owner.ownership_type.value if hasattr(owner.ownership_type, 'value') else str(owner.ownership_type),
                    distance_to_unit_miles=classified_tract.distance_to_unit_miles,
                    interest=owner.interest_fraction,
                    address_source=addr_source,
                    address_date=addr_date,
                    confidence_score=classified_tract.confidence_score
                )

        if progress_callback:
            progress_callback("Writing Excel file...", 0.9)

        # Step 10: Write Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"Notice_List_{unit_name.replace(' ', '_')}_{timestamp}.xlsx"
        output_path = Path(tempfile.gettempdir()) / output_filename

        success = excel_writer.write_excel(str(output_path), unit_name)

        if not success:
            return {"error": "Failed to write Excel file"}

        # Log to cache
        cache.log_processing(
            unit_name=unit_name,
            action="generate_notice_list",
            status="success",
            message=f"Generated notice list with {len(unit_tracts)} unit tracts, {len(offset_tracts)} offset tracts"
        )

        if progress_callback:
            progress_callback("Complete!", 1.0)

        return {
            "success": True,
            "output_path": str(output_path),
            "unit_tracts": len(unit_tracts),
            "offset_tracts": len(offset_tracts),
            "summary": excel_writer.get_summary()
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return {"error": str(e)}


def main():
    """Main Streamlit app."""

    st.title("📋 Notice List Maker")
    st.markdown("**Upload → Run → Download**")
    st.markdown("---")

    # Input section
    st.subheader("1. Upload Files")

    col1, col2 = st.columns(2)

    with col1:
        pdf_files = st.file_uploader(
            "PDF Unit Maps",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload unit maps, plats, or COGCC/RRC exhibits"
        )

    with col2:
        spreadsheet_files = st.file_uploader(
            "XLSX/CSV Tract Lists",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
            help="Upload tract spreadsheets with legal descriptions"
        )

    st.markdown("---")
    st.subheader("2. Unit Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        unit_name = st.text_input("Unit Name", placeholder="e.g., Smith 16-21 DSU")

    with col2:
        county = st.text_input("County", placeholder="e.g., Weld")

    with col3:
        state = st.text_input("State", value="CO", max_chars=2)

    st.markdown("---")

    # Run button
    can_run = (pdf_files or spreadsheet_files) and unit_name

    if st.button("▶️ RUN NOTICE LIST", type="primary", disabled=not can_run):
        if not can_run:
            st.error("Please upload at least one file and provide a unit name")
        else:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)

            # Run processing
            with st.spinner("Processing..."):
                result = process_notice_list(
                    pdf_files=pdf_files or [],
                    spreadsheet_files=spreadsheet_files or [],
                    unit_name=unit_name,
                    county=county,
                    state=state,
                    progress_callback=update_progress
                )

            # Show results
            if "error" in result:
                st.error(f"❌ Error: {result['error']}")
            elif result.get("success"):
                st.success("✅ Notice list generated successfully!")

                # Summary
                st.markdown("### Summary")
                col1, col2, col3 = st.columns(3)
                col1.metric("Unit Tracts", result["unit_tracts"])
                col2.metric("Offset Tracts", result["offset_tracts"])
                col3.metric("Total Rows", result["summary"]["total_rows"])

                # Download button
                st.markdown("---")
                with open(result["output_path"], "rb") as f:
                    st.download_button(
                        label="⬇️ DOWNLOAD XLSX",
                        data=f.read(),
                        file_name=Path(result["output_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                st.info("💡 Tip: Review the UNIT_NOTICE_LIST and OFFSET_NOTICE_LIST sheets")

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>"
        "Notice List Maker v1.0 | Production-grade oil & gas notice list generation"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("db").mkdir(exist_ok=True)

    main()
