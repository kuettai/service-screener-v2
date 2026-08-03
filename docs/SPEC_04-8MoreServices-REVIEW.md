# Review: SPEC_04-8MoreServices.md

> **Reviewed 2026-08-03.** Every API operation and field named in the spec was
> checked against the live botocore models, and every account-level API was
> executed against account `956288449190` / `ap-southeast-1`. Findings below are
> verified, not inferred.
>
> **Verdict: sound spec, approve with changes.** The 8 services are well chosen
> and ~85% of the named fields are correct. But there are **2 blocking issues**
> (one would have the scanner mutate production state), **6 correctness fixes**,
> and **~25 additional checks worth adding** from AWS documentation.

## Summary

| | Count |
|---|---|
| Services proposed | 8 |
| Checks proposed | ~87 |
| Blocking issues | **2** |
| Correctness fixes needed | 6 |
| Checks to drop or demote | 7 |
| **Additional checks recommended** | **~25** |
| Revised total | **~105** |

Cross-check against the other research in `SPEC_05_CHECK_COVERAGE_EXPANSION.md`
(the coverage-gap spec written the same day): **CodeBuild and EMR appear in
both.** They should be built once, to the union of both specs — see §5.

---

## 1. BLOCKING — must fix before implementation

### 1.1 `cfnDriftDetected` would mutate production state and incur cost

The spec says:

> `cfnDriftDetected` | `detect_stack_drift` → DriftStatus == "DRIFTED"

`DetectStackDrift` is **not a read operation.** Verified against the botocore
model — its only output is:

```
DetectStackDrift output: ['StackDriftDetectionId']
```

It *initiates* an asynchronous drift-detection operation. It changes stack state,
takes minutes to complete, is rate-limited, and is billed as a
configuration-item-generating operation. A scanner that calls it on every stack
in every region would be performing a write action against production
infrastructure — a direct violation of the read-only contract every other check
in this codebase honours.

**Fix — the data is already available free.** `DescribeStacks` returns
`DriftInformation` with `StackDriftStatus` and `LastCheckTimestamp`. Verified live
against real stacks:

```
ssv2-3786431e7498   NOT_CHECKED   null
ssv2-cf8c5422fd5c   NOT_CHECKED   null
```

So the check should read `DriftInformation.StackDriftStatus` from the response
the spec *already* fetches. Note the real-world value is usually `NOT_CHECKED`,
which is arguably the more useful finding — "nobody has ever checked this stack
for drift" — and needs a distinct INFO/FAIL treatment from `DRIFTED`. Suggest
splitting:

- `cfnDriftDetected` — FAIL when `StackDriftStatus == 'DRIFTED'`
- `cfnDriftNeverChecked` — FAIL/INFO when `StackDriftStatus == 'NOT_CHECKED'`

### 1.2 Three checks enumerate unbounded finding sets

Three checks are specified in terms of listing findings:

- `shubUnprocessedFindings` — "get_findings with workflow status NEW and age >7 days, count > 100"
- `inspectorCriticalFindings` — "list_findings with severity CRITICAL and status ACTIVE"
- `aaUnresolvedExternalAccess` / `aaFindingsOlderThan30Days` — "list_findings ..."

Verified live: both `securityhub get-findings` and `inspector2 list-findings`
return a `nextToken` on the first page. This account has **1,248 Inspector
findings**, so a naive implementation makes ~13 paginated calls for one check —
and a large account could make hundreds. This is exactly the class of problem
that produces the "[Slow] check took Ns" warnings already instrumented in
`services/Evaluator.py`.

**Fix for Inspector — use the aggregation API.** `list_finding_aggregations`
returns exact counts in **one call**. Verified live:

```json
{"accountAggregation": {"severityCounts":
  {"all": 1248, "medium": 796, "high": 322, "critical": 28},
  "exploitAvailableCount": 10, "fixAvailableCount": 1247}}
```

That single call satisfies `inspectorCriticalFindings` *and* enables two better
checks (see §4.3). No pagination.

**Fix for Security Hub and Access Analyzer:** there is no equivalent aggregation
API, so either (a) cap pagination explicitly and document the cap — the
convention SPEC_02 established with `INVENTORY_SAMPLE_LIMIT` in
`services/ssm/Ssm.py` — or (b) drop the count-based checks. I recommend capping
at a documented page limit and reporting "at least N", never silently truncating.

---

## 2. Correctness fixes — wrong field or API names

