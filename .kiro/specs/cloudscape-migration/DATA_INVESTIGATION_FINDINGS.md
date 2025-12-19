# Data Investigation Findings - Phase 2.5

## Date: December 8, 2024

## Summary

Investigation into data availability for missing features (CustomPage and GuardDuty special handling).

## Key Findings

### 1. GuardDuty Data Source ✅ COMPLETE

**Finding:** GuardDuty data IS available in api-full.json with raw data, but needs processing for charts/tables.

**Evidence:**
- ✅ Raw data in `api-full.json` under `guardduty.detail`
- ✅ Settings, UsageStat, FreeTrial, Findings all present
- ❌ Processed data (charts, grouped findings) NOT in JSON
- ❌ Processing happens in GuardDutyPageBuilder, not in Reporter

**Data Structure Found:**
```json
{
  "guardduty": {
    "detail": {
      "ap-southeast-1": {
        "Detector::b6c337ba6115507baf62cd630529d574": {
          "Settings": { "value": { "isEnabled": "ENABLED", "Settings": {...} } },
          "UsageStat": { "value": [{"DataSource": "S3_LOGS", "Total": {...}}] },
          "FreeTrial": { "value": {"CloudTrail": {"FreeTrialDaysRemaining": 0}} },
          "Findings": { "value": {"2": {...}, "5": {...}, "8": {...}} }
        }
      }
    }
  }
}
```

**Implementation:** Need to replicate GuardDutyPageBuilder processing in React components.

### 2. CustomPage Data Source

**Finding:** CustomPage features (CPFindings, CPModernize, CPTA) read data from **Excel file**, not JSON.

**Evidence:**
- `FindingsPageBuilder.py` loads `workItem.xlsx` using openpyxl
- Generates HTML tables directly from Excel sheets
- No JSON data structure for CustomPage

**Code Reference:**
```python
# From FindingsPageBuilder.py
def customPageInit(self):
    self.wb = openpyxl.load_workbook(_C.ROOT_DIR + '/' + Config.get('HTML_ACCOUNT_FOLDER_PATH') + '/workItem.xlsx')
```

**Implication:** We cannot use the Excel file in the browser (Cloudscape UI). We need to:
1. Extract data from Excel during Python generation
2. Add to api-full.json
3. Read from JSON in React

---

### 2. CPFindings Data Structure

**What it does:**
- Reads all sheets from workItem.xlsx (except 'Info' and 'Appendix')
- Creates a table with columns: Service, [Excel columns]
- Filters by suppression status
- Provides tabs for "Findings" and "Suppressed"

**Data needed in JSON:**
```json
{
  "customPage_findings": {
    "findings": [
      {
        "service": "s3",
        "rule": "BucketEncryption",
        "priority": "H",
        "category": "Security",
        "affectedResources": 15,
        "description": "...",
        "status": "Active" | "Suppressed"
      }
    ]
  }
}
```

---

### 3. CPModernize Data Structure

**Status:** ✅ Investigated

**What it does:**
- Analyzes modernization opportunities across compute and database resources
- Creates Sankey diagram showing modernization paths
- Tracks resources by type (EC2, RDS, Lambda, EKS, DynamoDB)
- Suggests migrations (e.g., Windows→Container, x86→Graviton, MSSQL→OpenSource)

**Data Source:** Collected during scan via `recordItem()` method
- Tracks EC2 instances (Windows/Linux, Graviton-eligible, outdated OS)
- Tracks RDS databases (engine types, Aurora candidates)
- Tracks Lambda functions
- Tracks EKS/ECS containers
- Tracks DynamoDB tables

**Data Structure:** Already collected in CustomPage.Modernize.*.json files during scan

**Data needed in JSON:**
```json
{
  "customPage_modernize": {
    "Computes": {
      "nodes": ["Resources (100)", "Computes (80)", "EC2 (60)", ...],
      "links": [
        {"source": 0, "target": 1, "value": 80},
        {"source": 1, "target": 2, "value": 60}
      ]
    },
    "Databases": {
      "nodes": ["Resources (100)", "Databases (20)", "RDS (15)", ...],
      "links": [...]
    }
  }
}
```

