# Spec: Check Coverage Expansion

> **STATUS: PROPOSAL — FOR REVIEW, NOT YET APPROVED FOR BUILD.**
> Researched 2026-08-03 against AWS Security Hub control documentation, the CIS
> AWS Foundations Benchmark v5.0.0 mapping, and live API probes in account
> `956288449190` / `ap-southeast-1`. Every API call named here was executed
> against that account; findings marked "verified live" mean the response was
> inspected, not assumed.
>
> Baseline: **36 services, 942 checks.** This proposal adds an estimated
> **95–130 checks**, of which **~40 need no new API call at all**.

## How this spec was built

Three sources, in decreasing order of authority:

1. **AWS Security Hub control definitions** — for every control the exact ID,
   title, severity, backing AWS Config rule and control text were read. Where a
   control's text contradicted an assumption, the text won (see §5 for two cases
   where that changed the recommendation).
2. **CIS AWS Foundations Benchmark v5.0.0** as supported by Security Hub — used
   to find controls in a certified benchmark that the scanner cannot currently
   evidence.
3. **Live API probes** — each proposed check was tested for data availability
   before being included. Anything that could not be retrieved was either
   dropped or explicitly flagged.

**Deliberately excluded from this proposal:**

- **Tag-existence controls** (`GuardDuty.2/3/4`, `EFS.5`, `SSM.5`, `DMS.2-5`,
  `NetworkFirewall.7/8`, `AppSync.4`, `Backup.2-5`, `ACM.3`, …). The scanner has a
  generic tagging check in `services/general.reporter.json`; per-resource tag
  checks are Low severity duplicates that inflate counts without adding signal.
- **Retired and deprecated controls.** `AppSync.1` and `AppSync.6` were retired
  2026-03-09 because AppSync now encrypts all caches by default; `CodeBuild.5`
  and `SNS.2` are retired. **`EFS.6` was removed from FSBP on 2026-07-30** — four
  days before this research — so it is not an FSBP gap.
- **Controls whose semantics a single-account scanner cannot reproduce.** See §6.

---

## 1. Findings that reframe the problem

### 1.1 "Low check count" is mostly NOT a gap

The starting hypothesis was that services with few checks are under-covered.
That is false for most of them, because FSBP is a much smaller standard than this
scanner:

| Service | Scanner checks | FSBP controls | Verdict |
|---|---:|---:|---|
| firehose | 8 | **1** (`DataFirehose.1`) | Scanner is a superset. No gap. |
| config | 12 | **1** (`Config.1`) | Scanner vastly exceeds FSBP. |
| sqs | 14 | **3** | All three already covered. No gap. |
| kms | 17 | 5 | 3 covered; the other 2 are IAM-resource controls (§3.4). |
| eventbridge | 14 | 3 | 2 covered; 1 Low gap (§3.5). |
| efs | 15 | 8 | 2 clean gaps (§3.3). |
| **guardduty** | **5** | **13** | **9 real gaps — the largest single opportunity.** |
| **ssm** | **14** | **7** | **2 Critical gaps entirely missing.** |

So the count-based heuristic surfaced two genuine targets out of eight. The rest
of this spec is driven by control-by-control comparison instead.

### 1.2 The scanner already fetches data it then discards

Three places retrieve an API response and read only part of it. These are the
cheapest checks available anywhere in this proposal — **zero new API calls**:

| Location | Fetched | Currently used | Unused |
|---|---|---|---|
| `services/guardduty/drivers/GuarddutyDriver.py:146` | `get_detector()` | `DataSources` (**deprecated field**) and `Status` | **`Features[]`** — maps 1:1 to 9 missing controls |
| `services/efs/drivers/EfsDriver.py:189` | `describe_access_points()` | a count only (`AccessPointsConfigured`) | `RootDirectory.Path`, `PosixUser` |
| `services/eventbridge/drivers/EventbridgeBus.py:64` | `describe_event_bus()` Policy | parsed, recorded as informational `hasResourcePolicy` | the pass/fail judgement itself |

