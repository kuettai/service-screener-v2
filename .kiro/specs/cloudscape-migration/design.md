# Design Document

## Overview

This design document outlines the architecture for migrating Service Screener V2's UI from AdminLTE to AWS Cloudscape Design System. The migration will be implemented in phases to ensure backward compatibility and minimize risk. The new UI will be a single-page React application that works offline with the file:// protocol, while maintaining all existing functionality and data structures.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Backend                           │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  Scanner │───▶│ Reporter │───▶│  Output Generator    │  │
│  └──────────┘    └──────────┘    └──────────────────────┘  │
│                                            │                  │
│                                            ▼                  │
│                                   ┌────────────────┐         │
│                                   │  JSON Files    │         │
│                                   │  - api-full    │         │
│                                   │  - api-raw     │         │
│                                   └────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Build Process                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Vite Build   │───▶│ Single File  │───▶│ Embed Data   │  │
│  │ (React)      │    │ Plugin       │    │ (JSON)       │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Output (ZIP)                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  {accountId}/                                        │   │
│  │    ├── index.html (Cloudscape - single file)        │   │
│  │    ├── legacy/                                       │   │
│  │    │   ├── index.html (AdminLTE)                    │   │
│  │    │   ├── cloudfront.html                          │   │
│  │    │   └── ec2.html                                 │   │
│  │    ├── api-full.json                                │   │
│  │    ├── api-raw.json                                 │   │
│  │    └── workItem.xlsx                                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
React Application (Cloudscape)
├── App.jsx (Main container with routing)
│   ├── TopNavigation (Account selector, branding)
│   ├── SideNavigation (Services, Frameworks)
│   └── AppLayout (Main content area)
│       ├── Dashboard (Summary view)
│       ├── ServiceDetail (Findings per service)
│       ├── FrameworkDetail (Compliance view)
│       └── SuppressionModal (Suppression info)
│
├── Components
│   ├── FindingCard (Individual finding display)
│   ├── FindingTable (Filterable findings table)
│   ├── KPICard (Dashboard metrics)
│   ├── ComplianceChart (Pie/Bar charts)
│   └── ErrorBoundary (Error handling)
│
└── Utils
    ├── dataLoader.js (JSON loading)
    ├── formatters.js (Data formatting)
    └── constants.js (Shared constants)
```

## Components and Interfaces

### Python Backend Components

#### 1. OutputGenerator (New)

**Purpose:** Orchestrates the generation of both AdminLTE and Cloudscape outputs

**Interface:**
```python
class OutputGenerator:
    def __init__(self, beta_mode: bool = False):
        """
        Args:
            beta_mode: If True, generate both AdminLTE and Cloudscape
                      If False, generate only AdminLTE (legacy)
        """
        
    def generate(self, contexts: dict, regions: list, account_id: str) -> None:
        """Generate output based on beta_mode"""
        
    def _generate_legacy(self) -> None:
        """Generate AdminLTE HTML (existing PageBuilder)"""
        
    def _generate_cloudscape(self) -> None:
        """Build and embed React app"""
        
    def _build_react_app(self) -> bool:
        """Run npm build, return success status"""
        
    def _embed_data(self, html_path: str, json_path: str) -> None:
        """Embed JSON data into HTML file"""
```

#### 2. Reporter (Modified)

**Purpose:** Process scan results into structured data (no changes to output format)

**Interface:** (Unchanged)
```python
class Reporter:
    def process(self, serviceObjs: dict) -> Reporter:
        """Process scan results"""
        
    def getSummary(self) -> Reporter:
        """Generate summary data"""
        
    def getDetails(self) -> None:
        """Generate detailed findings"""
        
    def getCard(self) -> dict:
        """Get card summary for UI"""
        
    def getDetail(self) -> dict:
        """Get detailed findings"""