---

### 4. CPTA (Trusted Advisor) Data Structure

**Status:** ✅ Investigated

**What it does:**
- Calls AWS Trusted Advisor API during scan
- Retrieves recommendations across 6 pillars:
  - Cost Optimization
  - Security
  - Performance
  - Fault Tolerance
  - Service Limits
  - Operational Excellence
- Shows error/warning/ok counts per recommendation
- Shows estimated monthly savings for cost optimization

**Data Source:** AWS Trusted Advisor API (called during scan)
- Requires Business or Enterprise Support plan
- Calls `trustedadvisor:list_recommendations`
- Calls `trustedadvisor:get_recommendation`

**Important:** TA data is generated DURING scan, not from Excel

**Data Structure:**
```json
{
  "customPage_ta": {
    "COST_OPTIMIZING": {
      "rows": [[service, finding, error_count, warning_count, ok_count, last_updated, savings, percent]],
      "thead": ["Services", "Findings", "# Error", "# Warning", "# OK", "Last Updated", "Savings", "Percent"],
      "total": {"Error": 5, "Warning": 10, "OK": 20}
    },
    "SECURITY": {...},
    "PERFORMANCE": {...},
    "FAULT_TOLERANCE": {...},
    "SERVICE_LIMITS": {...},
    "OPERATIONAL_EXCELLENCE": {...},
    "error": "" // or error message if TA not available
  }
}
```

---

### 5. GuardDuty Data

**Status:** ✅ Investigated (via code analysis)

**What it does:**
- GuardDutyPageBuilder processes raw findings from Reporter
- Creates custom visualizations:
  - Stacked bar chart (by criticality and region)
  - Donut chart (by category: EC2, IAM, K8s, S3, Malware, etc.)
  - Settings table (data sources, costs, free trial)
  - Grouped findings (by severity, service type, finding type)

**Data Source:** Reporter.getDetail() provides raw data

**Current State:**
- ✅ Raw data IS in api-full.json (guardduty.detail)
- ❌ Processed data (charts, settings, grouped findings) is NOT in api-full.json
- ⚠️ Processing happens in GuardDutyPageBuilder, not in Reporter

**Data Structure in api-full.json:**
```json
{
  "guardduty": {
    "summary": {...},
    "detail": {
      "us-east-1": {
        "detector-id": {
          "Findings": {"value": {"8": {...}, "5": {...}, "2": {...}}},
          "UsageStat": {"value": [...]},
          "FreeTrial": {"value": {...}},
          "Settings": {"value": {...}}
        }
      }
    }
  }
}
```

**Implementation:** Need to replicate GuardDutyPageBuilder processing in React OR add processed data to api-full.json

---

## Next Steps

### Immediate Actions

1. ✅ **CPFindings** - Extract Excel data to JSON
   - Modify OutputGenerator to read workItem.xlsx
   - Extract all findings with service, rule, priority, status
   - Add to api-full.json as `customPage_findings`

2. ⏳ **CPModernize** - Investigate data source
   - Read Modernize.py
   - Read ModernizePageBuilder.py
   - Determine data structure needed

3. ⏳ **CPTA** - Investigate data source
   - Read TA.py
   - Read TAPageBuilder.py
   - Check if TA API is called
   - Determine data structure needed

4. ⏳ **GuardDuty** - Run test scan
   - Enable GuardDuty in test account
   - Run scan with GuardDuty
   - Inspect api-full.json
   - Verify data completeness

### Implementation Strategy

#### Option A: Extract from Excel (Recommended for CPFindings)
**Pros:**
- Excel already has all the data
- No changes to existing code
- Just add extraction step

**Cons:**
- Requires openpyxl in OutputGenerator
- Excel must be generated before JSON embedding

