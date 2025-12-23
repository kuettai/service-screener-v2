import React from 'react';
import TopNavigation from '@cloudscape-design/components/top-navigation';

/**
 * TopNavigation component for Service Screener
 * Displays branding, account selector, and suppression indicator
 */
const ServiceScreenerTopNav = ({ accountId, hasSuppressions, onSuppressionClick }) => {
  const utilities = [];
  
  // Add GitHub link
  utilities.push({
    type: 'button',
    text: 'Visit GitHub',
    href: 'https://github.com/aws-samples/service-screener-v2',
    external: true,
    iconName: 'external'
  });
  
  // Add suppression indicator if suppressions are active
  if (hasSuppressions) {
    utilities.push({
      type: 'button',
      text: 'Suppressions Active',
      onClick: onSuppressionClick,
      iconName: 'status-warning',
      variant: 'primary-button'
    });
  }
  
  // Add account info
  utilities.push({
    type: 'menu-dropdown',
    text: accountId || 'Unknown Account',
    iconName: 'user-profile',
    items: [
      {
        id: 'account',
        text: `Account: ${accountId || 'Unknown'}`,
        disabled: true
      }
    ]
  });
  
  return (
    <TopNavigation
      identity={{
        href: '#/',
        title: 'Service Screener',
        logo: {
          src: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHJ4PSI0IiBmaWxsPSIjMjMyRjNFIi8+CiAgPHBhdGggZD0iTTEyIDEySDI4VjE2SDEyVjEyWiIgZmlsbD0iI0ZGOTkwMCIvPgogIDxwYXRoIGQ9Ik0xMiAyMEgyOFYyNEgxMlYyMFoiIGZpbGw9IiNGRjk5MDAiLz4KICA8cGF0aCBkPSJNMTIgMjhIMjhWMzJIMTJWMjhaIiBmaWxsPSIjRkY5OTAwIi8+Cjwvc3ZnPgo=',
          alt: 'Service Screener'
        }
      }}
      utilities={utilities}
      i18nStrings={{
        searchIconAriaLabel: 'Search',
        searchDismissIconAriaLabel: 'Close search',
        overflowMenuTriggerText: 'More',
        overflowMenuTitleText: 'All',
        overflowMenuBackIconAriaLabel: 'Back',
        overflowMenuDismissIconAriaLabel: 'Close menu'
      }}
    />
  );
};

export default ServiceScreenerTopNav;
