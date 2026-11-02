-- Reports facts_reader's attributes, memberships and table privileges as an error message,
-- the one output `gcloud sql import` shows. It changes nothing.
DO $$
DECLARE
  report text;
BEGIN
  SELECT format(
    'CHECK super=%s createrole=%s createdb=%s bypassrls=%s member_of=[%s] config=[%s] tables=%s selectable=%s writable=%s schema_create=%s db_create=%s',
    r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolbypassrls,
    (SELECT string_agg(b.rolname, ',' ORDER BY b.rolname)
       FROM pg_auth_members m JOIN pg_roles b ON b.oid = m.roleid
      WHERE m.member = r.oid),
    array_to_string(r.rolconfig, ','),
    (SELECT count(*) FROM pg_tables t WHERE t.schemaname = 'public'),
    (SELECT count(*) FROM pg_tables t WHERE t.schemaname = 'public'
        AND has_table_privilege(r.oid, format('%I.%I', t.schemaname, t.tablename), 'SELECT')),
    (SELECT count(*) FROM pg_tables t WHERE t.schemaname = 'public'
        AND has_table_privilege(r.oid, format('%I.%I', t.schemaname, t.tablename),
                                'INSERT, UPDATE, DELETE, TRUNCATE')),
    has_schema_privilege(r.oid, 'public', 'CREATE'),
    has_database_privilege(r.oid, current_database(), 'CREATE')
  ) INTO report
  FROM pg_roles r
  WHERE r.rolname = 'facts_reader';
  RAISE EXCEPTION '%', coalesce(report, 'CHECK facts_reader is missing');
END $$;
