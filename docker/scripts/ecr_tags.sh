#!/usr/bin/env bash
# Only way to configure timestamp format and it's persistent.. oh well.
aws configure set cli_timestamp_format iso8601
aws ecr describe-images --output text \
  --repository-name amuse-django \
  --filter tagStatus=TAGGED \
  --query 'imageDetails[].[[imagePushedAt,imageTags[]][]]' | sort -n

