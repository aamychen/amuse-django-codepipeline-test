#!/usr/bin/env bash
set -e
restore_rds_instance.sh amuse-dev
dump_to_s3.sh amuse-dev
