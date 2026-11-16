-- P4K-REPORT-02: remove recipient snapshots from the active schema without
-- deleting historical questionnaire/report-access audit rows. Run once in a
-- transaction before the matching application release. Idempotent on retry.
DO $$
DECLARE relation_pair text[];
BEGIN
  FOREACH relation_pair SLICE 1 IN ARRAY ARRAY[
    ARRAY['m8_report_access_revisions', 'm8_report_access_revisions_legacy_audit'],
    ARRAY['m8_report_access_recipients', 'm8_report_access_recipients_legacy_audit'],
    ARRAY['m8_cycle_report_access', 'm8_cycle_report_access_legacy_audit'],
    ARRAY['m8_cycle_report_recipients', 'm8_cycle_report_recipients_legacy_audit']
  ] LOOP
    IF to_regclass(current_schema() || '.' || relation_pair[1]) IS NOT NULL THEN
      IF to_regclass(current_schema() || '.' || relation_pair[2]) IS NOT NULL THEN
        RAISE EXCEPTION 'REPORT02_ARCHIVE_TARGET_EXISTS: %', relation_pair[2];
      END IF;
      EXECUTE format('ALTER TABLE %I RENAME TO %I', relation_pair[1], relation_pair[2]);
    END IF;
  END LOOP;
END $$;
