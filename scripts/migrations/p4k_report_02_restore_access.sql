-- Restore the historical relation names for rollback to the pre-REPORT-02
-- application. The immutable rows and triggers were retained by the up step.
DO $$
DECLARE relation_pair text[];
BEGIN
  FOREACH relation_pair SLICE 1 IN ARRAY ARRAY[
    ARRAY['m8_report_access_revisions_legacy_audit', 'm8_report_access_revisions'],
    ARRAY['m8_report_access_recipients_legacy_audit', 'm8_report_access_recipients'],
    ARRAY['m8_cycle_report_access_legacy_audit', 'm8_cycle_report_access'],
    ARRAY['m8_cycle_report_recipients_legacy_audit', 'm8_cycle_report_recipients']
  ] LOOP
    IF to_regclass(current_schema() || '.' || relation_pair[1]) IS NOT NULL THEN
      IF to_regclass(current_schema() || '.' || relation_pair[2]) IS NOT NULL THEN
        RAISE EXCEPTION 'REPORT02_RESTORE_TARGET_EXISTS: %', relation_pair[2];
      END IF;
      EXECUTE format('ALTER TABLE %I RENAME TO %I', relation_pair[1], relation_pair[2]);
    END IF;
  END LOOP;
END $$;
DO $$ BEGIN
  IF to_regclass(current_schema() || '.questionnaire_response_revisions') IS NOT NULL THEN
    ALTER TABLE questionnaire_response_revisions
      ADD COLUMN IF NOT EXISTS recipient_mapping_json JSONB;
  END IF;
END $$;
