import React from 'react';
import { Sankey, ResponsiveContainer, Tooltip } from 'recharts';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Box from '@cloudscape-design/components/box';
import Alert from '@cloudscape-design/components/alert';

/**
 * SankeyDiagram component
 * Renders a Sankey diagram using Recharts
 */
const SankeyDiagram = ({ title, data, height = 400 }) => {
  if (!data || !data.nodes || !data.links) {
    return (
      <Container header={<Header variant="h2">{title}</Header>}>
        <Alert type="info">
          No modernization data available for {title.toLowerCase()}.
        </Alert>
      </Container>
    );
  }

  // Transform data for Recharts Sankey
  const sankeyData = {
    nodes: data.nodes.map((node, index) => ({
      id: index,
      name: node
    })),
    links: data.links.map(link => ({
      source: link.source,
      target: link.target,
      value: link.value
    }))
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      if (data.source !== undefined) {
        // Link tooltip
        const sourceNode = sankeyData.nodes[data.source];
        const targetNode = sankeyData.nodes[data.target];
        return (
          <Box
            padding="s"
            backgroundColor="white"
            borderRadius="4px"
            boxShadow="0 2px 8px rgba(0,0,0,0.15)"
          >
            <Box variant="strong">{sourceNode?.name} → {targetNode?.name}</Box>
            <Box variant="p">Resources: {data.value}</Box>
          </Box>
        );
      } else {
        // Node tooltip
        return (
          <Box
            padding="s"
            backgroundColor="white"
            borderRadius="4px"
            boxShadow="0 2px 8px rgba(0,0,0,0.15)"
          >
            <Box variant="strong">{data.name}</Box>
            <Box variant="p">Value: {data.value}</Box>
          </Box>
        );
      }
    }
    return null;
  };

  return (
    <Container header={<Header variant="h2">{title}</Header>}>
      <Box padding={{ bottom: 'm' }}>
        <Box variant="p" color="text-body-secondary">
          This diagram shows the modernization pathway for {title.toLowerCase()}, 
          with flow indicating the number of resources that can be modernized.
        </Box>
      </Box>
      
      <div style={{ width: '100%', height: `${height}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={sankeyData}
            nodeWidth={15}
            nodePadding={10}
            margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          >
            <Tooltip content={<CustomTooltip />} />
          </Sankey>
        </ResponsiveContainer>
      </div>
      
      <Box padding={{ top: 'm' }}>
        <Box variant="small" color="text-body-secondary">
          <strong>Legend:</strong> Boxes represent resource types, arrows show modernization paths, 
          and thickness indicates the number of resources.
        </Box>
      </Box>
    </Container>
  );
};

export default SankeyDiagram;