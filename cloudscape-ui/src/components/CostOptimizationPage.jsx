import React, { useState, useEffect } from 'react';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Badge from '@cloudscape-design/components/badge';
import Button from '@cloudscape-design/components/button';
import Tabs from '@cloudscape-design/components/tabs';
import ExecutiveDashboard from './ExecutiveDashboard';

/**
 * KPI Card component for displaying cost optimization metrics
 */
const CostKPICard = ({ title, value, subtitle, variant = 'default', icon, onClick, clickable = false }) => {
  const content = (
    <SpaceBetween size="xs">
      <Box variant="awsui-key-label">{title}</Box>
      <Box 
        fontSize="display-l" 
        fontWeight="bold" 
        variant={variant}
      >
        {icon && <span style={{ marginRight: '8px' }}>{icon}</span>}
        {value}
      </Box>
      {subtitle && (
        <Box fontSize="body-s" color="text-body-secondary">
          {subtitle}
        </Box>
      )}
    </SpaceBetween>
  );
  
  if (clickable) {
    return (
      <Container>
        <div 
          onClick={onClick}
          style={{ cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              onClick();
            }
          }}
        >
          {content}
        </div>
      </Container>
    );
  }
  
  return <Container>{content}</Container>;
};

/**
 * CostOptimizationPage component
 * Main page for displaying AWS cost optimization recommendations
 */
