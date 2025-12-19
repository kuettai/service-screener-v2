# Data Investigation Complete - Phase 2.5

## Date: December 8, 2024

## Executive Summary

Completed investigation of all missing features. Found that **ALL CustomPage data needs to be added to api-full.json**.

## Key Findings

### 1. CPFindings - Excel-based ✅

**Data Source:** workItem.xlsx (Excel file)

**Current State:**
- ❌ NOT in api-full.json
- ✅ Available in Excel file
- ✅ Easy to extract

**Implementation:** Extract from Excel during OutputGenerator

---

### 2. CPModernize - JSON-based ✅

**Data Source:** CustomPage.Modernize.*.json files (generated during scan)

**Current State:**
- ❌ NOT in api-full.json
- ✅ Generated during scan in __fork/ directory
- ✅ Data structure already defined

**Implementation:** Read JSON files and add to api-full.json

---

### 3. CPTA - API-based ✅

**Data Source:** AWS Trusted Advisor API (called during scan)

**Current State:**
- ❌ NOT in api-full.json
- ✅ Data collected during scan via TA.py
- ⚠️ Requires Business/Enterprise Support plan
- ✅ Data structure already defined

**Implementation:** Read from TA.py output and add to api-full.json

---

### 4. GuardDuty - Needs Investigation ⏳

**Data Source:** GuardDuty service scan

**Current State:**
- ⏳ Need to run scan with GuardDuty to verify
- ⏳ Check if special data (charts, settings) is in api-full.json
- ⏳ Verify GuarddutyPageBuilder data structure

**Implementation:** TBD after running GuardDuty scan

---

## Data Flow Analysis

### Current Flow (AdminLTE)

```
Scan → __fork/*.json → PageBuilder → HTML
                    ↓
                Excel (workItem.xlsx) → CPFindings HTML
```

### Required Flow (Cloudscape)

```
Scan → __fork/*.json → OutputGenerator → api-full.json → Embedded in HTML → React
                    ↓
                Excel (workItem.xlsx) ↗
```

---

## Implementation Plan

### Step 1: Update OutputGenerator to Include CustomPage Data

```python
# In OutputGenerator._generate_legacy()

# After generating api-full.json, add CustomPage data
def _add_custompage_data(self, api_result_array):
    # 1. Extract CPFindings from Excel
    findings_data = self._extract_findings_from_excel()
    api_result_array['customPage_findings'] = findings_data
    
    # 2. Extract CPModernize from JSON files
    modernize_data = self._extract_modernize_from_json()
    api_result_array['customPage_modernize'] = modernize_data
    
    # 3. Extract CPTA from TA output
    ta_data = self._extract_ta_data()
    api_result_array['customPage_ta'] = ta_data
    
    return api_result_array
```

### Step 2: Implement Extraction Methods

#### Extract CPFindings from Excel
```python
def _extract_findings_from_excel(self):
    import openpyxl
    excel_path = self.html_folder + '/workItem.xlsx'
    
    if not os.path.exists(excel_path):
        return {'findings': [], 'suppressed': []}
    
    wb = openpyxl.load_workbook(excel_path)
    findings = []
    suppressed = []
    
    for sheet_name in wb.sheetnames:
        if sheet_name in ['Info', 'Appendix']:
            continue
        
        ws = wb[sheet_name]
        # Get column headers
        headers = [ws.cell(1, col).value for col in range(1, ws.max_column + 1)]
        
        # Extract rows
        for row in range(2, ws.max_row + 1):
            finding = {'service': sheet_name}
            for col, header in enumerate(headers, 1):
                finding[header] = ws.cell(row, col).value
            
            # Separate by status
            if finding.get('Status') == 'Suppressed':
                suppressed.append(finding)
            else:
                findings.append(finding)
    
    return {
        'columns': headers,
        'findings': findings,
        'suppressed': suppressed
    }
```

