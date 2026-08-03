# Spec: Repair and Extend Framework Mappings

## Context

`service-screener-v2` ships 12 compliance frameworks under `frameworks/*/map.json`.
Each maps a framework control to one or more service-screener checks in the form
`<service>.<checkKey>`. An audit on 2026-08-03 found two independent problems.

### Problem 1 — 87 dangling mapping entries render as false PASSES

`frameworks/Framework.py:133` falls through to `return {"c": check}` when a mapped
check key is not present in the scan data, and `formatCheckAndLinks()` at
`frameworks/Framework.py:149` treats any entry lacking an `"r"` field as
compliant. The result, confirmed by rendering SOC2.html:

```html
<dt class='text-success'><i class='fas fa-check'></i> [isEnabled]</dt>
```

A typo in a compliance mapping reports as a **passed control**. Silent, and
biased toward claiming compliance — the worst available failure mode for a
compliance document.

Distribution of the 87 (52 distinct names, some referenced from several controls):

| Framework | Dangling | Of total | Share |
|---|---|---|---|
| SOC2 | 57 | 91 | **63%** |
| RMiT | 9 | 490 | 2% |
| SSB | 4 | 43 | 9% |
| FTR | 4 | 144 | 3% |
| AAIL | 4 | 193 | 2% |
| SPIP | 3 | 78 | 4% |
| IRDAI | 2 | 212 | 1% |
| NIST | 2 | 219 | 1% |
| MSR | 1 | 68 | 1% |
| WAFS | 1 | 425 | 0% |
| CIS, RBI | 0 | — | clean |

SOC2 is the severe case: two thirds of its controls resolve to nothing, so its
report is largely green for reasons unrelated to the scanned account. Its
dangling names (`s3.bucketEncryption`, `iam.mfaEnabledForConsoleUsers`) follow
AWS Config rule naming rather than this repo's check keys, suggesting the file
was authored against Config rule IDs and never reconciled.

`scripts/validate_frameworks.py` (added 2026-08-03) detects all 87 and is wired
into CI via `.github/workflows/validate-frameworks.yml`.

### Problem 2 — recently-added services reach only WAFS

Every non-AWS framework map was last touched on **2026-07-01** by `060e46d`
(WAFv2 + Cognito), which updated nine maps at once. The convention was
"update all frameworks on a service addition," and it lapsed. WAFS has 23
commits; NIST last changed 2026-03-31; IRDAI only ever once.

Services present in WAFS but absent from most others: `acm`, `backup`, `config`,
`ecr`, `ecs`, `eventbridge`, `firehose`, `kinesis`, `route53`, `secretsmanager`,
`ssm`.

Run `python3 scripts/validate_frameworks.py --list-unmapped` for the live matrix.

## Scope

**Phase 1** — repair all 87 dangling entries.
**Phase 2** — extend the 10 non-AWS frameworks to cover the unmapped services.

Out of scope: authoring new checks, changing `Framework.py` rendering (the
false-PASS behaviour is now caught by CI at author time; changing the renderer to
fail loudly is a separate, larger change worth its own spec).

---

## Phase 1 — Repair the dangling entries

Of 52 distinct dangling names, **49 resolve to an existing check** and **3 have
no equivalent** and must be deleted.

### 1a. Typos in the service prefix (4 entries, 11 occurrences)

Unambiguous — the service name itself is misspelled.

| Dangling | Correction | Occurrences |
|---|---|---|
| `clooudtrail.EnableCloudTrailLogging` | `cloudtrail.EnableCloudTrailLogging` | 8 (RMiT) |
| `ec.SGSensitivePortOpenToAll` | `ec2.SGSensitivePortOpenToAll` | 1 (WAFS) |
| `is3.TlsEnforced` | `s3.TlsEnforced` | 1 (SPIP) |
| `**iam.guardDutyNotification` | `iam.enableGuardDuty` | 1 (SSB) |

### 1b. Case-only or near-identical renames (11 entries)

The check exists under different capitalisation. Zero semantic risk.