### 1.3 Verified live: GuardDuty is silently hiding real failures

Probe against detector `b6c337ba6115507baf62cd630529d574`:

```
Status: ENABLED
CLOUD_TRAIL             ENABLED     EKS_AUDIT_LOGS          ENABLED
DNS_LOGS                ENABLED     EBS_MALWARE_PROTECTION  ENABLED
FLOW_LOGS               ENABLED     RDS_LOGIN_EVENTS        ENABLED
S3_DATA_EVENTS          ENABLED     LAMBDA_NETWORK_LOGS     ENABLED
AI_PROTECTION           DISABLED    <-- not in the FSBP control list at all
EKS_RUNTIME_MONITORING  ENABLED     [EKS_ADDON_MANAGEMENT: DISABLED]
RUNTIME_MONITORING      DISABLED    [EKS_ADDON_MANAGEMENT, ECS_FARGATE_AGENT_MANAGEMENT,
                                     EC2_AGENT_MANAGEMENT all DISABLED]
```

`RUNTIME_MONITORING` disabled is a **High**-severity FSBP failure (GuardDuty.11)
in this very account, and the scanner reports nothing. `AI_PROTECTION` is a
feature newer than the FSBP control set — worth a scanner-original check.

### 1.4 Verified live: SSM public document sharing is permitted here

```
$ aws ssm get-service-setting --setting-id /ssm/documents/console/public-sharing-permission
SettingValue: "Enable"   Status: "Default"
```

`Enable` means this account **permits** public sharing of SSM documents —
GuardDuty.7's SSM equivalent, `SSM.7`, is **Critical** and currently unreported.
The scanner already makes this exact call shape at `services/ssm/Ssm.py:235` for
Default Host Management, so the pattern is proven.

### 1.5 Corrections to earlier assumptions

Two things I expected to be gaps are not:

- **The `account` control family is fully covered.** `Account.1` is
  `iam.hasAlternateContact` and `Account.2` is `iam.hasOrganization`. Coverage
  lives under `iam`, not a service named `account`, which is why a
  directory-name comparison mislabelled it. **One caveat worth a follow-up:**
  `Account.1` specifically concerns the *SECURITY* alternate contact, and
  `IamAccount.py:290` sums across contact types — so an account with only a
  BILLING contact would pass a check that Security Hub would fail. That is a
  correctness refinement, not new coverage.
- **`Macie.1` is already implemented** as `s3.MacieToEnable`. Only `Macie.2`
  (automated sensitive data discovery, **High**) is missing — a ~15-line addition
  to the existing driver, not a new service.

### 1.6 DocumentDB / Neptune: the cheap-win claim did NOT hold

An attractive theory was that `services/rds/Rds.py` already enumerates
DocumentDB and Neptune clusters and discards them via the `engineDriver` map
(confirmed present at `Rds.py:42-49`, covering only mariadb, mysql,
aurora-mysql, postgres, aurora-postgresql, sqlserver), so adding two map entries
would be nearly free.

**Probed live and could not confirm.** The test account has no clusters of any
engine, so all three of `rds describe-db-clusters`, `docdb describe-db-clusters`
and `neptune describe-db-clusters` returned `[]`. The cross-engine visibility of
`rds:DescribeDBClusters` is therefore **unverified**, and AWS has been narrowing
it. Anyone implementing this must confirm against an account that actually has a
DocumentDB or Neptune cluster before relying on the reuse; the fallback is the
dedicated `docdb` / `neptune` clients, which are present in the local boto3.
Cost estimates below reflect that uncertainty.

---

## 2. Priority 1 — Zero new API surface (est. 22–26 checks)

Highest value per unit of work in the entire proposal. All read data the scanner
already has, or make one call whose pattern already exists in the codebase.

### 2.1 GuardDuty feature-protection checks (9 checks)

Read `get_detector().Features[]`, already fetched. Proposed keys and the
authoritative control each evidences:

