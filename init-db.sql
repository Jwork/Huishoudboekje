-- =============================================================
-- PostgreSQL initialization script for Expense Tracker
-- Runs once on first container start (empty data volume)
-- =============================================================

-- Create the private schema for application tables
CREATE SCHEMA IF NOT EXISTS private;

-- Create application user (owns private schema, full access)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_worker') THEN
        CREATE ROLE app_worker LOGIN PASSWORD 'app_worker_secure_password';
    END IF;
END
$$;

-- Create analytics user (read-only on public schema, no password)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analytics_user') THEN
        CREATE ROLE analytics_user LOGIN;
    END IF;
END
$$;

-- Grant ownership and privileges on private schema
ALTER SCHEMA private OWNER TO app_worker;
GRANT ALL ON SCHEMA private TO app_worker;
GRANT USAGE ON SCHEMA private TO expenses;

-- Grant app_worker full access on public schema too (for views/dimensions)
GRANT ALL ON SCHEMA public TO app_worker;

-- Grant analytics_user read-only access on public schema
GRANT USAGE ON SCHEMA public TO analytics_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;

-- Ensure future objects in public are readable by analytics_user
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analytics_user;

-- Ensure future objects in private are accessible by app_worker
ALTER DEFAULT PRIVILEGES IN SCHEMA private GRANT ALL ON TABLES TO app_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA private GRANT ALL ON SEQUENCES TO app_worker;

-- Also let the expenses superuser create in private (for init_database)
GRANT ALL ON SCHEMA private TO expenses;
ALTER DEFAULT PRIVILEGES IN SCHEMA private GRANT ALL ON TABLES TO expenses;
ALTER DEFAULT PRIVILEGES IN SCHEMA private GRANT ALL ON SEQUENCES TO expenses;

-- Ensure future objects in public are also accessible by app_worker
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_worker;
