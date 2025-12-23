#!/bin/bash
# Test command for Service Screener with Cloudscape UI (beta mode)
# This command runs the screener with beta mode enabled to generate the new Cloudscape UI

python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --beta 1 \
  --suppress_file ./suppressions.json
