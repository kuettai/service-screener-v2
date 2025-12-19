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
  
  // Sort findings by criticality
  const sortedFindings = useMemo(() => {
    const criticalityOrder = { 'H': 0, 'M': 1, 'L': 2, 'I': 3 };
    return [...findings].sort((a, b) => {
      const orderA = criticalityOrder[a.criticality] ?? 4;
      const orderB = criticalityOrder[b.criticality] ?? 4;
      return orderA - orderB;
    });
  }, [findings]);
  
  // Helper functions
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
      
      {/* Findings Section */}
      <Container
        header={
          <Header 
            variant="h2" 
            counter={`(${sortedFindings.length})`}
            description="Expand each finding to view detailed information"
          >
            Findings
          </Header>
        }
      >
        <SpaceBetween size="m">
          {sortedFindings.length === 0 ? (
            <Box textAlign="center" padding={{ vertical: 'l' }}>
              <Box variant="h3" color="text-status-inactive">No findings</Box>
              <Box variant="p" color="text-status-inactive">
                This service has no findings.
              </Box>
            </Box>
          ) : (
            sortedFindings.map(finding => {
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
            })
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
};

export default ServiceDetail;