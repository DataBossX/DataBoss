-- Restore pending packages that were built after field-level provenance binding.
UPDATE title_package_details
   SET review_status = 'AWAITING_REVIEW'
 WHERE review_status = 'INVALIDATED_PRE_PROVENANCE'
   AND EXISTS (
       SELECT 1
         FROM title_instruments i
        WHERE i.title_case_id = title_package_details.title_case_id
          AND i.evidence_span_sha256 IS NOT NULL
   )
   AND NOT EXISTS (
       SELECT 1
         FROM title_instruments i
        WHERE i.title_case_id = title_package_details.title_case_id
          AND (
              (i.evidence_asset_version_id IS NOT NULL
               AND i.evidence_span_sha256 IS NULL)
              OR
              (i.review_status = 'REVIEWED'
               AND i.evidence_asset_version_id IS NULL)
          )
   );

UPDATE pipeline_runs
   SET status = 'WAITING_HUMAN',
       error = NULL
 WHERE id IN (
    SELECT pipeline_run_id
      FROM title_package_details
     WHERE review_status = 'AWAITING_REVIEW'
 );

-- Invalidate legacy packages regardless of whether they were pending or approved.
UPDATE title_package_details
   SET review_status = 'INVALIDATED_PRE_PROVENANCE',
       approved_manifest_sha256 = NULL
 WHERE EXISTS (
    SELECT 1
      FROM title_instruments i
     WHERE i.title_case_id = title_package_details.title_case_id
       AND (
           (i.evidence_asset_version_id IS NOT NULL
            AND i.evidence_span_sha256 IS NULL)
           OR
           (i.review_status = 'REVIEWED'
            AND i.evidence_asset_version_id IS NULL)
       )
 );

UPDATE pipeline_runs
   SET status = 'FAILED_TERMINAL',
       error = 'Package predates evidence-span binding and must be rebuilt'
 WHERE id IN (
    SELECT pipeline_run_id
      FROM title_package_details
     WHERE review_status = 'INVALIDATED_PRE_PROVENANCE'
 );
