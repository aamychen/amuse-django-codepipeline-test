#!/bin/bash
# Get env vars from AWS SSM Parameter Store and output them as environment
# variable assignments (KEY=VAL).
#
# This script can be used to supply a docker container with env vars from SSM
# like so:
# $ docker run -it --rm --env-file=<(./ssm_params_env_vars.sh <env>) amuse.io/app
#
# Note that a configured and authenticated AWS CLI is needed.

# First arg is environment (staging|prod)
environment=$1
env_var_path="/DeploymentConfig/amuse-django/amuse-django-${environment}/env/"

if [ -z "$1" ]; then
    echo "$(basename $0) <env:(staging|production)>"
    echo
    echo "Output env vars for a specific environment"
    exit 1
fi

# Get params
aws_cli_output=$(aws ssm get-parameters-by-path --with-decryption --output text --path ${env_var_path} --query "Parameters[].[Name,Value]")

# Reformat output to key=value
key_vals=$(echo "${aws_cli_output}" | sed s/$'\t'/=/)

# Drop SSM path prefix from key (using alternative regex delimiter due to slashes in the path)
# and output everything.
echo "${key_vals}" | sed s~"${env_var_path}"~~

