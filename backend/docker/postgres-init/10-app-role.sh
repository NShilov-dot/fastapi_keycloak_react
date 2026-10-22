#!/bin/sh
# Runs ONCE, on an empty data dir (docker-entrypoint-initdb.d), as the bootstrap
# superuser. Creates the app's login role as the plain OWNER of its database — not a
# superuser — so a SQL injection can't reach superuser-only primitives
# (COPY ... PROGRAM, server file access, other databases).
# Existing volumes keep their old role: `make clean` (wipes data) to re-initialise.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v app_db="$POSTGRES_DB" <<'EOSQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER DATABASE :"app_db" OWNER TO :"app_user";
-- Migrations CREATE EXTENSION pgcrypto; pre-create it so they never need superuser.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
EOSQL