| Dangling | Correction |
|---|---|
| `cloudtrail.logFileValidationEnabled` | `cloudtrail.LogFileValidationEnabled` |
| `kms.keyRotationEnabled` | `kms.KeyRotationEnabled` |
| `kms.cmkBackingKeyRotationEnabled` | `kms.KeyRotationEnabled` |
| `redshift.EnhancedVPCRouting` | `redshift.EnhancedVpcRouting` |
| `redshift.PubliclyAcessible` | `redshift.PubliclyAccessible` |
| `s3.bucketVersioning` | `s3.BucketVersioning` |
| `s3.bucketLifecycleEnabled` | `s3.BucketLifecycle` |
| `s3.bucketLoggingEnabled` | `s3.BucketLogging` |
| `s3.bucketPublicAccessBlock` | `s3.PublicAccessBlock` |
| `s3.ObjectLockEnabled` | `s3.ObjectLock` |
| `ec2.SGTCPAllOpen` | `ec2.SGAllTCPOpen` |

### 1c. Semantic renames (31 entries)

The intent is clear but the target name differs. Each verified against the
target's `shortDesc`.

| Dangling | Correction | Rationale |
|---|---|---|
| `cloudtrail.multiRegionTrailEnabled` | `cloudtrail.HasOneMultiRegionTrail` | same control |
| `cloudtrail.trailMultiRegion` | `cloudtrail.HasOneMultiRegionTrail` | same control |
| `cloudtrail.trailEnabled` | `cloudtrail.NeedToEnableCloudTrail` | "To have 1 CloudTrail" |
| `cloudtrail.cloudwatchLogsEnabled` | `cloudtrail.CloudWatchLogsLogGroupArn` | trail → CW Logs wiring |
| `cloudtrail.trailWithoutCWLogs` | `cloudwatch.trailWithoutCWLogs` | **check lives under `cloudwatch`, not `cloudtrail`** |
| `securityhub.isEnabled` | `cloudtrail.SecurityHubIntegration` | no `securityhub` service; this is the equivalent |
| `guardduty.isEnabled` | `iam.enableGuardDuty` | the `guardduty` service has no "is enabled" check; `iam.enableGuardDuty` is it |
| `config.isEnabled` | `config.configRecorderNotEnabled` | recorder enablement |
| `backup.resourcesProtectedByBackupPlan` | `backup.backupPlanNotAssigned` | unassigned plan == unprotected resources |
| `ec2.SGAllOpen` | `ec2.SGAllPortOpen` | same control |
| `ec2.SGAllOpenToAll` | `ec2.SGAllPortOpenToAll` | same control |
| `ec2.snapshotEBSIsPublic` | `ec2.EBSSnapshotIsPublic` | same control |
| `ec2.ebsOptimizedEnabled` | `ec2.EC2EbsOptimized` | same control |
| `ec2.instanceDetailedMonitoringEnabled` | `ec2.EC2DetailedMonitor` | same control |
| `ec2.instanceEbsBackupEnabled` | `ec2.EBSUpToDateSnapshot` | "Enable EBS Snapshot" |
| `ec2.securityGroupsRestrictedSSH` | `ec2.SGSensitivePortOpenToAll` | SSH is a sensitive port; **collapses with RDP below** |
| `ec2.securityGroupsRestrictedRDP` | `ec2.SGSensitivePortOpenToAll` | same target — dedupe when both appear in one control |
| `eks.eksPrivateEndpoint` | `eks.eksEndpointPublicAccess` | inverse phrasing, same control |
| `elasticache.encryptionInTransit` | `elasticache.EncInTransitAndRest` | superset, closest available |
| `dynamodb.backupStatus` | `dynamodb.disabledBackup` | same control |
| `dynamodb.enabledContinuousBackup` | `dynamodb.disabledPointInTimeRecovery` | PITR is continuous backup |
| `iam.accessKeysRotated` | `iam.hasAccessKeyNoRotate90days` | 90d is the CIS-aligned threshold |
| `iam.mfaEnabledForConsoleUsers` | `iam.mfaActive` | same control |
| `iam.usersMfaEnabled` | `iam.mfaActive` | same target as above |
| `iam.noFullAdminPolicies` | `iam.FullAdminAccess` | same control |
| `iam.noInlinePolicy` | `iam.InlinePolicy` | same control |
| `iam.noUserPolicies` | `iam.InlinePolicy` | same target as above |
| `iam.noRootUserAccessKey` | `iam.rootHasAccessKey` | same control |
| `rds.instanceBackupEnabled` | `rds.Backup` | same control |
| `rds.instanceEncryptionEnabled` | `rds.StorageEncrypted` | same control |
| `rds.instanceMultiAZ` | `rds.MultiAZ` | same control |
| `apigateway.endpointTypesPrivate` | `apigateway.PrivateAPI` | same control |
| `cloudwatch.hasAlarms` | `cloudwatch.alarmsWithoutSNS` | see note |

