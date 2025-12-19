# Custom Pages Content Analysis

## Current Implementation Status

The Custom Pages are currently showing basic tables with the data, but the content and layout need improvement to match the expected functionality.

## Data Available

From the test data, we have:

### customPage_findings
```javascript
{
  "columns": ["Region", "Check", "Type", "ResourceID", "Severity", "Status"],
  "findings": [
    // Array of 141 finding objects with properties:
    // - service, Region, Check, Type, ResourceID, Severity, Status
  ],
  "suppressed": [
    // Array of 75 suppressed finding objects
  ]
}
```

### customPage_modernize
```javascript
{
  "ec2instance": {
    "total": 4,
    "items": [
      // Array of EC2 instances with properties:
      // - platform, instanceType, id, keyTags
    ],
    "rules": {
      "WindowsOSNotLatest": [],
      "MoveToGraviton": [],
      "WindowsOSOutdated": []
    }
  }
}
```

### customPage_ta
```javascript
{
  "ec2instance": {
    "total": 4,
    "items": [
      // Same structure as modernize
    ],
    "rules": {
      "WindowsOSNotLatest": [],
      "MoveToGraviton": [],
      "WindowsOSOutdated": []
    }
  }
}
```

## Legacy AdminLTE Implementation

### CPFindings.html
- Has tabs for "Findings" and "Suppressed"
- Uses DataTables for displaying findings
- Shows columns: Region, Check, Type, ResourceID, Severity, Status
- Likely has filtering and sorting capabilities

### CPModernize.html
- Shows EC2 instances that can be modernized
- Displays recommendations for moving to newer generations or Graviton

### CPTA.html (Trusted Advisor)
- Shows Trusted Advisor recommendations
- Similar structure to Modernize

## Recommended Improvements

### 1. Findings Page
**Should include:**
- Tabs component with "Active Findings" and "Suppressed Findings"
- Filterable table with columns: Service, Region, Check, Type, Resource ID, Severity, Status
- Summary cards showing:
  - Total findings
  - Breakdown by severity (High, Medium, Low, Informational)
  - Breakdown by service
- Export to CSV functionality
- Search/filter by service, region, severity

### 2. Modernize Page
**Should include:**
- Summary card showing total instances and modernization opportunities
- Table of EC2 instances with:
  - Instance ID
  - Platform
  - Current Instance Type
  - Recommendation (if any)
  - Tags
- Filters by platform (Linux/Windows)
- Highlight instances that can move to Graviton or newer generations

### 3. TA (Trusted Advisor) Page
**Should include:**
- Similar to Modernize but specifically for TA recommendations
- Summary of TA checks
- Table of recommendations
- Links to AWS documentation for each recommendation

## Next Steps

To implement these improvements, I need to know:

1. **Priority**: Which page should we improve first?
2. **Features**: Are the recommended improvements above what you're looking for?
3. **Design**: Should we match the legacy AdminLTE layout exactly, or can we improve the UX with Cloudscape components?

Please provide feedback on what you'd like to see on each page.
