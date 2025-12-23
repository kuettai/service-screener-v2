// Fixed ServiceDetail component structure

// Summary Section (2 columns)
<Container
  header={
    <Header variant="h2" description="Key metrics and statistics for this service">
      Summary
    </Header>
  }
>
  <ColumnLayout columns={2} variant="default">
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
      {/* First 3 metrics */}
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Resources</Box>
          <Box fontSize="display-l" fontWeight="bold" color="text-status-info">{metrics.resources}</Box>
        </SpaceBetween>
      </div>
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Total Findings</Box>
          <Box fontSize="display-l" fontWeight="bold" color="text-status-warning">{metrics.totalFindings}</Box>
        </SpaceBetween>
      </div>
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Rules Executed</Box>
          <Box fontSize="display-l" fontWeight="bold" color="text-status-success">{metrics.rulesExecuted}</Box>
        </SpaceBetween>
      </div>
    </div>
    
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
      {/* Last 3 metrics */}
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Unique Rules</Box>
          <Box fontSize="display-l" fontWeight="bold" color="text-status-info">{metrics.uniqueRules}</Box>
        </SpaceBetween>
      </div>
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Suppressed</Box>
          <Box fontSize="display-l" fontWeight="bold" color="text-status-inactive">{metrics.suppressed}</Box>
        </SpaceBetween>
      </div>
      <div style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e9ebed' }}>
        <SpaceBetween size="xs">
          <Box variant="awsui-key-label">Time Spent</Box>
          <Box fontSize="display-l" fontWeight="bold">{metrics.timespent}</Box>
        </SpaceBetween>
      </div>
    </div>
  </ColumnLayout>
</Container>

// Findings Section (expandable details only)
<Container
  header={
    <Header 
      variant="h2" 
      counter={`(${sortedFindings.length})`}
      description="Expand each finding to view detailed information and remediation guidance"
    >
      Findings
    </Header>
  }
>
  <SpaceBetween size="m">
    {sortedFindings.map(finding => (
      <ExpandableSection
        key={finding.ruleName}
        headerText={
          <SpaceBetween size="s" direction="horizontal">
            <span style={{ fontSize: '20px' }}>{getCriticalityIcon(finding.criticality)}</span>
            <span style={{ backgroundColor: categoryStyle.backgroundColor, color: categoryStyle.color, padding: '4px 12px', borderRadius: '4px', fontSize: '12px', fontWeight: '500', display: 'inline-block' }}>
              {categoryStyle.label}
            </span>
            <span>{finding.ruleName}</span>
          </SpaceBetween>
        }
        variant="container"
      >
        <FindingDetails finding={finding} />
      </ExpandableSection>
    ))}
  </SpaceBetween>
</Container>