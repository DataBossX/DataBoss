"""Command-line interface for Horizon report generation."""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from .config import get_config
from .utils import setup_logging, print_table, parse_section_string
from .inventory import InventoryScanner
from .parsers import ParserFactory
from .generators import DocxGenerator, XlsxGenerator, PdfGenerator
from .qa import QAEngine
from .drive_sync import GoogleDriveSync
from .models import ReportBundle, ReportMetadata


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DataBoss Horizon Ownership Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m horizon_report generate --input inputs --date 2026-07-05
  python -m horizon_report qa --date 2026-07-05
  python -m horizon_report inventory
  python -m horizon_report sync-drive --date 2026-07-05
  python -m horizon_report build-all --input inputs --date 2026-07-05
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate ownership reports')
    gen_parser.add_argument('--input', '--input-folder', dest='input_folder', 
                           help='Input folder path (overrides config)')
    gen_parser.add_argument('--date', required=True, help='Report date (YYYY-MM-DD)')
    gen_parser.add_argument('--section', help='Section identifier (e.g., 31-12N-24W)')
    gen_parser.add_argument('--county', help='County name')
    gen_parser.add_argument('--state', help='State name')
    
    # QA command
    qa_parser = subparsers.add_parser('qa', help='Run QA checks on existing reports')
    qa_parser.add_argument('--date', required=True, help='Report date to check')
    
    # Inventory command
    inv_parser = subparsers.add_parser('inventory', help='Scan and inventory files')
    inv_parser.add_argument('--date', help='Report date (defaults to today)')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync-drive', help='Sync reports to Google Drive')
    sync_parser.add_argument('--date', required=True, help='Report date to sync')
    
    # Build-all command
    build_parser = subparsers.add_parser('build-all', help='Run full pipeline: inventory + generate + QA + sync')
    build_parser.add_argument('--input', '--input-folder', dest='input_folder',
                             help='Input folder path (overrides config)')
    build_parser.add_argument('--date', required=True, help='Report date (YYYY-MM-DD)')
    build_parser.add_argument('--section', help='Section identifier')
    build_parser.add_argument('--county', help='County name')
    build_parser.add_argument('--state', help='State name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Load configuration
    config = get_config()
    
    # Setup logging
    log_path = config.logs_path / f"run_{args.date if hasattr(args, 'date') and args.date else datetime.now().strftime('%Y-%m-%d')}.txt"
    logger = setup_logging(log_path)
    
    logger.info("=" * 80)
    logger.info(f"Horizon Report Generator - {args.command.upper()} Command")
    logger.info("=" * 80)
    
    config.log_configuration(logger)
    
    # Execute command
    try:
        if args.command == 'generate':
            return cmd_generate(args, config, logger)
        elif args.command == 'qa':
            return cmd_qa(args, config, logger)
        elif args.command == 'inventory':
            return cmd_inventory(args, config, logger)
        elif args.command == 'sync-drive':
            return cmd_sync_drive(args, config, logger)
        elif args.command == 'build-all':
            return cmd_build_all(args, config, logger)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


def cmd_generate(args, config, logger):
    """Generate ownership reports."""
    logger.info("Starting report generation...")
    
    # Override input folder if specified
    input_folder = Path(args.input_folder) if args.input_folder else config.input_path
    
    # Create scanner and scan input files
    scanner = InventoryScanner(logger)
    source_docs = scanner.scan_directory(input_folder)
    
    if not source_docs:
        logger.warning("No source files found in input folder")
    
    # Parse source documents
    logger.info("Parsing source documents...")
    for doc in source_docs:
        parser = ParserFactory.create_parser(doc, logger)
        if parser:
            doc.parsed_data = parser.parse(doc)
    
    # Build report bundle
    bundle = _build_report_bundle(args, config, source_docs, str(input_folder))
    
    # Extract ownership data from parsed documents
    from .parsers import ExcelParser
    excel_parser = ExcelParser(logger)
    for doc in source_docs:
        if doc.file_type in ['.xlsx', '.xls', '.csv'] and doc.parsed_data:
            entries = excel_parser.extract_ownership_entries(doc.parsed_data)
            bundle.ownership_entries.extend(entries)
    
    logger.info(f"Extracted {len(bundle.ownership_entries)} ownership entries")
    
    # Add analyst notes
    if not bundle.ownership_entries:
        bundle.analyst_notes.append("⚠️ NO VERIFIED OWNERSHIP DATA EXTRACTED — SOURCE REVIEW REQUIRED")
        bundle.analyst_notes.append("No ownership entries were extracted from source files")
        bundle.analyst_notes.append("Possible reasons: files may be templates, empty, or in unexpected format")
    
    bundle.analyst_notes.append(f"Processed {len(source_docs)} source documents")
    bundle.analyst_notes.append(f"Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}")
    
    # Generate outputs
    generated_files = _generate_outputs(bundle, args.date, config, logger)
    
    # Run QA
    qa_engine = QAEngine(logger, config)
    qa_results, confidence = qa_engine.run_all_checks(bundle, generated_files)
    bundle.qa_results = qa_results
    bundle.confidence_score = confidence
    
    # Generate QA report
    qa_md_path = config.reports_path / "qa" / f"qa_report_{args.date}.md"
    qa_engine.generate_qa_report(qa_md_path, bundle, confidence)
    generated_files['qa_md'] = qa_md_path
    
    # Sync to Google Drive
    drive_sync = GoogleDriveSync(logger, config)
    sync_files = [f for f in generated_files.values() if isinstance(f, Path) and f.exists()]
    sync_result = drive_sync.sync_files(sync_files)
    generated_files['drive_sync_status'] = sync_result['status']
    
    # Print summary
    _print_summary(bundle, generated_files, sync_result, logger)
    
    logger.info("=" * 80)
    logger.info("Report generation complete")
    logger.info("=" * 80)
    
    return 0


def cmd_qa(args, config, logger):
    """Run QA checks on existing reports."""
    logger.info(f"Running QA checks for date: {args.date}")
    
    # Find generated files
    generated_files = {
        'docx': config.reports_path / "generated" / f"Ownership_Report_{args.date}.docx",
        'xlsx': config.reports_path / "generated" / f"Ownership_Report_{args.date}.xlsx",
        'pdf': config.reports_path / "generated" / f"Ownership_Report_{args.date}.pdf",
        'log': config.logs_path / f"run_{args.date}.txt",
    }
    
    # Create minimal bundle for QA
    bundle = ReportBundle(
        metadata=ReportMetadata(
            report_date=args.date,
            generated_at=datetime.now()
        )
    )
    
    # Run QA
    qa_engine = QAEngine(logger, config)
    qa_results, confidence = qa_engine.run_all_checks(bundle, generated_files)
    
    # Generate QA report
    qa_md_path = config.reports_path / "qa" / f"qa_report_{args.date}.md"
    qa_engine.generate_qa_report(qa_md_path, bundle, confidence)
    
    logger.info(f"QA report generated: {qa_md_path}")
    logger.info(f"Confidence score: {confidence:.1f}/100")
    
    # Print summary table
    passed = sum(1 for r in qa_results if r.passed)
    print_table(
        ["Metric", "Value"],
        [
            ["QA Checks Run", len(qa_results)],
            ["Passed", passed],
            ["Failed", len(qa_results) - passed],
            ["Confidence Score", f"{confidence:.1f}/100"]
        ],
        title="QA Summary"
    )
    
    return 0


def cmd_inventory(args, config, logger):
    """Scan and inventory files."""
    report_date = args.date if hasattr(args, 'date') and args.date else datetime.now().strftime("%Y-%m-%d")
    
    logger.info("Starting file inventory scan...")
    
    # Scan directories
    scanner = InventoryScanner(logger)
    dirs_to_scan = [
        config.input_path,
        config.template_path,
        config.reports_path,
    ]
    
    all_docs = scanner.scan_multiple(dirs_to_scan)
    
    # Generate inventory reports
    inventory_path = config.reports_path / "inventory"
    scanner.generate_inventory_report(inventory_path, report_date)
    
    # Print summary
    categories = scanner.categorize_documents()
    
    rows = []
    for category, docs in categories.items():
        if docs:
            rows.append([category.replace('_', ' ').title(), len(docs)])
    
    print_table(
        ["Category", "Count"],
        rows,
        title="Inventory Summary"
    )
    
    logger.info(f"Total files inventoried: {len(all_docs)}")
    
    return 0


def cmd_sync_drive(args, config, logger):
    """Sync reports to Google Drive."""
    logger.info(f"Syncing reports for date: {args.date}")
    
    # Find generated files
    file_paths = [
        config.reports_path / "generated" / f"Ownership_Report_{args.date}.docx",
        config.reports_path / "generated" / f"Ownership_Report_{args.date}.xlsx",
        config.reports_path / "generated" / f"Ownership_Report_{args.date}.pdf",
        config.reports_path / "qa" / f"qa_report_{args.date}.md",
    ]
    
    # Filter to existing files
    existing_files = [f for f in file_paths if f.exists()]
    
    if not existing_files:
        logger.error("No generated files found to sync")
        return 1
    
    logger.info(f"Found {len(existing_files)} files to sync")
    
    # Sync
    drive_sync = GoogleDriveSync(logger, config)
    result = drive_sync.sync_files(existing_files)
    
    print_table(
        ["Metric", "Value"],
        [
            ["Sync Mode", result.get('mode', 'unknown')],
            ["Status", result.get('status', 'unknown')],
            ["Files Synced", result.get('files_synced', 0)],
            ["Message", result.get('message', '')]
        ],
        title="Google Drive Sync Result"
    )
    
    return 0 if result['status'] in ['success', 'skipped'] else 1


def cmd_build_all(args, config, logger):
    """Run full pipeline: inventory + generate + QA + sync."""
    logger.info("Running full build pipeline...")
    
    # Step 1: Inventory
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: INVENTORY")
    logger.info("=" * 80)
    cmd_inventory(args, config, logger)
    
    # Step 2: Generate
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: GENERATE REPORTS")
    logger.info("=" * 80)
    result = cmd_generate(args, config, logger)
    
    if result != 0:
        logger.error("Report generation failed, stopping pipeline")
        return result
    
    # Step 3: QA (already done in generate, but run standalone for completeness)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: QUALITY ASSURANCE")
    logger.info("=" * 80)
    cmd_qa(args, config, logger)
    
    # Step 4: Sync
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: GOOGLE DRIVE SYNC")
    logger.info("=" * 80)
    cmd_sync_drive(args, config, logger)
    
    logger.info("\n" + "=" * 80)
    logger.info("FULL PIPELINE COMPLETE")
    logger.info("=" * 80)
    
    return 0


def _build_report_bundle(args, config, source_docs, input_folder_str):
    """Build report bundle from arguments and config.
    
    Args:
        args: Command line arguments
        config: Configuration
        source_docs: List of source documents
        input_folder_str: Input folder string
        
    Returns:
        ReportBundle instance
    """
    # Parse section if provided
    section_info = {}
    if hasattr(args, 'section') and args.section:
        section_info = parse_section_string(args.section)
    elif config.section_target:
        section_info = parse_section_string(config.section_target)
    
    # Create metadata
    metadata = ReportMetadata(
        report_date=args.date,
        generated_at=datetime.now(),
        section=section_info.get('section', ''),
        township=section_info.get('township', ''),
        range=section_info.get('range', ''),
        county=getattr(args, 'county', None) or config.report_county,
        state=getattr(args, 'state', None) or config.report_state,
        input_folder=input_folder_str,
        sources_count=len(source_docs)
    )
    
    # Create bundle
    bundle = ReportBundle(
        metadata=metadata,
        source_documents=source_docs
    )
    
    return bundle


def _generate_outputs(bundle, date_str, config, logger):
    """Generate all output files.
    
    Args:
        bundle: Report bundle
        date_str: Date string
        config: Configuration
        logger: Logger
        
    Returns:
        Dictionary of generated file paths
    """
    output_dir = config.reports_path / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated = {}
    
    # DOCX
    logger.info("Generating DOCX report...")
    docx_path = output_dir / f"Ownership_Report_{date_str}.docx"
    docx_gen = DocxGenerator(logger)
    if docx_gen.generate(bundle, docx_path):
        generated['docx'] = docx_path
    
    # XLSX
    logger.info("Generating XLSX report...")
    xlsx_path = output_dir / f"Ownership_Report_{date_str}.xlsx"
    xlsx_gen = XlsxGenerator(logger)
    if xlsx_gen.generate(bundle, xlsx_path):
        generated['xlsx'] = xlsx_path
    
    # PDF
    logger.info("Generating PDF report...")
    pdf_path = output_dir / f"Ownership_Report_{date_str}.pdf"
    pdf_gen = PdfGenerator(logger)
    if pdf_gen.generate(bundle, pdf_path):
        generated['pdf'] = pdf_path
    else:
        logger.warning("PDF generation skipped or failed")
    
    # Log file
    generated['log'] = config.logs_path / f"run_{date_str}.txt"
    
    return generated


def _print_summary(bundle, generated_files, sync_result, logger):
    """Print summary of generation results.
    
    Args:
        bundle: Report bundle
        generated_files: Generated files dictionary
        sync_result: Sync result dictionary
        logger: Logger
    """
    print("\n" + "=" * 80)
    print("REPORT GENERATION SUMMARY")
    print("=" * 80)
    
    # Metadata
    rows = [
        ["Report Date", bundle.metadata.report_date],
        ["Generated At", bundle.metadata.generated_at.strftime("%Y-%m-%d %H:%M:%S")],
    ]
    
    if bundle.metadata.section:
        rows.append(["Section", f"{bundle.metadata.section}-{bundle.metadata.township}-{bundle.metadata.range}"])
    if bundle.metadata.county:
        rows.append(["County", f"{bundle.metadata.county}, {bundle.metadata.state}"])
    
    print_table(["Field", "Value"], rows, title="Report Information")
    
    # Statistics
    rows = [
        ["Source Documents", len(bundle.source_documents)],
        ["Ownership Entries", len(bundle.ownership_entries)],
        ["Chain Events", len(bundle.chain_events)],
        ["Missing Items", len(bundle.missing_items)],
        ["Exceptions", len(bundle.exceptions)],
        ["Confidence Score", f"{bundle.confidence_score:.1f}/100"]
    ]
    
    print_table(["Metric", "Value"], rows, title="Statistics")
    
    # Generated files
    file_rows = []
    for file_type, file_path in generated_files.items():
        if isinstance(file_path, Path):
            status = "✓ Created" if file_path.exists() else "✗ Missing"
            file_rows.append([file_type.upper(), file_path.name, status])
    
    if file_rows:
        print_table(["Type", "Filename", "Status"], file_rows, title="Generated Files")
    
    # Google Drive sync
    sync_rows = [
        ["Mode", sync_result.get('mode', 'unknown')],
        ["Status", sync_result.get('status', 'unknown')],
        ["Files Synced", sync_result.get('files_synced', 0)]
    ]
    
    print_table(["Field", "Value"], sync_rows, title="Google Drive Sync")
    
    # Critical warnings
    if bundle.confidence_score < 70:
        print("\n⚠️  CRITICAL WARNINGS:")
        print(f"   - Confidence score is LOW ({bundle.confidence_score:.1f}/100)")
        print("   - Significant human review required before using this report")
    
    if not bundle.ownership_entries:
        print("\n❌ CRITICAL: NO OWNERSHIP DATA EXTRACTED")
        print("   - No ownership entries were found in source documents")
        print("   - This report contains only structure, not actual data")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    sys.exit(main())