| Proposed check | Feature name | Control | Sev |
|---|---|---|---|
| `guarddutyRuntimeMonitoringDisabled` | `RUNTIME_MONITORING` | GuardDuty.11 | H |
| `guarddutyMalwareProtectionDisabled` | `EBS_MALWARE_PROTECTION` | GuardDuty.8 | H |
| `guarddutyS3ProtectionDisabled` | `S3_DATA_EVENTS` | GuardDuty.10 | H |
| `guarddutyRdsProtectionDisabled` | `RDS_LOGIN_EVENTS` | GuardDuty.9 | H |
| `guarddutyLambdaProtectionDisabled` | `LAMBDA_NETWORK_LOGS` | GuardDuty.6 | H |
| `guarddutyEksAuditLogsDisabled` | `EKS_AUDIT_LOGS` | GuardDuty.5 | H |
| `guarddutyEksRuntimeMonitoringDisabled` | `EKS_RUNTIME_MONITORING` + `EKS_ADDON_MANAGEMENT` | GuardDuty.7 | H |
| `guarddutyEcsRuntimeMonitoringDisabled` | `RUNTIME_MONITORING` + `ECS_FARGATE_AGENT_MANAGEMENT` | GuardDuty.12 | M |
| `guarddutyEc2RuntimeMonitoringDisabled` | `RUNTIME_MONITORING` + `EC2_AGENT_MANAGEMENT` | GuardDuty.13 | M |

Plus one scanner-original, since the feature exists in the API but has no FSBP
control yet:

| `guarddutyAiProtectionDisabled` | `AI_PROTECTION` | *(none — scanner original)* | M |

**Implementation note:** stop reading the deprecated `DataSources` field.
`Features[]` is the current representation and `DataSources` is documented as
deprecated. Also convert `Settings` from its current informational
`[-1, {...}]` shape — it reports status `-1` (FAIL) unconditionally, which is a
latent bug worth fixing in the same change.

### 2.2 SSM public-document controls (2 checks) — **Critical**

| Proposed check | Source | Control | Sev |
|---|---|---|---|
| `ssmDocumentPublicSharingAllowed` | `get_service_setting('/ssm/documents/console/public-sharing-permission')`, fails when `SettingValue == 'Enable'` | SSM.7 | **C** |
| `ssmDocumentPublic` | `list_documents(Owner=Self)` → `describe_document_permission(PermissionType='Share')`, fails when `AccountIds` contains `all` | SSM.4 | **C** |

Both verified live: the setting returned `Enable`/`Default`, and
`describe_document_permission` succeeded across all 12 self-owned documents
(none currently shared). Note SSM.7 is **per-Region** — the setting can differ
by Region, so it belongs in the region-scoped `SsmSessionManager` driver
alongside the existing DHMC check.

This closes the `SSM.4` gap explicitly flagged as unresolved in
`docs/SPEC_03_FRAMEWORK_MAPPING_REPAIR.md`.

### 2.3 EFS access point controls (2 checks)

`describe_access_points()` is already called at `EfsDriver.py:189` but only
counted.

| Proposed check | Condition | Control | Sev |
|---|---|---|---|
| `efsAccessPointNoRootDirectory` | `RootDirectory.Path == '/'` | EFS.3 | M |
| `efsAccessPointNoUserIdentity` | `PosixUser` absent | EFS.4 | M |

### 2.4 EventBridge missing resource policy (1 check)

| `ebBusNoResourcePolicy` | custom bus with no policy at all | EventBridge.3 | L |

The **inverse** of the existing `ebBusPublicPolicy`: that check flags a policy
that is too open, this one flags the absence of any policy, on AWS's reasoning
that a bare custom bus is implicitly open to every principal in the account. The
value is already computed as informational at `EventbridgeBus.py:64`.

### 2.5 CIS v5.0.0 IAM gaps (3 checks)

