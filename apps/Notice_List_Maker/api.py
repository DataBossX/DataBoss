"""
FastAPI Backend for Notice List Maker
Handles heavy processing: geospatial operations, owner resolution, etc.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import tempfile
import logging
from pathlib import Path
from datetime import datetime
import uuid

# Import our processing modules
from ingest.pdf_ingest import PDFIngestor
from ingest.spreadsheet_ingest import SpreadsheetIngestor
from ingest.normalize_input import InputNormalizer, Case
from geospatial.unit_builder import UnitBuilder
from geospatial.buffer_engine import BufferEngine
from geospatial.tract_selector import TractSelector
from title.owner_resolver import OwnerResolver
from title.lease_classifier import LeaseClassifier
from title.address_resolver import AddressResolver
from output.excel_writer import ExcelWriter
from db.database import Database
from connectors.connector_manager import ConnectorManager

logger = logging.getLogger(__name__)

app = FastAPI(title="Notice List Maker API", version="1.0.0")

# Store for job statuses
job_store: Dict[str, Dict] = {}


class ProcessingRequest(BaseModel):
    """Request to process notice list."""
    unit_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    plss_meridian: Optional[str] = "6PM"
    use_connectors: bool = False


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: float  # 0.0 - 1.0
    message: str
    result: Optional[Dict] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Notice List Maker API"}


@app.post("/api/notice-list/process", response_model=JobStatus)
async def create_notice_list_job(
    background_tasks: BackgroundTasks,
    pdf_files: List[UploadFile] = File(None),
    spreadsheet_files: List[UploadFile] = File(None),
    request_data: ProcessingRequest = None
):
    """
    Create a new notice list processing job.

    This endpoint accepts file uploads and metadata, then processes
    asynchronously in the background.
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    # Initialize job status
    job_store[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "message": "Job created",
        "created_at": datetime.now().isoformat()
    }

    # Save uploaded files to temp directory
    temp_dir = Path(tempfile.mkdtemp())
    pdf_paths = []
    sheet_paths = []

    try:
        if pdf_files:
            for pdf in pdf_files:
                temp_path = temp_dir / pdf.filename
                with open(temp_path, 'wb') as f:
                    content = await pdf.read()
                    f.write(content)
                pdf_paths.append(str(temp_path))

        if spreadsheet_files:
            for sheet in spreadsheet_files:
                temp_path = temp_dir / sheet.filename
                with open(temp_path, 'wb') as f:
                    content = await sheet.read()
                    f.write(content)
                sheet_paths.append(str(temp_path))

        # Schedule background processing
        background_tasks.add_task(
            process_notice_list,
            job_id=job_id,
            pdf_paths=pdf_paths,
            sheet_paths=sheet_paths,
            unit_name=request_data.unit_name if request_data else None,
            county=request_data.county if request_data else None,
            state=request_data.state if request_data else None,
            plss_meridian=request_data.plss_meridian if request_data else "6PM",
            use_connectors=request_data.use_connectors if request_data else False
        )

        return JobStatus(
            job_id=job_id,
            status="pending",
            progress=0.0,
            message="Job queued for processing"
        )

    except Exception as e:
        logger.error(f"Failed to create job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notice-list/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get status of a processing job."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_store[job_id]

    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result=job.get("result"),
        error=job.get("error")
    )