```

### React Frontend Components

#### 1. App Component

**Purpose:** Main application container with routing

**Props:**
```typescript
interface AppProps {
  // No props - loads data from window.__REPORT_DATA__
}
```

**State:**
```typescript
interface AppState {
  data: ReportData | null;
  loading: boolean;
  accountId: string;
}
```

#### 2. Dashboard Component

**Purpose:** Display summary of all services and findings

**Props:**
```typescript
interface DashboardProps {
  data: ReportData;
}
```

**Renders:**
- KPI cards (total services, findings, priorities)
- Service cards (findings per service)
- Navigation to service details

#### 3. ServiceDetail Component

**Purpose:** Display detailed findings for a specific service

**Props:**
```typescript
interface ServiceDetailProps {
  data: ReportData;
}
```

**Features:**
- Filterable findings table
- Expandable finding details
- Priority and category badges
- Resource lists by region

#### 4. FrameworkDetail Component

**Purpose:** Display compliance framework reports

**Props:**
```typescript
interface FrameworkDetailProps {
  data: FrameworkData;
}
```

**Features:**
- Compliance status summary
- Pie and bar charts
- Filterable compliance table
- Export to CSV

## Data Models

### ReportData (JSON Schema)

```typescript
interface ReportData {
  [serviceName: string]: {
    summary: {
      [ruleName: string]: Finding;
    };
    detail: {
      [region: string]: {
        [resourceId: string]: {
          [ruleName: string]: ResourceFinding;
        };
      };
    };
  };
}

interface Finding {
  "^description": string;
  shortDesc: string;
  criticality: "H" | "M" | "L" | "I";
  downtime: number;
  slowness: number;
  additionalCost: number;
  needFullTest: number;
  __categoryMain: "R" | "S" | "O" | "P" | "C";
  __categorySub?: string;
  __links: string[];
  __affectedResources: {
    [region: string]: string[];
  };
}

