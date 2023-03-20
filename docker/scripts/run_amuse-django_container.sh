#!/bin/bash
# Helper script for running an amuse-django docker container locally with
# settings for staging or prod.
# To authenticate your docker with ECR: $(aws ecr get-login --no-include-email)

ecr_repo="097538760983.dkr.ecr.eu-west-1.amazonaws.com/amuse-django"
script_path="$( cd "$(dirname "$0")"; pwd -P )"
script_name="$(basename $0)"

if [ -z "$2" ]; then
    echo "${script_name} <settings-env> <image-tag> <args>"
    echo
    echo "Run an amuse-django image with settings for staging or prod."
    echo "Settings are fetched from SSM Parameter Store with help from"
    echo "\"ssm_params_env_vars.sh\". Image is fetched from:"
    echo ${ecr_repo}
    echo
    echo "Arguments:"
    echo
    echo "settings-env    Which settings/SSM Params path (staging|production)"
    echo "image-tag       Docker image tag (find tags in ECR)"
    echo "args            Args to docker run (like \"sh\" or \"python manage.py shell\")"
    echo
    echo "Example usage:"
    echo
    echo "Launch a python shell for prod:"
    echo "${script_name} production some-tag python manage.py shell"
    echo
    echo "Show the state of migrations on staging as seen from image review-666:"
    echo "${script_name} staging review-666 python manage.py showmigrations"

    exit 1
fi

if [ "$1" = "production" ]; then
  echo "Sure you wanted PRODUCTION settings? (type \"yes\")"
  read a
  if [ "$a" != "yes" ];then
    exit 2
  fi
fi

docker run \
  -it \
  --rm \
  --entrypoint="" \
  --env-file=<(${script_path}/ssm_params_env_vars.sh $1) \
  097538760983.dkr.ecr.eu-west-1.amazonaws.com/amuse-django:${@:2}