Three CIS v5.0.0 requirements the scanner cannot currently evidence. **All three
APIs verified live.**

| Proposed check | API | Control | CIS v5 | Sev |
|---|---|---|---|---|
| `iamNoAccessAnalyzer` | `accessanalyzer:list_analyzers` — verified, returned 1 ACTIVE org analyzer | IAM.28 | 1.19 | **H** |
| `iamCloudShellFullAccessAttached` | `iam:list_entities_for_policy(AWSCloudShellFullAccess)` — verified, returned empty | IAM.27 | 1.21 | M |
| `iamExpiredServerCertificate` | `iam:list_server_certificates` — verified, returned empty | IAM.26 | 1.18 | M |

### 2.6 Config service-linked role (1 check)

| `configRecorderNotServiceLinkedRole` | `roleARN` from `describe_configuration_recorders` does not contain `AWSServiceRoleForConfig` | Config.1 sub-condition | M |

`ConfigCommon.py` already retrieves the recorder including `roleARN`; only a
predicate is missing. Config.1 explicitly requires the service-linked role
because "other roles might not have the necessary permissions for AWS Config to
accurately record your resources".

### 2.7 Macie automated discovery (1 check)

| `macieAutomatedDiscoveryDisabled` | `macie2:get_automated_discovery_configuration()` → `status != 'ENABLED'` | Macie.2 | **H** |

Add to the existing `services/s3/drivers/S3Macie.py`. **Must** be gated on the
account being a Macie administrator (`get_administrator_account` /
`describe_organization_configuration`), or every member account produces a false
positive.

### 2.8 KMS decryption-scope policy checks (2 checks)

| Proposed check | Control | Sev |
|---|---|---|
| `iamCustomerPolicyAllowsAllKmsDecrypt` | KMS.1 | M |
| `iamInlinePolicyAllowsAllKmsDecrypt` | KMS.2 | M |

**These belong in `iam`, not `kms`** — their Security Hub resource types are
`AWS::IAM::Policy` and `AWS::IAM::Group/Role/User`. The blocked-action set is
fixed and non-customizable: `kms:ReEncryptFrom` and `kms:Decrypt` on `Resource:
"*"`. KMS.1 covers attached *and* unattached customer managed policies and
excludes inline and AWS-managed ones; KMS.2 covers inline policies. The `iam`
service already enumerates both, so only new predicates are needed.

---

## 3. Priority 2 — New services, high prevalence (est. 22–30 checks)

### 3.1 CodeBuild (est. 10–14 checks)

The most widely deployed service in this proposal — nearly every account with
CI/CD has projects, and the scanner covers none of it.

| Control | Title | Sev |
|---|---|---|
| CodeBuild.1 | Bitbucket source repository URLs should not contain sensitive credentials | **C** |
| CodeBuild.2 | Project environment variables should not contain clear text credentials | **C** |
| CodeBuild.3 | S3 logs should be encrypted | L |
| CodeBuild.4 | Project environments should have a logging configuration | M |
| CodeBuild.7 | Report group exports should be encrypted at rest | M |

`boto3 codebuild`: `list_projects()` → `batch_get_projects()` (max 100/call)
gives `source.location`, `environment.environmentVariables[]` with
`type == PLAINTEXT`, `logsConfig.s3Logs.encryptionDisabled`, `logsConfig`.
Then `list_report_groups()` → `batch_get_report_groups()`.

