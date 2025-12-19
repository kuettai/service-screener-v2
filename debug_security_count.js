// Debug script to compare Dashboard vs FindingsPage Security counts
const fs = require('fs');

// Read the API data
const data = JSON.parse(fs.readFileSync('adminlte/aws/956288449190/api-full.json', 'utf8'));

console.log('=== SECURITY FINDINGS COUNT DEBUG ===\n');

// Count from customPage_findings (FindingsPage method)
const findingsPageSecurityHigh = data.customPage_findings.findings.filter(f => 
  f.Type === 'Security' && f.Severity === 'High'
).length;

const findingsPageSecurityTotal = data.customPage_findings.findings.filter(f => 
  f.Type === 'Security'
).length;

console.log('FindingsPage counts:');
console.log(`Security High: ${findingsPageSecurityHigh}`);
console.log(`Security Total: ${findingsPageSecurityTotal}\n`);

// Count from service data (Dashboard method)
const services = Object.keys(data).filter(key => 
  !key.startsWith('__') && 
  !key.startsWith('framework_') &&
  !key.startsWith('customPage_') &&
  typeof data[key] === 'object' &&
  data[key] !== null
);

let dashboardSecurityHigh = 0;
let dashboardSecurityTotal = 0;

services.forEach(service => {
  const serviceData = data[service];
  if (serviceData && serviceData.summary) {
    Object.values(serviceData.summary).forEach(finding => {
      if (finding.__categoryMain === 'S') {
        // Count affected resources
        let resourceCount = 0;
        if (finding.__affectedResources) {
          Object.values(finding.__affectedResources).forEach(resources => {
            if (Array.isArray(resources)) {
              resourceCount += resources.length;
            }
          });
        }
        
        // If no affected resources, count as 1
        if (resourceCount === 0) {
          resourceCount = 1;
        }
        
        dashboardSecurityTotal += resourceCount;
        
        if (finding.criticality === 'H') {
          dashboardSecurityHigh += resourceCount;
        }
      }
    });
  }
});

console.log('Dashboard counts:');
console.log(`Security High: ${dashboardSecurityHigh}`);
console.log(`Security Total: ${dashboardSecurityTotal}\n`);

console.log('Discrepancy:');
console.log(`High: Dashboard(${dashboardSecurityHigh}) - FindingsPage(${findingsPageSecurityHigh}) = ${dashboardSecurityHigh - findingsPageSecurityHigh}`);
console.log(`Total: Dashboard(${dashboardSecurityTotal}) - FindingsPage(${findingsPageSecurityTotal}) = ${dashboardSecurityTotal - findingsPageSecurityTotal}`);

// Let's find the specific discrepancy by listing all Dashboard Security findings
console.log('\n=== DASHBOARD SECURITY FINDINGS BREAKDOWN ===');
services.forEach(service => {
  const serviceData = data[service];
  if (serviceData && serviceData.summary) {
    Object.entries(serviceData.summary).forEach(([ruleName, finding]) => {
      if (finding.__categoryMain === 'S') {
        let resourceCount = 0;
        if (finding.__affectedResources) {
          Object.values(finding.__affectedResources).forEach(resources => {
            if (Array.isArray(resources)) {
              resourceCount += resources.length;
            }
          });
        }
        
        if (resourceCount === 0) {
          resourceCount = 1;
        }
        
        console.log(`${service}.${ruleName}: ${finding.criticality} severity, ${resourceCount} resources`);
      }
    });
  }
});

// Count High severity findings from FindingsPage by rule
console.log('\n=== FINDINGSPAGE HIGH SECURITY FINDINGS BY RULE ===');
const highSecurityByRule = {};
data.customPage_findings.findings.filter(f => f.Type === 'Security' && f.Severity === 'High').forEach(finding => {
  const key = `${finding.service}.${finding.Check}`;
  highSecurityByRule[key] = (highSecurityByRule[key] || 0) + 1;
});

Object.entries(highSecurityByRule).forEach(([rule, count]) => {
  console.log(`${rule}: ${count} resources`);
});