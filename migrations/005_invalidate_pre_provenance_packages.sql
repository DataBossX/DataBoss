UPDATE title_package_details
   SET review_status = 'INVALIDATED_PRE_PROVENANCE'
 WHERE review_status = 'AWAITING_REVIEW';

UPDATE pipeline_runs
   SET status = 'FAILED_TERMINAL',
       error = 'Package predates evidence-span binding and must be rebuilt'
 WHERE id IN (
    SELECT pipeline_run_id
      FROM title_package_details
     WHERE review_status = 'INVALIDATED_PRE_PROVENANCE'
 );

UPDATE title_cases
   SET status = 'NEEDS_PROVENANCE_REVIEW'
 WHERE EXISTS (
    SELECT 1
      FROM title_instruments i
     WHERE i.title_case_id = title_cases.id
       AND i.evidence_asset_version_id IS NOT NULL
       AND i.evidence_span_sha256 IS NULL
 );
