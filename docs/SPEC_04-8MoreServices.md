# Task: Add 8 New Services — Security & Developer Tooling

> **STATUS: COMPLETE (2026-08-03).** All 8 services built, tested against
> account 956288449190 / ap-southeast-1, and committed. 942 -> 1038 checks
> (+96), 36 -> 44 services.
>
> | Phase | Content | Checks | Commit |
> |---|---|---|---|
> | 0 | GuardDuty `Features[]` extension (not in this spec; from the review) | 5 -> 15 | `72fed68` |
> | 1 | CodeBuild | 15 | `064371c` |
> | 2 | Access Analyzer, Security Hub, Inspector | 26 | `c494b35` |
> | 3 | Athena, AppSync | 21 | `2e191f2` |
> | 4 | EMR, CloudFormation | 24 | `b7e6161` |
>
> Both blocking issues were fixed in this document before any code was written,
> and both fixes were verified in the finished services:
> `cfnDriftDetected` reads `DriftInformation` and never calls
> `detect_stack_drift`; Inspector uses `list_finding_aggregations` (one call)
> rather than paginating `list_findings`.
>
> Full review, including the ~25 additional checks that were folded in, is in
> `SPEC_04-8MoreServices-REVIEW.md`.

> **REVISED 2026-08-03** after review — see `SPEC_04-8MoreServices-REVIEW.md`.
> Changes applied below are marked **[FIX]**. Two were blocking:
> `cfnDriftDetected` must NOT call `detect_stack_drift` (a write operation), and
> the findings-count checks must not enumerate unbounded finding sets.
>
> **READ-ONLY CONTRACT.** Every check in this scanner uses only read
> (`describe_*` / `list_*` / `get_*`) operations. Before adding a check, confirm
> the API does not mutate state. `detect_stack_drift`, `create_*`, `put_*`,
> `update_*` and `enable_*` are all disqualified regardless of how useful the data
> would be.
>
> **Account-level services.** Security Hub, Inspector, Access Analyzer and EMR's
> block-public-access are account/region-scoped, not per-resource. Follow the
> SPEC_02 precedent and emit a single aggregate identifier
> (`SecurityHub::Account`, `Inspector::Account`, `AccessAnalyzer::Account`),
> mirroring `Config::Account` and `SSM::Account`.

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
| ~~`appsyncCachingDisabled`~~ | **[FIX] DROPPED.** `cachingConfig` is not a member of `GraphqlApi`; caching requires a separate `get_api_cache()` call. AWS also RETIRED the AppSync cache-encryption controls (AppSync.1, AppSync.6) on 2026-03-09 because caches are now encrypted by default, so there is little left to check here | — | — |
| `appsyncNoTags` | tags empty | L | O |

