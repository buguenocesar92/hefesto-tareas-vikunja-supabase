DO $$
DECLARE v integer; r text;
BEGIN
  v := current_setting('server_version_num')::int / 10000;
  IF v NOT IN (16,17) THEN RAISE EXCEPTION 'Validar version PostgreSQL: paquete admite16/17'; END IF;
  IF current_user <> 'vikunja_app' THEN RAISE EXCEPTION 'Usar rol vikunja_app'; END IF;
  IF NOT has_schema_privilege(current_user,'public','USAGE') OR NOT has_schema_privilege(current_user,'public','CREATE') THEN
    RAISE EXCEPTION 'Faltan permisos del esquema';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public' AND tableowner <> 'vikunja_app') THEN
    RAISE EXCEPTION 'Hay tablas de otro propietario; usar proyecto exclusivo';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public') AND
    (to_regclass('public.tasks') IS NULL OR to_regclass('public.users') IS NULL) THEN
    RAISE EXCEPTION 'Base no vacia sin marcadores Vikunja; revisar antes de migrar';
  END IF;
  FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) AND EXISTS(
      SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relkind IN ('r','p') AND has_table_privilege(r,c.oid,'SELECT,INSERT,UPDATE,DELETE')
    ) THEN RAISE EXCEPTION 'Tablas accesibles por rol API %',r; END IF;
  END LOOP;
END $$;
SELECT 'Preflight de permisos y base completado' AS resultado;
