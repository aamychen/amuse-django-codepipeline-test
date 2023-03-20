#!/bin/bash
# Fetch and import postgres dump into postgres container

s3_bucket="s3://amuse-dumps"
container_dump_path=/dumps
db_name=amuse
dump_name_format="amuse-dev.*"
me=$(basename "$0")
script_path=$( cd "$(dirname "$0")"; pwd -P )
dump_path=$( cd "${script_path}/../dumps"; pwd -P ) # aka "<git-root>/dumps"

set -e

[ -e "$dump_path" ] || (echo "Could not find dump dir ${dump_path}" && exit 1)

if [ -z "$1" ]; then
    echo "$me list|listlocal|latest|local|<dump date> [-d]"
    echo
    echo "list          list remote dumps"
    echo "listlocal     list local dumps"
    echo "latest        import latest dump from ${s3_bucket}"
    echo "local         import latest local dump"
    echo "<dump name>   import specific dump. use whole filename."
    echo
    echo "Add -d (last) to just download and skip import"
    exit 1

elif [ "$1" = "list" ]; then
    echo "Dumps available on $s3_bucket:"
    aws s3 ls "$s3_bucket" | sort -n | grep -o --color=never "$dump_name_format"
    exit 0

elif [ "$1" = "listlocal" ]; then
    echo "Dumps available locally:"
    ls -1tr "$dump_path" | grep "$dump_name_format"
    exit 0

elif [ "$1" = "latest" ]; then
    dump_name=$(aws s3 ls  "$s3_bucket" | sort -n | grep -o --color=never "$dump_name_format" | tail -1)
    if [ -z "$dump_name" ]; then
        echo "No psql dump found on $s3_bucket!"
        exit 1
    fi
    echo "Using dump $s3_bucket/$dump_name..."

elif [ "$1" = "local" ]; then
    dump_name=$(ls -1tr "$dump_path" | grep "$dump_name_format" | tail -1)
    if [ -z "$dump_name" ]; then
        echo "No dump found in $dump_path (matching regex \"$dump_name_format\")"
        exit 1
    fi

elif [[ "$1" =~ $dump_name_format ]]; then
    dump_name="$1"
    echo "Setting dump name to $dump_name"
fi

if [ -e "${dump_path}/${dump_name}" ]; then
    echo "$dump_name found locally: ${dump_path}/${dump_name}"
else
    echo "Getting ${s3_bucket}/${dump_name}..."
    aws s3 cp "${s3_bucket}/${dump_name}" "$dump_path"
fi

if [ "$2" = "-d" ]; then
    exit 0
fi

echo "Importing $dump_name"
# Kill all connections so db can be dropped
docker-compose exec postgres psql -h localhost -U postgres -c "
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$db_name'
  AND pid <> pg_backend_pid();
"

docker-compose exec postgres psql -h localhost -U postgres -c "DROP DATABASE $db_name" || true
time docker-compose exec postgres pg_restore \
    -h localhost \
    -U postgres \
    --dbname postgres \
    --jobs 2 \
    --clean \
    --create \
    "${container_dump_path}/${dump_name}" || true

echo "Done"
