# Implementation Plan

## Phase 1: Foundation and Parallel Output (Weeks 1-2)

- [x] 1. Set up React project structure
  - Create cloudscape-ui/ directory in service-screener-v2/
  - Initialize package.json with Cloudscape dependencies
  - Configure Vite with vite-plugin-singlefile
  - Set up TypeScript configuration
  - _Requirements: 1.5, 9.4_

- [x] 2. Implement core React components
- [x] 2.1 Create App component with routing
  - Implement HashRouter for file:// compatibility
  - Set up route definitions (Dashboard, ServiceDetail, FrameworkDetail)
  - Add data loading from window.__REPORT_DATA__
  - Implement loading and error states
  - _Requirements: 1.1, 7.3, 7.5_

- [x] 2.2 Create Dashboard component
  - Implement KPI cards (services, findings, priorities)
  - Create service cards grid
  - Add navigation to service details
  - Calculate and display statistics
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2.3 Create ServiceDetail component
  - Implement findings table with Cloudscape Table
  - Add filter functionality
  - Add sort functionality
  - Create expandable finding details
  - Display priority and category badges
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2.4 Create navigation components
  - Implement TopNavigation with account selector
  - Implement SideNavigation with services and frameworks
  - Add active state highlighting
  - Handle navigation events
  - _Requirements: 7.1, 7.2, 7.4_

- [x] 2.5 Create utility functions
  - Implement dataLoader.js for JSON loading
  - Create formatters for criticality, category labels
  - Add color mapping functions
  - Create constants file
  - _Requirements: 1.2, 2.1_

- [x] 3. Implement Python OutputGenerator class
- [x] 3.1 Create OutputGenerator class structure
  - Define __init__ with beta_mode parameter
  - Implement generate() method
  - Add _generate_legacy() method (calls existing PageBuilder)
  - Add _generate_cloudscape() method (only called if beta_mode=True)
  - _Requirements: 3.1, 3.2_

- [x] 3.2 Implement React build integration
  - Add _build_react_app() method with subprocess
  - Handle npm build execution
  - Capture build output and errors
  - Return success/failure status
  - _Requirements: 9.1, 9.2_

- [x] 3.3 Implement data embedding
  - Add _embed_data() method
  - Read api-full.json file
  - Inject JSON into HTML as window.__REPORT_DATA__
  - Properly escape special characters
  - Write modified HTML file
  - _Requirements: 9.5_

- [x] 3.4 Add error handling and fallback
  - Implement try-catch for build failures
  - Log errors to console and error.txt
  - Fall back to legacy HTML on failure
  - Add warning messages
  - _Requirements: 9.3, 13.2_

- [x] 4. Integrate OutputGenerator into Screener.py
  - Import OutputGenerator class
  - Replace PageBuilder calls with OutputGenerator
  - Pass beta flag value from Config to OutputGenerator
  - Maintain existing JSON generation
  - _Requirements: 2.1, 2.2, 2.3, 15.1_

- [x] 5. Test Phase 1 with real data
  - Run screener with --beta 1
  - Verify both outputs are generated
  - Test Cloudscape UI with file:// protocol
  - Verify all data displays correctly
  - Check bundle size < 5MB
  - _Requirements: 1.1, 1.5, 3.1, 10.1_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Framework Support and Advanced Features (Weeks 3-4)

- [x] 7. Implement Framework components
- [x] 7.1 Create FrameworkDetail component
  - Display framework metadata
  - Show compliance summary statistics
  - Render pie chart for compliance distribution
  - Render bar chart for category breakdown
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 7.2 Create framework compliance table
  - Implement table with required columns
  - Add filtering functionality
  - Add sorting functionality
  - Add CSV export button
  - Display compliance status badges
  - _Requirements: 6.4, 6.5_

- [x] 7.3 Add framework navigation
  - Add frameworks section to sidebar
  - Generate routes for each framework
  - Handle framework data loading
  - _Requirements: 6.1, 7.2_

