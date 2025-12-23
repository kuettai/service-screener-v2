import React from 'react';
import SideNavigation from '@cloudscape-design/components/side-navigation';
import { useLocation, useNavigate } from 'react-router-dom';
import { formatServiceName } from '../utils/formatters';

/**
 * SideNavigation component for Service Screener
 * Displays navigation links for Dashboard, Services, Pages, and Frameworks
 */
const ServiceScreenerSideNav = ({ services = [], frameworks = [], customPages = [], data = null }) => {
  const location = useLocation();
  const navigate = useNavigate();
  
  // Build navigation items
  const items = [
    {
      type: 'link',
      text: 'Dashboard',
      href: '#/'
    },
    {
      type: 'divider'
    },
    {
      type: 'section',
      text: 'Services',
      items: services.map(service => {
        // Special handling for GuardDuty - single consolidated view for all regions
        if (service.toLowerCase() === 'guardduty') {
          return {
            type: 'link',
            text: formatServiceName(service),
            href: `#/service/guardduty`
          };
        }
        
        // Regular service link
        return {
          type: 'link',
          text: formatServiceName(service),
          href: `#/service/${service.toLowerCase()}`
        };
      })
    }
  ];
  
  // Add custom pages section if custom pages exist
  const customPagesFromData = customPages || [];
  
  // Always include 'ta' (Trusted Advisor) and 'coh' (Cost Optimization Hub) as they load from separate data
  const allCustomPages = [...new Set([...customPagesFromData, 'ta', 'coh'])];
  
  if (allCustomPages.length > 0) {
    items.push({
      type: 'divider'
    });
    
    items.push({
      type: 'section',
      text: 'Pages',
      items: allCustomPages.map(page => {
        // Format page name (e.g., "findings" -> "Findings", "ta" -> "TA", "coh" -> "Cost Optimization Hub")
        const pageName = page === 'ta' ? 'Trusted Advisor' : 
                        page === 'coh' ? 'Cost Optimization Hub' :
                        page.charAt(0).toUpperCase() + page.slice(1);
        return {
          type: 'link',
          text: pageName,
          href: `#/page/${page.toLowerCase()}`
        };
      })
    });
  }
  
  // Add frameworks section if frameworks exist
  if (frameworks.length > 0) {
    items.push({
      type: 'divider'
    });
    
    items.push({
      type: 'section',
      text: 'Frameworks',
      items: frameworks.map(framework => {
        // Extract framework name from key (e.g., "framework_CIS" -> "CIS")
        const frameworkName = framework.replace('framework_', '');
        return {
          type: 'link',
          text: frameworkName.toUpperCase(),
          href: `#/framework/${frameworkName.toLowerCase()}`
        };
      })
    });
  }
  
  // Add "Others" section with GitHub star link
  items.push({
    type: 'divider'
  });
  
  items.push({
    type: 'section',
    text: 'Others',
    items: [
      {
        type: 'link',
        text: '⭐ Give us a Star ⭐',
        href: 'https://github.com/aws-samples/service-screener-v2',
        external: true
      },
      {
        type: 'link',
        text: 'Raise Issues',
        href: 'https://github.com/aws-samples/service-screener-v2/issues',
        external: true
      }
    ]
  });
  
  // Determine active href based on current location
  const getActiveHref = () => {
    const hash = location.hash || window.location.hash;
    
    // Remove leading # if present
    const path = hash.startsWith('#') ? hash : `#${hash}`;
    
    // If at root, return dashboard
    if (path === '#' || path === '#/') {
      return '#/';
    }
    
    return path;
  };
  
  const handleFollow = (event) => {
    event.preventDefault();
    
    const href = event.detail.href;
    
    // Handle external links
    if (href.startsWith('http')) {
      window.open(href, '_blank', 'noopener,noreferrer');
      return;
    }
    
    // Handle internal navigation
    // Extract path from href (remove #)
    const path = href.startsWith('#') ? href.substring(1) : href;
    
    navigate(path);
  };
  
  return (
    <SideNavigation
      activeHref={getActiveHref()}
      items={items}
      onFollow={handleFollow}
      header={{
        text: 'Navigation',
        href: '#/'
      }}
    />
  );
};

export default ServiceScreenerSideNav;
