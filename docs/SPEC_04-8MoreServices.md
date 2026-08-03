# Task: Add 8 New Services — Security & Developer Tooling

## Context

You are working on `service-screener-v2` — an open-source AWS security scanning tool at `/Users/kuettai/Documents/project/ss-genai/service-screener-v2`. You need to implement 8 new services following established patterns.

## Project Structure

```
service-screener-v2/
├── services/
│   ├── {service_name}/
│   │   ├── {ServiceName}.py           ← Main service class (discovery + hydration)
│   │   ├── {service_name}.reporter.json ← Check definitions (metadata)
│   │   ├── drivers/
│   │   │   └── {ServiceName}Common.py  ← Check methods (_checkXxx)
│   │   └── simulation/
│   │       ├── create_test_resources.sh
│   │       ├── cleanup_test_resources.sh
│   │       └── README.md
├── utils/ArguParser.py                 ← Default services list
├── scripts/RuleCount.py                ← Counts all rules
├── frameworks/WAFS/map.json            ← Well-Architected Security mapping
└── frameworks/AAIL/map.json            ← Agentic AI Lens mapping

```

## Reference Pattern

Use `services/secretsmanager/` or `services/sns/` as your reference implementation. Status codes: `-1` = FAIL, `1` = PASS, `0` = INFO/skip

## Reporter JSON Format (with remediation)

```json
{
  "checkName": {
    "category": "S",
    "criticality": "H",
    "resultType": "FAIL",
    "shortDesc": "Short description of the finding",
    "description": "Detailed description...",
    "remediation": "aws cli-command --flag {ResourceArn}",
    "remediation_risk": "low",
    "remediation_doc": "https://docs.aws.amazon.com/..."
  }
}

```

Set `remediation` to `null` if no safe one-liner exists. Set `remediation_risk` to `null` when remediation is null.

---

## Services to Implement

### Service 1: AppSync (`appsync`)

**boto3 client**: `appsync`

**Discovery**: `list_graphql_apis()` (paginated) → per-API: `get_graphql_api()`

**Checks (~12):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `appsyncNoAuthentication` | authenticationType is API_KEY only (no IAM/Cognito/OIDC/Lambda) | H | S |
| `appsyncApiKeyExpiringSoon` | list_api_keys → any key expires within 7 days | M | S |
| `appsyncApiKeyNoExpiry` | API key with very long expiry (>365 days) | M | S |
| `appsyncFieldLevelLogging` | logConfig is null or fieldLogLevel is NONE | M | O |
| `appsyncCloudWatchLogsNotEnabled` | logConfig is null or cloudWatchLogsRoleArn is empty | M | O |
| `appsyncXrayTracingDisabled` | xrayEnabled is false | L | O |
| `appsyncWafNotAssociated` | wafWebAclArn is null/empty (AND visibility is GLOBAL) | H | S |
| `appsyncIntrospectionEnabled` | introspectionConfig is ENABLED (production risk) | M | S |
| `appsyncNoQueryDepthLimit` | queryDepthLimit is 0 or not set | M | P |
| `appsyncNoResolverCountLimit` | resolverCountLimit is 0 or not set | M | P |
| `appsyncCachingDisabled` | cachingConfig is not set or ttl=0 | L | P |
| `appsyncNoTags` | tags empty | L | O |

**Framework mapping**: WAFS SEC09.BP02 (API protection), SEC06.BP01 (compute)

---

### Service 2: Security Hub (`securityhub`)

**boto3 client**: `securityhub`

**Discovery**: Account-level (one resource per region). `describe_hub()`, `get_enabled_standards()`, `list_members()`

**Checks (~8):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `shubNotEnabled` | describe_hub raises InvalidAccessException (hub not enabled) | H | S |
| `shubNoStandardsEnabled` | get_enabled_standards returns empty | H | S |
| `shubAutoEnableControlsDisabled` | describe_hub → AutoEnableControls is false | M | S |
| `shubFindingAggregatorMissing` | list_finding_aggregators returns empty (no cross-region) | M | O |
| `shubIntegrationsMissing` | list_enabled_products_for_import returns < 3 integrations | L | O |
| `shubUnprocessedFindings` | get_findings with workflow status NEW and age >7 days, count > 100 | M | O |
| `shubCISStandardDisabled` | get_enabled_standards doesn't include CIS standard ARN | M | S |
| `shubNoTags` | list_tags_for_resource returns empty | L | O |

**Framework mapping**: WAFS SEC01.BP03 (detective controls), SEC04.BP01 (logging/monitoring)

---

### Service 3: Inspector (`inspector2`)

**boto3 client**: `inspector2`

**Discovery**: Account-level. `batch_get_account_status()`, `list_coverage()`

