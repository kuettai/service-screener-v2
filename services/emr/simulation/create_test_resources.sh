#!/bin/bash
################################################################################
# Amazon EMR Service Screener - Read-Only Posture Report
#
# Creates NOTHING, deliberately. Launching an EMR cluster means:
#   - billable compute for as long as it runs (a 1-node m5.xlarge cluster is
#     roughly $0.06/hour including the EMR uplift), and
#   - creating the EMR_DefaultRole and EMR_EC2_DefaultRole IAM roles, which do
#     NOT exist in this account -- so the fixture would leave IAM roles behind.
#
# The account-level block-public-access check needs no cluster and is reported
# below. The 13 per-cluster checks were instead verified against synthetic
# describe_cluster data covering both a fully-insecure cluster and one whose
# security configuration exists but has encryption disabled (the case the
# two-hop describe_security_configuration lookup exists to catch).
#
# To exercise the cluster checks live, in an account where the spend is
# acceptable:
#   aws emr create-default-roles
#   aws emr create-cluster --name ss-test-emr --release-label emr-6.15.0 \
#       --instance-type m5.xlarge --instance-count 1 --use-default-roles \
#       --region <region>
#   # scan, then IMMEDIATELY:
#   aws emr terminate-clusters --cluster-ids <id>
#
# Usage: ./create_test_resources.sh [--region REGION] [--help]
################################################################################
set -u
REGION="${AWS_REGION:-ap-southeast-1}"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
while [[ $# -gt 0 ]]; do case $1 in
    --region) REGION="$2"; shift 2 ;;
    --help) grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //'; exit 0 ;;
    *) shift ;; esac; done
export AWS_PAGER=""
echo -e "${GREEN}=== Amazon EMR Posture Report (read-only) ===${NC}"
echo "Region: $REGION"
echo -e "${YELLOW}This script creates nothing. See the header for why.${NC}"; echo ""
aws emr get-block-public-access-configuration --region "$REGION" --output json 2>/dev/null | python3 -c "
import json,sys
try: c=json.load(sys.stdin)['BlockPublicAccessConfiguration']
except Exception: print('  block-public-access could not be read -> INFO'); sys.exit()
b=c.get('BlockPublicSecurityGroupRules')
rs=c.get('PermittedPublicSecurityGroupRuleRanges') or []
wide=[f\"{r.get('MinRange')}-{r.get('MaxRange')}\" for r in rs
      if not (r.get('MinRange')==r.get('MaxRange')==22)]
print(f'  BlockPublicSecurityGroupRules={b}')
print(f'  permitted ranges: ' + (', '.join(f\"{r.get('MinRange')}-{r.get('MaxRange')}\" for r in rs) or 'none'))
print('  -> emrBlockPublicAccessDisabled will ' + ('FAIL' if (b is not True or wide) else 'PASS'))
" 2>/dev/null
N=$(aws emr list-clusters --active --region "$REGION" --query 'length(Clusters)' --output text 2>/dev/null || echo 0)
echo "  active clusters: ${N:-0} (the 13 per-cluster checks report nothing when this is 0)"
echo ""; echo -e "${GREEN}=== Report Complete — nothing created ===${NC}"
echo "  cd ../../.. && python3 main.py --regions $REGION --services emr --beta 1 --sequential 1"