- [x] 8. Implement suppression features
- [x] 8.1 Create SuppressionModal component
  - Display suppression indicator in TopNavigation
  - Implement modal with suppression details
  - Show service-level suppressions table
  - Show resource-specific suppressions table
  - Add summary statistics
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 8.2 Add conditional suppression rendering
  - Check for suppressions in data
  - Show/hide indicator based on suppressions
  - Handle modal open/close events
  - _Requirements: 8.5_

- [x] 9. Implement data visualization
- [x] 9.1 Add chart components
  - Integrate Cloudscape chart components
  - Create pie chart for dashboard
  - Create bar chart for frameworks
  - Add tooltips to charts
  - _Requirements: 12.1, 12.2, 12.3, 12.5_

- [x] 9.2 Add KPI cards to dashboard
  - Create reusable KPI card component
  - Display metrics with icons
  - Add color coding for priorities
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 10. Implement accessibility features
- [x] 10.1 Add keyboard navigation
  - Ensure all interactive elements are keyboard accessible
  - Add focus indicators
  - Implement keyboard shortcuts
  - Test tab order
  - _Requirements: 11.1_

- [x] 10.2 Add ARIA labels
  - Add aria-label to all interactive elements
  - Add aria-describedby for complex components
  - Add role attributes where needed
  - Test with screen reader
  - _Requirements: 11.2_

- [x] 10.3 Implement responsive design
  - Test layout at different viewport sizes
  - Add mobile-specific styles
  - Implement hamburger menu for mobile
  - Test on tablets and phones
  - _Requirements: 11.3, 11.4_

- [x] 11. Add error handling and empty states
- [x] 11.1 Create ErrorBoundary component
  - Catch React errors
  - Display user-friendly error message
  - Log errors to console
  - _Requirements: 13.1_

- [x] 11.2 Add empty state components
  - Create "No findings" message
  - Create "No data" message
  - Add helpful icons and text
  - _Requirements: 13.3_

- [x] 11.3 Add browser compatibility checks
  - Detect incompatible browsers
  - Display compatibility message
  - Add noscript tag for JavaScript disabled
  - _Requirements: 13.4, 13.5_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Testing and Documentation (Week 5)

- [ ] 13. Write unit tests for React components
- [ ] 13.1 Test Dashboard component
  - Test KPI calculations
  - Test service card rendering
  - Test navigation clicks
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 13.2 Test ServiceDetail component
  - Test findings table rendering
  - Test filter functionality
  - Test sort functionality
  - Test expandable sections
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 13.3 Test FrameworkDetail component
  - Test compliance table rendering
  - Test chart rendering
  - Test CSV export
  - _Requirements: 6.2, 6.3, 6.4, 6.5_

- [ ] 13.4 Test utility functions
  - Test data loading
  - Test formatters
  - Test color mappings
  - _Requirements: 1.2, 2.1_

- [ ] 14. Write integration tests
- [ ] 14.1 Test end-to-end user flows
  - Test dashboard to service detail navigation
  - Test filtering and sorting
  - Test framework navigation
  - Test suppression modal
  - _Requirements: 4.5, 5.4, 5.5, 8.2_

- [ ] 14.2 Test file:// protocol compatibility
  - Test in Chrome
  - Test in Firefox
  - Test in Safari
  - Test in Edge
  - _Requirements: 1.1, 1.4_

- [ ] 14.3 Test offline functionality
  - Verify no network requests
  - Test with network disabled
  - Verify all assets load
  - _Requirements: 1.2, 1.3_

- [ ] 15. Write Python integration tests
- [ ] 15.1 Test OutputGenerator
  - Test with --beta 0 (legacy only)
  - Test with --beta 1 (both UIs)
  - Test default behavior (legacy)
  - _Requirements: 3.1, 3.2_

- [ ] 15.2 Test build integration
  - Test successful build
  - Test build failure fallback
  - Test data embedding
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [ ] 15.3 Test backward compatibility
  - Verify JSON files unchanged
  - Verify Excel export works
  - Verify directory structure preserved
  - _Requirements: 15.1, 15.2, 15.4_