All verified against the live botocore models.

| Spec says | Reality | Impact |
|---|---|---|
| EMR `TerminationProtection` | field is **`TerminationProtected`** | check would always pass |
| AppSync `cachingConfig` on the API object | **not a member of `GraphqlApi`.** Caching lives in a separate `GetApiCache` call | `appsyncCachingDisabled` cannot be implemented as specified |
| EMR `emrEncryptionAtRestDisabled` reads "SecurityConfiguration missing or encryption.atRest disabled" | `DescribeCluster` returns only the security configuration **name**. The content requires `DescribeSecurityConfiguration`, whose response is a **JSON string that must be parsed** | two-hop lookup + JSON parse, not a field read |
| EMR `emrPubliclyAccessible` via `EmrManagedMasterSecurityGroup` allows 0.0.0.0/0 | `DescribeCluster` returns only the SG **id**. Rule evaluation needs an EC2 `describe_security_groups` join | cross-service join; also note `ec2.SGSensitivePortOpenToAll` may already cover the same SG |
| Athena `athenaS3OutputNotEncrypted` — "OutputLocation points to unencrypted S3 bucket" | requires resolving an S3 URI to a bucket then calling `s3:GetBucketEncryption` | cross-service join; likely duplicates `s3.ServerSideEncrypted` |
| `inspector2` resource states | live response also includes **`codeRepository`**, which the spec omits | missing a check (see §4.3) |

Fields I verified as **correct** (no action needed): all AppSync fields except
`cachingConfig` (`introspectionConfig`, `queryDepthLimit`, `resolverCountLimit`,
`wafWebAclArn`, `xrayEnabled`, `logConfig`, `visibility`); all CodeBuild fields
(`privilegedMode`, `encryptionKey`, `vpcConfig`, `concurrentBuildLimit`, `badge`,
`artifacts.encryptionDisabled`, `source.insecureSsl`, `logsConfig.s3Logs`); all
EMR fields except the two above; all Athena `Configuration` members; all
CloudFormation `Stack` members; Security Hub `AutoEnableControls`; every
Access Analyzer type including `ACCOUNT_UNUSED_ACCESS`.

---

## 3. Checks to drop or demote

| Check | Recommendation | Reason |
|---|---|---|
| `athenaRequesterPaysDisabled` | **Drop** | Requester-pays is a billing-model choice, not a finding. Most workgroups should have it off. Would fire on nearly every workgroup as noise. |
| `emrNoBootstrapActions` | **Drop** | The spec itself calls it "informational". Absence of bootstrap actions is not a defect — plenty of clusters need none. |
| `emrMasterInstanceOnDemand` | **Demote to INFO** | Spot masters are a deliberate cost trade-off in dev/test. As a FAIL it punishes an intentional choice. |
| `cfnNestedStacksDeep` | **Drop or demote** | "Depth > 3" is an arbitrary threshold with no AWS guidance behind it, and computing true depth needs recursive `ParentId` resolution across all stacks. High effort, weak signal. |
| `cfnIAMCapabilityGranted` | **Demote to INFO** | Spec already marks it informational. `CAPABILITY_IAM` is required for any stack that creates a role — that is most stacks. |
| `cbBadgeEnabled` | **Drop** | The stated condition ("badge requires repo visibility") is not evaluable from the CodeBuild API; badge state alone is not a security finding. |
| `athenaEnginev2OrOlder` | **Keep but re-word** | String-comparing `"Athena engine version 3"` is fragile. Parse the trailing integer. |

Also: **7 of the ~87 checks are `*NoTags`** (one per service). Consistent with
existing services, but note SPEC_03's finding that tag checks map to no security
framework — they will remain unmapped. That is fine; just do not expect framework
coverage from them.

---

## 4. Additional checks recommended (~25)

These come from AWS Security Hub control documentation and the live API surface,
and are **not** in the spec.

### 4.1 GuardDuty is missing entirely from this spec — and it is the biggest gap

The spec adds Security Hub, Inspector and Access Analyzer but **not** GuardDuty
feature coverage. The existing `guardduty` service has only 5 checks and
`GuarddutyDriver.py:146` calls `get_detector()` while reading only the
**deprecated** `DataSources` field, discarding `Features[]`.

Verified live on detector `b6c337ba6115507baf62cd630529d574`:

