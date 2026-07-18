UPDATE title_package_details
   SET review_status = 'INVALIDATED_ECONOMIC_SEMANTICS',
       approved_manifest_sha256 = NULL
 WHERE title_case_id IN (
    SELECT DISTINCT u.title_case_id
      FROM title_economic_units u
     WHERE EXISTS (
         SELECT 1
           FROM title_economic_events burden
          WHERE burden.unit_id = u.id
            AND burden.event_kind = 'REVENUE_BURDEN'
     )
       AND EXISTS (
         SELECT 1
           FROM title_economic_events assignment
          WHERE assignment.unit_id = u.id
            AND assignment.event_kind = 'ASSIGNMENT'
            AND (
                assignment.burden_treatment IS NULL
                OR assignment.burden_treatment != 'EXPLICIT_EVENT_ALLOCATION'
            )
     )
 );

UPDATE pipeline_runs
   SET status = 'FAILED_TERMINAL',
       error = 'Economic assignment burden treatment is ambiguous; rebuild required'
 WHERE id IN (
    SELECT pipeline_run_id
      FROM title_package_details
     WHERE review_status = 'INVALIDATED_ECONOMIC_SEMANTICS'
 );

UPDATE title_cases
   SET status = 'NEEDS_ECONOMIC_REVIEW'
 WHERE id IN (
    SELECT title_case_id
      FROM title_package_details
     WHERE review_status = 'INVALIDATED_ECONOMIC_SEMANTICS'
 );