- [ ] 16. Performance testing
- [ ] 16.1 Test bundle size
  - Measure Cloudscape output size
  - Compare to AdminLTE size
  - Verify < 5MB
  - Verify 90% reduction
  - _Requirements: 10.1, 10.2_

- [ ] 16.2 Test load performance
  - Measure initial render time
  - Measure time to interactive
  - Verify < 2 seconds
  - Run Lighthouse audit
  - _Requirements: 10.3_

- [ ] 16.3 Test asset optimization
  - Verify CSS minification
  - Verify JS minification
  - Check for unused code
  - _Requirements: 10.5_

- [ ] 17. Accessibility testing
- [ ] 17.1 Run automated accessibility tests
  - Run axe-core tests
  - Run WAVE tests
  - Verify WCAG 2.1 Level AA compliance
  - _Requirements: 11.5_

- [ ] 17.2 Manual accessibility testing
  - Test keyboard navigation
  - Test with screen reader
  - Test color contrast
  - Test focus indicators
  - _Requirements: 11.1, 11.2_

- [x] 18. Create documentation
- [x] 18.1 Write README for Cloudscape UI
  - Explain new UI features
  - Document differences from AdminLTE
  - Add screenshots
  - _Requirements: 14.1, 14.4_

- [x] 18.2 Write MIGRATION_GUIDE
  - Step-by-step migration instructions
  - Document --beta flag usage
  - Explain transition period
  - Add troubleshooting section
  - _Requirements: 14.2, 14.3_

- [x] 18.3 Document file:// protocol limitations
  - Known browser issues
  - Workarounds
  - Alternative approaches
  - _Requirements: 14.5_

- [x] 18.4 Update main README
  - Add Cloudscape section
  - Update screenshots
  - Document new features
  - _Requirements: 14.1_

- [ ] 19. Checkpoint - Final validation
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Deployment and Cleanup (Weeks 6-7)

- [ ] 20. Deploy Phase 1 (Parallel Output)
  - Merge to main branch
  - Tag release as v2.1.0-beta
  - Update documentation
  - Announce to users (--beta 1 enables new UI)
  - _Requirements: 3.1_

- [ ] 21. Monitor and gather feedback
  - Monitor error logs
  - Track --beta flag usage
  - Collect user feedback
  - Fix critical bugs
  - _Requirements: 13.1, 13.2_

- [ ] 22. Deploy Phase 2 (Cloudscape as Default)
  - Change default to --beta 1 (both UIs)
  - Add deprecation notice for AdminLTE
  - Update documentation
  - Tag release as v2.2.0
  - _Requirements: 3.1_

- [ ] 23. Monitor adoption
  - Track Cloudscape vs AdminLTE usage
  - Monitor performance metrics
  - Collect user satisfaction scores
  - Address issues
  - _Requirements: 10.1, 10.2, 10.3_

- [ ] 24. Prepare for Phase 3 (AdminLTE removal)
  - Announce deprecation timeline
  - Give users 3 months notice
  - Provide migration support
  - Document breaking changes
  - _Requirements: 14.2_

- [ ] 25. Remove AdminLTE code (Phase 3)
- [ ] 25.1 Remove PageBuilder.py
  - Delete PageBuilder.py
  - Delete service-specific pageBuilders
  - Update imports in Screener.py
  - _Requirements: 15.1_

- [ ] 25.2 Remove templates
  - Delete templates/ directory
  - Remove template references
  - _Requirements: 15.1_

- [ ] 25.3 Remove AdminLTE assets
  - Delete adminlte/ directory
  - Update .gitignore
  - _Requirements: 10.2_

- [ ] 25.4 Update OutputGenerator
  - Remove _generate_legacy() method
  - Remove beta_mode parameter
  - Simplify generate() method
  - _Requirements: 15.1_

- [ ] 25.5 Update tests
  - Remove AdminLTE-related tests
  - Update integration tests
  - Verify all tests pass
  - _Requirements: 15.1_

- [ ] 26. Final documentation update
  - Remove AdminLTE references
  - Update all screenshots
  - Update migration guide
  - Tag release as v3.0.0
  - _Requirements: 14.1, 14.2_

- [ ] 27. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.