**Note on `cloudwatch.hasAlarms`.** There is no "has any alarms" check. The
closest is `alarmsWithoutSNS` ("Configure SNS notifications for alarms"), which
is arguably the better control anyway: an alarm nobody is notified about does
not evidence a monitoring control. Used in 4 SOC2 controls (CC4.1, A1.1,
PI1.1, PI1.3).

### 1d. Delete — no equivalent check exists (3 entries)

Removing them turns a false PASS into an honest "no relevant check, manual
intervention required", which is what the framework renders for an empty
section.

| Dangling | Why deleted |
|---|---|
| `ec2.securityGroupsHasDescription` | no SG-description check exists |
| `iam.supportRoleExists` | no support-role check exists (CIS 1.17 style) |
| `s3.bucketTaggingEnabled` | no S3 bucket-tagging check exists |

### Phase 1 acceptance criteria

- `python3 scripts/validate_frameworks.py` exits 0 with no errors.
- No pre-existing valid entry is removed (verified by diffing entry sets).
- Duplicate entries created by two dangling names collapsing onto one target
  (the SSH/RDP and `iam.mfaActive` cases) are deduplicated within their control.
- Every framework still renders: run a scan with `--frameworks` naming all 12
  and confirm each HTML page is produced.

---

## Phase 2 — Extend to the 10 non-AWS frameworks

### Guiding principle

A mapping is a claim that a check **evidences** a control. Only map where the
check genuinely provides evidence. An over-broad mapping is worse than a gap: a
gap renders as "manual intervention required", which is honest, whereas a wrong
mapping produces a PASS that misleads an auditor.

### NIST is the highest-value target and is nearly free

NIST's section IDs are **AWS Security Hub control IDs** (confirmed: its metadata
`_` field points at `securityhub/latest/userguide/nist-standard.html`, and
populated sections like `S3.10` match Security Hub's S3.10 exactly). It already
contains **empty, purpose-built sections for the new services**:

`SSM.1`–`SSM.4`, `SecretsManager.1`–`.4`, `Config.1`, `Backup.1`,
`EventBridge.3`, `EventBridge.4`, `ACM.1`, `ECR.1`–`.3`, `Kinesis.1`,
`Route53.2`, `ECS.*`

Mapping into these is not a judgement call — the Security Hub control definition
states exactly what is checked. Definitions fetched from AWS docs:

| Control | Security Hub definition | Proposed checks |
|---|---|---|
| `SSM.1` | EC2 instances should be managed by Systems Manager | `ec2.EC2SSMNotManaged`, `ssm.ssmDefaultHostManagementDisabled`, `ssm.ssmManagedInstanceNotOnline` |
| `SSM.2` | Managed instances should have patch compliance status COMPLIANT | `ssm.ssmManagedInstanceNotPatched` |
| `SSM.3` | Managed instances should have association compliance COMPLIANT | `ssm.ssmInventoryNotConfigured` (closest available; association compliance is not checked) |
| `SSM.4` | SSM documents should not be public | *(no check — leave empty)* |
| `SecretsManager.1` | Secrets should have automatic rotation enabled | `secretsmanager.smRotationNotEnabled`, `secretsmanager.smRotationLambdaMissing` |
| `SecretsManager.2` | Secrets with rotation configured should rotate successfully | `secretsmanager.smRotationOverdue`, `secretsmanager.smAutoRotationScheduleInvalid` |
| `SecretsManager.3` | Remove unused secrets (default 90 days) | `secretsmanager.smNotUsedRecently` |
| `SecretsManager.4` | Secrets should be rotated within a specified number of days | `secretsmanager.smLastChangedOld` |
| `Config.1` | AWS Config should be enabled and record all resources | `config.configRecorderNotEnabled`, `config.configRecorderNotAllResources`, `config.configRecorderExcludesGlobalResources`, `config.configRecorderLastStatusFailed`, `config.configDeliveryChannelMissing` |
| `Backup.1` | Recovery points should be encrypted at rest | `backup.backupRecoveryPointNotEncrypted`, `backup.backupRecoveryPointNoCMK` |
| `EventBridge.3` | Custom event buses should have a resource-based policy | `eventbridge.ebBusPublicPolicy`, `eventbridge.ebRuleTargetCrossAccountNoCondition` |
| `EventBridge.4` | Global endpoints should have event replication enabled | `eventbridge.ebGlobalEndpointNoReplication` |
| `ACM.1` | Certificates should be renewed / not expired | `acm.acmCertExpired`, `acm.acmCertExpiry30Days`, `acm.acmCertExpiry90Days` |
| `Kinesis.1` | Streams should be encrypted at rest | `kinesis.kinesisSSEDisabled`, `kinesis.kinesisSSEDefaultKey` |