**Implementation:**
```python
# In OutputGenerator._generate_cloudscape()
def _extract_findings_from_excel(self):
    import openpyxl
    excel_path = self.html_folder + '/workItem.xlsx'
    wb = openpyxl.load_workbook(excel_path)
    
    findings = []
    for sheet_name in wb.sheetnames:
        if sheet_name in ['Info', 'Appendix']:
            continue
        ws = wb[sheet_name]
        for row in range(2, ws.max_row + 1):
            finding = {
                'service': sheet_name,
                'rule': ws.cell(row, 1).value,
                'priority': ws.cell(row, 2).value,
                # ... extract all columns
            }
            findings.append(finding)
    
    return findings
```

#### Option B: Generate JSON during scan (Better long-term)
**Pros:**
- Cleaner architecture
- No Excel dependency
- Faster (no Excel parsing)

**Cons:**
- Requires changes to Reporter/CustomPage
- More complex implementation
- Affects existing code

**Decision:** Use Option A for Phase 2.5 (faster), consider Option B for future

---

## Data Structure Proposals

### customPage_findings
```json
{
  "customPage_findings": {
    "columns": ["Service", "Rule", "Priority", "Category", "Resources", "Description", "Status"],
    "findings": [
      {
        "service": "s3",
        "rule": "BucketEncryption",
        "priority": "H",
        "category": "Security",
        "resources": 15,
        "description": "Enable encryption at rest",
        "status": "Active"
      }
    ],
    "suppressed": [
      {
        "service": "s3",
        "rule": "BucketReplication",
        "priority": "M",
        "category": "Reliability",
        "resources": 15,
        "description": "Enable cross-region replication",
        "status": "Suppressed"
      }
    ]
  }
}
```

### customPage_modernize
```json
{
  "customPage_modernize": {
    "recommendations": [
      {
        "service": "ec2",
        "recommendation": "Migrate to Graviton instances",
        "priority": "H",
        "impact": "Cost savings 20-40%",
        "effort": "Medium",
        "resources": ["i-123", "i-456"]
      }
    ]
  }
}
```

### customPage_ta
```json
{
  "customPage_ta": {
    "checks": [
      {
        "category": "Cost Optimization",
        "check": "Low Utilization EC2 Instances",
        "status": "Warning",
        "affectedResources": 5,
        "estimatedSavings": "$500/month",
        "recommendation": "Right-size or terminate"
      }
    ],
    "summary": {
      "cost": { "ok": 10, "warning": 5, "error": 2 },
      "performance": { "ok": 15, "warning": 3, "error": 0 },
      "security": { "ok": 20, "warning": 2, "error": 1 },
      "faultTolerance": { "ok": 12, "warning": 4, "error": 0 },
      "serviceLimit": { "ok": 50, "warning": 5, "error": 0 }
    }
  }
}
```

---

## Risks and Mitigation

### Risk 1: Excel file not available when embedding data
**Mitigation:** Ensure Excel is generated before calling `_embed_data()`

### Risk 2: Excel structure changes
**Mitigation:** Document expected structure, add validation

### Risk 3: Large Excel files slow down extraction
**Mitigation:** Cache extracted data, optimize parsing

### Risk 4: TA API may not be available
**Mitigation:** Check if TA data is already collected, document limitations

---

## Timeline Impact

**Original Estimate:** 1-2 days for data investigation

**Actual Complexity:**
- CPFindings: Need Excel extraction (1 day)
- CPModernize: Need investigation (0.5 days)
- CPTA: Need investigation + possible TA API work (1-2 days)
- GuardDuty: Need test scan (0.5 days)

**Revised Estimate:** 3-4 days for complete data investigation and extraction

---

## Recommendations

1. **Start with CPFindings** - Clear path forward (Excel extraction)
2. **Investigate CPModernize and CPTA** - Understand data sources
3. **Test GuardDuty** - Run scan to see actual data
4. **Update OutputGenerator** - Add data extraction methods
5. **Document data structures** - Clear contracts for React components

---

## Status

- ✅ CPFindings data source identified (Excel)
- ⏳ CPModernize data source (investigating)
- ⏳ CPTA data source (investigating)
- ⏳ GuardDuty data (need test scan)

---

## Next Task

Continue with Task 1.2: Check GuardDuty special data availability