**Checks (~8):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `inspectorNotEnabled` | batch_get_account_status → state.status != ENABLED | H | S |
| `inspectorEc2ScanningDisabled` | resourceState.ec2.status != ENABLED | H | S |
| `inspectorEcrScanningDisabled` | resourceState.ecr.status != ENABLED | M | S |
| `inspectorLambdaScanningDisabled` | resourceState.lambda.status != ENABLED | M | S |
| `inspectorLambdaCodeScanningDisabled` | resourceState.lambdaCode.status != ENABLED | L | S |
| `inspectorCoverageGap` | list_coverage → resources with scanStatus != ACTIVE (>10%) | M | S |
| `inspectorCriticalFindings` | list_findings with severity CRITICAL and status ACTIVE | H | S |
| `inspectorSuppressedFindings` | list_finding_aggregations → suppressedCounts > total*0.5 | L | O |

**Framework mapping**: WAFS SEC01.BP02 (vulnerability management), SEC06.BP01 (compute protection)

---

### Service 4: Access Analyzer (`accessanalyzer`)

**boto3 client**: `accessanalyzer`

**Discovery**: `list_analyzers()` per region. Per-analyzer: `list_findings()`

**Checks (~8):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `aaNoAnalyzerConfigured` | list_analyzers returns empty | H | S |
| `aaNoAccountAnalyzer` | No analyzer with type ACCOUNT | H | S |
| `aaNoOrganizationAnalyzer` | No analyzer with type ORGANIZATION (if in org) | M | S |
| `aaAnalyzerNotActive` | analyzer.status != ACTIVE | H | R |
| `aaUnresolvedExternalAccess` | list_findings with status ACTIVE and resourceType has >5 findings | H | S |
| `aaFindingsOlderThan30Days` | list_findings with ACTIVE status and createdAt > 30 days | M | O |
| `aaUnusedAccessAnalyzerMissing` | No analyzer with type ACCOUNT_UNUSED_ACCESS | M | S |
| `aaNoArchiveRules` | list_archive_rules returns empty (no auto-archive for known-good) | L | O |

**Framework mapping**: WAFS SEC03.BP01 (least privilege), SEC03.BP04 (unused access)

---

### Service 5: EMR (`emr`)

**boto3 client**: `emr`

**Discovery**: `list_clusters(ClusterStates=['RUNNING','WAITING'])` → `describe_cluster()` per cluster

**Checks (~15):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `emrEncryptionAtRestDisabled` | SecurityConfiguration missing or encryption.atRest disabled | H | S |
| `emrEncryptionInTransitDisabled` | encryption.inTransit disabled | H | S |
| `emrNoSecurityConfiguration` | Cluster has no SecurityConfiguration attached | H | S |
| `emrKerberosNotEnabled` | KerberosAttributes is null/empty | M | S |
| `emrPubliclyAccessible` | Ec2InstanceAttributes.EmrManagedMasterSecurityGroup allows 0.0.0.0/0 on port 22/8443 | H | S |
| `emrLoggingDisabled` | LogUri is null | M | O |
| `emrStepConcurrencyLow` | StepConcurrencyLevel == 1 (default, underutilized) | L | P |
| `emrTerminationProtectionDisabled` | TerminationProtection is false | M | R |
| `emrAutoScalingDisabled` | AutoScalingRole is null AND no instance fleet auto-scaling | M | P |
| `emrMasterInstanceOnDemand` | Master node not using on-demand (spot for master = risk) | M | R |
| `emrNoBootstrapActions` | BootstrapActions empty (informational — security hardening usually here) | L | O |
| `emrBlockPublicAccessDisabled` | get_block_public_access_configuration → BlockPublicAccessConfiguration.BlockPublicSecurityGroupRules is false | H | S |
| `emrOldRelease` | ReleaseLabel < emr-6.x (very old, missing security patches) | M | S |
| `emrNoTags` | Tags empty | L | O |
| `emrIdleCluster` | Status.State == WAITING for > 24hr with 0 running steps | L | C |

**Framework mapping**: WAFS SEC08.BP01/BP02 (encryption), SEC06.BP01 (compute), SEC09.BP02 (network)

---

### Service 6: Athena (`athena`)

**boto3 client**: `athena`

**Discovery**: `list_work_groups()` → `get_work_group()` per workgroup

**Checks (~10):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `athenaWorkgroupNotEncrypted` | ResultConfiguration.EncryptionConfiguration is null | H | S |
| `athenaWorkgroupNoEnforcement` | EnforceWorkGroupConfiguration is false | M | S |
| `athenaPublishMetricsDisabled` | PublishCloudWatchMetricsEnabled is false | L | O |
| `athenaRequesterPaysDisabled` | RequesterPaysEnabled is false (informational for S3 cost) | L | C |
| `athenaWorkgroupS3OutputNoPrefix` | OutputLocation is bucket root (/) with no prefix | L | S |
| `athenaEnginev2OrOlder` | EngineVersion.SelectedEngineVersion < "Athena engine version 3" | M | P |
| `athenaBytesScannedNoLimit` | BytesScannedCutoffPerQuery is 0 (unlimited) | M | C |
| `athenaWorkgroupDisabled` | State == "DISABLED" | L | O |
| `athenaNoTags` | WorkGroup has no tags | L | O |
| `athenaS3OutputNotEncrypted` | ResultConfiguration.OutputLocation points to unencrypted S3 bucket | M | S |

