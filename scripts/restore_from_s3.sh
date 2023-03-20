#!/usr/bin/env bash
env=$1
dump_type=$2
s3_bucket="s3://amuse-dumps"
export PGUSER=amuse
export PGPASSWORD=blarg123
db_name=amuse

set -e

if [ -z "$env" ]; then
    echo "restore_from_s3.sh <env> <dump_type:dev|prod>"
    exit 2
fi

if [ -z "$dump_type" ]; then
    dump_type=dev
fi

dump_name_format="amuse_$dump_type.*"
export PGHOST="amuse-$env.clwh5euetoxb.eu-west-1.rds.amazonaws.com"
dump_name=$(aws s3 ls  "$s3_bucket" | sort -n | grep -o --color=never "$dump_name_format" | tail -1)
if [ -z "$dump_name" ]; then
    echo "No psql dump found on $s3_bucket!"
    exit 1
fi

echo "Restoring dump $s3_bucket/$dump_name to $PGHOST"

aws s3 cp "${s3_bucket}/${dump_name}" /tmp

echo "Connecting as $PGUSER and killing all connections..."
psql postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$db_name'
  AND pid <> pg_backend_pid();"

echo "Connecting as $PGUSER and dropping db + create db (owner $PGUSER)"
psql postgres -c "DROP DATABASE $db_name"
psql postgres -c "CREATE DATABASE $db_name WITH OWNER $PGUSER"

echo "Restoring from dump..."
pg_restore --dbname $db_name --jobs 2 "/tmp/${dump_name}" || true

echo "Removing dump from /tmp"
rm "/tmp/${dump_name}"

