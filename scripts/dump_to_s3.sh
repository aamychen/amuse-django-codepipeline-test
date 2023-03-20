#!/usr/bin/env bash
db_identifier=$1
db_host="${db_identifier}.clwh5euetoxb.eu-west-1.rds.amazonaws.com"
db_user="amuse"
db_password="blarg123"
db_name=amuse
s3_location="s3://amuse-dumps"
dump_name=${db_identifier}$(date +"%Y-%m-%d_%H_%M_%S").dump

export PGHOST=$db_host
export PGUSER=$db_user
export PGPASSWORD="$db_password"
export PGDATABASE=$db_name

function say {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

# Dump to S3
say "Dumping $db_host to ${s3_location}/${dump_name}"
time pg_dump -Fc | aws s3 cp - "${s3_location}/${dump_name}"