```
RUNTIME_MONITORING      DISABLED   <-- GuardDuty.11, HIGH severity, unreported
AI_PROTECTION           DISABLED   <-- no FSBP control yet; scanner original
EKS_RUNTIME_MONITORING  ENABLED    [EKS_ADDON_MANAGEMENT: DISABLED]
```

That is a **High**-severity failure in this account today that the scanner
silently ignores. Ten checks, **zero new API calls** — detailed in
`SPEC_05_CHECK_COVERAGE_EXPANSION.md` §2.1. Strongly recommend folding into this
spec's scope, since it is cheaper than any of the 8 new services.

### 4.2 Security Hub — add from FSBP/CIS

| Proposed | Source | Sev |
|---|---|---|
| `shubConsolidatedControlFindingsDisabled` | `describe_hub().ControlFindingGenerator != 'SECURITY_CONTROL'` — verified live, this account returns `STANDARD_CONTROL`, the legacy mode | M |

Verified live: `AutoEnableControls: true`, `ControlFindingGenerator: STANDARD_CONTROL`.
So `shubAutoEnableControlsDisabled` would PASS here but the new check would FAIL —
a real finding.

### 4.3 Inspector — from the aggregation API and live response

| Proposed | Source | Sev |
|---|---|---|
| `inspectorCodeRepositoryScanningDisabled` | `resourceState.codeRepository.status` — present in the live response, absent from the spec | M |
| `inspectorExploitableFindings` | `exploitAvailableCount > 0` from `list_finding_aggregations` — verified live: **10** | H |
| `inspectorFixAvailableNotApplied` | `fixAvailableCount` vs `all` — verified live: **1247 of 1248** have a fix available and are unpatched | H |

`inspectorExploitableFindings` is the strongest signal available from Inspector:
a known-exploited vulnerability with a fix available is the highest-priority
finding class in vulnerability management, and it costs one API call.

### 4.4 CodeBuild — FSBP controls the spec misses

The spec's CodeBuild list is good but omits two **Critical** FSBP controls:

| Proposed | FSBP | Sev |
|---|---|---|
| `cbSourceUrlCredentials` | **CodeBuild.1** "Bitbucket source repository URLs should not contain sensitive credentials" — check `source.location` and `secondarySources[].location` for embedded credentials | **C** |
| `cbPlaintextCredentialsInEnvVars` | **CodeBuild.2** "Project environment variables should not contain clear text credentials" — `environment.environmentVariables[]` where `type == PLAINTEXT` and name matches AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY | **C** |
| `cbReportGroupExportNotEncrypted` | **CodeBuild.7** — `list_report_groups()` → `batch_get_report_groups()` | M |
| `cbProjectVisibilityPublic` | `projectVisibility == 'PUBLIC_READ'` — a public CodeBuild project exposes build logs to anyone. Field verified present; enum is `['PUBLIC_READ', 'PRIVATE']`, so match `PUBLIC_READ` exactly, not the string `PUBLIC` | H |

`CodeBuild.2` is a well-documented real-world breach vector and the single
highest-value check in the whole spec. It must not be omitted.

### 4.5 EMR — FSBP alignment

| Proposed | FSBP | Sev |
|---|---|---|
| `emrBlockPublicAccessDisabled` | **EMR.2** — already in the spec; note resource type is account-level (`AWS::::Account`), so it belongs in a regional driver, not per-cluster | **C** |
| — | EMR.1/3/4 already covered by the spec's checks | |

### 4.6 AppSync — replace the unimplementable caching check

| Proposed | Source | Sev |
|---|---|---|
| `appsyncApiCacheNotEncrypted` | `get_api_cache()` → `atRestEncryptionEnabled` / `transitEncryptionEnabled` | M |

Note AWS **retired** `AppSync.1` and `AppSync.6` on 2026-03-09 because caches are
now encrypted by default — so this is only worth adding for legacy caches, and
should be INFO rather than FAIL. Prefer simply dropping `appsyncCachingDisabled`.

### 4.7 Access Analyzer — newer analyzer types

| Proposed | Source | Sev |
|---|---|---|
| `aaNoInternalAccessAnalyzer` | `ACCOUNT_INTERNAL_ACCESS` / `ORGANIZATION_INTERNAL_ACCESS` — verified as valid enum values, newer than the spec | L |

---

## 5. Overlap with the other SPEC_04

Both specs were produced on 2026-08-03 and **overlap on two services**:

