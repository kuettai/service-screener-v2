# Requirements Document

## Introduction

This document outlines the requirements for migrating the Service Screener V2 UI from AdminLTE (jQuery/Bootstrap) to AWS Cloudscape Design System (React). The migration aims to modernize the user interface, reduce bundle size, improve maintainability, and provide a better user experience while maintaining backward compatibility during the transition.

## Glossary

- **Service Screener**: An AWS environment assessment tool that generates reports on security, reliability, operational excellence, performance, and cost optimization
- **AdminLTE**: The current UI framework based on jQuery and Bootstrap 3
- **Cloudscape**: AWS's open-source design system built on React
- **PageBuilder**: Python class responsible for generating HTML pages from scan data
- **Reporter**: Python class that processes scan results into structured data
- **Single-File Build**: A build process that inlines all CSS and JavaScript into a single HTML file
- **Hash Router**: React Router mode that uses URL hash (#) for navigation, compatible with file:// protocol
- **api-full.json**: JSON file containing all processed findings and details
- **Framework Pages**: Compliance framework reports (CIS, NIST, SOC2, etc.)

## Requirements

### Requirement 1: Maintain Offline Functionality

**User Story:** As a security auditor, I want to view the Service Screener report offline without requiring a web server, so that I can review findings in secure, air-gapped environments.

#### Acceptance Criteria

1. WHEN the user opens the generated HTML file using file:// protocol, THEN the system SHALL display the complete report with all functionality
2. WHEN the report is opened offline, THEN the system SHALL load all assets (CSS, JavaScript, data) without external network requests
3. WHEN the user navigates between pages in the report, THEN the system SHALL maintain functionality without requiring a server
4. WHEN the report is opened in Chrome, Firefox, Safari, or Edge, THEN the system SHALL render correctly in all browsers
5. THE system SHALL generate a single HTML file with all assets inlined to ensure file:// protocol compatibility

### Requirement 2: Preserve Existing Data Structure

**User Story:** As a developer maintaining Service Screener, I want the JSON data structure to remain unchanged, so that existing integrations and workflows continue to work.

#### Acceptance Criteria

1. THE system SHALL continue generating api-full.json with the existing schema structure
2. THE system SHALL continue generating api-raw.json with the existing schema structure
3. WHEN the Python backend processes scan results, THEN the Reporter class SHALL produce identical JSON output as before
4. THE system SHALL maintain backward compatibility with existing JSON consumers
5. WHEN generating Excel exports, THEN the system SHALL use the same data structures as the current implementation

### Requirement 3: Implement Parallel Output Mode

**User Story:** As a Service Screener user, I want both the old HTML and new React UI available during the transition, so that I can validate the new UI before fully migrating.

#### Acceptance Criteria

1. WHEN the --beta flag is set to 1, THEN the system SHALL create both AdminLTE HTML pages and Cloudscape React app
2. WHEN the --beta flag is not set or set to 0, THEN the system SHALL generate only AdminLTE HTML (legacy mode)
3. WHEN the Cloudscape build is successful with --beta 1, THEN both UIs SHALL be available in the output
4. WHEN the Cloudscape build fails with --beta 1, THEN the system SHALL fall back to AdminLTE HTML only
5. THE system SHALL default to legacy mode (--beta 0) during the transition period for backward compatibility

### Requirement 4: Dashboard Summary View

**User Story:** As a security manager, I want to see a high-level dashboard of all findings across services, so that I can quickly understand the overall security posture.

#### Acceptance Criteria

1. WHEN the user opens the report, THEN the system SHALL display a dashboard with total services scanned
2. WHEN the dashboard loads, THEN the system SHALL show total findings count across all services
3. WHEN the dashboard loads, THEN the system SHALL display high, medium, and low priority finding counts
4. WHEN the dashboard displays service cards, THEN each card SHALL show the service name, finding counts by priority, and affected categories
5. WHEN the user clicks on a service card, THEN the system SHALL navigate to the detailed service view

### Requirement 5: Service Detail View

**User Story:** As a cloud engineer, I want to view detailed findings for each AWS service, so that I can understand and remediate specific issues.

#### Acceptance Criteria

1. WHEN the user navigates to a service detail page, THEN the system SHALL display all findings for that service
2. WHEN findings are displayed, THEN each finding SHALL show priority badge, category badge, rule name, description, and affected resource count
3. WHEN the user expands a finding, THEN the system SHALL display full description, recommendations with links, affected resources by region, and impact tags
4. WHEN the user types in the filter box, THEN the system SHALL filter findings by rule name or description in real-time
5. WHEN findings are displayed, THEN the system SHALL support sorting by priority, category, or rule name

### Requirement 6: Framework Compliance View

**User Story:** As a compliance officer, I want to view framework-specific compliance reports (CIS, NIST, etc.), so that I can assess adherence to regulatory standards.

#### Acceptance Criteria

1. WHEN framework scanning is enabled, THEN the system SHALL generate framework-specific pages for each selected framework
2. WHEN the user views a framework page, THEN the system SHALL display compliance status (Compliant, Need Attention, Not Available) for each control
3. WHEN the framework page loads, THEN the system SHALL show summary statistics with pie chart and bar chart visualizations
4. WHEN the user views framework details, THEN the system SHALL display a table with Category, Rule ID, Compliance Status, Description, and Reference columns
5. WHEN the user interacts with the framework table, THEN the system SHALL support filtering, sorting, and exporting to CSV

### Requirement 7: Navigation and Routing

**User Story:** As a report viewer, I want intuitive navigation between different sections of the report, so that I can efficiently review findings.

#### Acceptance Criteria

1. WHEN the report loads, THEN the system SHALL display a top navigation bar with Service Screener branding and account selector
2. WHEN the report loads, THEN the system SHALL display a left sidebar with Dashboard link, Services section, and Frameworks section
3. WHEN the user clicks a navigation item, THEN the system SHALL navigate to the corresponding page without page reload
4. WHEN the user navigates to a page, THEN the system SHALL highlight the active navigation item in the sidebar
5. WHEN using file:// protocol, THEN the system SHALL use hash-based routing (#/) to ensure navigation works correctly

### Requirement 8: Suppression Indicator

**User Story:** As a security analyst, I want to see when findings are suppressed, so that I understand which checks were intentionally excluded.

#### Acceptance Criteria

1. WHEN suppressions are active, THEN the system SHALL display a "Suppression Active" indicator in the top navigation
2. WHEN the user clicks the suppression indicator, THEN the system SHALL display a modal showing all active suppressions
3. WHEN the suppression modal is displayed, THEN the system SHALL show service-level suppressions with service name, rule name, and description
4. WHEN the suppression modal is displayed, THEN the system SHALL show resource-specific suppressions with service name, rule name, and affected resources
5. WHEN no suppressions are active, THEN the system SHALL not display the suppression indicator

### Requirement 9: Build and Integration

**User Story:** As a Service Screener maintainer, I want the React build process integrated into the Python workflow, so that users receive a complete output without manual steps.

#### Acceptance Criteria

1. WHEN the Python script generates output, THEN the system SHALL automatically build the React application
2. WHEN the React build completes, THEN the system SHALL copy the built files to the output directory
3. WHEN the build process fails, THEN the system SHALL log the error and continue with legacy HTML generation
4. THE system SHALL use vite-plugin-singlefile to generate a single HTML file with inlined assets
5. WHEN the build completes, THEN the system SHALL embed the api-full.json data into the HTML file for offline access

### Requirement 10: Performance and Size Optimization

**User Story:** As a user downloading the report, I want a smaller file size, so that downloads are faster and storage requirements are reduced.

#### Acceptance Criteria

1. WHEN the system generates the Cloudscape output, THEN the total bundle size SHALL be less than 5MB
2. WHEN compared to AdminLTE output, THEN the Cloudscape output SHALL be at least 90% smaller
3. WHEN the report loads, THEN the initial page render SHALL occur within 2 seconds on modern browsers
4. THE system SHALL use code splitting and lazy loading where appropriate to minimize initial bundle size
5. THE system SHALL minify and compress all assets during the build process

### Requirement 11: Accessibility and Responsive Design

**User Story:** As a user with accessibility needs, I want the report to be accessible and work on different screen sizes, so that I can review findings regardless of my device or abilities.

#### Acceptance Criteria

1. WHEN the report is viewed, THEN all interactive elements SHALL be keyboard accessible
2. WHEN using a screen reader, THEN all content SHALL be properly announced with appropriate ARIA labels
3. WHEN the report is viewed on mobile devices, THEN the layout SHALL adapt to smaller screen sizes
4. WHEN the report is viewed on tablets, THEN the navigation SHALL collapse to a hamburger menu
5. THE system SHALL meet WCAG 2.1 Level AA accessibility standards

### Requirement 12: Data Visualization

**User Story:** As a report viewer, I want visual representations of findings data, so that I can quickly understand trends and distributions.

#### Acceptance Criteria

1. WHEN the dashboard loads, THEN the system SHALL display KPI cards with key metrics
2. WHEN framework pages load, THEN the system SHALL display pie charts showing compliance status distribution
3. WHEN framework pages load, THEN the system SHALL display bar charts showing compliance breakdown by category
4. WHEN charts are displayed, THEN the system SHALL use Cloudscape's chart components for consistency
5. WHEN the user hovers over chart elements, THEN the system SHALL display tooltips with detailed information

### Requirement 13: Error Handling and Fallbacks

**User Story:** As a user, I want clear error messages when something goes wrong, so that I can understand and resolve issues.

#### Acceptance Criteria

1. WHEN the data fails to load, THEN the system SHALL display a user-friendly error message
2. WHEN the React build fails, THEN the system SHALL fall back to generating AdminLTE HTML
3. WHEN a service has no findings, THEN the system SHALL display an appropriate "No findings" message
4. WHEN the browser is incompatible, THEN the system SHALL display a message suggesting supported browsers
5. WHEN JavaScript is disabled, THEN the system SHALL display a message indicating JavaScript is required

### Requirement 14: Documentation and Migration Guide

**User Story:** As a Service Screener user, I want clear documentation on the new UI, so that I can understand the changes and migrate smoothly.

#### Acceptance Criteria

1. THE system SHALL include a README.md file explaining the new Cloudscape UI
2. THE system SHALL include a MIGRATION_GUIDE.md file with step-by-step migration instructions
3. THE system SHALL document how to use the --beta flag to enable the new Cloudscape UI
4. THE system SHALL include screenshots comparing old and new UI
5. THE system SHALL document known limitations and workarounds for file:// protocol

### Requirement 15: Backward Compatibility

**User Story:** As a Service Screener user with existing workflows, I want the new UI to not break my current processes, so that I can adopt it at my own pace.

#### Acceptance Criteria

1. WHEN the system generates output, THEN the JSON files SHALL remain in the same location with the same names
2. WHEN the system generates output, THEN the Excel export SHALL continue to work as before
3. WHEN users have custom scripts parsing output, THEN those scripts SHALL continue to work without modification
4. THE system SHALL maintain the same output directory structure during the transition period
5. WHEN the --beta flag is not specified, THEN the system SHALL default to legacy mode (AdminLTE only) for backward compatibility