**Framework mapping**: **[FIX]** WAFS **SEC05.BP01** (create network layers / edge
protection) for `appsyncWafNotAssociated` and `appsyncNoAuthentication` — NOT
SEC09.BP02, which is encryption in transit. SEC02.BP02 (temporary credentials)
for the API-key expiry checks. SEC04.BP01 (service logging) for the logging
checks.

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
| `shubUnprocessedFindings` | **[FIX]** `get_findings` paginates without bound (verified: returns `NextToken` on page one). Cap pagination at a documented page limit, report "at least N", and NEVER silently truncate — follow the `INVENTORY_SAMPLE_LIMIT` precedent in `services/ssm/Ssm.py`. Report INFO when the cap is hit | M | O |
| `shubCISStandardDisabled` | get_enabled_standards doesn't include CIS standard ARN | M | S |
| `shubLegacyControlFindingGenerator` | **[FIX, new]** `describe_hub().ControlFindingGenerator != 'SECURITY_CONTROL'` — legacy `STANDARD_CONTROL` mode duplicates findings across standards. Verified live: this account returns `STANDARD_CONTROL` | M | O |
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
| `inspectorCodeRepositoryScanningDisabled` | **[FIX, new]** `resourceState.codeRepository.status != ENABLED` — present in the live API response, omitted from the original spec | M | S |
| `inspectorCoverageGap` | list_coverage → resources with scanStatus != ACTIVE (>10%) | M | S |
| `inspectorCriticalFindings` | **[FIX]** `list_finding_aggregations(aggregationType='ACCOUNT')` → `severityCounts.critical > 0`. Do **NOT** use `list_findings` — it paginates over every finding (verified: 1,248 in the test account, ~13 calls for one check). The aggregation API returns exact counts in ONE call | H | S |
| `inspectorExploitableFindings` | **[FIX, new]** same one call → `exploitAvailableCount > 0`. A vulnerability with a known exploit is the highest-priority class in vulnerability management | H | S |
| `inspectorFixAvailableNotApplied` | **[FIX, new]** same one call → `fixAvailableCount` is a high proportion of `all` (unpatched despite an available fix) | H | S |
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
| `emrEncryptionAtRestDisabled` | **[FIX]** `describe_cluster` returns only the security configuration NAME. Two-hop: `describe_security_configuration(Name=...)` → its `SecurityConfiguration` field is a **JSON string that must be parsed** → `EncryptionConfiguration.EnableAtRestEncryption`. Report INFO (not FAIL) when no security configuration is attached, so this does not double-report with `emrNoSecurityConfiguration` | H | S |
| `emrEncryptionInTransitDisabled` | **[FIX]** same two-hop + JSON parse → `EncryptionConfiguration.EnableInTransitEncryption`. Same INFO-when-absent rule | H | S |
| `emrNoSecurityConfiguration` | Cluster has no SecurityConfiguration attached. **[FIX]** This is the single FAIL for the absent case; the two checks above stay INFO then | H | S |
| `emrKerberosNotEnabled` | KerberosAttributes is null/empty | M | S |
| `emrPubliclyAccessible` | **[FIX]** `describe_cluster` returns only the SG **id** in `Ec2InstanceAttributes.EmrManagedMasterSecurityGroup`. Needs an EC2 `describe_security_groups` join to evaluate rules. Check whether `ec2.SGSensitivePortOpenToAll` already covers the same SG before implementing — if so, drop this to avoid duplicate reporting | H | S |
| `emrLoggingDisabled` | LogUri is null | M | O |
| `emrStepConcurrencyLow` | StepConcurrencyLevel == 1 (default, underutilized) | L | P |
| `emrTerminationProtectionDisabled` | **[FIX]** the field is **`TerminationProtected`**, not `TerminationProtection`. As written the check would always pass | M | R |
| `emrAutoScalingDisabled` | AutoScalingRole is null AND no instance fleet auto-scaling | M | P |
| `emrMasterInstanceOnDemand` | **[FIX]** demote to INFO. A spot master is a deliberate cost trade-off in dev/test; as a FAIL it punishes an intentional choice | L | R |
| ~~`emrNoBootstrapActions`~~ | **[FIX] DROPPED.** Absence of bootstrap actions is not a defect — many clusters need none | — | — |
| `emrBlockPublicAccessDisabled` | get_block_public_access_configuration → BlockPublicAccessConfiguration.BlockPublicSecurityGroupRules is false. **[FIX]** This is ACCOUNT/region-level (`AWS::::Account`), not per-cluster — put it in a regional driver and emit it once, not once per cluster | H | S |
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
| ~~`cbBadgeEnabled`~~ | **[FIX] DROPPED.** "badge requires repo visibility" is not evaluable from the CodeBuild API, and badge state alone is not a security finding | — | — |
| `cbInsecureSSL` | source.insecureSsl is true | H | S |
| `cbPlaintextCredentialsInEnvVars` | **[FIX, new — FSBP CodeBuild.2, CRITICAL]** any `environment.environmentVariables[]` with `type == PLAINTEXT` whose name matches a credential pattern (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and secret/password/token/key fragments). Plaintext AWS keys in build env vars are a well-documented breach vector. **Report the variable NAME only, never the value** | H | S |
| `cbSourceUrlCredentials` | **[FIX, new — FSBP CodeBuild.1, CRITICAL]** `source.location` or any `secondarySources[].location` contains embedded credentials (`https://user:pass@host` form). **Never emit the matched credential** | H | S |
| `cbReportGroupExportNotEncrypted` | **[FIX, new — FSBP CodeBuild.7]** `list_report_groups()` → `batch_get_report_groups()` → `exportConfig.s3Destination.encryptionDisabled` is true | M | S |
| `cbProjectVisibilityPublic` | **[FIX, new]** `projectVisibility == 'PUBLIC_READ'` — build logs are world-readable. Note the enum is `['PUBLIC_READ','PRIVATE']`; match `PUBLIC_READ`, not `PUBLIC` | H | S |
| `cbNoTags` | tags empty | L | O |

