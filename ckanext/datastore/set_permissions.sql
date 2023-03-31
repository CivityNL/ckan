/*
This script configures the permissions for the datastore.
It ensures that the datastore read-only user will only be able to select from
the datastore database but has no create/write/edit permission or any
permissions on other databases. You must execute this script as a database
superuser on the PostgreSQL server that hosts your datastore database.
For example, if PostgreSQL is running locally and the "postgres" user has the
appropriate permissions (as in the default Ubuntu PostgreSQL install), you can
run:
    ckan -c /etc/ckan/default/ckan.ini datastore set-permissions | sudo -u postgres psql
Or, if your PostgreSQL server is remote, you can pipe the permissions script
over SSH:
    ckan -c /etc/ckan/default/ckan.ini datastore set-permissions | ssh dbserver sudo -u postgres psql
*/

-- Most of the following commands apply to an explicit database or to the whole
-- 'public' schema, and could be executed anywhere. But ALTER DEFAULT
-- PERMISSIONS applies to the current database, and so we must be connected to
-- the datastore DB:
\connect {datastoredb}

-- revoke permissions for the read-only user
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE USAGE ON SCHEMA public FROM PUBLIC;

GRANT CREATE ON SCHEMA public TO {mainuser};
GRANT USAGE ON SCHEMA public TO {mainuser};

GRANT CREATE ON SCHEMA public TO {writeuser};
GRANT USAGE ON SCHEMA public TO {writeuser};

-- take connect permissions from main db
REVOKE CONNECT ON DATABASE {maindb} FROM {readuser};

-- grant select permissions for read-only user
GRANT CONNECT ON DATABASE {datastoredb} TO {readuser};
GRANT USAGE ON SCHEMA public TO {readuser};

-- grant access to current tables and views to read-only user
GRANT SELECT ON ALL TABLES IN SCHEMA public TO {readuser};

-- grant access to new tables and views by default
ALTER DEFAULT PRIVILEGES FOR USER {writeuser} IN SCHEMA public
   GRANT SELECT ON TABLES TO {readuser};

-- a view for listing valid table (resource id) and view names
-- DEV-4541: this view only works with the datastore aliases, but returns weird/wrong results with other views. As we
-- don't use aliases and all views created belong to a resource we simplified this view to fix issues without changing
-- too much logic in the datastore extension
CREATE OR REPLACE VIEW "_table_metadata" AS
    SELECT DISTINCT
        substr(md5(relname), 0, 17) AS "_id",
        relname AS name,
        oid AS oid,
        NULL::name AS alias_of
    FROM
        pg_class
    WHERE
        (relkind = 'r'::"char" OR relkind = 'v'::"char")
        AND relnamespace = (
            SELECT oid FROM pg_namespace WHERE nspname='public'
        )
    ORDER BY oid DESC;
ALTER VIEW "_table_metadata" OWNER TO {writeuser};
GRANT SELECT ON "_table_metadata" TO {readuser};

-- _full_text fields are now updated by a trigger when set to NULL
CREATE OR REPLACE FUNCTION populate_full_text_trigger() RETURNS trigger
AS $body$
    BEGIN
        IF NEW._full_text IS NOT NULL THEN
            RETURN NEW;
        END IF;
        NEW._full_text := (
            SELECT to_tsvector(string_agg(value, ' '))
            FROM json_each_text(row_to_json(NEW.*))
            WHERE key NOT LIKE '\_%' AND key != 'wkb_geometry');
        RETURN NEW;
    END;
$body$ LANGUAGE plpgsql;
ALTER FUNCTION populate_full_text_trigger() OWNER TO {writeuser};

-- migrate existing tables that don''t have full text trigger applied
-- DEV-4541: this 'migration' only works in the assumption that all tables are datastore created tables which is not the
-- case with many of the iot tables. With the logic below we now check if it makes sense if a table has a trigger, based
-- on the presence of a '_full_text' column of type 'tsvector' and based on that either create or drop the trigger.
DO
$body$
    declare
        -- loop variables
        existing_table       name;
        has_full_text_column bool;
        has_trigger          bool;
        -- constants
        _schema_name         TEXT := 'public';
        _trigger_name        TEXT := 'zfulltext';
        _column_name         TEXT := '_full_text';
        _column_type         TEXT := 'tsvector';
    BEGIN
        FOR existing_table, has_full_text_column, has_trigger IN
            -- select all tables with either the correct column but no trigger or vice versa
            SELECT relname, full_text_column.table_name IS NOT NULL, zfulltext_trigger.tgrelid IS NOT NULL
            FROM pg_class
            LEFT JOIN (
                SELECT table_name FROM information_schema.columns
                WHERE column_name = _column_name AND data_type = _column_type AND table_schema = _schema_name
            ) AS full_text_column ON relname = full_text_column.table_name
            LEFT JOIN (
                select tgrelid FROM pg_trigger WHERE tgname = _trigger_name
            ) AS zfulltext_trigger ON relname::regclass = zfulltext_trigger.tgrelid
            WHERE relkind = 'r'::char AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = _schema_name)
				AND (full_text_column.table_name IS NOT NULL) != (zfulltext_trigger.tgrelid IS NOT NULL)
        LOOP
            IF has_full_text_column AND NOT has_trigger THEN
                -- yes on the column, but no on the trigger means it should have the trigger so we create it
                RAISE NOTICE 'creating trigger (%) for (%)', _trigger_name, existing_table;
                EXECUTE 'CREATE TRIGGER ' || _trigger_name || ' BEFORE INSERT OR UPDATE ON ' ||
                        quote_ident(existing_table) || ' FOR EACH ROW EXECUTE PROCEDURE populate_full_text_trigger();';
            ELSIF NOT has_full_text_column AND has_trigger THEN
                -- no on the column, but yes on the trigger means it should NOT have the trigger so we drop it
                RAISE NOTICE 'dropping trigger (%) for (%)', _trigger_name, existing_table;
                EXECUTE 'DROP TRIGGER ' || _trigger_name || ' ON ' || quote_ident(existing_table) || ';';
            ELSE
                -- nothing should end up here as from the query has_full_text_column should always be different from
                -- has_trigger (so only TRUE/FALSE or FALSE/TRUE) and both possibilities are handled above
                RAISE EXCEPTION 'query returned (%, %, %) which should not be possible', existing_table, has_full_text_column, has_trigger;
            END IF;
        END LOOP;
    END;
$body$;