const CostOptimizationPage = () => {
  const [cohData, setCohData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTabId, setActiveTabId] = useState('executive');

  useEffect(() => {
    loadCOHData();
  }, []);

  const loadCOHData = async () => {
    try {
      setLoading(true);
      
      // Load COH data from embedded window.__COH_DATA__
      if (typeof window !== 'undefined' && window.__COH_DATA__) {
        const data = window.__COH_DATA__;
        setCohData(data);
        setError(null);
      } else {
        throw new Error('Cost Optimization Hub data not available');
      }
    } catch (err) {
      console.error('Error loading COH data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = (format) => {
    // In a real implementation, this would trigger the export functionality
    console.log(`Exporting executive report in ${format} format`);
    
    // Mock export functionality
    const exportData = {
      timestamp: new Date().toISOString(),
      format: format,
      data: cohData
    };
    
    // For now, just log the export action
    alert(`Executive report export in ${format.toUpperCase()} format initiated. Check console for details.`);
    console.log('Export data:', exportData);
  };

  const handleDrillDown = (metricType) => {
    // In a real implementation, this would navigate to detailed views
    console.log(`Drilling down into ${metricType} details`);
    
    // For now, switch to the appropriate tab based on metric type
    if (metricType.includes('recommendation') || metricType.includes('priority')) {
      setActiveTabId('recommendations');
    } else if (metricType.includes('analytics') || metricType.includes('service')) {
      setActiveTabId('analytics');
    } else {
      setActiveTabId('overview');
    }
  };

  if (loading) {
    return (
      <Container>
        <StatusIndicator type="loading">Loading Cost Optimization Hub data...</StatusIndicator>
      </Container>
    );
  }

  if (error || (cohData && cohData.error)) {
    const errorMessage = error || cohData?.error || 'Unknown error';
    
    return (
      <Container
        header={
          <Header variant="h1">
            Cost Optimization Hub
          </Header>
        }
      >
        <Alert type="warning" header="Cost Optimization Hub Unavailable">
          <Box variant="p">
            {errorMessage}
          </Box>
          <Box variant="p">
            <strong>Possible causes:</strong>
          </Box>
          <ul>
            <li>Cost Optimization Hub is not enabled in your AWS account</li>
            <li>Insufficient IAM permissions for cost optimization services</li>
            <li>No cost optimization recommendations are currently available</li>
          </ul>
          <Box variant="p">
            Please check your AWS configuration and try refreshing the data.
          </Box>
        </Alert>
      </Container>
    );
  }

  if (!cohData || !cohData.executive_summary) {
    return (
      <Container
        header={
          <Header variant="h1">
            Cost Optimization Hub
          </Header>
        }
      >
        <Alert type="info">
          No cost optimization data available. Please run a cost optimization scan to see recommendations.
        </Alert>
      </Container>
    );
  }

  const tabs = [
    {
      id: 'executive',
      label: 'Executive Dashboard',
      content: renderExecutiveDashboardTab()
    },
    {
      id: 'overview',
      label: 'Overview',
      content: renderOverviewTab()
    },
    {
      id: 'recommendations',
      label: 'Recommendations',
      content: renderRecommendationsTab()
    },
    {
      id: 'analytics',
      label: 'Analytics',
      content: renderAnalyticsTab()
    }
  ];

  return (
    <SpaceBetween size="l">
      <Container
        header={
          <Header
            variant="h1"
            description="AWS Cost Optimization Hub provides unified cost optimization recommendations across multiple AWS services"
            actions={
              <Button 
                variant="primary" 
                iconName="refresh"
                onClick={loadCOHData}
              >
                Refresh Data
              </Button>
            }
          >
            Cost Optimization Hub
          </Header>
        }
      >
        {renderExecutiveSummary()}
      </Container>

      <Tabs
        activeTabId={activeTabId}
        onChange={({ detail }) => setActiveTabId(detail.activeTabId)}
        tabs={tabs}
      />
    </SpaceBetween>
  );

  function renderExecutiveDashboardTab() {
    return (
      <ExecutiveDashboard
        cohData={cohData}
        onExport={handleExport}
        onDrillDown={handleDrillDown}
      />
    );
  }

  function renderExecutiveSummary() {
    const summary = cohData.executive_summary;
    const keyMetrics = cohData.key_metrics || {};
    
    return (
      <SpaceBetween size="m">
        <Header variant="h2">Executive Summary</Header>
        
        <ColumnLayout columns={4} variant="text-grid">
          <CostKPICard
            title="Monthly Savings Potential"
            value={`$${keyMetrics.total_monthly_savings?.toLocaleString() || '0'}`}
            subtitle={`$${keyMetrics.total_annual_savings?.toLocaleString() || '0'}/year`}
            variant="h2"
            icon="💰"
          />
          
          <CostKPICard
            title="Total Recommendations"
            value={keyMetrics.total_recommendations || 0}
            subtitle="optimization opportunities"
            variant="h2"
            icon="💡"
          />
          
          <CostKPICard
            title="High Priority Actions"
            value={keyMetrics.high_priority_count || 0}
            subtitle="immediate attention required"
            variant="h2"
            icon="⚠️"
          />
          
          <CostKPICard
            title="Quick Wins"
            value={keyMetrics.quick_wins_count || 0}
            subtitle="low effort, high impact"
            variant="h2"
            icon="🚀"
          />
        </ColumnLayout>

        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="awsui-key-label">Data Quality Score</Box>
            <Box fontSize="heading-l" fontWeight="bold" color="text-status-success">
              {keyMetrics.data_quality_score || 0}%
            </Box>
          </div>
          <div>
            <Box variant="awsui-key-label">Last Updated</Box>
            <Box fontSize="body-m" color="text-body-secondary">
              {summary.data_freshness ? new Date(summary.data_freshness).toLocaleString() : 'Unknown'}
            </Box>
          </div>
        </ColumnLayout>
      </SpaceBetween>
    );
  }

  function renderOverviewTab() {
    return (
      <SpaceBetween size="l">
        <Container
          header={
            <Header variant="h2">
              Implementation Roadmap
            </Header>
          }
        >
          {renderImplementationRoadmap()}
        </Container>

        <Container
          header={
            <Header variant="h2">
              Top Savings Opportunities
            </Header>
          }
        >
          {renderTopOpportunities()}
        </Container>
      </SpaceBetween>
    );
  }

  function renderRecommendationsTab() {
    return (
      <Container
        header={
          <Header variant="h2">
            Cost Optimization Recommendations
          </Header>
        }
      >
        <Alert type="info">
          Detailed recommendations table will be implemented in the next phase.
          This will include sortable, filterable recommendations with implementation guidance.
        </Alert>
      </Container>
    );
  }

  function renderAnalyticsTab() {
    return (
      <Container
        header={
          <Header variant="h2">
            Cost Analytics & Insights
          </Header>
        }
      >
        <Alert type="info">
          Interactive charts and analytics will be implemented in the next phase.
          This will include savings trends, ROI analysis, and opportunity matrices.
        </Alert>
      </Container>
    );
  }

  function renderImplementationRoadmap() {
    const roadmap = cohData.executive_summary?.implementation_roadmap || [];
    
    if (roadmap.length === 0) {
      return (
        <Box textAlign="center" color="inherit">
          <b>No roadmap data available</b>
          <Box padding={{ bottom: 's' }} variant="p" color="inherit">
            Implementation roadmap will be generated based on your recommendations.
          </Box>
        </Box>
      );
    }

    return (
      <SpaceBetween size="m">
        {roadmap.map((phase, index) => (
          <Container key={index}>
            <SpaceBetween size="s">
              <Header variant="h3">
                {phase.phase}
                <Badge color="blue" style={{ marginLeft: '8px' }}>
                  {phase.timeline}
                </Badge>
              </Header>
              
              <ColumnLayout columns={3} variant="text-grid">
                <div>
                  <Box variant="awsui-key-label">Expected Savings</Box>
                  <Box fontSize="heading-m" fontWeight="bold" color="text-status-success">
                    ${phase.expected_savings?.toLocaleString() || '0'}/month
                  </Box>
                </div>
                <div>
                  <Box variant="awsui-key-label">Recommendations</Box>
                  <Box fontSize="heading-m" fontWeight="bold">
                    {phase.recommendation_count || 0} items
                  </Box>
                </div>
                <div>
                  <Box variant="awsui-key-label">Implementation Status</Box>
                  <Badge color="grey">Not Started</Badge>
                </div>
              </ColumnLayout>

              {phase.key_activities && phase.key_activities.length > 0 && (
                <div>
                  <Box variant="awsui-key-label" margin={{ bottom: 'xs' }}>
                    Key Activities
                  </Box>
                  <ul>
                    {phase.key_activities.map((activity, actIndex) => (
                      <li key={actIndex}>{activity}</li>
                    ))}
                  </ul>
                </div>
              )}
            </SpaceBetween>
          </Container>
        ))}
      </SpaceBetween>
    );
  }

  function renderTopOpportunities() {
    const topCategories = cohData.executive_summary?.top_categories || [];
    
    if (topCategories.length === 0) {
      return (
        <Box textAlign="center" color="inherit">
          <b>No opportunities identified</b>
          <Box padding={{ bottom: 's' }} variant="p" color="inherit">
            Top savings opportunities will appear here when recommendations are available.
          </Box>
        </Box>
      );
    }

    return (
      <SpaceBetween size="m">
        {topCategories.map((category, index) => (
          <Container key={index}>
            <SpaceBetween size="s" direction="horizontal">
              <div style={{ flex: 1 }}>
                <Header variant="h4">
                  {category.category?.charAt(0).toUpperCase() + category.category?.slice(1) || 'Unknown Category'}
                </Header>
                <Box fontSize="body-s" color="text-body-secondary">
                  {getCategoryDescription(category.category)}
                </Box>
              </div>
              <div>
                <Box fontSize="heading-l" fontWeight="bold" color="text-status-success">
                  ${category.savings?.toLocaleString() || '0'}/month
                </Box>
              </div>
            </SpaceBetween>
          </Container>
        ))}
      </SpaceBetween>
    );
  }
};

// Helper function to get category descriptions
function getCategoryDescription(category) {
  const descriptions = {
    'compute': 'Optimize EC2 instances, Auto Scaling, and compute resources',
    'storage': 'Optimize S3, EBS, and other storage services',
    'database': 'Optimize RDS, DynamoDB, and database configurations',
    'commitment': 'Leverage Reserved Instances and Savings Plans',
    'general': 'General cost optimization opportunities'
  };
  
  return descriptions[category] || 'Cost optimization opportunities';
}

export default CostOptimizationPage;