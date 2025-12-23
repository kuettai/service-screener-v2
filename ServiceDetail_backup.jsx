import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Table from '@cloudscape-design/components/table';
import Box from '@cloudscape-design/components/box';
import Badge from '@cloudscape-design/components/badge';
import TextFilter from '@cloudscape-design/components/text-filter';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import Link from '@cloudscape-design/components/link';
import ColumnLayout from '@cloudscape-design/components/column-layout';

import { 
  getServiceData, 
  getServiceFindings 
} from '../utils/dataLoader';
import { 
  formatServiceName,
  formatCriticality,
  getCriticalityColor,
  formatCategory,
  getCategoryColor,
  countAffectedResources,
  getImpactTags,
  parseLinks
} from '../utils/formatters';
import { renderHtml } from '../utils/htmlDecoder';

/**
 * Expandable finding details component
 */
const FindingDetails = ({ finding }) => {
  const impactTags = getImpactTags(finding);
  const links = parseLinks(finding);
  const affectedResources = finding.__affectedResources || {};
  
  return (
    <SpaceBetween size="m">
      {/* Full Description */}
      <div>
        <Box variant="awsui-key-label">Full Description</Box>
        <Box variant="p">
          <div dangerouslySetInnerHTML={renderHtml(finding['^description'] || finding.shortDesc)} />
        </Box>
      </div>
      
      {/* Impact Tags */}
      {impactTags.length > 0 && (
        <div>
          <Box variant="awsui-key-label">Impact</Box>
          <SpaceBetween size="xs" direction="horizontal">
            {impactTags.map(tag => (
              <Badge key={tag} color="blue">{tag}</Badge>
            ))}
          </SpaceBetween>
        </div>
      )}
      
      {/* Recommendations */}
      {links.length > 0 && (
        <div>
          <Box variant="awsui-key-label">Recommendations</Box>
          <SpaceBetween size="xs">
            {links.map((link, index) => (
              <Link key={index} href={link.url} external>
                {link.text}
              </Link>
            ))}
          </SpaceBetween>
        </div>
      )}
      
      {/* Affected Resources by Region */}
      {Object.keys(affectedResources).length > 0 && (
        <div>
          <Box variant="awsui-key-label">Affected Resources by Region</Box>
          <ColumnLayout columns={2}>
            {Object.entries(affectedResources).map(([region, resources]) => (
              <div key={region}>
                <Box variant="awsui-key-label" fontSize="body-s">
                  {region} ({resources.length})
                </Box>
                <Box variant="code">
                  {resources.slice(0, 5).join(', ')}
                  {resources.length > 5 && ` ... and ${resources.length - 5} more`}
                </Box>
              </div>
            ))}
          </ColumnLayout>
        </div>
      )}
    </SpaceBetween>
  );
};

/**
 * ServiceDetail component - displays findings for a specific service
 */
