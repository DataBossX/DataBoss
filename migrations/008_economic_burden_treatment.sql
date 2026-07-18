ALTER TABLE title_economic_events
    ADD COLUMN burden_treatment TEXT CHECK (
        burden_treatment IS NULL
        OR burden_treatment IN (
            'EXPLICIT_EVENT_ALLOCATION',
            'NO_BURDENS'
        )
    );