| Service | This spec | `SPEC_05_CHECK_COVERAGE_EXPANSION.md` |
|---|---|---|
| **CodeBuild** | 12 checks, misses CodeBuild.1/2/7 (2 Critical) | 5 FSBP controls incl. both Criticals |
| **EMR** | 15 checks, richer operational coverage | 4 FSBP controls, notes JSON-parse and two-hop issues |

**Recommendation:** build each once, to the **union**. This spec has better
breadth (operational, cost, reliability checks); the coverage spec has the
authoritative FSBP control mapping and Critical severities. Merging gives
CodeBuild ~16 checks and EMR ~17.

Also note the coverage spec independently identified **MSK** as the highest
security-density gap (MSK.4 public access + MSK.6 unauthenticated = Critical
pairing). MSK is absent from this spec and is arguably a better addition than
Athena or CloudFormation on impact grounds.

---

## 6. Structural notes

**Good, keep as-is:**

- The per-service format matches SPEC_02 exactly, which built cleanly.
- Mandatory simulation runs (step 8) — SPEC_02 proved this catches real problems
  that static review misses.
- Explicit remediation-null guidance in the header matches the validator's actual
  rule (`scripts/validate_reporter.py` requires `remediation_risk` be null when
  `remediation` is null).

**Add to the spec before building:**

1. **Framework mapping is under-specified.** Step 6 says "update WAFS/AAIL" but
   the per-service mapping lines name best practices imprecisely — e.g. AppSync
   cites "SEC09.BP02 (API protection)" but SEC09.BP02 is encryption in transit;
   API protection is SEC05.BP01. Since these checks derive from Security Hub
   controls, also map them into **NIST**, where the section IDs *are* Security Hub
   control IDs — that mapping is mechanical. Add `python3 scripts/validate_frameworks.py`
   to the validation list; it is now CI-enforced and will fail the build on a
   dangling entry.
2. **CloudFormation service-name collision risk.** `Screener.getServiceModuleDynamically`
   builds the class name via `service.title()`, so `cloudformation` → class
   `Cloudformation` in `services/cloudformation/Cloudformation.py`. That is fine,
   but note SPEC_02 hit a real collision with `config` shadowing
   `utils/Config.py`; the same aliasing discipline applies if anything imports
   `boto3` CloudFormation types by that name.
3. **Account-level vs per-resource drivers.** Security Hub, Inspector,
   Access Analyzer, and EMR's block-public-access are all account/region-scoped,
   not per-resource. SPEC_02 established the pattern (`Config::Account`,
   `SSM::Account`, `EventBridge::Account`) — the spec should say so explicitly so
   implementers do not invent a per-resource shape.
4. **Simulation feasibility warnings.** Several of these cannot be simulated
   safely, and the spec should say so up front rather than letting an implementer
   discover it: enabling Security Hub / Inspector / GuardDuty features are
   **account-level mutations** with real cost; an EMR cluster costs money per hour;
   Access Analyzer findings cannot be manufactured on demand. Expect
   read-only posture reports for these, as SPEC_02 did for `config`.
5. **Severity sanity.** `cbPrivilegedMode` at H and `cbInsecureSSL` at H are right.
   But `emrEncryptionAtRestDisabled` at H and `emrNoSecurityConfiguration` at H
   will double-report on the same cluster — one of them should be the finding and
   the other INFO, or they should be merged.

---

## 7. Recommended disposition

**Approve with changes.** Suggested build order, revised for effort-vs-impact:

| Phase | Content | Est. checks | Rationale |
|---|---|---:|---|
| **0** | GuardDuty `Features[]` (§4.1) | 10 | Zero new API calls; closes a live High finding. Cheapest work in either spec. |
| **1** | CodeBuild (merged union, §5) | ~16 | 2 Critical credential-exposure controls; highest prevalence of the 8. |
| **2** | Access Analyzer + Security Hub + Inspector | ~27 | All account-level, all one-call APIs, no simulation infrastructure needed. Use the Inspector aggregation API (§1.2). |
| **3** | AppSync + Athena | ~20 | Straightforward per-resource services, no blocking issues. |
| **4** | EMR (merged union) + CloudFormation | ~30 | Highest effort — EMR needs two-hop lookups and JSON parsing; CFN needs the drift fix (§1.1). |

Blocking issues §1.1 and §1.2 must be resolved in the spec text before any code
is written. The 6 correctness fixes in §2 should be applied to the spec tables so
implementers are not debugging against wrong field names.
