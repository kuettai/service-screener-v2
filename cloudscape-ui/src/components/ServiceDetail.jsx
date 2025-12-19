import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Box from '@cloudscape-design/components/box';
import Badge from '@cloudscape-design/components/badge';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import Link from '@cloudscape-design/components/link';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import BarChart from '@cloudscape-design/components/bar-chart';
import PieChart from '@cloudscape-design/components/pie-chart';
import Select from '@cloudscape-design/components/select';
import TextFilter from '@cloudscape-design/components/text-filter';
import Grid from '@cloudscape-design/components/grid';
import Table from '@cloudscape-design/components/table';

import { 
  loadReportData,
  getServiceData, 
  getServiceFindings 
} from '../utils/dataLoader';
import { 
  formatServiceName,
  countAffectedResources,
  getImpactTags,
  parseLinks
} from '../utils/formatters';
import { renderHtml } from '../utils/htmlDecoder';

/**
 * ServiceDetail component - shows detailed findings for a specific service
 */
const ServiceDetail = () => {
  const { serviceName } = useParams();
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [severityFilter, setSeverityFilter] = useState({ label: 'All Severities', value: 'all' });
  const [categoryFilter, setCategoryFilter] = useState({ label: 'All Categories', value: 'all' });
  
  // Load report data
  useEffect(() => {
    const loadData = async () => {
      try {
        const data = await loadReportData();
        setReportData(data);
      } catch (error) {
        console.error('Failed to load report data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, []);
  
  // Get service data
  const serviceData = useMemo(() => {
    return reportData ? getServiceData(reportData, serviceName) : null;
  }, [reportData, serviceName]);
  
  const findings = useMemo(() => {
    return serviceData ? getServiceFindings(serviceData) : [];
  }, [serviceData]);
  
  // Helper functions (defined before useMemo hooks that use them)
  const getCriticalityIcon = (criticality) => {
    switch (criticality) {
      case 'H': return '🔴';
      case 'M': return '🟡';
      case 'L': return '🔵';
      case 'I': return '⚪';
      default: return '⚫';
    }
  };
  
  const getCategoryStyle = (category) => {
    const styles = {
      'S': { backgroundColor: '#d13212', color: 'white', label: 'Security' },
      'R': { backgroundColor: '#f012be', color: 'white', label: 'Reliability' },
      'C': { backgroundColor: '#0073bb', color: 'white', label: 'Cost Ops' },
      'P': { backgroundColor: '#1d8102', color: 'white', label: 'Performance' },
      'O': { backgroundColor: '#ff851b', color: 'white', label: 'Ops Excellence' }
    };
    return styles[category] || { backgroundColor: '#545b64', color: 'white', label: category };
  };
  
  // Calculate metrics
  const metrics = useMemo(() => {
    if (!serviceData) return null;
    
    const stats = serviceData.stats || {};
    const totalFindings = findings.length;
    const uniqueRules = new Set(findings.map(f => f.ruleName)).size;
    
    const formatTime = (seconds) => {
      if (!seconds || seconds === 0) return '0.00s';
      return `${parseFloat(seconds).toFixed(2)}s`;
    };
    
    return {
      resources: stats.resources || 0,
      totalFindings,
      rulesExecuted: stats.rules || 0,
      uniqueRules,
      suppressed: stats.suppressed || 0,
      timespent: formatTime(stats.timespent)
    };
  }, [serviceData, findings]);
  
  // Filter and sort findings
  const filteredFindings = useMemo(() => {
    let filtered = [...findings];
    
    // Apply search filter
    if (searchText) {
      const search = searchText.toLowerCase();
      filtered = filtered.filter(finding => 
        finding.ruleName?.toLowerCase().includes(search) ||
        finding.shortDesc?.toLowerCase().includes(search) ||
        finding['^description']?.toLowerCase().includes(search)
      );
    }
    
    // Apply severity filter
    if (severityFilter.value !== 'all') {
      filtered = filtered.filter(finding => finding.criticality === severityFilter.value);
    }
    
    // Apply category filter
    if (categoryFilter.value !== 'all') {
      filtered = filtered.filter(finding => finding.__categoryMain === categoryFilter.value);
    }
    
    return filtered;
  }, [findings, searchText, severityFilter, categoryFilter]);
  
  const sortedFindings = useMemo(() => {
    const criticalityOrder = { 'H': 0, 'M': 1, 'L': 2, 'I': 3 };
    return [...filteredFindings].sort((a, b) => {
      const orderA = criticalityOrder[a.criticality] ?? 4;
      const orderB = criticalityOrder[b.criticality] ?? 4;
      return orderA - orderB;
    });
  }, [filteredFindings]);
  
  // Chart data
  const chartData = useMemo(() => {
    if (!findings.length) return { severityChart: [], categoryChart: [] };
    
    // Group findings by region and severity for stacked bar chart
    const regionSeverityData = {};
    const categoryCounts = {};
    
    findings.forEach(finding => {
      // Extract regions from affected resources
      const affectedResources = finding.__affectedResources || {};
      const regions = Object.keys(affectedResources);
      
      // If no regions in affected resources, try to get from finding data
      if (regions.length === 0) {
        // Fallback: use a default region or extract from other fields
        regions.push('Global');
      }
      
      regions.forEach(region => {
        if (!regionSeverityData[region]) {
          regionSeverityData[region] = { 'H': 0, 'M': 0, 'L': 0, 'I': 0 };
        }
        
        // Count by severity for this region
        if (regionSeverityData[region].hasOwnProperty(finding.criticality)) {
          regionSeverityData[region][finding.criticality]++;
        }
      });
      
      // Count by category for pie chart
      const category = finding.__categoryMain;
      if (category) {
        categoryCounts[category] = (categoryCounts[category] || 0) + 1;
      }
    });
    
    // Create stacked bar chart data
    const regions = Object.keys(regionSeverityData).sort();
    const severityChart = regions.map(region => ({
      x: region,
      y: regionSeverityData[region]['H'] + regionSeverityData[region]['M'] + 
          regionSeverityData[region]['L'] + regionSeverityData[region]['I']
    }));
    
    // Create series data for stacked bars
    const stackedSeries = [
      {
        title: 'High',
        type: 'bar',
        data: regions.map(region => ({ x: region, y: regionSeverityData[region]['H'] })),
        color: '#d13212'
      },
      {
        title: 'Medium', 
        type: 'bar',
        data: regions.map(region => ({ x: region, y: regionSeverityData[region]['M'] })),
        color: '#ff9900'
      },
      {
        title: 'Low',
        type: 'bar', 
        data: regions.map(region => ({ x: region, y: regionSeverityData[region]['L'] })),
        color: '#0073bb'
      },
      {
        title: 'Info',
        type: 'bar',
        data: regions.map(region => ({ x: region, y: regionSeverityData[region]['I'] })),
        color: '#545b64'
      }
    ].filter(series => series.data.some(item => item.y > 0));
    
    const categoryChart = Object.entries(categoryCounts).map(([category, count]) => {
      const style = getCategoryStyle(category);
      return {
        title: style.label,
        value: count,
        color: style.backgroundColor
      };
    });
    
    // Calculate affected resources by severity
    const severityResources = { 'H': 0, 'M': 0, 'L': 0, 'I': 0 };
    findings.forEach(finding => {
      const severity = finding.criticality;
      if (severityResources.hasOwnProperty(severity)) {
        const resourceCount = countAffectedResources(finding.__affectedResources || {});
        severityResources[severity] += resourceCount;
      }
    });
    
    // Severity distribution table data
    const totalFindings = findings.length;
    const severityData = [
      {
        severity: 'High',
        icon: '🔴',
        count: Object.values(regionSeverityData).reduce((sum, region) => sum + region.H, 0),
        resources: severityResources.H,
        color: 'text-status-error',
        barColor: '#d13212'
      },
      {
        severity: 'Medium',
        icon: '🟡',
        count: Object.values(regionSeverityData).reduce((sum, region) => sum + region.M, 0),
        resources: severityResources.M,
        color: 'text-status-warning',
        barColor: '#ff9900'
      },
      {
        severity: 'Low',
        icon: '🔵',
        count: Object.values(regionSeverityData).reduce((sum, region) => sum + region.L, 0),
        resources: severityResources.L,
        color: 'text-status-info',
        barColor: '#0073bb'
      },
      {
        severity: 'Info',
        icon: '⚪',
        count: Object.values(regionSeverityData).reduce((sum, region) => sum + region.I, 0),
        resources: severityResources.I,
        color: 'text-status-inactive',
        barColor: '#545b64'
      }
    ].map(item => ({
      ...item,
      percentage: totalFindings > 0 ? ((item.count / totalFindings) * 100).toFixed(1) : '0.0'
    })).filter(item => item.count > 0); // Only show severities that have findings
    
    return { 
      severityChart, 
      categoryChart, 
      stackedSeries,
      regions,
      severityTable: severityData
    };
  }, [findings]);
  

  
  // Filter options
  const severityOptions = [
    { label: 'All Severities', value: 'all' },
    { label: 'High', value: 'H' },
    { label: 'Medium', value: 'M' },
    { label: 'Low', value: 'L' },
    { label: 'Informational', value: 'I' }
  ];
  
  const categoryOptions = useMemo(() => {
    const categories = new Set(findings.map(f => f.__categoryMain).filter(Boolean));
    const options = [{ label: 'All Categories', value: 'all' }];
    
    categories.forEach(category => {
      const style = getCategoryStyle(category);
      options.push({ label: style.label, value: category });
    });
    
    return options;
  }, [findings]);
  
  // Loading state
  if (loading) {
    return (
      <Box textAlign="center" padding={{ vertical: 'xxl' }}>
        <Box variant="h2" color="text-status-inactive">Loading...</Box>
        <Box variant="p" color="text-status-inactive">
          Loading service data for {formatServiceName(serviceName)}...
        </Box>
      </Box>
    );
  }
  
  // Service not found
  if (!serviceData) {
    return (
      <Box textAlign="center" padding={{ vertical: 'xxl' }}>
        <Box variant="h2" color="text-status-inactive">Service not found</Box>
        <Box variant="p" color="text-status-inactive">
          The service "{serviceName}" was not found in the report data.
        </Box>
      </Box>
    );
  }
  
  return (
    <SpaceBetween size="l">
      {/* Page Header */}
      <Header 
        variant="h1"
        description={`Detailed findings for ${formatServiceName(serviceName)}`}
      >
        {formatServiceName(serviceName)}
      </Header>
      
      {/* Stats Section */}
      <Container
        header={
          <Header variant="h2" description="Key metrics and statistics for this service">
            Stats
          </Header>
        }
      >
        <ColumnLayout columns={6} variant="default" minColumnWidth={120}>
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Resources</Box>
              <Box fontSize="display-l" fontWeight="bold" color="text-status-info">
                {metrics.resources}
              </Box>
            </SpaceBetween>
          </Box>
          
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Total Findings</Box>
              <Box fontSize="display-l" fontWeight="bold" color="text-status-warning">
                {metrics.totalFindings}
              </Box>
            </SpaceBetween>
          </Box>
          
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Rules Executed</Box>
              <Box fontSize="display-l" fontWeight="bold" color="text-status-success">
                {metrics.rulesExecuted}
              </Box>
            </SpaceBetween>
          </Box>
          
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Unique Rules</Box>
              <Box fontSize="display-l" fontWeight="bold" color="text-status-info">
                {metrics.uniqueRules}
              </Box>
            </SpaceBetween>
          </Box>
          
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Suppressed</Box>
              <Box fontSize="display-l" fontWeight="bold" color="text-status-inactive">
                {metrics.suppressed}
              </Box>
            </SpaceBetween>
          </Box>
          
          <Box padding="l" backgroundColor="background-container-content" borderRadius="s">
            <SpaceBetween size="xs">
              <Box variant="awsui-key-label">Time Spent</Box>
              <Box fontSize="display-l" fontWeight="bold">
                {metrics.timespent}
              </Box>
            </SpaceBetween>
          </Box>
        </ColumnLayout>
      </Container>
      
      {/* Charts Section - Expandable */}
      {findings.length > 0 && (
        <ExpandableSection
          headerText="Charts"
          variant="container"
          defaultExpanded={false}
          headerDescription="Visual breakdown of findings by severity and category"
        >
          <SpaceBetween size="l">
            {/* Full-width stacked bar chart for regions */}
            <div>
              <Box variant="h3" padding={{ bottom: 's' }}>Findings by Region and Severity</Box>
              <BarChart
                series={chartData.stackedSeries}
                xDomain={chartData.regions}
                yDomain={[0, Math.max(...chartData.severityChart.map(item => item.y), 1)]}
                xTitle="Region"
                yTitle="Count"
                height={400}
                stackedBars
                hideFilter
                legendTitle="Severity"
              />
            </div>
            
            {/* Second row: Pie chart + Top Rules */}
            <Grid
              gridDefinition={[
                { colspan: { default: 12, xs: 6 } },
                { colspan: { default: 12, xs: 6 } }
              ]}
            >
              <div>
                <Box variant="h3" padding={{ bottom: 's' }}>Findings by Category</Box>
                <PieChart
                  data={chartData.categoryChart}
                  detailPopoverContent={(datum) => [
                    { key: 'Category', value: datum.title },
                    { key: 'Findings', value: datum.value },
                    { key: 'Percentage', value: `${((datum.value / findings.length) * 100).toFixed(1)}%` }
                  ]}
                  segmentDescription={(datum) => `${datum.title}: ${datum.value} findings (${((datum.value / findings.length) * 100).toFixed(1)}%)`}
                  height={300}
                  hideFilter
                  hideLegend
                />
              </div>
              
              <div>
                <Box variant="h3" padding={{ bottom: 's' }}>Severity Distribution</Box>
                <Table
                  columnDefinitions={[
                    {
                      id: 'severity',
                      header: 'Severity',
                      cell: item => (
                        <SpaceBetween size="xs" direction="horizontal" alignItems="center">
                          <span style={{ fontSize: '16px' }}>{item.icon}</span>
                          <span style={{ fontWeight: '500' }}>{item.severity}</span>
                        </SpaceBetween>
                      ),
                      width: 120
                    },
                    {
                      id: 'count',
                      header: 'Findings',
                      cell: item => (
                        <Box fontSize="heading-s" fontWeight="bold" color={item.color}>
                          {item.count}
                        </Box>
                      ),
                      width: 70
                    },
                    {
                      id: 'resources',
                      header: 'Resources',
                      cell: item => (
                        <Box fontSize="body-m" color="text-body-secondary">
                          {item.resources}
                        </Box>
                      ),
                      width: 80
                    },
                    {
                      id: 'percentage',
                      header: '%',
                      cell: item => (
                        <Box fontSize="body-m">
                          {item.percentage}%
                        </Box>
                      ),
                      width: 60
                    },
                    {
                      id: 'bar',
                      header: 'Distribution',
                      cell: item => (
                        <div style={{ width: '100%', backgroundColor: '#f2f3f3', borderRadius: '4px', height: '8px', position: 'relative' }}>
                          <div
                            style={{
                              width: `${item.percentage}%`,
                              backgroundColor: item.barColor,
                              height: '100%',
                              borderRadius: '4px',
                              transition: 'width 0.3s ease'
                            }}
                          />
                        </div>
                      )
                    }
                  ]}
                  items={chartData.severityTable}
                  variant="borderless"
                  wrapLines
                />
              </div>
            </Grid>
          </SpaceBetween>
        </ExpandableSection>
      )}
      
      {/* Findings Section */}
      <Container
        header={
          <Header 
            variant="h2" 
            counter={`(${sortedFindings.length})`}
            description="Filter and expand findings to view detailed information"
          >
            Findings
          </Header>
        }
      >
        {/* Filters */}
        <SpaceBetween size="m">
          <Grid
            gridDefinition={[
              { colspan: { default: 12, xs: 6 } },
              { colspan: { default: 12, xs: 3 } },
              { colspan: { default: 12, xs: 3 } }
            ]}
          >
            <TextFilter
              filteringText={searchText}
              filteringPlaceholder="Search findings..."
              filteringAriaLabel="Filter findings"
              onChange={({ detail }) => setSearchText(detail.filteringText)}
            />
            
            <Select
              selectedOption={severityFilter}
              onChange={({ detail }) => setSeverityFilter(detail.selectedOption)}
              options={severityOptions}
              placeholder="Filter by severity"
            />
            
            <Select
              selectedOption={categoryFilter}
              onChange={({ detail }) => setCategoryFilter(detail.selectedOption)}
              options={categoryOptions}
              placeholder="Filter by category"
            />
          </Grid>
          
          {/* Findings List */}
          {sortedFindings.length === 0 ? (
            <Box textAlign="center" padding={{ vertical: 'l' }}>
              <Box variant="h3" color="text-status-inactive">No findings</Box>
              <Box variant="p" color="text-status-inactive">
                {searchText || severityFilter.value !== 'all' || categoryFilter.value !== 'all' 
                  ? 'No findings match your filter criteria.' 
                  : 'This service has no findings.'}
              </Box>
            </Box>
          ) : (
            <SpaceBetween size="m">
              {sortedFindings.map(finding => {
              const categoryStyle = getCategoryStyle(finding.__categoryMain);
              
              return (
                <ExpandableSection
                  key={finding.ruleName}
                  headerText={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '20px' }}>
                        {getCriticalityIcon(finding.criticality)}
                      </span>
                      <span style={{
                        backgroundColor: categoryStyle.backgroundColor,
                        color: categoryStyle.color,
                        padding: '4px 12px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '500'
                      }}>
                        {categoryStyle.label}
                      </span>
                      <span style={{ fontWeight: '500' }}>
                        {finding.ruleName}
                      </span>
                    </div>
                  }
                  variant="container"
                >
                  <SpaceBetween size="m">
                    <div>
                      <Box variant="awsui-key-label">Description</Box>
                      <Box variant="p">
                        <div dangerouslySetInnerHTML={renderHtml(finding['^description'] || finding.shortDesc)} />
                      </Box>
                    </div>
                    
                    {finding.__affectedResources && Object.keys(finding.__affectedResources).length > 0 && (
                      <div>
                        <Box variant="awsui-key-label">
                          Affected Resources ({countAffectedResources(finding.__affectedResources)})
                        </Box>
                        <SpaceBetween size="xs">
                          {Object.entries(finding.__affectedResources).map(([region, resources]) => (
                            <div key={region}>
                              <Box variant="small" fontWeight="bold">{region}</Box>
                              <Box variant="small" color="text-body-secondary">
                                {Array.isArray(resources) ? resources.join(', ') : resources}
                              </Box>
                            </div>
                          ))}
                        </SpaceBetween>
                      </div>
                    )}
                    
                    {finding.__links && finding.__links.length > 0 && (
                      <div>
                        <Box variant="awsui-key-label">Documentation</Box>
                        <SpaceBetween size="xs">
                          {finding.__links.map((link, index) => (
                            <Link key={index} href={link} external>
                              Reference {index + 1}
                            </Link>
                          ))}
                        </SpaceBetween>
                      </div>
                    )}
                  </SpaceBetween>
                </ExpandableSection>
              );
              })}
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
};

export default ServiceDetail;