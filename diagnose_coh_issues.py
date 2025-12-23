#!/usr/bin/env python3
"""
Diagnose COH Implementation Issues

This script identifies the specific issues causing warnings and provides
exact solutions to get all green results.
"""

import sys
import boto3
from botocore.exceptions import ClientError
sys.path.append('.')

def diagnose_issues():
    """Diagnose each specific issue and provide solutions"""
    print("🔍 Diagnosing COH Implementation Issues")
    print("=" * 50)
    
    issues = []
    solutions = []
    
    # Issue 1: Cost Explorer Permissions
    print("\n1️⃣ Testing Cost Explorer Permissions...")
    try:
        ce_client = boto3.client('ce', region_name='us-east-1')
        response = ce_client.get_rightsizing_recommendation(
            Service='AmazonEC2',
            Configuration={
                'BenefitsConsidered': False,
                'RecommendationTarget': 'SAME_INSTANCE_FAMILY'
            }
        )
        print("✅ Cost Explorer permissions OK")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            issues.append("Cost Explorer access denied")
            solutions.append("Add IAM permission: ce:GetRightsizingRecommendation")
        print(f"❌ Cost Explorer: {error_code}")
    
    # Issue 2: Cost Optimization Hub API Parameters
    print("\n2️⃣ Testing COH API Parameters...")
    try:
        coh_client = boto3.client('cost-optimization-hub', region_name='us-east-1')
        
        # Test with correct parameters
        response = coh_client.list_recommendations(maxResults=10)
        print("✅ COH API parameters OK")
        
        # Test filters
        try:
            response = coh_client.list_recommendations(
                maxResults=10,
                filter={
                    'restartNeeded': False,  # Should be boolean, not list
                    'implementationEfforts': ['VeryLow', 'Low']
                }
            )
            print("✅ COH API filters OK")
        except ClientError as e:
            issues.append(f"COH API filter error: {e.response['Error']['Code']}")
            solutions.append("Update COH API filter parameters to match current API version")
            
    except Exception as e:
        issues.append(f"COH API error: {str(e)}")
        solutions.append("Check COH API documentation for correct parameters")
    
    # Issue 3: Savings Plans API
    print("\n3️⃣ Testing Savings Plans API...")
    try:
        sp_client = boto3.client('savingsplans', region_name='us-east-1')
        
        # Test utilization (this was failing)
        try:
            ce_client = boto3.client('ce', region_name='us-east-1')
            response = ce_client.get_savings_plans_utilization(
                TimePeriod={
                    'Start': '2024-01-01',
                    'End': '2024-01-31'
                }
            )
            print("✅ Savings Plans utilization OK")
        except ClientError as e:
            if e.response['Error']['Code'] == 'DataUnavailableException':
                issues.append("No Savings Plans data available")
                solutions.append("Account needs active Savings Plans or historical data")
            else:
                issues.append(f"Savings Plans utilization error: {e.response['Error']['Code']}")
                solutions.append("Check Savings Plans API parameters")
                
    except Exception as e:
        issues.append(f"Savings Plans error: {str(e)}")
    
    # Issue 4: Reserved Instance Coverage
    print("\n4️⃣ Testing RI Coverage API...")
    try:
        ce_client = boto3.client('ce', region_name='us-east-1')
        response = ce_client.get_reservation_coverage(
            TimePeriod={
                'Start': '2024-01-01',
                'End': '2024-01-31'
            },
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )
        print("✅ RI Coverage API OK")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            issues.append("RI Coverage API parameter validation failed")
            solutions.append("Fix GroupBy parameter - use supported dimensions only")
        print(f"❌ RI Coverage: {error_code}")
    
    # Issue 5: Configuration Issues
    print("\n5️⃣ Checking Configuration Issues...")
    try:
        from utils.CustomPage.Pages.COH.COH import COH
        from unittest.mock import patch
        
        with patch('utils.Config.Config.get') as mock_config:
            mock_config.return_value = 'us-east-1'
            
            coh = COH()
            
            # Check if clients are properly initialized
            if hasattr(coh, 'coh_client') and coh.coh_client:
                print("✅ COH client initialized")
            else:
                issues.append("COH client not properly initialized")
                solutions.append("Fix COH client initialization in COH.__init__()")
                
            if hasattr(coh, 'cost_explorer_client') and coh.cost_explorer_client:
                print("✅ Cost Explorer client initialized")
            else:
                issues.append("Cost Explorer client not properly initialized")
                solutions.append("Fix Cost Explorer client initialization")
                
    except Exception as e:
        issues.append(f"Configuration error: {str(e)}")
        solutions.append("Check COH class initialization and Config setup")
    
    return issues, solutions

def main():
    """Main diagnostic function"""
    issues, solutions = diagnose_issues()
    
    print("\n" + "=" * 50)
    print("🎯 DIAGNOSIS COMPLETE")
    print("=" * 50)
    
    if not issues:
        print("🎉 NO ISSUES FOUND - Everything should be green!")
        return True
    
    print(f"❌ Found {len(issues)} issues that need fixing:")
    print()
    
    for i, (issue, solution) in enumerate(zip(issues, solutions), 1):
        print(f"{i}. ❌ ISSUE: {issue}")
        print(f"   🔧 SOLUTION: {solution}")
        print()
    
    print("🔧 REQUIRED ACTIONS TO GET ALL GREEN:")
    print("=" * 50)
    
    # Group solutions by type
    iam_fixes = [s for s in solutions if 'permission' in s.lower() or 'iam' in s.lower()]
    api_fixes = [s for s in solutions if 'api' in s.lower() or 'parameter' in s.lower()]
    config_fixes = [s for s in solutions if 'config' in s.lower() or 'initialization' in s.lower()]
    account_fixes = [s for s in solutions if 'account' in s.lower() or 'enable' in s.lower()]
    
    if iam_fixes:
        print("🔐 IAM PERMISSIONS NEEDED:")
        for fix in iam_fixes:
            print(f"   • {fix}")
        print()
    
    if api_fixes:
        print("🔧 CODE FIXES NEEDED:")
        for fix in api_fixes:
            print(f"   • {fix}")
        print()
    
    if config_fixes:
        print("⚙️ CONFIGURATION FIXES NEEDED:")
        for fix in config_fixes:
            print(f"   • {fix}")
        print()
    
    if account_fixes:
        print("🏢 ACCOUNT SETUP NEEDED:")
        for fix in account_fixes:
            print(f"   • {fix}")
        print()
    
    print("📋 PRIORITY ORDER:")
    print("1. Fix IAM permissions first")
    print("2. Fix API parameter issues in code")
    print("3. Test again to validate all green")
    
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)