@app.get("/api/notice-list/download/{job_id}")
async def download_result(job_id: str):
    """Download the generated Excel file."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_store[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    output_path = job.get("result", {}).get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(output_path).name
    )


async def process_notice_list(
    job_id: str,
    pdf_paths: List[str],
    sheet_paths: List[str],
    unit_name: Optional[str],
    county: Optional[str],
    state: Optional[str],
    plss_meridian: str,
    use_connectors: bool
):
    """
    Background task to process notice list.

    This is the main processing pipeline.
    """
    try:
        # Update status
        update_job_status(job_id, "processing", 0.1, "Initializing...")

        # Initialize components
        db = Database()
        pdf_ingestor = PDFIngestor()
        sheet_ingestor = SpreadsheetIngestor()
        normalizer = InputNormalizer()

        update_job_status(job_id, "processing", 0.2, "Ingesting files...")

        # Ingest PDFs
        all_pdf_tracts = []
        for pdf_path in pdf_paths:
            result = pdf_ingestor.read_pdf(pdf_path)
            if "error" not in result:
                all_pdf_tracts.extend(result.get("tracts", []))

        # Ingest spreadsheets
        all_sheet_tracts = []
        for sheet_path in sheet_paths:
            result = sheet_ingestor.read_file(sheet_path)
            if result.get("success"):
                all_sheet_tracts.extend(sheet_ingestor.tracts)

        update_job_status(job_id, "processing", 0.3, "Normalizing input...")

        # Normalize inputs into Case object
        case = normalizer.normalize_to_case(
            pdf_tracts=all_pdf_tracts,
            sheet_tracts=all_sheet_tracts,
            unit_name=unit_name,
            county=county,
            state=state,
            plss_meridian=plss_meridian
        )

        # Save case to database
        case_id = db.save_case(case)

        update_job_status(job_id, "processing", 0.4, "Building unit geometry...")

        # Build unit geometry
        unit_builder = UnitBuilder(base_meridian=plss_meridian)
        for tract in case.unit_tracts:
            unit_builder.add_tract(
                tract_id=tract.tract_id,
                legal_description=tract.legal_description,
                gross_acres=tract.gross_acres,
                net_acres=tract.net_acres
            )

        unit_polygon = unit_builder.build_unit_polygon()
        if not unit_polygon:
            raise ValueError("Failed to build unit polygon")

        update_job_status(job_id, "processing", 0.5, "Creating offset buffer...")

        # Create offset buffer
        buffer_engine = BufferEngine(buffer_distance_miles=0.5)
        offset_polygon = buffer_engine.get_offset_zone(unit_polygon, exclude_unit=True)

        update_job_status(job_id, "processing", 0.6, "Classifying tracts...")

        # Classify tracts
        selector = TractSelector(unit_polygon, offset_polygon)
        tracts_to_classify = [
            {
                "tract_id": t.tract_id,
                "legal_description": t.legal_description,
                "geometry": unit_builder.tracts[i].geometry
            }
            for i, t in enumerate(case.unit_tracts)
        ]

        unit_tracts, offset_tracts = selector.classify_batch(tracts_to_classify)

        update_job_status(job_id, "processing", 0.7, "Resolving owners...")

        # Initialize title components
        owner_resolver = OwnerResolver()
        lease_classifier = LeaseClassifier()
        address_resolver = AddressResolver()

        # Use connectors if enabled
        if use_connectors:
            connector_mgr = ConnectorManager(db)

            for tract in unit_tracts + offset_tracts:
                # Resolve owners via connectors
                owners = await connector_mgr.search_owners(tract.tract_id)
                for owner_data in owners:
                    owner_resolver.add_owner_from_connector(
                        tract_id=tract.tract_id,
                        owner_data=owner_data
                    )

                # Resolve addresses
                for owner in owner_resolver.get_owners_by_tract(tract.tract_id):
                    address_data = await connector_mgr.resolve_address(owner.owner_name)
                    if address_data:
                        address_resolver.add_address_from_connector(
                            owner_name=owner.owner_name,
                            address_data=address_data
                        )

        update_job_status(job_id, "processing", 0.8, "Generating Excel output...")

        # Generate Excel output
        excel_writer = ExcelWriter()

        # Add unit tracts
        for classified_tract in unit_tracts:
            owners = owner_resolver.get_owners_by_tract(classified_tract.tract_id)

            for owner in owners:
                lease_status = lease_classifier.classify_owner(
                    owner_name=owner.owner_name,
                    ownership_type=owner.ownership_type.value,
                    tract_id=classified_tract.tract_id
                )

                best_addr = address_resolver.get_best_address(owner.owner_name)

                excel_writer.add_unit_row(
                    owner_name=owner.owner_name,
                    mailing_address=str(best_addr.address) if best_addr else "UNKNOWN",
                    tract_id=classified_tract.tract_id,
                    legal_description=classified_tract.legal_description,
                    lease_status=lease_status.value,
                    ownership_type=owner.ownership_type.value,
                    interest=owner.interest_fraction,
                    address_source=best_addr.source.value if best_addr else "unknown",
                    address_date=best_addr.source_date if best_addr else None,
                    confidence_score=classified_tract.confidence_score,
                    offset_method=classified_tract.offset_method,
                    evidence=owner.raw_data.get("evidence", []) if owner.raw_data else []
                )

        # Add offset tracts
        for classified_tract in offset_tracts:
            owners = owner_resolver.get_owners_by_tract(classified_tract.tract_id)

            for owner in owners:
                lease_status = lease_classifier.classify_owner(
                    owner_name=owner.owner_name,
                    ownership_type=owner.ownership_type.value,
                    tract_id=classified_tract.tract_id
                )

                best_addr = address_resolver.get_best_address(owner.owner_name)

                excel_writer.add_offset_row(
                    owner_name=owner.owner_name,
                    mailing_address=str(best_addr.address) if best_addr else "UNKNOWN",
                    tract_id=classified_tract.tract_id,
                    legal_description=classified_tract.legal_description,
                    lease_status=lease_status.value,
                    ownership_type=owner.ownership_type.value,
                    distance_to_unit_miles=classified_tract.distance_to_unit_miles,
                    interest=owner.interest_fraction,
                    address_source=best_addr.source.value if best_addr else "unknown",
                    address_date=best_addr.source_date if best_addr else None,
                    confidence_score=classified_tract.confidence_score,
                    offset_method=classified_tract.offset_method,
                    evidence=owner.raw_data.get("evidence", []) if owner.raw_data else []
                )

        update_job_status(job_id, "processing", 0.9, "Writing Excel file...")

        # Write Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"Notice_List_{unit_name or 'Unit'}_{timestamp}.xlsx"
        output_path = Path(tempfile.gettempdir()) / output_filename

        success = excel_writer.write_excel(str(output_path), unit_name)

        if not success:
            raise ValueError("Failed to write Excel file")

        # Update job with completion
        update_job_status(
            job_id,
            "completed",
            1.0,
            "Processing complete",
            result={
                "output_path": str(output_path),
                "case_id": case_id,
                "unit_tracts": len(unit_tracts),
                "offset_tracts": len(offset_tracts),
                "summary": excel_writer.get_summary()
            }
        )

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0.0, "Processing failed", error=str(e))


def update_job_status(
    job_id: str,
    status: str,
    progress: float,
    message: str,
    result: Optional[Dict] = None,
    error: Optional[str] = None
):
    """Update job status in store."""
    if job_id in job_store:
        job_store[job_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            "updated_at": datetime.now().isoformat()
        })

        if result:
            job_store[job_id]["result"] = result

        if error:
            job_store[job_id]["error"] = error


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
