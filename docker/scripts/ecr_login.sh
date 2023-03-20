#!/usr/bin/env bash
# Helper script for logging in docker to our private ECR
# This method is a bit more complex than just running $(aws ecr get-login --no-include-email)
# but it's a bit more secure since it doesn't expose the password to the system through
# process lists / command history

# The first line is from `aws ecr get-authorization-token help`
# The second is just piping the password into docker login.
aws ecr get-authorization-token --output text --query 'authorizationData[].authorizationToken' | base64 -D | cut -d: -f2 \
  | docker login --username AWS --password-stdin 097538760983.dkr.ecr.eu-west-1.amazonaws.com