`CodeBuild.2` — plaintext `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in build
environment variables — is a well-documented real-world breach vector, and
credential exposure is the highest-value finding class a scanner produces.

**Scanner-original worth adding:** `environment.privilegedMode` (retired as
`CodeBuild.5`, but privileged Docker in CI is still a genuine container-escape
risk, and the field is in the same response).

### 3.2 MSK (est. 12–16 checks)

Best security density on the list, and a coherent gap next to the existing
`kinesis` and `firehose` coverage.

| Control | Title | Sev |
|---|---|---|
| MSK.4 | MSK clusters should have public access disabled | **C** |
| MSK.1 | Clusters should be encrypted in transit among broker nodes | M |
| MSK.3 | MSK Connect connectors should be encrypted in transit | M |
| MSK.5 | MSK connectors should have logging enabled | M |
| MSK.6 | MSK clusters should disable unauthenticated access | M |
| MSK.2 | Clusters should have enhanced monitoring configured | L |

Two clients: `kafka` and `kafkaconnect`. Use the **`_v2` variants**
(`list_clusters_v2`, `describe_cluster_v2`) — they cover Provisioned *and*
Serverless clusters. Fields: `BrokerNodeGroupInfo.ConnectivityInfo.PublicAccess.Type`
(MSK.4), `EncryptionInfo.EncryptionInTransit.InCluster` (MSK.1),
`ClientAuthentication.Unauthenticated.Enabled` (MSK.6).

**MSK.4 + MSK.6 together is the catastrophic pairing**: a publicly reachable
Kafka broker with unauthenticated access means anyone on the internet can read
and write the streaming data plane.

---

## 4. Priority 3 — Lower prevalence or unconfirmed (est. 30–45 checks)

Worth doing, but each has a caveat that keeps it below Priority 2.

| Service | Controls | Est. | Caveat |
|---|---|---:|---|
| **DocumentDB** | 6 (1 Critical: public snapshots) | 10–14 | Cost depends entirely on §1.6 being confirmed. 6/6 controls substantive — best signal density if the RDS reuse holds. `DocumentDB.6` needs `describe_db_cluster_parameters` for the `tls` parameter. |
| **Neptune** | 9 (1 Critical: public snapshots) | 14–18 | Same dependency. Low real-world prevalence — rank it on cheapness, not importance. Do together with DocumentDB as one work item. |
| **EMR** | 4 (1 Critical, 1 High) | 8–10 | Best severity profile of any candidate (50% Critical/High) but only 4 controls, and prevalence is declining as workloads move to Glue. `describe_security_configuration` returns a **JSON string that must be parsed**; EMR.1 needs a two-hop cluster→instances lookup. |
| **Network Firewall** | 10 (8 Medium, 2 tag) | 14–18 | Highest raw count, but **no Critical or High at all**, and deployed in a minority of accounts, so most scans would show an empty section. |

---

## 5. Explicitly rejected, with reasons

Rejections matter as much as additions — each of these looked attractive until
the control text was read.

| Candidate | Why rejected |
|---|---|
| **`EFS.6`** mount targets in public subnets | **Removed from FSBP on 2026-07-30**, per the control page's own notice. Speccing it would add a check against a retired control. |
| **`AppSync`** as a new service | Only **2** substantive controls after removing the tag check and the two retired cache-encryption controls. Not worth a module, reporter file, page builder and registration. If `AppSync.5` (API-key-only auth, **High**) is wanted, fold it into `apigateway`. |
| **`DMS`** as a new service | 13 controls collapses to ~6 useful: 4 are tag checks and 3 are engine-specific endpoint checks that only fire for particular migration topologies. DMS resources are also **transient** — spun up for a migration, torn down after — so point-in-time scans frequently find nothing. `DMS.7/8` need nested JSON-string parsing with per-component severity comparison, the fiddliest work in the whole survey. |
| **`account` service** | No gap. Fully covered by `iam` (§1.5). |
| **`WAF` (Classic)** | The scanner covers WAFv2 only. Already documented in SPEC_03 as the reason `WAF.1-8` stay unmapped. |
| **All `tagged-*` controls** | Low severity, duplicated by the generic tagging check. |

---

## 6. Data-availability constraints (read before estimating)

Several proposed checks cannot fully reproduce Security Hub's semantics. Each
needs an explicit INFO state rather than a guessed pass/fail — the same
discipline SPEC_02 applied to account-level SSM settings.

- **Multi-account / delegated admin.** GuardDuty.5–13 evaluate the delegated
  administrator *plus every member account*, and emit findings only in the admin
  account. A single-account scanner gives a structurally different answer.
  Document the divergence rather than pretending parity. AWS also documents that
  a suspended member account forces `FAILED` until disassociated.
- **Aggregator awareness.** `Config.1` behaves differently in aggregation vs.
  linked Regions, and AWS states it "will always have a status of PASSED" when
  Security Hub CSPM is enabled. Only the service-linked-role sub-condition
  (§2.6) is cleanly checkable.
- **Feature-must-be-in-use.** `SSM.2` "only checks instances that are managed by
  Systems Manager Patch Manager"; `SSM.3` requires State Manager associations to
  exist. Both need a not-applicable state.
- **Cross-service joins.** `EFS.2` (AWS Backup `list_protected_resources`),
  `EFS.6` (EC2 subnet `MapPublicIpOnLaunch`).
- **Per-Region account settings.** `SSM.7`'s block-public-sharing setting is
  account-level *but differs per Region*, so it must be evaluated per Region, not
  once per account.
- **Unverified setting ID.** `SSM.6` (SSM Automation CloudWatch logging) is
  Medium severity, but its setting ID is **not stated** in either the FSBP or
  AWS Config documentation and was **not** verified. Do not implement until the
  ID is confirmed against a live account.
- **One case where the scanner is BETTER than FSBP.** `KMS.5` via AWS Config
  "also returns a FAILED finding ... if your configurations prevent AWS Config
  from recording the key policy". The scanner calls `get_key_policy` directly
  (`KmsCommon.py:161`), avoiding that false positive. Preserve this; do not
  "align" it with Config-mediated behaviour.

---

## 7. Proposed phasing and estimates

| Phase | Content | Est. checks | New API surface |
|---|---|---:|---|
| **1** | §2 in full — GuardDuty features, SSM public docs, EFS access points, EventBridge policy, CIS IAM trio, Config SLR, Macie.2, KMS-in-IAM | **22–26** | Almost none |
| **2** | CodeBuild + MSK | **22–30** | 3 new clients |
| **3** | DocumentDB + Neptune (gated on §1.6) | 24–32 | 0–2 clients |
| **4** | EMR, then Network Firewall | 22–28 | 2 new clients |

Phase 1 alone closes **2 Critical** and **8 High** severity gaps for very little
work, and fixes two latent bugs (GuardDuty's unconditional `-1` status, its use
of the deprecated `DataSources` field).

## 8. Acceptance criteria (per phase, when built)

Carried over from SPEC_02/03, which these proved out:

- Reporter keys match `_check` methods 1:1; `scripts/validate_reporter.py` passes.
- `scripts/validate_frameworks.py` exits 0 — **every new check should be mapped
  into at least the frameworks whose control it evidences.** Since these checks
  are derived *from* Security Hub controls, the NIST mapping is mechanical.
- Simulation scripts per service, actually executed, with honest documentation of
  which checks cannot be forced to FAIL through the API.
- Full scan exits 0 with no traceback; new rows render with real pass/fail state.
- No account-level or region-wide setting is mutated by a simulation.

## 9. Open questions for the maintainer

1. **Is Phase 3 worth it given §1.6?** DocumentDB and Neptune are cheap *only*
   if `rds:DescribeDBClusters` returns their engines. That needs an account with
   such a cluster to confirm. Deprioritise until someone can test?
2. **Multi-account posture.** Should GuardDuty checks attempt delegated-admin
   awareness (`list_organization_admin_accounts`), or stay local-detector-only
   with the divergence documented? Local-only is my recommendation — simpler and
   honest.
3. **Do you want scanner-original checks** beyond FSBP (`AI_PROTECTION`,
   CodeBuild privileged mode, ACM RSA key length)? They add real value but have
   no upstream control to cite in a framework mapping.
4. **`Account.1` refinement** — worth fixing `IamAccount.py:290` to require the
   SECURITY contact type specifically, matching Security Hub?
