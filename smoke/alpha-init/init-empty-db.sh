#!/usr/bin/env bash
set -euo pipefail
# EMPTY DISPOSABLE CI DATABASE ONLY. No drop/terminate/migration commands.
cd "$(dirname "$0")/db"
: "${PGHOST:=certify-db}" "${PGPORT:=5432}" "${PGUSER:=postgres}"
export PGHOST PGPORT PGUSER
# Refuse an existing target; let CREATE DATABASE fail rather than deleting it.
test "$(psql -X -v ON_ERROR_STOP=1 -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname='inji_certify'")" = 0
psql -X -v ON_ERROR_STOP=1 -d postgres -v dbuname=certifyuser -v dbuserpwd="'postgres'" -f role_dbuser.sql
psql -X -v ON_ERROR_STOP=1 -d postgres -v mosipdbname=inji_certify -f db.sql
psql -X -v ON_ERROR_STOP=1 -d inji_certify -v mosipdbname=inji_certify -v dbuname=certifyuser -f ddl.sql
psql -X -v ON_ERROR_STOP=1 -d inji_certify -v mosipdbname=inji_certify -v dbuname=certifyuser -f grants.sql
psql -X -v ON_ERROR_STOP=1 -d inji_certify -v mosipdbname=inji_certify -f dml.sql
psql -X -v ON_ERROR_STOP=1 -d inji_certify -f ../assert-db.sql