interface ResourceFinding {
  criticality: "H" | "M" | "L" | "I";
  shortDesc: string;
  __categoryMain: "R" | "S" | "O" | "P" | "C";
  value: string;
}
```

### FrameworkData (JSON Schema)

```typescript
interface FrameworkData {
  metadata: {
    fullname: string;
    shortname: string;
    description: string;
    _: string; // URL
  };
  summary: {
    mcn: [number, number, number]; // [Not Available, Compliant, Need Attention]
    stats: {
      [category: string]: [number, number, number];
    };
  };
  details: Array<[string, string, number, string, string]>;
  // [Category, Rule ID, Compliance Status, Description, Reference]
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: File Protocol Compatibility
*For any* generated report, when opened with file:// protocol, the application should load and display all content without external network requests
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Single File Output
*For any* Cloudscape build, the output should be exactly one HTML file with all CSS and JavaScript inlined
**Validates: Requirements 1.5**

### Property 3: JSON Schema Preservation
*For any* scan result, the generated api-full.json and api-raw.json should match the existing schema structure exactly
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 4: Reporter Output Consistency
*For any* scan input, the Reporter class should produce identical JSON output before and after migration
**Validates: Requirements 2.3, 2.5**

### Property 5: Parallel Output Generation
*For any* execution with --beta 1, the system should generate both AdminLTE HTML and Cloudscape React app
**Validates: Requirements 3.1**

### Property 6: Dashboard Aggregation Accuracy
*For any* report data, the dashboard should display correct counts for total services, total findings, and findings by priority
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 7: Service Card Completeness
*For any* service in the dashboard, the service card should contain service name, finding counts by priority, and affected categories
**Validates: Requirements 4.4**

### Property 8: Finding Display Completeness
*For any* finding in service detail view, the display should include priority badge, category badge, rule name, description, and affected resource count
**Validates: Requirements 5.2**

### Property 9: Finding Expansion Completeness
*For any* expanded finding, the display should include full description, recommendations with links, affected resources by region, and impact tags
**Validates: Requirements 5.3**

### Property 10: Filter Correctness
*For any* filter text, the filtered findings should match only those whose rule name or description contains the filter text (case-insensitive)
**Validates: Requirements 5.4**

### Property 11: Sort Correctness
*For any* sort column (priority, category, rule name), the sorted findings should be in correct ascending or descending order
**Validates: Requirements 5.5**

### Property 12: Framework Page Generation
*For any* enabled framework, the system should generate a framework-specific page with compliance data
**Validates: Requirements 6.1**

### Property 13: Compliance Status Display
*For any* framework control, the display should show one of three compliance statuses: Compliant, Need Attention, or Not Available
**Validates: Requirements 6.2**

### Property 14: Navigation Without Reload
*For any* navigation action, the system should update the URL and content without triggering a full page reload
**Validates: Requirements 7.3**

### Property 15: Active Navigation Highlighting
*For any* current page, the corresponding navigation item in the sidebar should have active styling
**Validates: Requirements 7.4**

### Property 16: Hash-Based Routing
*For any* navigation URL, when using file:// protocol, the URL should contain a hash fragment (#/)
**Validates: Requirements 7.5**

### Property 17: Suppression Indicator Visibility
*For any* report, the suppression indicator should be visible if and only if suppressions are active
**Validates: Requirements 8.1, 8.5**

### Property 18: Suppression Modal Content
*For any* active suppression, the modal should display service name, rule name, and either description (service-level) or affected resources (resource-specific)
**Validates: Requirements 8.3, 8.4**

### Property 19: Build Integration Success
*For any* successful Python execution, the React build should be automatically triggered and completed
**Validates: Requirements 9.1, 9.2**

### Property 20: Build Failure Fallback
*For any* React build failure, the system should log the error and generate AdminLTE HTML as fallback
**Validates: Requirements 9.3, 13.2**

### Property 21: Data Embedding
*For any* completed build, the HTML file should contain the api-full.json data embedded in a script tag
**Validates: Requirements 9.5**

### Property 22: Bundle Size Limit
*For any* Cloudscape build, the total file size should be less than 5MB
**Validates: Requirements 10.1**

### Property 23: Size Reduction
*For any* report, the Cloudscape output should be at least 90% smaller than the AdminLTE output
**Validates: Requirements 10.2**

### Property 24: Render Performance
*For any* report load, the initial page render should complete within 2 seconds on modern browsers
**Validates: Requirements 10.3**

### Property 25: Asset Minification
*For any* build output, all CSS and JavaScript assets should be minified
**Validates: Requirements 10.5**

### Property 26: Keyboard Accessibility
*For any* interactive element, it should be reachable and operable using only keyboard navigation
**Validates: Requirements 11.1**

### Property 27: ARIA Labels
*For any* UI component, appropriate ARIA labels should be present for screen reader compatibility
**Validates: Requirements 11.2**

### Property 28: Responsive Layout
*For any* viewport width, the layout should adapt appropriately without horizontal scrolling or content overflow
**Validates: Requirements 11.3**

### Property 29: Chart Rendering
*For any* framework page, pie charts and bar charts should be rendered with correct data
**Validates: Requirements 12.2, 12.3**

### Property 30: Chart Tooltips
*For any* chart element, hovering should display a tooltip with detailed information
**Validates: Requirements 12.5**

### Property 31: Error Message Display
*For any* data load failure, a user-friendly error message should be displayed
**Validates: Requirements 13.1**

### Property 32: File Path Preservation
*For any* output generation, JSON files should be created at the same paths with the same names as before
**Validates: Requirements 15.1**

### Property 33: Directory Structure Preservation
*For any* output generation, the directory structure should match the existing structure
**Validates: Requirements 15.4**

## Error Handling

### Build Errors

**Scenario:** React build fails due to npm/node issues

**Handling:**
1. Log error to console and error.txt file
2. Fall back to AdminLTE HTML generation
3. Continue with Excel export
4. Include warning in output about Cloudscape unavailability

**Code:**
```python
try:
    success = self._build_react_app()
    if not success:
        raise BuildError("React build failed")
    self._embed_data()
except BuildError as e:
    _warn(f"Cloudscape build failed: {e}. Falling back to legacy HTML.")
    self._generate_legacy()
```

### Data Loading Errors

**Scenario:** JSON data fails to load in browser

**Handling:**
1. Display error message with troubleshooting steps
2. Suggest checking browser console
3. Provide link to documentation

**Code:**
```jsx
if (!data) {
  return (
    <Alert type="error" header="Data Loading Failed">
      Unable to load report data. Please check:
      <ul>
        <li>File is not corrupted</li>
        <li>Browser console for errors</li>
        <li>File:// protocol is supported</li>
      </ul>
    </Alert>
  );
}
```

### Missing Service Data

**Scenario:** Service has no findings

**Handling:**
1. Display empty state message
2. Show service was scanned successfully
3. Indicate no issues found

**Code:**
```jsx
if (findings.length === 0) {
  return (
    <Box textAlign="center">
      <Icon name="status-positive" size="large" />
      <Box variant="h2">No findings</Box>
      <Box variant="p">
        This service was scanned successfully with no issues found.
      </Box>
    </Box>
  );
}
```

## Testing Strategy

### Unit Testing

**Framework:** Jest + React Testing Library

**Coverage:**
- Component rendering
- User interactions (clicks, filters, sorts)
- Data transformations
- Error boundaries

**Example Tests:**
```javascript
describe('Dashboard', () => {
  it('displays correct service count', () => {
    const data = mockReportData();
    render(<Dashboard data={data} />);
    expect(screen.getByText(/Total Services/)).toHaveTextContent('2');
  });
  
  it('navigates to service detail on card click', () => {
    const data = mockReportData();
    render(<Dashboard data={data} />);
    fireEvent.click(screen.getByText('CLOUDFRONT'));
    expect(window.location.hash).toBe('#/service/cloudfront');
  });
});
```

### Integration Testing

**Framework:** Playwright

**Coverage:**
- End-to-end user flows
- File:// protocol compatibility
- Cross-browser testing
- Offline functionality

**Example Tests:**
```javascript
test('complete user flow', async ({ page }) => {
  await page.goto('file:///path/to/dist/index.html');
  
  // Verify dashboard loads
  await expect(page.locator('h1')).toContainText('Service Screener Dashboard');
  
  // Navigate to service
  await page.click('text=CLOUDFRONT');
  await expect(page.locator('h1')).toContainText('CLOUDFRONT');
  
  // Filter findings
  await page.fill('[placeholder="Find findings"]', 'encryption');
  await expect(page.locator('table tbody tr')).toHaveCount(2);
});
```

### Python Integration Testing

**Framework:** pytest

**Coverage:**
- Output generation with different ui_mode flags
- Build process integration
- Data embedding
- Fallback behavior

**Example Tests:**
```python
def test_cloudscape_output_generation():
    """Test Cloudscape output is generated correctly"""
    generator = OutputGenerator(ui_mode='cloudscape')
    generator.generate(mock_contexts, ['us-east-1'], '123456789')
    
    assert os.path.exists('output/123456789/index.html')
    assert os.path.getsize('output/123456789/index.html') < 5 * 1024 * 1024
    
    with open('output/123456789/index.html') as f:
        content = f.read()
        assert 'window.__REPORT_DATA__' in content

def test_build_failure_fallback():
    """Test fallback to legacy HTML on build failure"""
    with patch('subprocess.run', side_effect=Exception('Build failed')):
        generator = OutputGenerator(ui_mode='cloudscape')
        generator.generate(mock_contexts, ['us-east-1'], '123456789')
        
        # Should fall back to legacy
        assert os.path.exists('output/123456789/legacy/index.html')
```

### Performance Testing

**Tools:** Lighthouse, WebPageTest

**Metrics:**
- Initial load time < 2s
- Time to Interactive < 3s
- Bundle size < 5MB
- Lighthouse score > 90

**Automated Checks:**
```javascript
test('performance metrics', async ({ page }) => {
  const metrics = await page.evaluate(() => {
    const paint = performance.getEntriesByType('paint');
    const fcp = paint.find(e => e.name === 'first-contentful-paint');
    return {
      fcp: fcp.startTime,
      domContentLoaded: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart
    };
  });
  
  expect(metrics.fcp).toBeLessThan(2000);
  expect(metrics.domContentLoaded).toBeLessThan(3000);
});
```

## Implementation Notes

### Build Process

1. **Vite Configuration:**
   - Use `vite-plugin-singlefile` for single HTML output
   - Configure base path as `./` for relative paths
   - Inline all assets using `assetsInlineLimit: 100000000`

2. **Data Embedding:**
   - Read api-full.json after build
   - Inject into HTML as `window.__REPORT_DATA__`
   - Escape special characters properly

3. **Python Integration:**
   - Add subprocess call to run `npm run build`
   - Copy dist/index.html to output directory
   - Handle build failures gracefully

### Routing Strategy

- Use `HashRouter` instead of `BrowserRouter`
- URLs will be: `file://path/index.html#/service/ec2`
- Hash routing works with file:// protocol
- No server-side routing needed

### State Management

- Use React hooks (useState, useEffect)
- No external state management library needed
- Data loaded once on mount from window.__REPORT_DATA__
- Navigation state managed by React Router

### Styling

- Use Cloudscape components exclusively
- Import `@cloudscape-design/global-styles`
- No custom CSS needed initially
- Cloudscape handles responsive design

## Deployment Strategy

### Phase 1: Parallel Output (Weeks 1-2)

**Goal:** Generate both UIs, validate Cloudscape

**Tasks:**
- Implement OutputGenerator class
- Add --ui-mode flag
- Build React app in Python workflow
- Test with real data
- Gather user feedback

**Success Criteria:**
- Both UIs generate successfully
- Cloudscape UI displays all data correctly
- File:// protocol works in all browsers
- Bundle size < 5MB

### Phase 2: Cloudscape as Default (Weeks 3-5)

**Goal:** Make Cloudscape the primary UI

**Tasks:**
- Change default ui_mode to 'cloudscape'
- Update documentation
- Add migration guide
- Deprecation notice for AdminLTE
- Monitor user feedback

**Success Criteria:**
- Users successfully adopt Cloudscape
- No critical bugs reported
- Performance metrics met
- Positive user feedback

### Phase 3: Remove AdminLTE (Weeks 6-7)

**Goal:** Clean up legacy code

**Tasks:**
- Remove PageBuilder.py
- Remove templates/
- Remove AdminLTE assets
- Update tests
- Final documentation

**Success Criteria:**
- Codebase simplified
- All tests passing
- Documentation complete
- No regressions

## Rollback Plan

If critical issues are discovered:

1. **Immediate:** Set default ui_mode to 'legacy'
2. **Short-term:** Fix issues in Cloudscape
3. **Long-term:** Re-enable Cloudscape after fixes

**Rollback Triggers:**
- Critical bugs affecting > 10% of users
- Performance degradation > 50%
- Data loss or corruption
- Security vulnerabilities

## Monitoring and Metrics

### Success Metrics

- **Adoption Rate:** % of users using Cloudscape vs AdminLTE
- **Bundle Size:** Cloudscape output size vs AdminLTE
- **Load Time:** Time to first contentful paint
- **Error Rate:** % of failed builds or loads
- **User Satisfaction:** Feedback scores

### Monitoring

- Log build success/failure rates
- Track ui_mode usage
- Monitor error.txt for issues
- Collect user feedback via GitHub issues

## Future Enhancements

### Post-Migration Improvements

1. **Dark Mode:** Add theme toggle
2. **Export Options:** PDF, CSV, JSON downloads
3. **Search:** Global search across all findings
4. **Filters:** Advanced filtering by multiple criteria
5. **Comparison:** Compare reports across time
6. **Annotations:** Add notes to findings
7. **Sharing:** Generate shareable links (with server)

### Technical Debt

- Remove PageBuilder.py completely
- Remove AdminLTE assets
- Simplify Python output generation
- Add more comprehensive tests
- Improve error messages