#### Extract CPModernize from JSON
```python
def _extract_modernize_from_json(self):
    import glob
    
    modernize_files = glob.glob(_C.FORK_DIR + '/CustomPage.Modernize.*.json')
    
    if not modernize_files:
        return {}
    
    # Modernize data is already in the right format
    # Just need to aggregate from all service files
    modernize_data = {}
    
    for file_path in modernize_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Merge data
            for key, value in data.items():
                if key not in modernize_data:
                    modernize_data[key] = value
    
    return modernize_data
```

#### Extract CPTA from TA Output
```python
def _extract_ta_data(self):
    ta_files = glob.glob(_C.FORK_DIR + '/CustomPage.TA.*.json')
    
    if not ta_files:
        return {'error': 'No TA data available'}
    
    # TA data structure is already defined in TA.py
    # Just need to read and format
    ta_data = {}
    
    for file_path in ta_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # TA data is already in the right format
            ta_data.update(data)
    
    return ta_data
```

---

## Data Structures for React

### customPage_findings
```typescript
interface CPFindings {
  columns: string[];
  findings: Finding[];
  suppressed: Finding[];
}

interface Finding {
  service: string;
  [key: string]: any; // Dynamic columns from Excel
}
```

### customPage_modernize
```typescript
interface CPModernize {
  Computes: SankeyData;
  Databases: SankeyData;
}

interface SankeyData {
  nodes: string[]; // ["Resources (100)", "Computes (80)", ...]
  links: Link[];
}

interface Link {
  source: number; // Index in nodes array
  target: number; // Index in nodes array
  value: number;  // Flow value
}
```

### customPage_ta
```typescript
interface CPTA {
  COST_OPTIMIZING?: TASection;
  SECURITY?: TASection;
  PERFORMANCE?: TASection;
  FAULT_TOLERANCE?: TASection;
  SERVICE_LIMITS?: TASection;
  OPERATIONAL_EXCELLENCE?: TASection;
  error?: string;
}

interface TASection {
  rows: any[][]; // Table rows
  thead: string[]; // Table headers
  total: {
    Error: number;
    Warning: number;
    OK: number;
  };
}
```

---

## Estimated Effort

### Task 1.3: Update OutputGenerator
- **Effort:** 1-2 days
- **Complexity:** Medium
- **Dependencies:** openpyxl library

### Task 2-5: Implement React Components
- **CPFindings:** 2 days
- **CPModernize:** 2-3 days (Sankey diagram)
- **CPTA:** 2-3 days (6 sections)
- **GuardDuty:** 3-4 days (custom charts)

**Total:** 10-14 days

---

## Risks

### Risk 1: Excel File Timing
**Issue:** Excel must be generated before embedding data  
**Mitigation:** Ensure Excel generation happens in _generate_legacy() before calling _add_custompage_data()

### Risk 2: CustomPage JSON Files Missing
**Issue:** If scan doesn't generate CustomPage files  
**Mitigation:** Check if files exist, return empty data if not

### Risk 3: TA API Access
**Issue:** User may not have Business/Enterprise Support  
**Mitigation:** Handle error gracefully, show message in UI

### Risk 4: Large Excel Files
**Issue:** Parsing large Excel files may be slow  
**Mitigation:** Cache extracted data, optimize parsing

---

## Next Steps

1. ✅ Investigation complete
2. ⏳ Mark Task 1.1 complete
3. ⏳ Run GuardDuty scan (Task 1.2)
4. ⏳ Implement OutputGenerator updates (Task 1.3)
5. ⏳ Implement React components (Tasks 2-5)

---

## Conclusion

**All CustomPage data sources identified:**
- ✅ CPFindings: Excel (workItem.xlsx)
- ✅ CPModernize: JSON files (__fork/CustomPage.Modernize.*.json)
- ✅ CPTA: JSON files (__fork/CustomPage.TA.*.json)
- ⏳ GuardDuty: Need to verify

**Implementation path is clear:**
1. Extract data from Excel and JSON files
2. Add to api-full.json
3. Create React components to display

**Estimated timeline:** 10-14 days for full implementation

**Ready to proceed with implementation!**
