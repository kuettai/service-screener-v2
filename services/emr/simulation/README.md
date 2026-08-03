# EMR Simulation Testing

**No fixtures, by design.** `create_test_resources.sh` is a read-only posture
report; `cleanup_test_resources.sh` is a no-op.

## Why nothing is created

Launching an EMR cluster means **billable compute** for as long as it runs (a
1-node `m5.xlarge` cluster is roughly $0.06/hour including the EMR uplift), and
it requires the `EMR_DefaultRole` / `EMR_EC2_DefaultRole` IAM roles, which **do
not exist in this account** — so a fixture would leave IAM roles behind after
teardown.

The account-level check (`emrBlockPublicAccessDisabled`, FSBP EMR.2) needs no
cluster and is verified live — the posture report predicts exactly what the scan
finds.

## How the 13 per-cluster checks were verified

Against synthetic `describe_cluster` data covering two cases, both branches of
every check:

- **A fully insecure cluster** — no security configuration, spot master, public
  master IP, `emr-5.30.0`, no logging, no termination protection, no tags, step
  concurrency 1. Result: 9 FAIL, 3 INFO.
- **A cluster whose security configuration exists but has encryption OFF** —
  precisely the case the two-hop `describe_security_configuration` lookup and its
  JSON-string parse exist to catch. Result: `emrEncryptionAtRestDisabled` and
  `emrEncryptionInTransitDisabled` both FAIL, everything else PASS.

That second case is why the field-name correction mattered: the spec named
`TerminationProtection`, but the real field is **`TerminationProtected`** — with
the spec's name the check would have silently always passed.

## Exercising the cluster checks live

Only in an account where the spend is acceptable:

```bash
aws emr create-default-roles
aws emr create-cluster --name ss-test-emr --release-label emr-6.15.0 \
    --instance-type m5.xlarge --instance-count 1 --use-default-roles \
    --region ap-southeast-1
# scan, then IMMEDIATELY:
aws emr terminate-clusters --cluster-ids <id>
```

## Cost

Zero as shipped — the report uses only read APIs.