**Framework mapping**: WAFS SEC08.BP01 (encryption at rest) for the encryption
checks; **SEC02.BP03** (store and use secrets securely) for the two new credential
checks; SEC06.BP02 (reduce attack surface) for `cbPrivilegedMode`; SEC04.BP01 for
logging. Also map into **NIST** `CodeBuild.1/2/7` — those section IDs are Security
Hub control IDs, so the mapping is mechanical.

---

### Service 8: CloudFormation (`cloudformation`)

**boto3 client**: `cloudformation`

**Discovery**: `list_stacks(StackStatusFilter=['CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE'])` → `describe_stacks()` per stack

**Checks (~10):**

| Check | FAIL condition | Sev | Pillar |
| --- | --- | --- | --- |
| `cfnTerminationProtectionDisabled` | EnableTerminationProtection is false | M | R |
| `cfnNoRollbackConfiguration` | RollbackConfiguration is null or MonitoringTimeInMinutes == 0 | L | R |
| `cfnDriftDetected` | **[FIX]** `DriftInformation.StackDriftStatus == "DRIFTED"` from the `describe_stacks` response already fetched. Do **NOT** call `detect_stack_drift` — it is a WRITE operation whose only output is a `StackDriftDetectionId`; it initiates an async, billed, rate-limited detection run that mutates stack state | M | R |
| `cfnDriftNeverChecked` | **[FIX, new]** `DriftInformation.StackDriftStatus == "NOT_CHECKED"` — drift has never been assessed on this stack. Verified as the common real-world value | L | R |
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

## Simulation feasibility — read before writing step 8

**[FIX]** Several of these services cannot be simulated safely. Do not discover
this mid-implementation; plan for it:

| Service | Simulation approach |
|---|---|
| Security Hub, Inspector, GuardDuty features | **Read-only posture report.** Enabling these is an account-level mutation with real recurring cost, and disabling them to force a FAIL removes a security control from the account. Follow the `services/config/simulation/` precedent: a script that reports what each check will return and creates nothing. |
| Access Analyzer | Analyzer creation is cheap, but **findings cannot be manufactured on demand** — they depend on real cross-account policy. Create an analyzer; report the findings-based checks as INFO. |
| EMR | A cluster costs money per hour. Smallest viable cluster, torn down immediately, or read-only report. |
| CodeBuild, AppSync, Athena, CloudFormation | Fully simulable. All create cheap or free resources. |

Where a check cannot be forced to FAIL, say so explicitly in the simulation
README — the SPEC_02 services documented every such case and that proved more
useful than a fixture that silently exercised nothing.

## Validation

After all 8 services:

- All reporter.json files are valid JSON: `python3 scripts/validate_reporter.py`
- **[FIX]** `python3 scripts/validate_frameworks.py` exits 0. This is now
  CI-enforced (`.github/workflows/validate-frameworks.yml`) and fails the build on
  a mapping that points at a nonexistent check. Note a dangling mapping renders as
  a GREEN COMPLIANT tick, not an error, so this is not optional.
- All `_check` methods match reporter keys 1:1
- RuleCount.py reports correct totals
- Full scan exits 0 with no tracebacks: `python3 main.py --services ALL --regions ap-southeast-1 --beta 1 --sequential 1`
- Each service has simulation scripts that have been run
- **[FIX]** No check calls a mutating API. Grep the new drivers for
  `detect_`, `create_`, `put_`, `update_`, `delete_`, `enable_`, `start_` before
  committing.

```

