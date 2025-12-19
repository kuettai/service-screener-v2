// Debug script to test GuardDuty data processing
// Run this in browser console after opening the Cloudscape UI

console.log('=== GuardDuty Debug Script ===');

// Check if data exists
const data = window.__REPORT_DATA__;
if (!data) {
    console.error('No report data found');
} else {
    console.log('✅ Report data found');
    
    if (data.guardduty) {
        console.log('✅ GuardDuty data found');
        console.log('GuardDuty structure:', Object.keys(data.guardduty));
        
        if (data.guardduty.detail) {
            console.log('✅ GuardDuty detail found');
            const regions = Object.keys(data.guardduty.detail);
            console.log('Regions:', regions);
            
            regions.forEach(region => {
                console.log(`\n--- Region: ${region} ---`);
                const regionData = data.guardduty.detail[region];
                const detectors = Object.keys(regionData);
                console.log('Detectors:', detectors);
                
                detectors.forEach(detector => {
                    const detectorData = regionData[detector];
                    console.log(`Detector ${detector} components:`, Object.keys(detectorData));
                    
                    if (detectorData.Findings && detectorData.Findings.value) {
                        const findings = detectorData.Findings.value;
                        console.log('Findings severity levels:', Object.keys(findings));
                        
                        Object.entries(findings).forEach(([severity, severityFindings]) => {
                            console.log(`  ${severity}: ${Object.keys(severityFindings).length} finding types`);
                        });
                    }
                });
            });
        } else {
            console.error('❌ No GuardDuty detail data');
        }
    } else {
        console.error('❌ No GuardDuty data');
    }
}

// Test navigation to GuardDuty page
console.log('\n=== Testing Navigation ===');
try {
    window.location.hash = '#/service/guardduty';
    console.log('✅ Navigation attempted');
} catch (error) {
    console.error('❌ Navigation failed:', error);
}