const ServiceDetail = ({ data }) => {
  const { serviceName } = useParams();
  const [filteringText, setFilteringText] = useState('');
  const [sortingColumn, setSortingColumn] = useState({ sortingField: 'criticality' });
  const [sortingDescending, setSortingDescending] = useState(false);
  
  // Get service data
  const serviceData = getServiceData(data, serviceName);
  const findings = useMemo(() => {
    if (!serviceData) return [];
    return getServiceFindings(serviceData);
  }, [serviceData]);
  
  // Filter findings
  const filteredFindings = useMemo(() => {
    if (!filteringText) return findings;
    
    const lowerFilter = filteringText.toLowerCase();
    return findings.filter(finding => 
      finding.ruleName.toLowerCase().includes(lowerFilter) ||
      (finding.shortDesc && finding.shortDesc.toLowerCase().includes(lowerFilter)) ||
      (finding['^description'] && finding['^description'].toLowerCase().includes(lowerFilter))
    );
  }, [findings, filteringText]);
  
  // Sort findings
  const sortedFindings = useMemo(() => {
    const sorted = [...filteredFindings];
    
    const criticalityOrder = { 'H': 0, 'M': 1, 'L': 2, 'I': 3 };
    
    sorted.sort((a, b) => {
      let comparison = 0;
      
      switch (sortingColumn.sortingField) {
        case 'criticality':
          comparison = criticalityOrder[a.criticality] - criticalityOrder[b.criticality];
          break;
        case 'category':
          comparison = (a.__categoryMain || '').localeCompare(b.__categoryMain || '');
          break;
        case 'ruleName':
          comparison = a.ruleName.localeCompare(b.ruleName);
          break;
        case 'resources':
          comparison = countAffectedResources(a.__affectedResources) - 
                      countAffectedResources(b.__affectedResources);
          break;
        default:
          comparison = 0;
      }
      
      return sortingDescending ? -comparison : comparison;
    });
    
    return sorted;
  }, [filteredFindings, sortingColumn, sortingDescending]);
  
  // Handle sorting
  const handleSortingChange = (event) => {
    const { sortingColumn: newSortingColumn, isDescending } = event.detail;
    setSortingColumn(newSortingColumn);
    setSortingDescending(isDescending || false);
  };
  
  // If service not found
  if (!serviceData) {
    return (
      <Container>
        <Box textAlign="center" padding={{ vertical: 'xxl' }}>
          <Box variant="h2" color="text-status-error">
            Service Not Found
          </Box>
          <Box variant="p" color="text-status-inactive">
            The service "{serviceName}" was not found in this report.
          </Box>
        </Box>
      </Container>
    );
  }
  
  // Get icon for criticality
  const getCriticalityIcon = (criticality) => {
    switch (criticality) {
      case 'H': return '🚫';
      case 'M': return '⚠️';
      case 'L': return '👁️';
      case 'I': return 'ℹ️';
      default: return '';
    }
  };
  
  // Column definitions
  const columnDefinitions = [
    {
      id: 'criticality',
      header: 'Priority',
      cell: item => (
        <span style={{ fontSize: '20px' }}>
          {getCriticalityIcon(item.criticality)}
        </span>
      ),
      sortingField: 'criticality',
      width: 80
    },
    {
      id: 'category',
      header: 'Category',
      cell: item => {
        const getCategoryStyle = (category) => {
          const styles = {
            'S': { backgroundColor: '#d13212', color: 'white' },
            'R': { backgroundColor: '#f012be', color: 'white' },
            'C': { backgroundColor: '#0073bb', color: 'white' },
            'P': { backgroundColor: '#1d8102', color: 'white' },
            'O': { backgroundColor: '#001f3f', color: 'white' }
          };
          return styles[category] || { backgroundColor: '#545b64', color: 'white' };
        };
        
        const style = getCategoryStyle(item.__categoryMain);
        return (
          <span style={{
            ...style,
            padding: '4px 12px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: '500',
            display: 'inline-block'
          }}>
            {formatCategory(item.__categoryMain)}
          </span>
        );
      },
      sortingField: 'category',
      width: 180
    },
    {
      id: 'ruleName',
      header: 'Rule Name',
      cell: item => item.ruleName,
      sortingField: 'ruleName',
      width: 250
    },
    {
      id: 'description',
      header: 'Description',
      cell: item => (
        <Box variant="span">
          <span dangerouslySetInnerHTML={renderHtml(item.shortDesc)} />
        </Box>
      ),
      width: 400
    },
    {
      id: 'resources',
      header: 'Affected Resources',
      cell: item => countAffectedResources(item.__affectedResources),
      sortingField: 'resources',
      width: 150
    }
  ];
  
  // Calculate metrics
  const metrics = useMemo(() => {
    const stats = serviceData?.stats || {};
    const totalFindings = findings.length;
    const uniqueRules = new Set(findings.map(f => f.ruleName)).size;
    
    // Count total affected resources
    let affectedResourceCount = 0;
    findings.forEach(finding => {
      affectedResourceCount += countAffectedResources(finding.__affectedResources);
    });
    
    // Format time spent
    const formatTime = (seconds) => {
      if (!seconds) return '0s';
      if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
      return `${seconds.toFixed(3)}s`;
    };
    
    return {
      resources: stats.resources || affectedResourceCount || 0,
      totalFindings: affectedResourceCount || totalFindings,
      rulesExecuted: stats.rules || 0,
      uniqueRules,
      suppressed: stats.suppressed || 0,
      timespent: formatTime(stats.timespent)
    };
  }, [serviceData, findings]);
  
  return (
    <SpaceBetween size="l">
      <Header 
        variant="h1"
        description={`Detailed findings for ${formatServiceName(serviceName)}`}
      >
        {formatServiceName(serviceName)}
      </Header>
      
      {/* Summary Section - 2 columns layout */}
      <Container
        header={
          <Header variant="h2" description="Key metrics and statistics for this service">
            Summary
          </Header>
        }
      >
        <ColumnLayout columns={2} variant="default">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Resources</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-info">
              {metrics.resources}
            </Box>
          </SpaceBetween>
        </div>
        
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Total Findings</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-warning">
              {metrics.totalFindings}
            </Box>
          </SpaceBetween>
        </div>
        
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Rules Executed</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-success">
              {metrics.rulesExecuted}
            </Box>
          </SpaceBetween>
        </div>
        
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Unique Rules</Box>
            <Box fontSize="display-l" fontWeight="bold">
              {metrics.uniqueRules}
            </Box>
          </SpaceBetween>
        </div>
        
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Suppressed</Box>
            <Box fontSize="display-l" fontWeight="bold" color="text-status-error">
              {metrics.suppressed}
            </Box>
          </SpaceBetween>
        </div>
        
        <div style={{ 
          backgroundColor: '#f9f9f9', 
          padding: '20px', 
          borderRadius: '8px',
          border: '1px solid #e9ebed'
        }}>
          <SpaceBetween size="xs">
            <Box variant="awsui-key-label">Time Spent</Box>
            <Box fontSize="display-l" fontWeight="bold">
              {metrics.timespent}
            </Box>
          </SpaceBetween>
            <div style={{ 
              backgroundColor: '#f9f9f9', 
              padding: '20px', 
              borderRadius: '8px',
              border: '1px solid #e9ebed'
            }}>
              <SpaceBetween size="xs">
                <Box variant="awsui-key-label">Suppressed</Box>
                <Box fontSize="display-l" fontWeight="bold" color="text-status-inactive">
                  {metrics.suppressed}
                </Box>
              </SpaceBetween>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ 
              backgroundColor: '#f9f9f9', 
              padding: '20px', 
              borderRadius: '8px',
              border: '1px solid #e9ebed'
            }}>
              <SpaceBetween size="xs">
                <Box variant="awsui-key-label">Exceptions</Box>
                <Box fontSize="display-l" fontWeight="bold">
                  {metrics.exceptions}
                </Box>
              </SpaceBetween>
            </div>
            
            <div style={{ 
              backgroundColor: '#f9f9f9', 
              padding: '20px', 
              borderRadius: '8px',
              border: '1px solid #e9ebed'
            }}>
              <SpaceBetween size="xs">
                <Box variant="awsui-key-label">Time Spent</Box>
                <Box fontSize="display-l" fontWeight="bold">
                  {metrics.timespent}
                </Box>
              </SpaceBetween>
            </div>
          </div>
        </ColumnLayout>
      </Container>
      
      {/* Findings Details */}
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
          {sortedFindings.map(finding => {
            const getCategoryStyleForHeader = (category) => {
              const styles = {
                'S': { backgroundColor: '#d13212', color: 'white', label: 'Security' },
                'R': { backgroundColor: '#f012be', color: 'white', label: 'Reliability' },
                'C': { backgroundColor: '#0073bb', color: 'white', label: 'Cost Optimization' },
                'P': { backgroundColor: '#1d8102', color: 'white', label: 'Performance' },
                'O': { backgroundColor: '#001f3f', color: 'white', label: 'Operational Excellence' }
              };
              return styles[category] || { backgroundColor: '#545b64', color: 'white', label: category };
            };
            
            const categoryStyle = getCategoryStyleForHeader(finding.__categoryMain);
            
            return (
              <ExpandableSection
                key={finding.ruleName}
                headerText={
                  <SpaceBetween size="s" direction="horizontal">
                    <span style={{ fontSize: '20px' }}>
                      {getCriticalityIcon(finding.criticality)}
                    </span>
                    <span style={{
                      backgroundColor: categoryStyle.backgroundColor,
                      color: categoryStyle.color,
                      padding: '4px 12px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: '500',
                      display: 'inline-block'
                    }}>
                      {categoryStyle.label}
                    </span>
                    <span>{finding.ruleName}</span>
                  </SpaceBetween>
                }
                variant="container"
              >
                <FindingDetails finding={finding} />
              </ExpandableSection>
            );
          })}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
};

export default ServiceDetail;
