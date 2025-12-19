import React from 'react';
import { useParams } from 'react-router-dom';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Box from '@cloudscape-design/components/box';
import Alert from '@cloudscape-design/components/alert';
import Table from '@cloudscape-design/components/table';
import SpaceBetween from '@cloudscape-design/components/space-between';
import FindingsPage from './FindingsPage';

/**
 * CustomPage component
 * Displays custom pages like Findings, Modernize, TA
 */
const CustomPage = ({ data }) => {
  const { pageName } = useParams();
  
  if (!data || !pageName) {
    return (
      <Container>
        <Alert type="error">
          Invalid page data
        </Alert>
      </Container>
    );
  }
  
  // Get custom page data
  const pageKey = `customPage_${pageName}`;
  const pageData = data[pageKey];
  
  if (!pageData) {
    return (
      <Container>
        <Alert type="warning">
          Page "{pageName}" not found in report data
        </Alert>
      </Container>
    );
  }
  
  // Format page title
  const pageTitle = pageName === 'ta' ? 'Trusted Advisor' :
                   pageName.charAt(0).toUpperCase() + pageName.slice(1);
  
  // Render based on page type
  if (pageName === 'findings') {
    return <FindingsPage data={data} />;
  } else if (pageName === 'modernize') {
    return renderModernizePage(pageData, pageTitle);
  } else if (pageName === 'ta') {
    return renderTAPage(pageData, pageTitle);
  }
  
  // Default rendering for unknown page types
  return (
    <Container header={<Header variant="h1">{pageTitle}</Header>}>
      <Box variant="p">
        Custom page data available. Specific rendering not yet implemented.
      </Box>
      <Box variant="code">
        <pre>{JSON.stringify(pageData, null, 2)}</pre>
      </Box>
    </Container>
  );
};



/**
 * Render Modernize page
 */
const renderModernizePage = (pageData, pageTitle) => {
  const ec2Data = pageData.ec2instance || {};
  const instances = ec2Data.items || [];
  
  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h1">{pageTitle}</Header>}>
        <Box variant="p">
          Total EC2 instances: {ec2Data.total || 0}
        </Box>
      </Container>
      
      <Container header={<Header variant="h2">EC2 Instances</Header>}>
        <Table
          columnDefinitions={[
            {
              id: 'id',
              header: 'Instance ID',
              cell: item => item.id || '-'
            },
            {
              id: 'platform',
              header: 'Platform',
              cell: item => item.platform || '-'
            },
            {
              id: 'instanceType',
              header: 'Instance Type',
              cell: item => item.instanceType || '-'
            },
            {
              id: 'keyTags',
              header: 'Key Tags',
              cell: item => item.keyTags ? item.keyTags.join(', ') : '-'
            }
          ]}
          items={instances}
          loadingText="Loading instances"
          empty={
            <Box textAlign="center" color="inherit">
              <b>No instances</b>
              <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                No EC2 instances to display.
              </Box>
            </Box>
          }
          sortingDisabled={false}
          variant="embedded"
        />
      </Container>
    </SpaceBetween>
  );
};

/**
 * Render Trusted Advisor page
 */
const renderTAPage = (pageData, pageTitle) => {
  const ec2Data = pageData.ec2instance || {};
  const instances = ec2Data.items || [];
  
  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h1">{pageTitle}</Header>}>
        <Box variant="p">
          Trusted Advisor recommendations for EC2 instances: {ec2Data.total || 0}
        </Box>
      </Container>
      
      <Container header={<Header variant="h2">EC2 Recommendations</Header>}>
        <Table
          columnDefinitions={[
            {
              id: 'id',
              header: 'Instance ID',
              cell: item => item.id || '-'
            },
            {
              id: 'platform',
              header: 'Platform',
              cell: item => item.platform || '-'
            },
            {
              id: 'instanceType',
              header: 'Instance Type',
              cell: item => item.instanceType || '-'
            },
            {
              id: 'keyTags',
              header: 'Key Tags',
              cell: item => item.keyTags ? item.keyTags.join(', ') : '-'
            }
          ]}
          items={instances}
          loadingText="Loading recommendations"
          empty={
            <Box textAlign="center" color="inherit">
              <b>No recommendations</b>
              <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                No Trusted Advisor recommendations to display.
              </Box>
            </Box>
          }
          sortingDisabled={false}
          variant="embedded"
        />
      </Container>
    </SpaceBetween>
  );
};

export default CustomPage;