`SSM.4` stays empty: no check inspects SSM document sharing. That is an honest
gap, and a candidate for a future check.

### The other 9 frameworks

These use bespoke control vocabularies, so each mapping is a compliance
judgement. Proposed additions, grouped by the control theme they evidence:

**Secrets management** (`secretsmanager.*`) → wherever the framework has a
credential-management or key-management control. Candidates: RBI "Data Security
and Privacy", IRDAI `DS.*`, RMiT `10.49`-family (cryptography), SPIP
"Data Protection", MSR `DP.*`.

**Detective controls / configuration management** (`config.*`) → CIS `Config.1`
currently holds `iam.EnableConfigService` and `iam.PartialEnableConfigService`,
which predate the `config` service and infer Config's state from IAM. The real
`config.*` checks are strictly better evidence and should be added alongside
(not replacing — the IAM checks still resolve and may cover the
org-level case). Also IRDAI "Monitoring, Logging and Incident Response", RBI
"Monitoring and Logging", SOC2 CC3.4 (dangling today, fixed in Phase 1).

**Patch and vulnerability management** (`ssm.ssmManagedInstance*`) → IRDAI
"Vulnerability Assessment and Penetration Testing" (currently 3 empty sections),
RMiT patch-management controls, SSB `WKLD.*`.

**Session access auditing** (`ssm.ssmSessionManager*`) → any privileged-access or
audit-trail control: RBI "Access Control", IRDAI `IAM.*`, SPIP
"Identity Protection".

**Backup and recovery** (`backup.*`) → IRDAI "Business Continuity and Disaster
Recovery" (currently empty), RMiT BCP controls, SOC2 A1.2/A1.3 (dangling today).

**Event-driven reliability** (`eventbridge.ebRule*`) → thinner justification
outside AAIL; map only where a framework has an explicit
message-durability control.

### Phase 2 method (mandatory)

For each framework, one at a time:

1. Read the framework's own control text — do not infer intent from the control
   ID alone. Where the framework is an AWS-published standard (NIST via Security
   Hub, CIS, FTR, SSB) fetch the authoritative definition.
2. Prefer **filling an empty section** over adding to a populated one. An empty
   section is a known gap; a populated one already has evidence.
3. Map a check only where it evidences the control. **Record the rationale in the
   commit message**, not in `map.json` (the file has no comment facility).
4. Run `python3 scripts/validate_frameworks.py` after each framework.
5. Render the framework and confirm the new rows appear as expected.

### Phase 2 acceptance criteria

- `validate_frameworks.py` exits 0.
- No framework loses a pre-existing entry.
- Every one of the 12 frameworks renders without a traceback.
- `--list-unmapped` shows materially improved coverage for the 11 services that
  currently reach only WAFS.
- Each commit states why its mappings evidence their controls.

## Non-goals

- Do not add mappings to reach a coverage target. An unmapped control that
  renders "manual intervention required" is correct when no check evidences it.
- Do not change `Framework.py`'s treatment of unresolvable checks in this work.
  CI now prevents new dangling entries; making the renderer fail loudly is a
  separate change.
- Do not touch `emptyCheckDefaultMsg` or any framework metadata.