**Framework mapping**: WAFS SEC08.BP01 (encryption), OPS03.BP01 (query monitoring)

---

### Service 7: CodeBuild (`codebuild`)

**boto3 client**: `codebuild`

**Discovery**: `list_projects()` → `batch_get_projects()` (batches of 100)

**Checks (~12):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `cbEncryptionDefaultKey` | encryptionKey is null (uses default aws/codebuild key) | M | S |
| `cbPrivilegedMode` | environment.privilegedMode is true | H | S |
| `cbNoVpcConfig` | vpcConfig is null (no VPC, builds have internet access) | M | S |
| `cbLogsDisabled` | logsConfig.cloudWatchLogs.status == "DISABLED" AND logsConfig.s3Logs.status == "DISABLED" | M | O |
| `cbSourceCredentialsInsecure` | source.type is GITHUB/BITBUCKET AND source.auth is null (public source) | L | S |
| `cbNoArtifactEncryption` | artifacts.encryptionDisabled is true | H | S |
| `cbImageOutdated` | environment.image contains deprecated/EOL image (e.g., ubuntu:standard:1.0) | M | S |
| `cbConcurrentBuildLimitNotSet` | concurrentBuildLimit is null (unlimited) | L | C |
| `cbS3LogsNotEncrypted` | logsConfig.s3Logs.encryptionDisabled is true | M | S |
| `cbBadgeEnabled` | badge.badgeEnabled AND badge requires repo visibility | L | S |
| `cbInsecureSSL` | source.insecureSsl is true | H | S |
| `cbNoTags` | tags empty | L | O |

**Framework mapping**: WAFS SEC08.BP01 (encryption), SEC06.BP01 (compute), SEC09.BP01 (network)

---

### Service 8: CloudFormation (`cloudformation`)

**boto3 client**: `cloudformation`

**Discovery**: `list_stacks(StackStatusFilter=['CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE'])` → `describe_stacks()` per stack

**Checks (~10):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `cfnTerminationProtectionDisabled` | EnableTerminationProtection is false | M | R |
| `cfnNoRollbackConfiguration` | RollbackConfiguration is null or MonitoringTimeInMinutes == 0 | L | R |
| `cfnDriftDetected` | detect_stack_drift → DriftStatus == "DRIFTED" | M | R |
| `cfnNoNotifications` | NotificationARNs is empty | L | O |
| `cfnIAMCapabilityGranted` | Capabilities contains CAPABILITY_IAM or CAPABILITY_NAMED_IAM (informational) | L | S |
| `cfnStackPolicyMissing` | get_stack_policy returns empty | M | S |
| `cfnOldStackUnupdated` | LastUpdatedTime > 365 days ago | L | O |
| `cfnRollbackFailed` | StackStatus contains ROLLBACK_FAILED | H | R |
| `cfnNestedStacksDeep` | Nested stack depth > 3 levels (OperationalComplexity) | L | O |
| `cfnNoTags` | Tags empty | L | O |

**Framework mapping**: WAFS OPS05.BP01 (infrastructure as code), REL09.BP01 (change management)

---

## Implementation Steps (per service)

1. `python3 scripts/CreateService.py {service_name}`
2. Implement `{ServiceName}.py` (service class)
3. Implement `drivers/{ServiceName}Common.py` (check methods)
4. Create `{service_name}.reporter.json` with all check metadata + 3 remediation fields
5. Update `utils/ArguParser.py` — add service to default list
6. Update `frameworks/WAFS/map.json` — add mappings
7. Create `simulation/create_test_resources.sh` + `cleanup_test_resources.sh` + `README.md`
8. **RUN the simulation end-to-end** (MANDATORY — do not skip):```bash cd services/{service_name}/simulation chmod +x create_test_resources.sh cleanup_test_resources.sh ./create_test_resources.sh sleep 30 cd ../../.. python3 main.py --regions ap-southeast-1 --services {service_name} --beta 1 --sequential 1

# Verify checks fired FAIL on test resources

cd services/{service_name}/simulation ./cleanup_test_resources.sh cd ../../..

```Report
9. Validate: `python3 scripts/RuleCount.py`
10. Test against real account: `python3 main.py --regions ap-southeast-1 --services {service_name} --beta 1 --sequential 1`
11. Commit per service: `git commit -m "feat: Add {ServiceName} service (N checks) + framework mappings"`

## Validation

After all 8 services:

- All reporter.json files are valid JSON
- All `_check` methods match reporter keys 1:1
- RuleCount.py reports correct totals
- Full scan exits 0 with no tracebacks: `python3 main.py --services ALL --regions ap-southeast-1 --beta 1 --sequential 1`
- Each service has simulation scripts that have been run

```

