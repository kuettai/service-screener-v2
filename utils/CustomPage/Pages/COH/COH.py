"""
Cost Optimization Hub (COH) - Core Data Collection and Processing

This module provides the main data collection and processing functionality for the
Cost Optimization Hub custom page. It integrates with three AWS cost optimization APIs:
- Cost Optimization Hub API
- Cost Explorer API  
- Savings Plans API

The module follows the existing CustomObject pattern used by other Service Screener
custom pages while providing specialized cost optimization functionality.
"""

import json
import boto3
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, NoCredentialsError

from utils.Config import Config
from utils.CustomPage.CustomObject import CustomObject
from utils.Tools import _pr, _warn


@dataclass
class CostRecommendation:
    """Unified data model for cost optimization recommendations from all sources"""
    id: str
    source: str  # 'coh', 'cost_explorer', 'savings_plans'
    category: str  # 'compute', 'storage', 'database', etc.
    service: str  # 'ec2', 's3', 'rds', etc.
    title: str
    description: str
    
    # Financial Impact
    monthly_savings: float
    annual_savings: float
    confidence_level: str  # 'high', 'medium', 'low'
    
    # Implementation Details
    implementation_effort: str  # 'low', 'medium', 'high'
    implementation_steps: List[str]
    required_permissions: List[str]
    potential_risks: List[str]
    
    # Resource Information
    affected_resources: List[Dict]
    resource_count: int
    
    # Prioritization
    priority_score: float
    priority_level: str  # 'high', 'medium', 'low'
    
    # Metadata
    created_date: datetime
    last_updated: datetime
    status: str  # 'new', 'reviewed', 'implemented', 'dismissed'


@dataclass
class ExecutiveSummary:
    """Executive-level summary of cost optimization opportunities"""
    total_recommendations: int
    total_monthly_savings: float
    total_annual_savings: float
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    top_categories: List[Dict]
    implementation_roadmap: List[Dict]
    data_freshness: datetime


class CostOptimizationHubClient:
    """
    Enhanced client for AWS Cost Optimization Hub API
    
    Provides comprehensive access to Cost Optimization Hub recommendations with
    multi-region support, intelligent error handling, and retry logic.
    """
    
    def __init__(self, session=None, retry_config=None):
        self.session = session or boto3.Session()
        self.clients = {}  # Cache clients by region
        self.supported_regions = [
            'us-east-1', 'us-west-2', 'eu-west-1', 'eu-central-1',
            'ap-southeast-1', 'ap-northeast-1', 'ap-south-1'
        ]
        self.retry_config = retry_config or {
            'max_attempts': 3,
            'backoff_factor': 2,
            'initial_delay': 1
        }
        
    def _get_client(self, region='us-east-1'):
        """Get or create COH client for specified region with caching"""
        if region not in self.clients:
            try:
                ssBoto = Config.get('ssBoto')
                if ssBoto:
                    self.clients[region] = ssBoto.client('cost-optimization-hub', region_name=region)
                else:
                    self.clients[region] = self.session.client('cost-optimization-hub', region_name=region)
            except Exception as e:
                _warn(f"Failed to create COH client for region {region}: {str(e)}")
                return None
        
        return self.clients[region]
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        import time
        
        for attempt in range(self.retry_config['max_attempts']):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                # Don't retry on certain errors
                if error_code in ['OptInRequiredException', 'AccessDeniedException', 'UnauthorizedOperation']:
                    raise e
                
                # Retry on throttling and temporary errors
                if error_code in ['Throttling', 'ThrottlingException', 'ServiceUnavailable', 'InternalServerError']:
                    if attempt < self.retry_config['max_attempts'] - 1:
                        delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                        _warn(f"Retrying after {delay}s due to {error_code} (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue
                
                raise e
            except Exception as e:
                if attempt < self.retry_config['max_attempts'] - 1:
                    delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                    _warn(f"Retrying after {delay}s due to unexpected error (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                raise e
        
        raise Exception(f"Max retry attempts ({self.retry_config['max_attempts']}) exceeded")
    
    def list_recommendations(self, region='us-east-1', max_results=100, filters=None):
        """
        List cost optimization recommendations with advanced filtering
        
        Args:
            region: AWS region to query
            max_results: Maximum number of recommendations to return
            filters: Optional filters for recommendations
            
        Returns:
            List of recommendation dictionaries
        """
        if region not in self.supported_regions:
            _warn(f"Cost Optimization Hub not supported in region {region}")
            return []
        
        try:
            client = self._get_client(region)
            if not client:
                return []
            
            def _list_recommendations():
                recommendations = []
                
                # Build request parameters
                request_params = {
                    'maxResults': min(max_results, 100)  # API limit is 100 per request
                }
                
                # Add filters if provided
                if filters:
                    if 'categories' in filters:
                        request_params['filter'] = {
                            'categories': filters['categories']
                        }
                    if 'implementationEfforts' in filters:
                        if 'filter' not in request_params:
                            request_params['filter'] = {}
                        request_params['filter']['implementationEfforts'] = filters['implementationEfforts']
                
                # Use paginator for large result sets
                paginator = client.get_paginator('list_recommendations')
                page_count = 0
                
                for page in paginator.paginate(
                    **request_params,
                    PaginationConfig={'MaxItems': max_results}
                ):
                    page_count += 1
                    items = page.get('items', [])
                    recommendations.extend(items)
                    
                    # Add region info to each recommendation
                    for rec in items:
                        rec['_region'] = region
                        rec['_page'] = page_count
                
                return recommendations
            
            return self._retry_with_backoff(_list_recommendations)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'OptInRequiredException':
                _warn(f"Cost Optimization Hub not enabled in region {region}. Enable it in AWS Console.")
                return []
            elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
                _warn(f"Insufficient permissions for Cost Optimization Hub in {region}. Required: cost-optimization-hub:ListRecommendations")
                return []
            elif error_code == 'ValidationException':
                _warn(f"Invalid request parameters for Cost Optimization Hub in {region}: {e.response['Error']['Message']}")
                return []
            else:
                _warn(f"Error accessing Cost Optimization Hub in {region}: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in Cost Optimization Hub for {region}: {str(e)}")
            return []
    
    def get_recommendation(self, recommendation_id, region='us-east-1'):
        """
        Get detailed recommendation information
        
        Args:
            recommendation_id: Unique identifier for the recommendation
            region: AWS region where the recommendation exists
            
        Returns:
            Dictionary with detailed recommendation data
        """
        if region not in self.supported_regions:
            _warn(f"Cost Optimization Hub not supported in region {region}")
            return {}
        
        try:
            client = self._get_client(region)
            if not client:
                return {}
            
            def _get_recommendation():
                response = client.get_recommendation(recommendationId=recommendation_id)
                recommendation = response.get('recommendation', {})
                
                # Add metadata
                recommendation['_region'] = region
                recommendation['_retrieved_at'] = datetime.now().isoformat()
                
                return recommendation
            
            return self._retry_with_backoff(_get_recommendation)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                _warn(f"Recommendation {recommendation_id} not found in region {region}")
                return {}
            elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
                _warn(f"Insufficient permissions to get recommendation details in {region}")
                return {}
            else:
                _warn(f"Error getting recommendation {recommendation_id}: {str(e)}")
                return {}
        except Exception as e:
            _warn(f"Unexpected error getting recommendation {recommendation_id}: {str(e)}")
            return {}
    
    def list_recommendations_multi_region(self, regions=None, max_results_per_region=100, filters=None):
        """
        Collect recommendations from multiple regions in parallel
        
        Args:
            regions: List of regions to query (defaults to all supported regions)
            max_results_per_region: Maximum recommendations per region
            filters: Optional filters to apply
            
        Returns:
            Dictionary mapping regions to their recommendations
        """
        if regions is None:
            regions = self.supported_regions
        
        # Filter to only supported regions
        valid_regions = [r for r in regions if r in self.supported_regions]
        
        if not valid_regions:
            _warn("No valid regions specified for Cost Optimization Hub")
            return {}
        
        results = {}
        
        # Use ThreadPoolExecutor for parallel collection
        with ThreadPoolExecutor(max_workers=min(len(valid_regions), 5)) as executor:
            # Submit tasks for each region
            future_to_region = {
                executor.submit(
                    self.list_recommendations, 
                    region, 
                    max_results_per_region, 
                    filters
                ): region 
                for region in valid_regions
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    recommendations = future.result(timeout=30)  # 30 second timeout per region
                    results[region] = recommendations
                    if recommendations:
                        _pr(f"Collected {len(recommendations)} recommendations from {region}")
                except Exception as e:
                    _warn(f"Failed to collect recommendations from {region}: {str(e)}")
                    results[region] = []
        
        return results
    
    def get_recommendation_summary(self, region='us-east-1'):
        """
        Get summary statistics for recommendations in a region
        
        Args:
            region: AWS region to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        try:
            recommendations = self.list_recommendations(region, max_results=1000)
            
            if not recommendations:
                return {
                    'total_count': 0,
                    'total_monthly_savings': 0.0,
                    'categories': {},
                    'implementation_efforts': {},
                    'region': region
                }
            
            # Calculate summary statistics
            total_savings = sum(float(rec.get('estimatedMonthlySavings', 0)) for rec in recommendations)
            
            # Group by category
            categories = {}
            for rec in recommendations:
                category = rec.get('category', 'unknown')
                if category not in categories:
                    categories[category] = {'count': 0, 'savings': 0.0}
                categories[category]['count'] += 1
                categories[category]['savings'] += float(rec.get('estimatedMonthlySavings', 0))
            
            # Group by implementation effort
            efforts = {}
            for rec in recommendations:
                effort = rec.get('implementationEffort', 'unknown')
                if effort not in efforts:
                    efforts[effort] = {'count': 0, 'savings': 0.0}
                efforts[effort]['count'] += 1
                efforts[effort]['savings'] += float(rec.get('estimatedMonthlySavings', 0))
            
            return {
                'total_count': len(recommendations),
                'total_monthly_savings': total_savings,
                'categories': categories,
                'implementation_efforts': efforts,
                'region': region,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            _warn(f"Error generating recommendation summary for {region}: {str(e)}")
            return {
                'total_count': 0,
                'total_monthly_savings': 0.0,
                'categories': {},
                'implementation_efforts': {},
                'region': region,
                'error': str(e)
            }
    
    def validate_region_support(self, region):
        """
        Validate if Cost Optimization Hub is supported in the given region
        
        Args:
            region: AWS region to validate
            
        Returns:
            Boolean indicating support status
        """
        return region in self.supported_regions
    
    def get_supported_regions(self):
        """
        Get list of regions where Cost Optimization Hub is available
        
        Returns:
            List of supported region names
        """
        return self.supported_regions.copy()
    
    def test_connectivity(self, region='us-east-1'):
        """
        Test connectivity and permissions for Cost Optimization Hub
        
        Args:
            region: AWS region to test
            
        Returns:
            Dictionary with test results
        """
        test_result = {
            'region': region,
            'supported': region in self.supported_regions,
            'accessible': False,
            'permissions_ok': False,
            'error': None,
            'tested_at': datetime.now().isoformat()
        }
        
        if not test_result['supported']:
            test_result['error'] = f"Cost Optimization Hub not supported in {region}"
            return test_result
        
        try:
            client = self._get_client(region)
            if not client:
                test_result['error'] = "Failed to create client"
                return test_result
            
            # Test with minimal API call
            response = client.list_recommendations(maxResults=1)
            test_result['accessible'] = True
            test_result['permissions_ok'] = True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            test_result['accessible'] = True  # We can reach the service
            
            if error_code == 'OptInRequiredException':
                test_result['error'] = "Cost Optimization Hub not enabled"
            elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
                test_result['error'] = "Insufficient permissions"
            else:
                test_result['error'] = f"API Error: {error_code}"
                
        except Exception as e:
            test_result['error'] = f"Connection error: {str(e)}"
        
        return test_result


class CostExplorerClient:
    """
    Enhanced client for AWS Cost Explorer API
    
    Provides comprehensive access to Cost Explorer recommendations including
    rightsizing, Reserved Instance analysis, usage forecasting, and trend analysis.
    """
    
    def __init__(self, session=None, retry_config=None):
        self.session = session or boto3.Session()
        self.client = None
        self.retry_config = retry_config or {
            'max_attempts': 3,
            'backoff_factor': 2,
            'initial_delay': 1
        }
        
    def _get_client(self):
        """Get Cost Explorer client (always us-east-1)"""
        if not self.client:
            ssBoto = Config.get('ssBoto')
            if ssBoto:
                self.client = ssBoto.client('ce', region_name='us-east-1')
            else:
                self.client = self.session.client('ce', region_name='us-east-1')
        return self.client
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        import time
        
        for attempt in range(self.retry_config['max_attempts']):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                # Don't retry on certain errors
                if error_code in ['AccessDeniedException', 'UnauthorizedOperation', 'ValidationException']:
                    raise e
                
                # Retry on throttling and temporary errors
                if error_code in ['Throttling', 'ThrottlingException', 'ServiceUnavailable', 'InternalServerError']:
                    if attempt < self.retry_config['max_attempts'] - 1:
                        delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                        _warn(f"Retrying Cost Explorer after {delay}s due to {error_code} (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue
                
                raise e
            except Exception as e:
                if attempt < self.retry_config['max_attempts'] - 1:
                    delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                    _warn(f"Retrying Cost Explorer after {delay}s due to unexpected error (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                raise e
        
        raise Exception(f"Max retry attempts ({self.retry_config['max_attempts']}) exceeded")
    
    def get_rightsizing_recommendations(self, service='AmazonEC2', lookback_days=30, recommendation_target='SAME_INSTANCE_FAMILY'):
        """
        Get EC2 rightsizing recommendations with enhanced configuration options
        
        Args:
            service: AWS service to analyze (default: AmazonEC2)
            lookback_days: Number of days to look back for usage analysis
            recommendation_target: Rightsizing target (SAME_INSTANCE_FAMILY, CROSS_INSTANCE_FAMILY)
            
        Returns:
            List of rightsizing recommendations with enhanced metadata
        """
        try:
            client = self._get_client()
            
            def _get_rightsizing():
                response = client.get_rightsizing_recommendation(
                    Service=service,
                    Configuration={
                        'BenefitsConsidered': True,
                        'RecommendationTarget': recommendation_target
                    }
                )
                
                recommendations = response.get('RightsizingRecommendations', [])
                
                # Enrich recommendations with additional metadata
                for rec in recommendations:
                    rec['_service'] = service
                    rec['_lookback_days'] = lookback_days
                    rec['_recommendation_target'] = recommendation_target
                    rec['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate additional metrics
                    current_instance = rec.get('CurrentInstance', {})
                    if current_instance:
                        rec['_current_monthly_cost'] = float(current_instance.get('MonthlyCost', 0))
                        rec['_utilization_average'] = self._calculate_average_utilization(current_instance)
                
                return recommendations
            
            return self._retry_with_backoff(_get_rightsizing)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for Cost Explorer rightsizing. Required: ce:GetRightsizingRecommendation")
                return []
            elif error_code == 'ValidationException':
                _warn(f"Invalid parameters for rightsizing recommendations: {e.response['Error']['Message']}")
                return []
            else:
                _warn(f"Error getting rightsizing recommendations: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in Cost Explorer rightsizing: {str(e)}")
            return []
    
    def get_reserved_instance_coverage(self, lookback_days=30, group_by_service=True):
        """
        Get Reserved Instance coverage analysis with enhanced grouping options
        
        Args:
            lookback_days: Number of days to analyze
            group_by_service: Whether to group results by AWS service
            
        Returns:
            List of RI coverage data with enhanced analysis
        """
        try:
            client = self._get_client()
            
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            
            def _get_ri_coverage():
                request_params = {
                    'TimePeriod': {
                        'Start': start_date,
                        'End': end_date
                    }
                }
                
                if group_by_service:
                    request_params['GroupBy'] = [
                        {
                            'Type': 'DIMENSION',
                            'Key': 'SERVICE'
                        }
                    ]
                
                response = client.get_reservation_coverage(**request_params)
                coverage_data = response.get('CoveragesByTime', [])
                
                # Enrich coverage data with analysis
                for coverage in coverage_data:
                    coverage['_lookback_days'] = lookback_days
                    coverage['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate coverage metrics
                    total = coverage.get('Total', {})
                    if total:
                        coverage['_coverage_percentage'] = self._calculate_coverage_percentage(total)
                        coverage['_potential_savings'] = self._estimate_ri_savings_potential(total)
                
                return coverage_data
            
            return self._retry_with_backoff(_get_ri_coverage)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for RI coverage analysis. Required: ce:GetReservationCoverage")
                return []
            else:
                _warn(f"Error getting RI coverage: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in RI coverage analysis: {str(e)}")
            return []
    
    def get_usage_forecast(self, metric='UnblendedCost', forecast_days=30, granularity='MONTHLY'):
        """
        Get usage and cost forecasting for trend analysis
        
        Args:
            metric: Metric to forecast (UnblendedCost, UsageQuantity, etc.)
            forecast_days: Number of days to forecast into the future
            granularity: Forecast granularity (DAILY, MONTHLY)
            
        Returns:
            Forecast data with trend analysis
        """
        try:
            client = self._get_client()
            
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=forecast_days)).strftime('%Y-%m-%d')
            
            def _get_forecast():
                response = client.get_cost_and_usage_with_resources(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity=granularity,
                    Metrics=[metric],
                    GroupBy=[
                        {
                            'Type': 'DIMENSION',
                            'Key': 'SERVICE'
                        }
                    ]
                )
                
                forecast_data = response.get('ResultsByTime', [])
                
                # Enrich with trend analysis
                for result in forecast_data:
                    result['_forecast_days'] = forecast_days
                    result['_metric'] = metric
                    result['_granularity'] = granularity
                    result['_retrieved_at'] = datetime.now().isoformat()
                
                return forecast_data
            
            return self._retry_with_backoff(_get_forecast)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for usage forecasting. Required: ce:GetCostAndUsageWithResources")
                return []
            else:
                _warn(f"Error getting usage forecast: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in usage forecasting: {str(e)}")
            return []
    
    def get_reservation_recommendations(self, service='AmazonEC2', lookback_days=60, term_in_years='ONE_YEAR', payment_option='NO_UPFRONT'):
        """
        Get Reserved Instance purchase recommendations
        
        Args:
            service: AWS service for RI recommendations
            lookback_days: Historical usage period to analyze
            term_in_years: RI term (ONE_YEAR, THREE_YEARS)
            payment_option: Payment option (NO_UPFRONT, PARTIAL_UPFRONT, ALL_UPFRONT)
            
        Returns:
            RI purchase recommendations with financial analysis
        """
        try:
            client = self._get_client()
            
            def _get_ri_recommendations():
                response = client.get_reservation_purchase_recommendation(
                    Service=service,
                    Configuration={
                        'LookbackPeriodInDays': str(lookback_days),
                        'TermInYears': term_in_years,
                        'PaymentOption': payment_option
                    }
                )
                
                recommendations = response.get('Recommendations', [])
                
                # Enrich with metadata
                for rec in recommendations:
                    rec['_service'] = service
                    rec['_lookback_days'] = lookback_days
                    rec['_term'] = term_in_years
                    rec['_payment_option'] = payment_option
                    rec['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate ROI metrics
                    if 'RecommendationDetails' in rec:
                        details = rec['RecommendationDetails']
                        rec['_estimated_roi'] = self._calculate_ri_roi(details)
                
                return recommendations
            
            return self._retry_with_backoff(_get_ri_recommendations)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for RI recommendations. Required: ce:GetReservationPurchaseRecommendation")
                return []
            else:
                _warn(f"Error getting RI recommendations: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in RI recommendations: {str(e)}")
            return []
    
    def get_cost_anomaly_detection(self, lookback_days=30):
        """
        Get cost anomaly detection results for identifying unusual spending patterns
        
        Args:
            lookback_days: Number of days to look back for anomalies
            
        Returns:
            List of detected cost anomalies
        """
        try:
            client = self._get_client()
            
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            
            def _get_anomalies():
                response = client.get_anomalies(
                    DateInterval={
                        'StartDate': start_date,
                        'EndDate': end_date
                    }
                )
                
                anomalies = response.get('Anomalies', [])
                
                # Enrich anomaly data
                for anomaly in anomalies:
                    anomaly['_lookback_days'] = lookback_days
                    anomaly['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate severity score
                    impact = anomaly.get('Impact', {})
                    anomaly['_severity_score'] = self._calculate_anomaly_severity(impact)
                
                return anomalies
            
            return self._retry_with_backoff(_get_anomalies)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for anomaly detection. Required: ce:GetAnomalies")
                return []
            else:
                _warn(f"Error getting cost anomalies: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in anomaly detection: {str(e)}")
            return []
    
    def _calculate_average_utilization(self, instance_data):
        """Calculate average utilization from instance metrics"""
        try:
            utilization = instance_data.get('ResourceUtilization', {})
            ec2_utilization = utilization.get('EC2ResourceUtilization', {})
            
            cpu_util = float(ec2_utilization.get('MaxCpuUtilizationPercentage', 0))
            memory_util = float(ec2_utilization.get('MaxMemoryUtilizationPercentage', 0))
            
            # Average of CPU and memory utilization
            if cpu_util > 0 and memory_util > 0:
                return (cpu_util + memory_util) / 2
            elif cpu_util > 0:
                return cpu_util
            elif memory_util > 0:
                return memory_util
            else:
                return 0
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _calculate_coverage_percentage(self, coverage_data):
        """Calculate RI coverage percentage"""
        try:
            covered_hours = float(coverage_data.get('CoverageHours', {}).get('CoveredHours', 0))
            total_hours = float(coverage_data.get('CoverageHours', {}).get('TotalRunningHours', 0))
            
            if total_hours > 0:
                return (covered_hours / total_hours) * 100
            return 0
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _estimate_ri_savings_potential(self, coverage_data):
        """Estimate potential savings from additional RI purchases"""
        try:
            uncovered_cost = float(coverage_data.get('CoverageCost', {}).get('OnDemandCost', 0))
            # Estimate 20-30% savings potential for uncovered usage
            return uncovered_cost * 0.25
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _calculate_ri_roi(self, recommendation_details):
        """Calculate ROI for RI recommendations"""
        try:
            estimated_savings = float(recommendation_details.get('EstimatedMonthlySavingsAmount', 0))
            upfront_cost = float(recommendation_details.get('UpfrontCost', 0))
            
            if upfront_cost > 0:
                # Calculate months to break even
                months_to_break_even = upfront_cost / estimated_savings if estimated_savings > 0 else float('inf')
                return {
                    'monthly_savings': estimated_savings,
                    'upfront_cost': upfront_cost,
                    'months_to_break_even': months_to_break_even,
                    'annual_roi_percentage': (estimated_savings * 12 / upfront_cost * 100) if upfront_cost > 0 else 0
                }
            else:
                return {
                    'monthly_savings': estimated_savings,
                    'upfront_cost': 0,
                    'months_to_break_even': 0,
                    'annual_roi_percentage': float('inf') if estimated_savings > 0 else 0
                }
        except (ValueError, TypeError, KeyError):
            return {
                'monthly_savings': 0,
                'upfront_cost': 0,
                'months_to_break_even': float('inf'),
                'annual_roi_percentage': 0
            }
    
    def _calculate_anomaly_severity(self, impact_data):
        """Calculate severity score for cost anomalies"""
        try:
            max_impact = float(impact_data.get('MaxImpact', 0))
            total_impact = float(impact_data.get('TotalImpact', 0))
            
            # Severity based on impact amount
            if max_impact >= 1000:
                return 'high'
            elif max_impact >= 100:
                return 'medium'
            elif max_impact > 0:
                return 'low'
            else:
                return 'none'
        except (ValueError, TypeError, KeyError):
            return 'unknown'
    
    def test_connectivity(self):
        """
        Test connectivity and permissions for Cost Explorer
        
        Returns:
            Dictionary with test results
        """
        test_result = {
            'service': 'cost_explorer',
            'accessible': False,
            'permissions_ok': False,
            'error': None,
            'tested_at': datetime.now().isoformat()
        }
        
        try:
            client = self._get_client()
            
            # Test with minimal API call
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            response = client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )
            
            test_result['accessible'] = True
            test_result['permissions_ok'] = True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            test_result['accessible'] = True  # We can reach the service
            
            if error_code == 'AccessDeniedException':
                test_result['error'] = "Insufficient permissions for Cost Explorer"
            else:
                test_result['error'] = f"API Error: {error_code}"
                
        except Exception as e:
            test_result['error'] = f"Connection error: {str(e)}"
        
        return test_result


class SavingsPlansClient:
    """
    Enhanced client for AWS Savings Plans API
    
    Provides comprehensive access to Savings Plans recommendations, coverage analysis,
    utilization tracking, and commitment optimization across different plan types.
    """
    
    def __init__(self, session=None, retry_config=None):
        self.session = session or boto3.Session()
        self.client = None
        self.ce_client = None  # Cost Explorer client for SP recommendations
        self.retry_config = retry_config or {
            'max_attempts': 3,
            'backoff_factor': 2,
            'initial_delay': 1
        }
        
    def _get_client(self):
        """Get Savings Plans client (always us-east-1)"""
        if not self.client:
            ssBoto = Config.get('ssBoto')
            if ssBoto:
                self.client = ssBoto.client('savingsplans', region_name='us-east-1')
            else:
                self.client = self.session.client('savingsplans', region_name='us-east-1')
        return self.client
    
    def _get_ce_client(self):
        """Get Cost Explorer client for Savings Plans recommendations"""
        if not self.ce_client:
            ssBoto = Config.get('ssBoto')
            if ssBoto:
                self.ce_client = ssBoto.client('ce', region_name='us-east-1')
            else:
                self.ce_client = self.session.client('ce', region_name='us-east-1')
        return self.ce_client
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        import time
        
        for attempt in range(self.retry_config['max_attempts']):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                # Don't retry on certain errors
                if error_code in ['AccessDeniedException', 'UnauthorizedOperation', 'ValidationException']:
                    raise e
                
                # Retry on throttling and temporary errors
                if error_code in ['Throttling', 'ThrottlingException', 'ServiceUnavailable', 'InternalServerError']:
                    if attempt < self.retry_config['max_attempts'] - 1:
                        delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                        _warn(f"Retrying Savings Plans after {delay}s due to {error_code} (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue
                
                raise e
            except Exception as e:
                if attempt < self.retry_config['max_attempts'] - 1:
                    delay = self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                    _warn(f"Retrying Savings Plans after {delay}s due to unexpected error (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                raise e
        
        raise Exception(f"Max retry attempts ({self.retry_config['max_attempts']}) exceeded")
    
    def get_savings_plans_purchase_recommendations(self, sp_type='COMPUTE_SP', term='ONE_YEAR', payment_option='NO_UPFRONT', lookback_days='SIXTY_DAYS'):
        """
        Get Savings Plans purchase recommendations with enhanced configuration options
        
        Args:
            sp_type: Type of Savings Plan (COMPUTE_SP, EC2_INSTANCE_SP)
            term: Term length (ONE_YEAR, THREE_YEARS)
            payment_option: Payment option (NO_UPFRONT, PARTIAL_UPFRONT, ALL_UPFRONT)
            lookback_days: Historical usage period (SEVEN_DAYS, THIRTY_DAYS, SIXTY_DAYS)
            
        Returns:
            Enhanced Savings Plans purchase recommendations
        """
        try:
            ce_client = self._get_ce_client()
            
            def _get_sp_recommendations():
                response = ce_client.get_savings_plans_purchase_recommendation(
                    SavingsPlansType=sp_type,
                    TermInYears=term,
                    PaymentOption=payment_option,
                    LookbackPeriodInDays=lookback_days
                )
                
                recommendation = response.get('SavingsPlanssPurchaseRecommendation', {})
                
                # Enrich with metadata
                recommendation['_sp_type'] = sp_type
                recommendation['_term'] = term
                recommendation['_payment_option'] = payment_option
                recommendation['_lookback_days'] = lookback_days
                recommendation['_retrieved_at'] = datetime.now().isoformat()
                
                # Calculate additional metrics
                if 'SavingsPlansDetails' in recommendation:
                    details = recommendation['SavingsPlansDetails']
                    recommendation['_roi_analysis'] = self._calculate_sp_roi(recommendation)
                    recommendation['_commitment_analysis'] = self._analyze_commitment_level(details)
                
                return recommendation
            
            return self._retry_with_backoff(_get_sp_recommendations)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for Savings Plans recommendations. Required: ce:GetSavingsPlanssPurchaseRecommendation")
                return {}
            elif error_code == 'ValidationException':
                _warn(f"Invalid parameters for Savings Plans recommendations: {e.response['Error']['Message']}")
                return {}
            else:
                _warn(f"Error getting Savings Plans recommendations: {str(e)}")
                return {}
        except Exception as e:
            _warn(f"Unexpected error in Savings Plans recommendations: {str(e)}")
            return {}
    
    def get_savings_plans_coverage(self, lookback_days=30, group_by_attributes=None):
        """
        Get Savings Plans coverage analysis with enhanced grouping options
        
        Args:
            lookback_days: Number of days to analyze
            group_by_attributes: List of attributes to group by (SERVICE, INSTANCE_TYPE, etc.)
            
        Returns:
            Enhanced Savings Plans coverage data
        """
        try:
            ce_client = self._get_ce_client()
            
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            
            def _get_sp_coverage():
                request_params = {
                    'TimePeriod': {
                        'Start': start_date,
                        'End': end_date
                    }
                }
                
                if group_by_attributes:
                    request_params['GroupBy'] = [
                        {
                            'Type': 'DIMENSION',
                            'Key': attr
                        } for attr in group_by_attributes
                    ]
                
                response = ce_client.get_savings_plans_coverage(**request_params)
                coverage_data = response.get('SavingsPlanssCoverages', [])
                
                # Enrich coverage data
                for coverage in coverage_data:
                    coverage['_lookback_days'] = lookback_days
                    coverage['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate coverage metrics
                    attributes = coverage.get('Attributes', {})
                    coverage['_coverage_percentage'] = self._calculate_sp_coverage_percentage(coverage)
                    coverage['_potential_savings'] = self._estimate_sp_savings_potential(coverage)
                
                return coverage_data
            
            return self._retry_with_backoff(_get_sp_coverage)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for Savings Plans coverage. Required: ce:GetSavingsPlansCoverage")
                return []
            else:
                _warn(f"Error getting Savings Plans coverage: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in Savings Plans coverage: {str(e)}")
            return []
    
    def get_savings_plans_utilization(self, lookback_days=30, granularity='MONTHLY'):
        """
        Get Savings Plans utilization tracking
        
        Args:
            lookback_days: Number of days to analyze
            granularity: Data granularity (DAILY, MONTHLY)
            
        Returns:
            Savings Plans utilization data with trend analysis
        """
        try:
            ce_client = self._get_ce_client()
            
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            
            def _get_sp_utilization():
                response = ce_client.get_savings_plans_utilization(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity=granularity
                )
                
                utilization_data = response.get('SavingsPlansUtilizationsByTime', [])
                
                # Enrich utilization data
                for util in utilization_data:
                    util['_lookback_days'] = lookback_days
                    util['_granularity'] = granularity
                    util['_retrieved_at'] = datetime.now().isoformat()
                    
                    # Calculate utilization metrics
                    total = util.get('Total', {})
                    util['_utilization_percentage'] = self._calculate_sp_utilization_percentage(total)
                    util['_efficiency_score'] = self._calculate_sp_efficiency_score(total)
                
                return utilization_data
            
            return self._retry_with_backoff(_get_sp_utilization)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions for Savings Plans utilization. Required: ce:GetSavingsPlansUtilization")
                return []
            else:
                _warn(f"Error getting Savings Plans utilization: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error in Savings Plans utilization: {str(e)}")
            return []
    
    def describe_savings_plans(self, sp_ids=None, states=None):
        """
        Describe existing Savings Plans with enhanced filtering
        
        Args:
            sp_ids: List of Savings Plan IDs to describe
            states: List of states to filter by (active, retired, etc.)
            
        Returns:
            List of existing Savings Plans with enhanced metadata
        """
        try:
            client = self._get_client()
            
            def _describe_savings_plans():
                request_params = {}
                
                if sp_ids:
                    request_params['savingsPlanIds'] = sp_ids
                
                if states:
                    request_params['states'] = states
                
                response = client.describe_savings_plans(**request_params)
                savings_plans = response.get('savingsPlans', [])
                
                # Enrich Savings Plans data
                for sp in savings_plans:
                    sp['_retrieved_at'] = datetime.now().isoformat()
                    sp['_commitment_analysis'] = self._analyze_existing_sp_commitment(sp)
                    sp['_performance_metrics'] = self._calculate_sp_performance_metrics(sp)
                
                return savings_plans
            
            return self._retry_with_backoff(_describe_savings_plans)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                _warn("Insufficient permissions to describe Savings Plans. Required: savingsplans:DescribeSavingsPlans")
                return []
            else:
                _warn(f"Error describing Savings Plans: {str(e)}")
                return []
        except Exception as e:
            _warn(f"Unexpected error describing Savings Plans: {str(e)}")
            return []
    
    def get_comprehensive_sp_analysis(self):
        """
        Get comprehensive Savings Plans analysis combining all data sources
        
        Returns:
            Dictionary with complete Savings Plans analysis
        """
        try:
            analysis = {
                'purchase_recommendations': {},
                'coverage_analysis': [],
                'utilization_tracking': [],
                'existing_plans': [],
                'optimization_opportunities': []
            }
            
            # Get purchase recommendations for different configurations
            sp_configs = [
                {'sp_type': 'COMPUTE_SP', 'term': 'ONE_YEAR', 'payment': 'NO_UPFRONT'},
                {'sp_type': 'COMPUTE_SP', 'term': 'THREE_YEARS', 'payment': 'NO_UPFRONT'},
                {'sp_type': 'EC2_INSTANCE_SP', 'term': 'ONE_YEAR', 'payment': 'NO_UPFRONT'}
            ]
            
            for config in sp_configs:
                key = f"{config['sp_type']}_{config['term']}_{config['payment']}"
                analysis['purchase_recommendations'][key] = self.get_savings_plans_purchase_recommendations(
                    sp_type=config['sp_type'],
                    term=config['term'],
                    payment_option=config['payment']
                )
            
            # Get coverage analysis
            analysis['coverage_analysis'] = self.get_savings_plans_coverage(
                lookback_days=30,
                group_by_attributes=['SERVICE']
            )
            
            # Get utilization tracking
            analysis['utilization_tracking'] = self.get_savings_plans_utilization(
                lookback_days=30,
                granularity='MONTHLY'
            )
            
            # Get existing Savings Plans
            analysis['existing_plans'] = self.describe_savings_plans(
                states=['active', 'payment-pending']
            )
            
            # Analyze optimization opportunities
            analysis['optimization_opportunities'] = self._identify_sp_optimization_opportunities(analysis)
            
            # Add analysis metadata
            analysis['_analysis_timestamp'] = datetime.now().isoformat()
            analysis['_total_recommendations'] = sum(
                1 for rec in analysis['purchase_recommendations'].values() if rec
            ) + len(analysis['optimization_opportunities'])
            
            return analysis
            
        except Exception as e:
            _warn(f"Error in comprehensive Savings Plans analysis: {str(e)}")
            return {
                'purchase_recommendations': {},
                'coverage_analysis': [],
                'utilization_tracking': [],
                'existing_plans': [],
                'optimization_opportunities': [],
                '_error': str(e)
            }
    
    def _calculate_sp_roi(self, recommendation):
        """Calculate ROI for Savings Plans recommendations"""
        try:
            estimated_savings = float(recommendation.get('EstimatedMonthlySavings', 0))
            details = recommendation.get('SavingsPlansDetails', {})
            hourly_commitment = float(details.get('HourlyCommitment', 0))
            
            # Calculate annual commitment and savings
            annual_commitment = hourly_commitment * 24 * 365
            annual_savings = estimated_savings * 12
            
            roi_percentage = (annual_savings / annual_commitment * 100) if annual_commitment > 0 else 0
            
            return {
                'monthly_savings': estimated_savings,
                'annual_savings': annual_savings,
                'hourly_commitment': hourly_commitment,
                'annual_commitment': annual_commitment,
                'roi_percentage': roi_percentage,
                'payback_period_months': (annual_commitment / annual_savings * 12) if annual_savings > 0 else float('inf')
            }
        except (ValueError, TypeError, KeyError):
            return {
                'monthly_savings': 0,
                'annual_savings': 0,
                'hourly_commitment': 0,
                'annual_commitment': 0,
                'roi_percentage': 0,
                'payback_period_months': float('inf')
            }
    
    def _analyze_commitment_level(self, details):
        """Analyze Savings Plans commitment level and recommendations"""
        try:
            hourly_commitment = float(details.get('HourlyCommitment', 0))
            
            # Categorize commitment level
            if hourly_commitment >= 10:
                commitment_level = 'high'
            elif hourly_commitment >= 1:
                commitment_level = 'medium'
            else:
                commitment_level = 'low'
            
            return {
                'hourly_commitment': hourly_commitment,
                'commitment_level': commitment_level,
                'monthly_commitment': hourly_commitment * 24 * 30,
                'annual_commitment': hourly_commitment * 24 * 365
            }
        except (ValueError, TypeError, KeyError):
            return {
                'hourly_commitment': 0,
                'commitment_level': 'unknown',
                'monthly_commitment': 0,
                'annual_commitment': 0
            }
    
    def _calculate_sp_coverage_percentage(self, coverage_data):
        """Calculate Savings Plans coverage percentage"""
        try:
            coverage = coverage_data.get('Coverage', {})
            covered_hours = float(coverage.get('CoverageHours', {}).get('CoveredHours', 0))
            total_hours = float(coverage.get('CoverageHours', {}).get('TotalRunningHours', 0))
            
            if total_hours > 0:
                return (covered_hours / total_hours) * 100
            return 0
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _estimate_sp_savings_potential(self, coverage_data):
        """Estimate potential savings from additional Savings Plans"""
        try:
            coverage = coverage_data.get('Coverage', {})
            uncovered_cost = float(coverage.get('CoverageCost', {}).get('OnDemandCost', 0))
            # Estimate 10-20% savings potential for uncovered usage
            return uncovered_cost * 0.15
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _calculate_sp_utilization_percentage(self, utilization_data):
        """Calculate Savings Plans utilization percentage"""
        try:
            utilization = utilization_data.get('Utilization', {})
            used_commitment = float(utilization.get('UsedCommitment', 0))
            total_commitment = float(utilization.get('TotalCommitment', 0))
            
            if total_commitment > 0:
                return (used_commitment / total_commitment) * 100
            return 0
        except (ValueError, TypeError, KeyError):
            return 0
    
    def _calculate_sp_efficiency_score(self, utilization_data):
        """Calculate Savings Plans efficiency score"""
        try:
            utilization_pct = self._calculate_sp_utilization_percentage(utilization_data)
            
            # Efficiency score based on utilization
            if utilization_pct >= 95:
                return 'excellent'
            elif utilization_pct >= 80:
                return 'good'
            elif utilization_pct >= 60:
                return 'fair'
            else:
                return 'poor'
        except Exception:
            return 'unknown'
    
    def _analyze_existing_sp_commitment(self, savings_plan):
        """Analyze existing Savings Plan commitment and performance"""
        try:
            commitment = float(savings_plan.get('commitment', 0))
            state = savings_plan.get('state', 'unknown')
            
            return {
                'commitment_amount': commitment,
                'state': state,
                'start_time': savings_plan.get('start', 'unknown'),
                'end_time': savings_plan.get('end', 'unknown'),
                'sp_type': savings_plan.get('savingsPlanType', 'unknown'),
                'payment_option': savings_plan.get('paymentOption', 'unknown')
            }
        except (ValueError, TypeError, KeyError):
            return {
                'commitment_amount': 0,
                'state': 'unknown',
                'start_time': 'unknown',
                'end_time': 'unknown',
                'sp_type': 'unknown',
                'payment_option': 'unknown'
            }
    
    def _calculate_sp_performance_metrics(self, savings_plan):
        """Calculate performance metrics for existing Savings Plans"""
        try:
            # This would typically require additional API calls to get utilization data
            # For now, return placeholder structure
            return {
                'utilization_trend': 'stable',
                'savings_realized': 0,
                'efficiency_rating': 'unknown'
            }
        except Exception:
            return {
                'utilization_trend': 'unknown',
                'savings_realized': 0,
                'efficiency_rating': 'unknown'
            }
    
    def _identify_sp_optimization_opportunities(self, analysis):
        """Identify Savings Plans optimization opportunities"""
        opportunities = []
        
        try:
            # Analyze existing plans for optimization
            existing_plans = analysis.get('existing_plans', [])
            utilization_data = analysis.get('utilization_tracking', [])
            
            # Check for underutilized plans
            for util in utilization_data:
                util_pct = util.get('_utilization_percentage', 0)
                if util_pct < 80:
                    opportunities.append({
                        'type': 'underutilization',
                        'description': f"Savings Plan utilization at {util_pct:.1f}% - consider rightsizing",
                        'impact': 'medium',
                        'action': 'Review usage patterns and consider plan modification'
                    })
            
            # Check for coverage gaps
            coverage_data = analysis.get('coverage_analysis', [])
            for coverage in coverage_data:
                coverage_pct = coverage.get('_coverage_percentage', 0)
                if coverage_pct < 70:
                    opportunities.append({
                        'type': 'coverage_gap',
                        'description': f"Low Savings Plans coverage at {coverage_pct:.1f}%",
                        'impact': 'high',
                        'action': 'Consider additional Savings Plans purchase'
                    })
            
        except Exception as e:
            _warn(f"Error identifying SP optimization opportunities: {str(e)}")
        
        return opportunities
    
    def test_connectivity(self):
        """
        Test connectivity and permissions for Savings Plans
        
        Returns:
            Dictionary with test results
        """
        test_result = {
            'service': 'savings_plans',
            'accessible': False,
            'permissions_ok': False,
            'error': None,
            'tested_at': datetime.now().isoformat()
        }
        
        try:
            client = self._get_client()
            
            # Test with minimal API call
            response = client.describe_savings_plans(maxResults=1)
            test_result['accessible'] = True
            test_result['permissions_ok'] = True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            test_result['accessible'] = True  # We can reach the service
            
            if error_code == 'AccessDeniedException':
                test_result['error'] = "Insufficient permissions for Savings Plans"
            else:
                test_result['error'] = f"API Error: {error_code}"
                
        except Exception as e:
            test_result['error'] = f"Connection error: {str(e)}"
        
        return test_result


class COH(CustomObject):
    """
    Cost Optimization Hub main class
    
    Inherits from CustomObject to integrate with Service Screener's CustomPage infrastructure.
    Collects and processes cost optimization data from multiple AWS sources.
    """
    
    def __init__(self):
        super().__init__()
        self.coh_client = CostOptimizationHubClient()
        self.ce_client = CostExplorerClient()
        self.sp_client = SavingsPlansClient()
        
        # Data storage
        self.recommendations = []
        self.executive_summary = None
        self.error_messages = []
        self.data_collection_time = None
        
        # Configuration
        self.regions = Config.get('regions', ['us-east-1'])
        self.max_recommendations = 1000
        
    def build(self):
        """
        Main build method called by CustomPage infrastructure
        Collects data from all cost optimization sources
        """
        print("... Running Cost Optimization Hub data collection")
        start_time = datetime.now()
        
        try:
            # Collect data from all sources in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._collect_coh_data): 'coh',
                    executor.submit(self._collect_cost_explorer_data): 'cost_explorer',
                    executor.submit(self._collect_savings_plans_data): 'savings_plans'
                }
                
                raw_data = {}
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        raw_data[source] = future.result()
                    except Exception as e:
                        self.error_messages.append(f"Error collecting {source} data: {str(e)}")
                        raw_data[source] = []
            
            # Process and normalize all recommendations
            self.recommendations = self._process_all_recommendations(raw_data)
            
            # Generate executive summary
            self.executive_summary = self._generate_executive_summary()
            
            self.data_collection_time = datetime.now() - start_time
            print(f"... COH data collection completed in {self.data_collection_time.total_seconds():.2f} seconds")
            print(f"... Collected {len(self.recommendations)} cost optimization recommendations")
            
        except Exception as e:
            error_msg = f"Critical error in COH data collection: {str(e)}"
            self.error_messages.append(error_msg)
            _warn(error_msg)
    
    def _collect_coh_data(self):
        """Collect data from Cost Optimization Hub API with enhanced multi-region support"""
        try:
            # Use multi-region collection for better performance
            all_recommendations = []
            
            # Filter regions to only those supported by COH
            coh_regions = [r for r in self.regions if self.coh_client.validate_region_support(r)]
            
            if not coh_regions:
                _warn("No supported regions found for Cost Optimization Hub")
                return []
            
            # Collect from all supported regions in parallel
            regional_data = self.coh_client.list_recommendations_multi_region(
                regions=coh_regions,
                max_results_per_region=self.max_recommendations // max(len(coh_regions), 1),
                filters={
                    'categories': ['COMPUTE', 'STORAGE', 'DATABASE'],  # Focus on major categories
                    'implementationEfforts': ['VERY_LOW', 'LOW', 'MEDIUM']  # Prioritize easier implementations
                }
            )
            
            # Flatten results and add enrichment
            for region, recommendations in regional_data.items():
                for rec in recommendations:
                    # Enrich with additional metadata
                    rec['_collection_timestamp'] = datetime.now().isoformat()
                    rec['_source_region'] = region
                    
                    # Get detailed information for high-value recommendations
                    if float(rec.get('estimatedMonthlySavings', 0)) > 100:  # $100+ monthly savings
                        detailed_rec = self.coh_client.get_recommendation(
                            rec.get('recommendationId', ''), 
                            region
                        )
                        if detailed_rec:
                            rec.update(detailed_rec)
                    
                    all_recommendations.append(rec)
            
            # Sort by savings potential (highest first)
            all_recommendations.sort(
                key=lambda x: float(x.get('estimatedMonthlySavings', 0)), 
                reverse=True
            )
            
            # Limit to max recommendations
            if len(all_recommendations) > self.max_recommendations:
                all_recommendations = all_recommendations[:self.max_recommendations]
            
            _pr(f"Collected {len(all_recommendations)} COH recommendations from {len(coh_regions)} regions")
            return all_recommendations
            
        except Exception as e:
            error_msg = f"Error collecting Cost Optimization Hub data: {str(e)}"
            self.error_messages.append(error_msg)
            _warn(error_msg)
            return []
    
    def _collect_cost_explorer_data(self):
        """Collect data from Cost Explorer API with enhanced functionality and processing"""
        try:
            data = {
                'rightsizing': [],
                'ri_coverage': [],
                'ri_recommendations': [],
                'usage_forecast': [],
                'cost_anomalies': [],
                'processed_anomalies': [],
                'trend_recommendations': []
            }
            
            # Collect rightsizing recommendations with different targets
            rightsizing_same_family = self.ce_client.get_rightsizing_recommendations(
                recommendation_target='SAME_INSTANCE_FAMILY'
            )
            rightsizing_cross_family = self.ce_client.get_rightsizing_recommendations(
                recommendation_target='CROSS_INSTANCE_FAMILY'
            )
            
            # Combine and deduplicate rightsizing recommendations
            all_rightsizing = rightsizing_same_family + rightsizing_cross_family
            seen_instances = set()
            unique_rightsizing = []
            
            for rec in all_rightsizing:
                instance_id = rec.get('CurrentInstance', {}).get('ResourceId', '')
                if instance_id and instance_id not in seen_instances:
                    seen_instances.add(instance_id)
                    unique_rightsizing.append(rec)
            
            data['rightsizing'] = unique_rightsizing
            
            # Collect RI coverage analysis
            data['ri_coverage'] = self.ce_client.get_reserved_instance_coverage(
                lookback_days=30,
                group_by_service=True
            )
            
            # Collect RI purchase recommendations
            data['ri_recommendations'] = self.ce_client.get_reservation_recommendations(
                service='AmazonEC2',
                lookback_days=60,
                term_in_years='ONE_YEAR',
                payment_option='NO_UPFRONT'
            )
            
            # Collect usage forecast for trend analysis
            forecast_data = self.ce_client.get_usage_forecast(
                metric='UnblendedCost',
                forecast_days=30,
                granularity='MONTHLY'
            )
            data['usage_forecast'] = forecast_data
            
            # Collect and process cost anomalies
            raw_anomalies = self.ce_client.get_cost_anomaly_detection(lookback_days=30)
            data['cost_anomalies'] = raw_anomalies
            
            # Process anomalies into actionable recommendations
            data['processed_anomalies'] = self.process_cost_anomalies(raw_anomalies)
            
            # Analyze usage trends for optimization opportunities
            data['trend_recommendations'] = self.analyze_usage_trends(forecast_data)
            
            # Add collection metadata
            data['_collection_timestamp'] = datetime.now().isoformat()
            data['_total_recommendations'] = (
                len(data['rightsizing']) + 
                len(data['ri_recommendations']) +
                len(data['processed_anomalies']) +
                len(data['trend_recommendations'])
            )
            
            _pr(f"Collected Cost Explorer data: {data['_total_recommendations']} recommendations, "
                f"{len(data['cost_anomalies'])} anomalies, {len(data['trend_recommendations'])} trend analyses")
            
            return data
            
        except Exception as e:
            error_msg = f"Error collecting Cost Explorer data: {str(e)}"
            self.error_messages.append(error_msg)
            _warn(error_msg)
            return {
                'rightsizing': [],
                'ri_coverage': [],
                'ri_recommendations': [],
                'usage_forecast': [],
                'cost_anomalies': [],
                'processed_anomalies': [],
                'trend_recommendations': [],
                '_error': error_msg
            }
    
    def _collect_savings_plans_data(self):
        """Collect data from Savings Plans API with comprehensive analysis"""
        try:
            # Get comprehensive Savings Plans analysis
            comprehensive_analysis = self.sp_client.get_comprehensive_sp_analysis()
            
            # Extract and organize the data
            data = {
                'purchase_recommendations': comprehensive_analysis.get('purchase_recommendations', {}),
                'coverage_analysis': comprehensive_analysis.get('coverage_analysis', []),
                'utilization_tracking': comprehensive_analysis.get('utilization_tracking', []),
                'existing_plans': comprehensive_analysis.get('existing_plans', []),
                'optimization_opportunities': comprehensive_analysis.get('optimization_opportunities', [])
            }
            
            # Process purchase recommendations into standardized format
            processed_recommendations = []
            for config_key, recommendation in data['purchase_recommendations'].items():
                if recommendation and recommendation.get('EstimatedMonthlySavings', 0) > 0:
                    # Convert to standard recommendation format
                    processed_rec = self._convert_sp_recommendation_to_standard(recommendation, config_key)
                    if processed_rec:
                        processed_recommendations.append(processed_rec)
            
            data['processed_recommendations'] = processed_recommendations
            
            # Process optimization opportunities into recommendations
            optimization_recs = []
            for opportunity in data['optimization_opportunities']:
                opt_rec = self._convert_sp_opportunity_to_recommendation(opportunity)
                if opt_rec:
                    optimization_recs.append(opt_rec)
            
            data['optimization_recommendations'] = optimization_recs
            
            # Add collection metadata
            data['_collection_timestamp'] = datetime.now().isoformat()
            data['_total_recommendations'] = len(processed_recommendations) + len(optimization_recs)
            data['_existing_plans_count'] = len(data['existing_plans'])
            
            _pr(f"Collected Savings Plans data: {data['_total_recommendations']} recommendations, "
                f"{data['_existing_plans_count']} existing plans")
            
            return data
            
        except Exception as e:
            error_msg = f"Error collecting Savings Plans data: {str(e)}"
            self.error_messages.append(error_msg)
            _warn(error_msg)
            return {
                'purchase_recommendations': {},
                'coverage_analysis': [],
                'utilization_tracking': [],
                'existing_plans': [],
                'optimization_opportunities': [],
                'processed_recommendations': [],
                'optimization_recommendations': [],
                '_error': error_msg
            }
    
    def _process_all_recommendations(self, raw_data):
        """Process and normalize recommendations from all sources with enhanced validation"""
        # Use the new validation-aware processing method
        processed_recommendations, processing_stats = self.process_recommendations_with_validation(raw_data)
        
        # Store processing statistics for later analysis
        self._processing_stats = processing_stats
        
        # Log processing results
        _pr(f"Processed {processing_stats['valid_processed']} valid recommendations from {processing_stats['total_input']} total inputs")
        
        if processing_stats['invalid_skipped'] > 0:
            _warn(f"Skipped {processing_stats['invalid_skipped']} invalid recommendations")
        
        if processing_stats['validation_errors']:
            _warn(f"Encountered {len(processing_stats['validation_errors'])} validation errors")
            # Log first few errors for debugging
            for error in processing_stats['validation_errors'][:5]:
                _warn(f"  - {error}")
        
        return processed_recommendations
    
    def _normalize_coh_recommendation(self, rec):
        """Normalize Cost Optimization Hub recommendation to unified format with enhanced data processing"""
        try:
            # Extract basic information
            recommendation_id = rec.get('recommendationId', '')
            category = rec.get('category', 'general').lower()
            source_service = rec.get('source', 'unknown').lower()
            
            # Map category to our standard categories
            category_mapping = {
                'compute': 'compute',
                'storage': 'storage', 
                'database': 'database',
                'networking': 'networking',
                'cost_optimization': 'general'
            }
            normalized_category = category_mapping.get(category, 'general')
            
            # Extract financial information
            monthly_savings = float(rec.get('estimatedMonthlySavings', 0))
            annual_savings = monthly_savings * 12
            
            # Map implementation effort
            effort_mapping = {
                'VERY_LOW': 'low',
                'LOW': 'low',
                'MEDIUM': 'medium',
                'HIGH': 'high',
                'VERY_HIGH': 'high'
            }
            implementation_effort = effort_mapping.get(
                rec.get('implementationEffort', 'MEDIUM'), 
                'medium'
            )
            
            # Extract resource information
            affected_resources = []
            resource_count = rec.get('resourceCount', 0)
            
            # Process resource details if available
            if 'resources' in rec:
                for resource in rec['resources'][:10]:  # Limit to first 10 resources
                    affected_resources.append({
                        'id': resource.get('resourceId', ''),
                        'type': resource.get('resourceType', ''),
                        'region': resource.get('region', rec.get('_source_region', '')),
                        'tags': resource.get('tags', {})
                    })
            
            # Generate implementation steps based on category and service
            implementation_steps = self._generate_implementation_steps(
                normalized_category, 
                source_service, 
                rec
            )
            
            # Determine required permissions
            required_permissions = self._get_required_permissions(
                normalized_category,
                source_service
            )
            
            # Assess potential risks
            potential_risks = self._assess_potential_risks(
                normalized_category,
                implementation_effort,
                monthly_savings
            )
            
            # Determine confidence level based on data quality
            confidence_level = self._calculate_confidence_level(rec)
            
            return CostRecommendation(
                id=recommendation_id,
                source='coh',
                category=normalized_category,
                service=source_service,
                title=rec.get('name', 'Cost Optimization Recommendation'),
                description=rec.get('description', 'No description available'),
                monthly_savings=monthly_savings,
                annual_savings=annual_savings,
                confidence_level=confidence_level,
                implementation_effort=implementation_effort,
                implementation_steps=implementation_steps,
                required_permissions=required_permissions,
                potential_risks=potential_risks,
                affected_resources=affected_resources,
                resource_count=resource_count,
                priority_score=0.0,  # Will be calculated later
                priority_level='medium',  # Will be calculated later
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
            
        except Exception as e:
            _warn(f"Error normalizing COH recommendation {rec.get('recommendationId', 'unknown')}: {str(e)}")
            return None
    
    def _generate_implementation_steps(self, category, service, rec):
        """Generate implementation steps based on recommendation type"""
        base_steps = [
            "Review recommendation details and affected resources",
            "Assess impact on current operations and dependencies",
            "Plan implementation during appropriate maintenance window"
        ]
        
        category_steps = {
            'compute': [
                "Analyze current instance utilization patterns",
                "Test application performance with recommended changes",
                "Update auto-scaling policies if applicable",
                "Monitor performance metrics after implementation"
            ],
            'storage': [
                "Analyze storage access patterns and lifecycle policies",
                "Test data retrieval performance with new storage class",
                "Update backup and archival procedures",
                "Monitor storage costs and access patterns"
            ],
            'database': [
                "Review database performance metrics and query patterns",
                "Test application compatibility with recommended changes",
                "Update connection strings and configurations",
                "Monitor database performance and costs"
            ],
            'networking': [
                "Analyze network traffic patterns and bandwidth usage",
                "Test connectivity and latency with recommended changes",
                "Update security groups and routing tables",
                "Monitor network performance and costs"
            ]
        }
        
        steps = base_steps + category_steps.get(category, [])
        steps.append("Document changes and update operational procedures")
        
        return steps
    
    def _get_required_permissions(self, category, service):
        """Determine required IAM permissions based on recommendation type"""
        base_permissions = [
            'iam:GetRole',
            'iam:ListRoles',
            'tag:GetResources'
        ]
        
        service_permissions = {
            'ec2': [
                'ec2:DescribeInstances',
                'ec2:ModifyInstanceAttribute',
                'ec2:StopInstances',
                'ec2:StartInstances',
                'ec2:DescribeInstanceTypes'
            ],
            's3': [
                's3:GetBucketLocation',
                's3:GetBucketVersioning',
                's3:PutBucketVersioning',
                's3:PutLifecycleConfiguration'
            ],
            'rds': [
                'rds:DescribeDBInstances',
                'rds:ModifyDBInstance',
                'rds:DescribeDBClusters',
                'rds:ModifyDBCluster'
            ],
            'lambda': [
                'lambda:GetFunction',
                'lambda:UpdateFunctionConfiguration',
                'lambda:ListFunctions'
            ]
        }
        
        permissions = base_permissions + service_permissions.get(service, [])
        return list(set(permissions))  # Remove duplicates
    
    def _assess_potential_risks(self, category, effort, savings):
        """Assess potential risks based on recommendation characteristics"""
        risks = []
        
        # Risk based on implementation effort
        if effort == 'high':
            risks.extend([
                "Complex implementation may require extended maintenance window",
                "Higher chance of configuration errors or service disruption"
            ])
        elif effort == 'medium':
            risks.append("Moderate implementation complexity requires careful planning")
        
        # Risk based on savings amount (higher savings often mean bigger changes)
        if savings > 500:
            risks.append("High-impact change requires thorough testing and rollback plan")
        
        # Category-specific risks
        category_risks = {
            'compute': [
                "Potential performance impact during instance type changes",
                "Application compatibility issues with new instance types"
            ],
            'storage': [
                "Data retrieval latency changes with different storage classes",
                "Potential data access pattern disruption"
            ],
            'database': [
                "Database performance impact during configuration changes",
                "Application connection and query performance effects"
            ],
            'networking': [
                "Network connectivity disruption during changes",
                "Security group and routing configuration impacts"
            ]
        }
        
        risks.extend(category_risks.get(category, []))
        
        # Always include general risks
        risks.extend([
            "Cost savings estimates are projections and may vary",
            "Changes should be tested in non-production environment first"
        ])
        
        return list(set(risks))  # Remove duplicates
    
    def _calculate_confidence_level(self, rec):
        """Calculate confidence level based on data quality and completeness"""
        confidence_score = 0
        
        # Check data completeness
        if rec.get('estimatedMonthlySavings', 0) > 0:
            confidence_score += 2
        
        if rec.get('resourceCount', 0) > 0:
            confidence_score += 1
            
        if rec.get('description'):
            confidence_score += 1
            
        if rec.get('implementationEffort'):
            confidence_score += 1
            
        # Check if we have detailed resource information
        if 'resources' in rec and rec['resources']:
            confidence_score += 2
            
        # Check data freshness
        if rec.get('_collection_timestamp'):
            confidence_score += 1
        
        # Map score to confidence level
        if confidence_score >= 6:
            return 'high'
        elif confidence_score >= 4:
            return 'medium'
        else:
            return 'low'
    
    def _normalize_ce_recommendation(self, rec):
        """Normalize Cost Explorer recommendation to unified format with enhanced processing"""
        try:
            current_instance = rec.get('CurrentInstance', {})
            recommended_instance = rec.get('RightsizingRecommendation', {})
            
            # Extract instance information
            resource_id = current_instance.get('ResourceId', 'unknown')
            instance_name = current_instance.get('InstanceName', 'EC2 Instance')
            current_type = current_instance.get('InstanceType', 'unknown')
            
            # Extract financial information
            monthly_savings = 0
            if 'EstimatedMonthlySavings' in rec:
                monthly_savings = float(rec['EstimatedMonthlySavings'])
            elif current_instance.get('MonthlyCost'):
                # Calculate savings from cost difference if available
                current_cost = float(current_instance.get('MonthlyCost', 0))
                recommended_cost = float(recommended_instance.get('EstimatedMonthlyCost', current_cost))
                monthly_savings = max(0, current_cost - recommended_cost)
            
            # Extract utilization information
            utilization_data = current_instance.get('ResourceUtilization', {}).get('EC2ResourceUtilization', {})
            cpu_utilization = float(utilization_data.get('MaxCpuUtilizationPercentage', 0))
            memory_utilization = float(utilization_data.get('MaxMemoryUtilizationPercentage', 0))
            
            # Determine recommendation type and effort
            recommendation_type = rec.get('RightsizingType', 'Modify')
            if recommendation_type == 'Terminate':
                implementation_effort = 'low'
                title = f"Terminate underutilized instance {instance_name}"
                description = f"Instance {resource_id} shows very low utilization and can be terminated"
            elif recommendation_type == 'Modify':
                implementation_effort = 'medium'
                recommended_type = recommended_instance.get('InstanceType', 'smaller instance')
                title = f"Rightsize {instance_name} from {current_type} to {recommended_type}"
                description = f"Instance {resource_id} can be rightsized to optimize costs while maintaining performance"
            else:
                implementation_effort = 'medium'
                title = f"Optimize {instance_name}"
                description = f"Cost optimization opportunity identified for instance {resource_id}"
            
            # Generate detailed implementation steps
            implementation_steps = self._generate_ce_implementation_steps(
                recommendation_type, 
                current_type, 
                recommended_instance.get('InstanceType', ''),
                cpu_utilization,
                memory_utilization
            )
            
            # Assess confidence level based on utilization data
            confidence_level = self._assess_ce_confidence_level(
                cpu_utilization, 
                memory_utilization, 
                monthly_savings,
                rec.get('_lookback_days', 30)
            )
            
            # Create affected resources list
            affected_resources = [{
                'id': resource_id,
                'type': 'EC2Instance',
                'current_instance_type': current_type,
                'recommended_instance_type': recommended_instance.get('InstanceType', ''),
                'region': current_instance.get('Region', ''),
                'cpu_utilization': cpu_utilization,
                'memory_utilization': memory_utilization,
                'monthly_cost': current_instance.get('MonthlyCost', 0),
                'tags': current_instance.get('Tags', [])
            }]
            
            # Determine potential risks based on recommendation type
            potential_risks = self._assess_ce_risks(
                recommendation_type,
                cpu_utilization,
                memory_utilization,
                monthly_savings
            )
            
            return CostRecommendation(
                id=f"ce_{resource_id}",
                source='cost_explorer',
                category='compute',
                service='ec2',
                title=title,
                description=description,
                monthly_savings=monthly_savings,
                annual_savings=monthly_savings * 12,
                confidence_level=confidence_level,
                implementation_effort=implementation_effort,
                implementation_steps=implementation_steps,
                required_permissions=[
                    'ec2:DescribeInstances',
                    'ec2:ModifyInstanceAttribute',
                    'ec2:StopInstances',
                    'ec2:StartInstances',
                    'ec2:TerminateInstances' if recommendation_type == 'Terminate' else 'ec2:DescribeInstanceTypes'
                ],
                potential_risks=potential_risks,
                affected_resources=affected_resources,
                resource_count=1,
                priority_score=0.0,  # Will be calculated later
                priority_level='medium',  # Will be calculated later
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
            
        except Exception as e:
            _warn(f"Error normalizing Cost Explorer recommendation: {str(e)}")
            return None
    
    def _generate_ce_implementation_steps(self, rec_type, current_type, recommended_type, cpu_util, memory_util):
        """Generate detailed implementation steps for Cost Explorer recommendations"""
        base_steps = [
            "Review current instance utilization patterns and performance metrics",
            "Identify application dependencies and peak usage periods",
            "Plan implementation during low-traffic maintenance window"
        ]
        
        if rec_type == 'Terminate':
            specific_steps = [
                "Verify instance is truly unused (check application logs, monitoring)",
                "Ensure no critical services or data are running on the instance",
                "Create final backup if needed",
                "Update load balancer and DNS configurations",
                "Terminate instance and monitor for any issues",
                "Update infrastructure documentation"
            ]
        elif rec_type == 'Modify':
            specific_steps = [
                f"Test application performance with {recommended_type} in staging environment",
                "Create AMI backup of current instance",
                f"Stop instance and change type from {current_type} to {recommended_type}",
                "Start instance and verify all services are running correctly",
                "Monitor CPU and memory utilization for 24-48 hours",
                "Update monitoring thresholds and auto-scaling policies if applicable"
            ]
        else:
            specific_steps = [
                "Analyze detailed utilization patterns over extended period",
                "Consult with application teams on performance requirements",
                "Implement recommended optimization changes",
                "Monitor performance and cost impact"
            ]
        
        return base_steps + specific_steps + [
            "Document changes and update operational procedures",
            "Set up alerts for performance monitoring"
        ]
    
    def _assess_ce_confidence_level(self, cpu_util, memory_util, savings, lookback_days):
        """Assess confidence level for Cost Explorer recommendations"""
        confidence_score = 0
        
        # Higher confidence for longer observation periods
        if lookback_days >= 30:
            confidence_score += 2
        elif lookback_days >= 14:
            confidence_score += 1
        
        # Higher confidence for clear utilization patterns
        if cpu_util < 20 and memory_util < 20:
            confidence_score += 3  # Very underutilized
        elif cpu_util < 40 and memory_util < 40:
            confidence_score += 2  # Moderately underutilized
        elif cpu_util < 60 or memory_util < 60:
            confidence_score += 1  # Some optimization potential
        
        # Higher confidence for significant savings
        if savings > 100:
            confidence_score += 2
        elif savings > 50:
            confidence_score += 1
        
        # Map to confidence levels
        if confidence_score >= 6:
            return 'high'
        elif confidence_score >= 3:
            return 'medium'
        else:
            return 'low'
    
    def _assess_ce_risks(self, rec_type, cpu_util, memory_util, savings):
        """Assess potential risks for Cost Explorer recommendations"""
        risks = []
        
        if rec_type == 'Terminate':
            risks.extend([
                "Permanent data loss if instance contains important data",
                "Service disruption if instance is actually in use",
                "Potential impact on dependent services or applications"
            ])
        elif rec_type == 'Modify':
            if cpu_util > 50 or memory_util > 50:
                risks.append("Performance degradation risk due to moderate current utilization")
            
            risks.extend([
                "Temporary service interruption during instance type change",
                "Potential application compatibility issues with new instance type",
                "Performance impact if workload patterns change"
            ])
        
        # Risk based on savings amount
        if savings > 200:
            risks.append("High-impact change requires thorough testing and monitoring")
        
        # General risks
        risks.extend([
            "Utilization patterns may change over time",
            "Recommendations based on historical data may not reflect future needs",
            "Always test changes in non-production environment first"
        ])
        
        return risks
    
    def _normalize_sp_recommendation(self, rec):
        """Normalize Savings Plans recommendation to unified format"""
        try:
            details = rec.get('SavingsPlansDetails', {})
            monthly_savings = float(rec.get('EstimatedMonthlySavings', 0))
            
            return CostRecommendation(
                id=f"sp_{details.get('OfferingId', 'unknown')}",
                source='savings_plans',
                category='commitment',
                service='savings_plans',
                title="Savings Plans Purchase Recommendation",
                description=f"Purchase {details.get('SavingsPlansType', 'Compute')} Savings Plan",
                monthly_savings=monthly_savings,
                annual_savings=monthly_savings * 12,
                confidence_level='high',
                implementation_effort='low',
                implementation_steps=[
                    "Review Savings Plans terms and conditions",
                    "Confirm commitment amount and duration",
                    "Purchase Savings Plan through AWS Console or API"
                ],
                required_permissions=['savingsplans:CreateSavingsPlan'],
                potential_risks=['Financial commitment', 'Usage pattern changes'],
                affected_resources=[],
                resource_count=0,
                priority_score=0.0,
                priority_level='medium',
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
        except Exception as e:
            _warn(f"Error normalizing Savings Plans recommendation: {str(e)}")
            return None
    
    def _deduplicate_recommendations(self, recommendations):
        """
        Advanced deduplication logic across multiple sources with intelligent merging
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of deduplicated recommendations with merged information
        """
        if not recommendations:
            return []
        
        # Group recommendations by similarity
        similarity_groups = self._group_similar_recommendations(recommendations)
        
        # Merge each group into a single recommendation
        deduplicated = []
        for group in similarity_groups:
            merged_rec = self._merge_recommendation_group(group)
            if merged_rec:
                deduplicated.append(merged_rec)
        
        # Sort by priority score (highest first) for consistent ordering
        deduplicated.sort(key=lambda x: x.priority_score, reverse=True)
        
        return deduplicated
    
    def _group_similar_recommendations(self, recommendations):
        """
        Group similar recommendations using multiple similarity criteria
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of recommendation groups (each group is a list of similar recommendations)
        """
        groups = []
        ungrouped = recommendations.copy()
        
        while ungrouped:
            # Take the first recommendation as the seed for a new group
            seed = ungrouped.pop(0)
            current_group = [seed]
            
            # Find all similar recommendations
            remaining = []
            for rec in ungrouped:
                if self._are_recommendations_similar(seed, rec):
                    current_group.append(rec)
                else:
                    remaining.append(rec)
            
            ungrouped = remaining
            groups.append(current_group)
        
        return groups
    
    def _are_recommendations_similar(self, rec1, rec2):
        """
        Determine if two recommendations are similar enough to be merged
        
        Args:
            rec1, rec2: CostRecommendation objects to compare
            
        Returns:
            Boolean indicating if recommendations are similar
        """
        # Different sources can have similar recommendations
        if rec1.source == rec2.source and rec1.id == rec2.id:
            return True  # Exact duplicate
        
        # Check for similar resource targeting
        if (rec1.service == rec2.service and 
            rec1.category == rec2.category):
            
            # For compute recommendations, check if they target the same resources
            if rec1.category == 'compute':
                rec1_resources = {res.get('id', '') for res in rec1.affected_resources}
                rec2_resources = {res.get('id', '') for res in rec2.affected_resources}
                
                # If they share any resources, they're similar
                if rec1_resources.intersection(rec2_resources):
                    return True
            
            # For commitment recommendations, check if they're the same type
            elif rec1.category == 'commitment':
                # RI and SP recommendations for similar services are related
                if (rec1.service in ['reserved_instances', 'savings_plans'] and
                    rec2.service in ['reserved_instances', 'savings_plans']):
                    return True
            
            # For storage/database, check if savings amounts are very similar
            elif rec1.category in ['storage', 'database']:
                savings_diff = abs(rec1.monthly_savings - rec2.monthly_savings)
                avg_savings = (rec1.monthly_savings + rec2.monthly_savings) / 2
                
                # If savings are within 20% of each other, consider similar
                if avg_savings > 0 and savings_diff / avg_savings < 0.2:
                    return True
        
        return False
    
    def _merge_recommendation_group(self, group):
        """
        Merge a group of similar recommendations into a single recommendation
        
        Args:
            group: List of similar CostRecommendation objects
            
        Returns:
            Single merged CostRecommendation object
        """
        if len(group) == 1:
            return group[0]
        
        # Choose the primary recommendation (highest savings or best source priority)
        source_priority = {'coh': 3, 'cost_explorer': 2, 'savings_plans': 1}
        
        primary = max(group, key=lambda r: (
            r.monthly_savings,
            source_priority.get(r.source, 0),
            len(r.implementation_steps)
        ))
        
        # Create merged recommendation based on primary
        merged = CostRecommendation(
            id=f"merged_{primary.id}",
            source=f"merged_{'+'.join(sorted(set(r.source for r in group)))}",
            category=primary.category,
            service=primary.service,
            title=self._merge_titles(group),
            description=self._merge_descriptions(group),
            monthly_savings=self._merge_savings(group),
            annual_savings=self._merge_savings(group) * 12,
            confidence_level=self._merge_confidence_levels(group),
            implementation_effort=self._merge_implementation_efforts(group),
            implementation_steps=self._merge_implementation_steps(group),
            required_permissions=self._merge_permissions(group),
            potential_risks=self._merge_risks(group),
            affected_resources=self._merge_affected_resources(group),
            resource_count=sum(r.resource_count for r in group),
            priority_score=0.0,  # Will be calculated later
            priority_level='medium',  # Will be calculated later
            created_date=min(r.created_date for r in group),
            last_updated=max(r.last_updated for r in group),
            status='new'
        )
        
        return merged
    
    def _merge_titles(self, group):
        """Merge titles from a group of recommendations"""
        if len(group) == 1:
            return group[0].title
        
        # Use the title from the highest-savings recommendation
        primary = max(group, key=lambda r: r.monthly_savings)
        
        # Add source information if multiple sources
        sources = set(r.source for r in group)
        if len(sources) > 1:
            return f"{primary.title} (Multiple Sources)"
        
        return primary.title
    
    def _merge_descriptions(self, group):
        """Merge descriptions from a group of recommendations"""
        if len(group) == 1:
            return group[0].description
        
        primary = max(group, key=lambda r: r.monthly_savings)
        sources = sorted(set(r.source for r in group))
        
        merged_desc = primary.description
        if len(sources) > 1:
            merged_desc += f" This recommendation is supported by multiple sources: {', '.join(sources)}."
        
        return merged_desc
    
    def _merge_savings(self, group):
        """Merge savings calculations from a group of recommendations"""
        # Use the maximum savings as the potential (optimistic estimate)
        return max(r.monthly_savings for r in group)
    
    def _merge_confidence_levels(self, group):
        """Merge confidence levels from a group of recommendations"""
        confidence_scores = {'high': 3, 'medium': 2, 'low': 1}
        
        # Use the highest confidence level from the group
        max_confidence = max(group, key=lambda r: confidence_scores.get(r.confidence_level, 1))
        return max_confidence.confidence_level
    
    def _merge_implementation_efforts(self, group):
        """Merge implementation efforts from a group of recommendations"""
        effort_scores = {'low': 1, 'medium': 2, 'high': 3}
        
        # Use the maximum effort (most conservative estimate)
        max_effort = max(group, key=lambda r: effort_scores.get(r.implementation_effort, 2))
        return max_effort.implementation_effort
    
    def _merge_implementation_steps(self, group):
        """Merge implementation steps from a group of recommendations"""
        all_steps = []
        seen_steps = set()
        
        # Collect unique steps from all recommendations
        for rec in group:
            for step in rec.implementation_steps:
                step_lower = step.lower().strip()
                if step_lower not in seen_steps:
                    seen_steps.add(step_lower)
                    all_steps.append(step)
        
        # Add a note about multiple sources if applicable
        sources = set(r.source for r in group)
        if len(sources) > 1:
            all_steps.insert(0, f"Review recommendations from multiple sources: {', '.join(sorted(sources))}")
        
        return all_steps
    
    def _merge_permissions(self, group):
        """Merge required permissions from a group of recommendations"""
        all_permissions = set()
        
        for rec in group:
            all_permissions.update(rec.required_permissions)
        
        return sorted(list(all_permissions))
    
    def _merge_risks(self, group):
        """Merge potential risks from a group of recommendations"""
        all_risks = []
        seen_risks = set()
        
        # Collect unique risks from all recommendations
        for rec in group:
            for risk in rec.potential_risks:
                risk_lower = risk.lower().strip()
                if risk_lower not in seen_risks:
                    seen_risks.add(risk_lower)
                    all_risks.append(risk)
        
        # Add risk about conflicting recommendations if multiple sources
        sources = set(r.source for r in group)
        if len(sources) > 1:
            all_risks.append("Multiple sources provide similar recommendations - verify consistency before implementation")
        
        return all_risks
    
    def _merge_affected_resources(self, group):
        """Merge affected resources from a group of recommendations"""
        all_resources = []
        seen_resource_ids = set()
        
        for rec in group:
            for resource in rec.affected_resources:
                resource_id = resource.get('id', '')
                if resource_id and resource_id not in seen_resource_ids:
                    seen_resource_ids.add(resource_id)
                    # Add source information to resource
                    enhanced_resource = resource.copy()
                    enhanced_resource['_source'] = rec.source
                    all_resources.append(enhanced_resource)
        
        return all_resources
    
    def _calculate_priorities(self, recommendations):
        """
        Advanced priority calculation using multiple factors and machine learning-inspired scoring
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of recommendations with calculated priority scores and levels
        """
        if not recommendations:
            return recommendations
        
        # Calculate individual factor scores for each recommendation
        for rec in recommendations:
            rec.priority_score = self._calculate_comprehensive_priority_score(rec)
            rec.priority_level = self._determine_priority_level(rec.priority_score)
        
        # Apply relative prioritization within categories
        self._apply_category_relative_prioritization(recommendations)
        
        # Apply business impact adjustments
        self._apply_business_impact_adjustments(recommendations)
        
        # Sort by priority score (highest first)
        recommendations.sort(key=lambda x: (x.priority_score, x.monthly_savings), reverse=True)
        
        return recommendations
    
    def _calculate_comprehensive_priority_score(self, rec):
        """
        Calculate comprehensive priority score using multiple weighted factors
        
        Args:
            rec: CostRecommendation object
            
        Returns:
            Float priority score (0-100)
        """
        # Factor 1: Financial Impact (40% weight)
        financial_score = self._calculate_financial_impact_score(rec)
        
        # Factor 2: Implementation Feasibility (25% weight)
        feasibility_score = self._calculate_feasibility_score(rec)
        
        # Factor 3: Risk Assessment (20% weight)
        risk_score = self._calculate_risk_score(rec)
        
        # Factor 4: Confidence Level (10% weight)
        confidence_score = self._calculate_confidence_score(rec)
        
        # Factor 5: Strategic Alignment (5% weight)
        strategic_score = self._calculate_strategic_alignment_score(rec)
        
        # Weighted combination
        priority_score = (
            financial_score * 0.40 +
            feasibility_score * 0.25 +
            risk_score * 0.20 +
            confidence_score * 0.10 +
            strategic_score * 0.05
        )
        
        return min(100, max(0, priority_score))
    
    def _calculate_financial_impact_score(self, rec):
        """Calculate score based on financial impact (0-100)"""
        # Base score from monthly savings
        if rec.monthly_savings <= 0:
            return 0
        
        # Logarithmic scaling for diminishing returns on very high savings
        import math
        base_score = min(80, math.log10(rec.monthly_savings + 1) * 20)
        
        # Bonus for high annual savings
        if rec.annual_savings >= 10000:  # $10k+ annual savings
            base_score += 15
        elif rec.annual_savings >= 5000:  # $5k+ annual savings
            base_score += 10
        elif rec.annual_savings >= 1000:  # $1k+ annual savings
            base_score += 5
        
        # Bonus for affecting multiple resources (economies of scale)
        if rec.resource_count > 1:
            scale_bonus = min(10, rec.resource_count * 2)
            base_score += scale_bonus
        
        return min(100, base_score)
    
    def _calculate_feasibility_score(self, rec):
        """Calculate score based on implementation feasibility (0-100)"""
        # Base score from implementation effort (inverted - lower effort = higher score)
        effort_scores = {'low': 90, 'medium': 60, 'high': 30}
        base_score = effort_scores.get(rec.implementation_effort, 60)
        
        # Adjust based on number of implementation steps
        step_count = len(rec.implementation_steps)
        if step_count <= 3:
            base_score += 10  # Very simple implementation
        elif step_count <= 5:
            base_score += 5   # Moderate implementation
        elif step_count > 10:
            base_score -= 10  # Complex implementation
        
        # Adjust based on required permissions complexity
        permission_count = len(rec.required_permissions)
        if permission_count <= 2:
            base_score += 5   # Simple permissions
        elif permission_count > 5:
            base_score -= 5   # Complex permissions
        
        # Category-specific adjustments
        if rec.category == 'commitment':
            base_score += 10  # Commitments are usually straightforward
        elif rec.category == 'monitoring':
            base_score -= 5   # Monitoring requires ongoing effort
        
        return min(100, max(0, base_score))
    
    def _calculate_risk_score(self, rec):
        """Calculate score based on risk assessment (0-100, higher = lower risk)"""
        # Start with high score (low risk)
        base_score = 80
        
        # Reduce score based on number of risks
        risk_count = len(rec.potential_risks)
        risk_penalty = min(30, risk_count * 5)
        base_score -= risk_penalty
        
        # Category-specific risk adjustments
        if rec.category == 'compute':
            base_score -= 10  # Compute changes have performance risk
        elif rec.category == 'commitment':
            base_score -= 15  # Financial commitments have long-term risk
        elif rec.category == 'storage':
            base_score -= 5   # Storage changes have data access risk
        
        # Implementation effort risk adjustment
        effort_risk = {'low': 0, 'medium': -5, 'high': -15}
        base_score += effort_risk.get(rec.implementation_effort, -5)
        
        # Source reliability adjustment
        source_reliability = {
            'coh': 5,           # Official AWS recommendations
            'cost_explorer': 5, # Official AWS service
            'savings_plans': 5, # Official AWS service
            'merged': -5        # Multiple sources may have conflicts
        }
        base_score += source_reliability.get(rec.source, 0)
        
        return min(100, max(0, base_score))
    
    def _calculate_confidence_score(self, rec):
        """Calculate score based on confidence level (0-100)"""
        confidence_scores = {'high': 90, 'medium': 60, 'low': 30}
        base_score = confidence_scores.get(rec.confidence_level, 60)
        
        # Adjust based on data quality indicators
        if hasattr(rec, '_data_quality_score'):
            # Use data quality score if available
            quality_adjustment = (rec._data_quality_score - 50) / 5  # Scale to ±10
            base_score += quality_adjustment
        
        # Adjust based on source credibility
        if 'merged' in rec.source:
            base_score += 10  # Multiple sources increase confidence
        
        return min(100, max(0, base_score))
    
    def _calculate_strategic_alignment_score(self, rec):
        """Calculate score based on strategic alignment (0-100)"""
        base_score = 50  # Neutral baseline
        
        # Prioritize certain categories based on strategic importance
        strategic_priorities = {
            'commitment': 20,   # Long-term cost optimization
            'compute': 15,      # Core infrastructure optimization
            'storage': 10,      # Data management optimization
            'database': 10,     # Performance and cost optimization
            'monitoring': 5,    # Operational excellence
            'optimization': 5   # General improvements
        }
        
        base_score += strategic_priorities.get(rec.category, 0)
        
        # Bonus for recommendations that affect multiple services
        if rec.resource_count > 5:
            base_score += 15  # High impact across infrastructure
        elif rec.resource_count > 1:
            base_score += 5   # Moderate impact
        
        # Bonus for proactive vs reactive recommendations
        if rec.category in ['monitoring', 'optimization']:
            base_score += 10  # Proactive optimization
        
        return min(100, max(0, base_score))
    
    def _determine_priority_level(self, priority_score):
        """Determine priority level based on calculated score"""
        if priority_score >= 75:
            return 'high'
        elif priority_score >= 50:
            return 'medium'
        else:
            return 'low'
    
    def _apply_category_relative_prioritization(self, recommendations):
        """Apply relative prioritization within each category"""
        # Group recommendations by category
        categories = {}
        for rec in recommendations:
            if rec.category not in categories:
                categories[rec.category] = []
            categories[rec.category].append(rec)
        
        # Apply relative adjustments within each category
        for category, recs in categories.items():
            if len(recs) <= 1:
                continue
            
            # Sort by current priority score
            recs.sort(key=lambda x: x.priority_score, reverse=True)
            
            # Apply relative bonuses/penalties
            for i, rec in enumerate(recs):
                if i == 0:  # Top recommendation in category
                    rec.priority_score += 5
                elif i == len(recs) - 1:  # Bottom recommendation in category
                    rec.priority_score -= 3
    
    def _apply_business_impact_adjustments(self, recommendations):
        """Apply business impact adjustments based on overall portfolio"""
        # Calculate total potential savings
        total_savings = sum(rec.monthly_savings for rec in recommendations)
        
        if total_savings == 0:
            return
        
        # Apply adjustments based on relative impact
        for rec in recommendations:
            savings_percentage = rec.monthly_savings / total_savings
            
            # Boost high-impact recommendations
            if savings_percentage >= 0.3:  # 30%+ of total savings
                rec.priority_score += 10
            elif savings_percentage >= 0.1:  # 10%+ of total savings
                rec.priority_score += 5
            
            # Ensure scores stay within bounds
            rec.priority_score = min(100, max(0, rec.priority_score))
            
            # Recalculate priority level after adjustments
            rec.priority_level = self._determine_priority_level(rec.priority_score)
    
    def _generate_executive_summary(self):
        """
        Generate comprehensive executive summary of cost optimization opportunities
        
        Returns:
            ExecutiveSummary object with detailed metrics and insights
        """
        if not self.recommendations:
            return ExecutiveSummary(
                total_recommendations=0,
                total_monthly_savings=0.0,
                total_annual_savings=0.0,
                high_priority_count=0,
                medium_priority_count=0,
                low_priority_count=0,
                top_categories=[],
                implementation_roadmap=[],
                data_freshness=datetime.now()
            )
        
        # Calculate comprehensive totals and metrics
        total_monthly = sum(rec.monthly_savings for rec in self.recommendations)
        total_annual = sum(rec.annual_savings for rec in self.recommendations)
        
        # Count by priority with enhanced metrics
        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        priority_savings = {'high': 0.0, 'medium': 0.0, 'low': 0.0}
        
        for rec in self.recommendations:
            priority_counts[rec.priority_level] += 1
            priority_savings[rec.priority_level] += rec.monthly_savings
        
        # Enhanced category analysis with detailed metrics
        category_analysis = defaultdict(lambda: {
            'count': 0,
            'total_savings': 0.0,
            'avg_savings': 0.0,
            'high_priority_count': 0,
            'quick_wins_count': 0,
            'implementation_effort_distribution': {'low': 0, 'medium': 0, 'high': 0}
        })
        
        for rec in self.recommendations:
            cat_data = category_analysis[rec.category]
            cat_data['count'] += 1
            cat_data['total_savings'] += rec.monthly_savings
            cat_data['implementation_effort_distribution'][rec.implementation_effort] += 1
            
            if rec.priority_level == 'high':
                cat_data['high_priority_count'] += 1
            
            if rec.implementation_effort == 'low' and rec.monthly_savings >= 50:
                cat_data['quick_wins_count'] += 1
        
        # Calculate averages
        for cat_data in category_analysis.values():
            if cat_data['count'] > 0:
                cat_data['avg_savings'] = cat_data['total_savings'] / cat_data['count']
        
        # Create top categories with enhanced information
        top_categories = []
        sorted_categories = sorted(category_analysis.items(), 
                                 key=lambda x: x[1]['total_savings'], reverse=True)
        
        for category, data in sorted_categories[:5]:
            top_categories.append({
                'category': category,
                'total_savings': data['total_savings'],
                'recommendation_count': data['count'],
                'avg_savings_per_rec': data['avg_savings'],
                'high_priority_count': data['high_priority_count'],
                'quick_wins_count': data['quick_wins_count'],
                'effort_distribution': data['implementation_effort_distribution']
            })
        
        # Generate comprehensive implementation roadmap
        implementation_roadmap = self._create_executive_implementation_roadmap()
        
        # Create opportunity matrix for executive view
        opportunity_matrix = self._create_executive_opportunity_matrix()
        
        # Calculate key performance indicators
        kpis = self._calculate_executive_kpis()
        
        return ExecutiveSummary(
            total_recommendations=len(self.recommendations),
            total_monthly_savings=total_monthly,
            total_annual_savings=total_annual,
            high_priority_count=priority_counts['high'],
            medium_priority_count=priority_counts['medium'],
            low_priority_count=priority_counts['low'],
            top_categories=top_categories,
            implementation_roadmap=implementation_roadmap,
            data_freshness=datetime.now()
        )
    
    def _create_executive_implementation_roadmap(self):
        """
        Create executive-level implementation roadmap with timeline estimates
        
        Returns:
            List of roadmap phases with detailed planning information
        """
        if not self.recommendations:
            return []
        
        # Phase 1: Immediate Actions (0-30 days)
        immediate_actions = [rec for rec in self.recommendations 
                           if rec.implementation_effort == 'low' and rec.priority_level in ['high', 'medium']]
        
        # Phase 2: Strategic Initiatives (1-3 months)
        strategic_initiatives = [rec for rec in self.recommendations 
                               if rec.implementation_effort == 'medium' and rec.monthly_savings >= 100]
        
        # Phase 3: Complex Transformations (3-6 months)
        complex_transformations = [rec for rec in self.recommendations 
                                 if rec.implementation_effort == 'high']
        
        roadmap = []
        
        if immediate_actions:
            immediate_savings = sum(rec.monthly_savings for rec in immediate_actions)
            roadmap.append({
                'phase': 'Immediate Actions',
                'timeline': '0-30 days',
                'recommendation_count': len(immediate_actions),
                'monthly_savings_potential': immediate_savings,
                'annual_savings_potential': immediate_savings * 12,
                'key_focus_areas': self._get_top_focus_areas(immediate_actions),
                'success_criteria': [
                    f'Implement {len(immediate_actions)} quick-win optimizations',
                    f'Achieve ${immediate_savings:,.0f}/month in cost savings',
                    'Establish baseline metrics and monitoring'
                ],
                'resource_requirements': {
                    'effort_level': 'Low',
                    'estimated_hours': len(immediate_actions) * 8,
                    'skills_needed': ['AWS Console access', 'Basic configuration changes']
                }
            })
        
        if strategic_initiatives:
            strategic_savings = sum(rec.monthly_savings for rec in strategic_initiatives)
            roadmap.append({
                'phase': 'Strategic Initiatives',
                'timeline': '1-3 months',
                'recommendation_count': len(strategic_initiatives),
                'monthly_savings_potential': strategic_savings,
                'annual_savings_potential': strategic_savings * 12,
                'key_focus_areas': self._get_top_focus_areas(strategic_initiatives),
                'success_criteria': [
                    f'Complete {len(strategic_initiatives)} medium-complexity optimizations',
                    f'Achieve additional ${strategic_savings:,.0f}/month in savings',
                    'Implement automated monitoring and alerting'
                ],
                'resource_requirements': {
                    'effort_level': 'Medium',
                    'estimated_hours': len(strategic_initiatives) * 24,
                    'skills_needed': ['AWS architecture', 'Performance optimization', 'Automation tools']
                }
            })
        
        if complex_transformations:
            complex_savings = sum(rec.monthly_savings for rec in complex_transformations)
            roadmap.append({
                'phase': 'Complex Transformations',
                'timeline': '3-6 months',
                'recommendation_count': len(complex_transformations),
                'monthly_savings_potential': complex_savings,
                'annual_savings_potential': complex_savings * 12,
                'key_focus_areas': self._get_top_focus_areas(complex_transformations),
                'success_criteria': [
                    f'Execute {len(complex_transformations)} high-impact transformations',
                    f'Achieve additional ${complex_savings:,.0f}/month in savings',
                    'Establish continuous optimization processes'
                ],
                'resource_requirements': {
                    'effort_level': 'High',
                    'estimated_hours': len(complex_transformations) * 80,
                    'skills_needed': ['Advanced AWS architecture', 'Migration expertise', 'Change management']
                }
            })
        
        # Add cumulative metrics
        cumulative_savings = 0
        cumulative_recs = 0
        
        for phase in roadmap:
            cumulative_savings += phase['monthly_savings_potential']
            cumulative_recs += phase['recommendation_count']
            phase['cumulative_monthly_savings'] = cumulative_savings
            phase['cumulative_recommendations'] = cumulative_recs
            phase['cumulative_annual_savings'] = cumulative_savings * 12
        
        return roadmap
    
    def _get_top_focus_areas(self, recommendations):
        """Get top focus areas for a set of recommendations"""
        service_counts = defaultdict(int)
        category_counts = defaultdict(int)
        
        for rec in recommendations:
            service_counts[rec.service] += 1
            category_counts[rec.category] += 1
        
        top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        focus_areas = []
        
        # Add service-specific focus areas
        for service, count in top_services:
            focus_areas.append(f"{service.upper()} optimization ({count} recommendations)")
        
        # Add category-specific focus areas
        for category, count in top_categories:
            if len(focus_areas) < 5:  # Limit to 5 total focus areas
                focus_areas.append(f"{category.title()} cost reduction ({count} opportunities)")
        
        return focus_areas[:5]
    
    def _create_executive_opportunity_matrix(self):
        """
        Create executive-level opportunity matrix showing impact vs effort
        
        Returns:
            Dictionary with opportunity matrix data and insights
        """
        matrix = {
            'high_impact_low_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'high_impact_medium_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'high_impact_high_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'medium_impact_low_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'medium_impact_medium_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'medium_impact_high_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'low_impact_low_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'low_impact_medium_effort': {'count': 0, 'savings': 0.0, 'recommendations': []},
            'low_impact_high_effort': {'count': 0, 'savings': 0.0, 'recommendations': []}
        }
        
        for rec in self.recommendations:
            # Categorize impact based on monthly savings
            if rec.monthly_savings >= 200:
                impact = 'high'
            elif rec.monthly_savings >= 50:
                impact = 'medium'
            else:
                impact = 'low'
            
            effort = rec.implementation_effort
            key = f"{impact}_impact_{effort}_effort"
            
            matrix[key]['count'] += 1
            matrix[key]['savings'] += rec.monthly_savings
            
            # Add top recommendations for executive visibility
            if len(matrix[key]['recommendations']) < 3:
                matrix[key]['recommendations'].append({
                    'title': rec.title,
                    'service': rec.service,
                    'monthly_savings': rec.monthly_savings,
                    'confidence_level': rec.confidence_level
                })
        
        # Add executive insights
        total_savings = sum(rec.monthly_savings for rec in self.recommendations)
        
        matrix['executive_insights'] = {
            'quick_wins': {
                'count': matrix['high_impact_low_effort']['count'] + matrix['medium_impact_low_effort']['count'],
                'savings': matrix['high_impact_low_effort']['savings'] + matrix['medium_impact_low_effort']['savings'],
                'percentage_of_total': ((matrix['high_impact_low_effort']['savings'] + matrix['medium_impact_low_effort']['savings']) / max(total_savings, 1)) * 100
            },
            'major_projects': {
                'count': matrix['high_impact_high_effort']['count'],
                'savings': matrix['high_impact_high_effort']['savings'],
                'percentage_of_total': (matrix['high_impact_high_effort']['savings'] / max(total_savings, 1)) * 100
            },
            'questionable_investments': {
                'count': matrix['low_impact_high_effort']['count'],
                'savings': matrix['low_impact_high_effort']['savings'],
                'recommendation': 'Consider deprioritizing these low-impact, high-effort items'
            }
        }
        
        return matrix
    
    def _calculate_executive_kpis(self):
        """
        Calculate key performance indicators for executive reporting
        
        Returns:
            Dictionary with executive KPIs and metrics
        """
        if not self.recommendations:
            return {}
        
        total_monthly_savings = sum(rec.monthly_savings for rec in self.recommendations)
        total_annual_savings = total_monthly_savings * 12
        
        # Calculate implementation metrics
        low_effort_count = len([rec for rec in self.recommendations if rec.implementation_effort == 'low'])
        high_confidence_count = len([rec for rec in self.recommendations if rec.confidence_level == 'high'])
        
        # Calculate financial metrics
        high_impact_savings = sum(rec.monthly_savings for rec in self.recommendations if rec.monthly_savings >= 200)
        quick_wins_savings = sum(rec.monthly_savings for rec in self.recommendations 
                               if rec.implementation_effort == 'low' and rec.monthly_savings >= 50)
        
        # Calculate risk metrics
        high_risk_count = len([rec for rec in self.recommendations 
                             if rec.implementation_effort == 'high' or rec.confidence_level == 'low'])
        
        # Calculate efficiency metrics
        avg_savings_per_rec = total_monthly_savings / len(self.recommendations)
        
        # Estimate implementation timeline
        total_effort_hours = (
            len([rec for rec in self.recommendations if rec.implementation_effort == 'low']) * 8 +
            len([rec for rec in self.recommendations if rec.implementation_effort == 'medium']) * 24 +
            len([rec for rec in self.recommendations if rec.implementation_effort == 'high']) * 80
        )
        
        # Estimate ROI (assuming average implementation cost)
        estimated_implementation_cost = (
            len([rec for rec in self.recommendations if rec.implementation_effort == 'low']) * 500 +
            len([rec for rec in self.recommendations if rec.implementation_effort == 'medium']) * 2000 +
            len([rec for rec in self.recommendations if rec.implementation_effort == 'high']) * 5000
        )
        
        roi_percentage = 0
        payback_months = 0
        if estimated_implementation_cost > 0:
            roi_percentage = ((total_annual_savings - estimated_implementation_cost) / estimated_implementation_cost) * 100
            payback_months = estimated_implementation_cost / max(total_monthly_savings, 1)
        
        return {
            'financial_impact': {
                'total_annual_savings_potential': total_annual_savings,
                'high_impact_savings_percentage': (high_impact_savings / max(total_monthly_savings, 1)) * 100,
                'quick_wins_savings_potential': quick_wins_savings,
                'average_savings_per_recommendation': avg_savings_per_rec
            },
            'implementation_feasibility': {
                'low_effort_percentage': (low_effort_count / len(self.recommendations)) * 100,
                'high_confidence_percentage': (high_confidence_count / len(self.recommendations)) * 100,
                'estimated_total_effort_hours': total_effort_hours,
                'estimated_implementation_timeline_weeks': max(4, total_effort_hours / 40)  # Assuming 40 hours/week
            },
            'risk_assessment': {
                'high_risk_percentage': (high_risk_count / len(self.recommendations)) * 100,
                'portfolio_risk_level': 'Low' if high_risk_count < len(self.recommendations) * 0.3 else 'Medium' if high_risk_count < len(self.recommendations) * 0.6 else 'High'
            },
            'roi_analysis': {
                'estimated_roi_percentage': roi_percentage,
                'estimated_payback_months': payback_months,
                'estimated_implementation_cost': estimated_implementation_cost
            }
        }
    
    def get_recommendations_by_category(self):
        """Get recommendations grouped by category"""
        categories = defaultdict(list)
        for rec in self.recommendations:
            categories[rec.category].append(rec)
        return dict(categories)
    
    def get_recommendations_by_priority(self):
        """Get recommendations grouped by priority level"""
        priorities = defaultdict(list)
        for rec in self.recommendations:
            priorities[rec.priority_level].append(rec)
        return dict(priorities)
    
    def to_dict(self):
        """Convert COH data to dictionary for JSON serialization"""
        return {
            'recommendations': [asdict(rec) for rec in self.recommendations],
            'executive_summary': asdict(self.executive_summary) if self.executive_summary else None,
            'error_messages': self.error_messages,
            'data_collection_time': self.data_collection_time.total_seconds() if self.data_collection_time else 0,
            'timestamp': datetime.now().isoformat()
        }   
 
    # Additional methods for Task 2.3: Enhanced data processing and validation
    
    def validate_recommendation_data(self, rec, source='unknown'):
        """
        Validate recommendation data and handle missing or malformed fields gracefully
        
        Args:
            rec: Raw recommendation dictionary
            source: Source of the recommendation for error reporting
            
        Returns:
            Tuple of (is_valid, cleaned_rec, validation_errors)
        """
        validation_errors = []
        cleaned_rec = rec.copy() if rec else {}
        
        # Required fields validation
        required_fields = {
            'coh': ['recommendationId', 'estimatedMonthlySavings'],
            'cost_explorer': ['CurrentInstance', 'EstimatedMonthlySavings'],
            'savings_plans': ['EstimatedMonthlySavings']
        }
        
        source_required = required_fields.get(source, [])
        for field in source_required:
            if field not in cleaned_rec or cleaned_rec[field] is None:
                validation_errors.append(f"Missing required field: {field}")
                
                # Provide default values where possible
                if field == 'estimatedMonthlySavings' or field == 'EstimatedMonthlySavings':
                    cleaned_rec[field] = 0.0
                elif field == 'recommendationId':
                    cleaned_rec[field] = f"unknown_{source}_{datetime.now().timestamp()}"
        
        # Data type validation and cleaning
        try:
            # Clean financial data
            if 'estimatedMonthlySavings' in cleaned_rec:
                savings = cleaned_rec['estimatedMonthlySavings']
                if isinstance(savings, str):
                    # Remove currency symbols and convert
                    savings = savings.replace('$', '').replace(',', '')
                    cleaned_rec['estimatedMonthlySavings'] = float(savings)
                elif not isinstance(savings, (int, float)):
                    cleaned_rec['estimatedMonthlySavings'] = 0.0
                    validation_errors.append("Invalid savings amount, defaulted to 0")
                
                # Ensure non-negative
                if cleaned_rec['estimatedMonthlySavings'] < 0:
                    cleaned_rec['estimatedMonthlySavings'] = 0.0
                    validation_errors.append("Negative savings amount, defaulted to 0")
            
            # Clean resource count
            if 'resourceCount' in cleaned_rec:
                try:
                    cleaned_rec['resourceCount'] = max(0, int(cleaned_rec['resourceCount']))
                except (ValueError, TypeError):
                    cleaned_rec['resourceCount'] = 0
                    validation_errors.append("Invalid resource count, defaulted to 0")
            
            # Clean text fields
            text_fields = ['name', 'title', 'description', 'category', 'source']
            for field in text_fields:
                if field in cleaned_rec and cleaned_rec[field]:
                    # Remove excessive whitespace and ensure reasonable length
                    cleaned_rec[field] = str(cleaned_rec[field]).strip()[:500]
                elif field in cleaned_rec:
                    cleaned_rec[field] = f"No {field} available"
            
            # Validate implementation effort
            if 'implementationEffort' in cleaned_rec:
                valid_efforts = ['VERY_LOW', 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
                if cleaned_rec['implementationEffort'] not in valid_efforts:
                    cleaned_rec['implementationEffort'] = 'MEDIUM'
                    validation_errors.append("Invalid implementation effort, defaulted to MEDIUM")
            
        except Exception as e:
            validation_errors.append(f"Data cleaning error: {str(e)}")
        
        # Determine if recommendation is valid enough to process
        try:
            savings_amount = float(cleaned_rec.get('estimatedMonthlySavings', 0))
        except (ValueError, TypeError):
            savings_amount = 0
            
        is_valid = (
            len(validation_errors) == 0 or  # No errors
            (savings_amount > 0 and  # Has savings potential
             len([e for e in validation_errors if 'Missing required field' in e]) == 0)  # No missing required fields
        )
        
        return is_valid, cleaned_rec, validation_errors
    
    def enrich_recommendation_metadata(self, rec, source):
        """
        Enrich recommendation with additional metadata and context
        
        Args:
            rec: Recommendation dictionary
            source: Source system ('coh', 'cost_explorer', 'savings_plans')
            
        Returns:
            Enhanced recommendation dictionary
        """
        enriched_rec = rec.copy()
        
        # Add processing metadata
        enriched_rec['_processed_at'] = datetime.now().isoformat()
        enriched_rec['_source_system'] = source
        enriched_rec['_data_quality_score'] = self._calculate_data_quality_score(rec)
        
        # Add service categorization
        service = rec.get('source', '').lower()
        if service in ['ec2', 'ecs', 'eks', 'lambda', 'fargate']:
            enriched_rec['_service_category'] = 'compute'
        elif service in ['s3', 'ebs', 'efs', 'fsx']:
            enriched_rec['_service_category'] = 'storage'
        elif service in ['rds', 'dynamodb', 'redshift', 'elasticache']:
            enriched_rec['_service_category'] = 'database'
        else:
            enriched_rec['_service_category'] = 'general'
        
        # Add savings tier classification
        monthly_savings = float(rec.get('estimatedMonthlySavings', 0))
        if monthly_savings >= 1000:
            enriched_rec['_savings_tier'] = 'high'
        elif monthly_savings >= 100:
            enriched_rec['_savings_tier'] = 'medium'
        elif monthly_savings > 0:
            enriched_rec['_savings_tier'] = 'low'
        else:
            enriched_rec['_savings_tier'] = 'none'
        
        # Add implementation complexity hints
        effort = rec.get('implementationEffort', 'MEDIUM')
        resource_count = rec.get('resourceCount', 0)
        
        complexity_factors = []
        if effort in ['HIGH', 'VERY_HIGH']:
            complexity_factors.append('high_effort')
        if resource_count > 10:
            complexity_factors.append('many_resources')
        if monthly_savings > 500:
            complexity_factors.append('high_impact')
        
        enriched_rec['_complexity_factors'] = complexity_factors
        
        return enriched_rec
    
    def _calculate_data_quality_score(self, rec):
        """
        Calculate a data quality score (0-100) based on completeness and validity
        
        Args:
            rec: Recommendation dictionary
            
        Returns:
            Integer score from 0-100
        """
        score = 0
        max_score = 100
        
        # Basic required fields (40 points)
        if rec.get('estimatedMonthlySavings', 0) > 0:
            score += 20
        if rec.get('recommendationId') or rec.get('CurrentInstance', {}).get('ResourceId'):
            score += 20
        
        # Descriptive fields (30 points)
        if rec.get('name') or rec.get('title'):
            score += 10
        if rec.get('description') and len(str(rec['description'])) > 20:
            score += 10
        if rec.get('category') or rec.get('source'):
            score += 10
        
        # Implementation details (20 points)
        if rec.get('implementationEffort'):
            score += 10
        if rec.get('resourceCount', 0) > 0:
            score += 10
        
        # Additional metadata (10 points)
        if rec.get('resources') or rec.get('_collection_timestamp'):
            score += 5
        if rec.get('_source_region'):
            score += 5
        
        return min(score, max_score)
    
    def process_recommendations_with_validation(self, raw_data):
        """
        Process recommendations with comprehensive validation and error handling
        
        Args:
            raw_data: Dictionary with raw data from all sources
            
        Returns:
            Tuple of (processed_recommendations, processing_stats)
        """
        processing_stats = {
            'total_input': 0,
            'valid_processed': 0,
            'invalid_skipped': 0,
            'validation_errors': [],
            'source_breakdown': {}
        }
        
        processed_recommendations = []
        
        # Process each source with validation
        for source, data in raw_data.items():
            source_stats = {
                'input_count': 0,
                'processed_count': 0,
                'skipped_count': 0,
                'errors': []
            }
            
            if source == 'coh':
                recommendations = data if isinstance(data, list) else []
                source_stats['input_count'] = len(recommendations)
                
                for rec in recommendations:
                    is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'coh')
                    
                    if is_valid:
                        enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'coh')
                        normalized = self._normalize_coh_recommendation(enriched_rec)
                        if normalized:
                            processed_recommendations.append(normalized)
                            source_stats['processed_count'] += 1
                        else:
                            source_stats['skipped_count'] += 1
                    else:
                        source_stats['skipped_count'] += 1
                        source_stats['errors'].extend(errors)
            
            elif source == 'cost_explorer':
                # Handle multiple types of Cost Explorer data
                ce_data = data if isinstance(data, dict) else {}
                
                # Process rightsizing recommendations
                rightsizing_recs = ce_data.get('rightsizing', [])
                source_stats['input_count'] += len(rightsizing_recs)
                
                for rec in rightsizing_recs:
                    is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'cost_explorer')
                    
                    if is_valid:
                        enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'cost_explorer')
                        normalized = self._normalize_ce_recommendation(enriched_rec)
                        if normalized:
                            processed_recommendations.append(normalized)
                            source_stats['processed_count'] += 1
                        else:
                            source_stats['skipped_count'] += 1
                    else:
                        source_stats['skipped_count'] += 1
                        source_stats['errors'].extend(errors)
                
                # Process RI recommendations if available
                ri_recs = ce_data.get('ri_recommendations', [])
                source_stats['input_count'] += len(ri_recs)
                
                for rec in ri_recs:
                    # Convert RI recommendation to standard format
                    ri_rec_normalized = self._convert_ri_recommendation_to_standard(rec)
                    if ri_rec_normalized:
                        is_valid, cleaned_rec, errors = self.validate_recommendation_data(ri_rec_normalized, 'cost_explorer')
                        
                        if is_valid:
                            enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'cost_explorer')
                            normalized = self._normalize_ri_recommendation(enriched_rec)
                            if normalized:
                                processed_recommendations.append(normalized)
                                source_stats['processed_count'] += 1
                            else:
                                source_stats['skipped_count'] += 1
                        else:
                            source_stats['skipped_count'] += 1
                            source_stats['errors'].extend(errors)
            
            elif source == 'savings_plans':
                # Handle comprehensive Savings Plans data
                sp_data = data if isinstance(data, dict) else {}
                
                # Process purchase recommendations
                purchase_recs = sp_data.get('processed_recommendations', [])
                source_stats['input_count'] += len(purchase_recs)
                
                for rec in purchase_recs:
                    is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'savings_plans')
                    
                    if is_valid:
                        enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'savings_plans')
                        normalized = self._normalize_sp_recommendation(enriched_rec)
                        if normalized:
                            processed_recommendations.append(normalized)
                            source_stats['processed_count'] += 1
                        else:
                            source_stats['skipped_count'] += 1
                    else:
                        source_stats['skipped_count'] += 1
                        source_stats['errors'].extend(errors)
                
                # Process optimization recommendations
                opt_recs = sp_data.get('optimization_recommendations', [])
                source_stats['input_count'] += len(opt_recs)
                
                for rec in opt_recs:
                    is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'savings_plans')
                    
                    if is_valid:
                        enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'savings_plans')
                        normalized = self._normalize_sp_optimization_recommendation(enriched_rec)
                        if normalized:
                            processed_recommendations.append(normalized)
                            source_stats['processed_count'] += 1
                        else:
                            source_stats['skipped_count'] += 1
                    else:
                        source_stats['skipped_count'] += 1
                        source_stats['errors'].extend(errors)
            
            # Update overall stats
            processing_stats['total_input'] += source_stats['input_count']
            processing_stats['valid_processed'] += source_stats['processed_count']
            processing_stats['invalid_skipped'] += source_stats['skipped_count']
            processing_stats['validation_errors'].extend(source_stats['errors'])
            processing_stats['source_breakdown'][source] = source_stats
        
        # Apply deduplication and prioritization
        if processed_recommendations:
            deduplicated = self._deduplicate_recommendations(processed_recommendations)
            prioritized = self._calculate_priorities(deduplicated)
            
            processing_stats['final_count'] = len(prioritized)
            processing_stats['deduplicated_count'] = len(processed_recommendations) - len(deduplicated)
            
            return prioritized, processing_stats
        
        processing_stats['final_count'] = 0
        processing_stats['deduplicated_count'] = 0
        return [], processing_stats
    
    def get_processing_summary(self):
        """
        Get a summary of the data processing results
        
        Returns:
            Dictionary with processing statistics and quality metrics
        """
        if not hasattr(self, '_processing_stats'):
            return {'error': 'No processing statistics available'}
        
        stats = self._processing_stats
        
        # Calculate quality metrics
        total_input = stats.get('total_input', 0)
        valid_processed = stats.get('valid_processed', 0)
        
        quality_metrics = {
            'data_quality_rate': (valid_processed / total_input * 100) if total_input > 0 else 0,
            'processing_success_rate': (stats.get('final_count', 0) / valid_processed * 100) if valid_processed > 0 else 0,
            'deduplication_rate': (stats.get('deduplicated_count', 0) / valid_processed * 100) if valid_processed > 0 else 0
        }
        
        return {
            'processing_stats': stats,
            'quality_metrics': quality_metrics,
            'recommendations_count': len(self.recommendations),
            'error_count': len(self.error_messages),
            'collection_time_seconds': self.data_collection_time.total_seconds() if self.data_collection_time else 0
        } 
   
    # Additional methods for Task 3.3: Enhanced Cost Explorer processing
    
    def _convert_ri_recommendation_to_standard(self, ri_rec):
        """
        Convert RI recommendation to standard recommendation format
        
        Args:
            ri_rec: Raw RI recommendation from Cost Explorer
            
        Returns:
            Standardized recommendation dictionary
        """
        try:
            details = ri_rec.get('RecommendationDetails', {})
            
            # Extract basic information
            instance_type = details.get('InstanceType', 'unknown')
            region = details.get('Region', 'unknown')
            
            # Calculate savings information
            monthly_savings = float(details.get('EstimatedMonthlySavingsAmount', 0))
            upfront_cost = float(details.get('UpfrontCost', 0))
            
            return {
                'recommendationId': f"ri_{instance_type}_{region}_{datetime.now().timestamp()}",
                'EstimatedMonthlySavings': monthly_savings,
                'category': 'commitment',
                'source': 'reserved_instances',
                'name': f"Reserved Instance Purchase - {instance_type}",
                'description': f"Purchase Reserved Instance for {instance_type} in {region}",
                'implementationEffort': 'LOW',
                'resourceCount': int(details.get('RecommendedNumberOfInstancesToPurchase', 1)),
                'RecommendationDetails': details,
                '_ri_term': ri_rec.get('TermInYears', 'ONE_YEAR'),
                '_payment_option': ri_rec.get('PaymentOption', 'NO_UPFRONT'),
                '_upfront_cost': upfront_cost,
                '_source_region': region
            }
        except Exception as e:
            _warn(f"Error converting RI recommendation: {str(e)}")
            return None
    
    def _normalize_ri_recommendation(self, rec):
        """
        Normalize Reserved Instance recommendation to unified format
        
        Args:
            rec: Processed RI recommendation dictionary
            
        Returns:
            CostRecommendation object for RI purchase
        """
        try:
            details = rec.get('RecommendationDetails', {})
            
            # Extract financial information
            monthly_savings = float(rec.get('EstimatedMonthlySavings', 0))
            upfront_cost = float(rec.get('_upfront_cost', 0))
            
            # Calculate ROI metrics
            roi_data = self.ce_client._calculate_ri_roi(details)
            
            # Generate implementation steps for RI purchase
            implementation_steps = [
                "Review Reserved Instance terms and commitment requirements",
                f"Confirm {rec.get('resourceCount', 1)} instances needed for {rec.get('_ri_term', 'ONE_YEAR')} term",
                "Verify budget approval for upfront costs if applicable",
                "Purchase Reserved Instance through AWS Console or API",
                "Monitor RI utilization and coverage after purchase",
                "Set up alerts for RI expiration and renewal planning"
            ]
            
            # Assess risks for RI commitment
            potential_risks = [
                "Financial commitment for the full RI term",
                "Risk of over-provisioning if usage patterns change",
                "Limited flexibility compared to On-Demand instances",
                f"Upfront cost of ${upfront_cost:,.2f} if applicable"
            ]
            
            if roi_data['months_to_break_even'] > 12:
                potential_risks.append(f"Long break-even period of {roi_data['months_to_break_even']:.1f} months")
            
            # Create affected resources (conceptual for RI)
            affected_resources = [{
                'id': f"ri_purchase_{details.get('InstanceType', 'unknown')}",
                'type': 'ReservedInstance',
                'instance_type': details.get('InstanceType', 'unknown'),
                'region': rec.get('_source_region', 'unknown'),
                'quantity': rec.get('resourceCount', 1),
                'term': rec.get('_ri_term', 'ONE_YEAR'),
                'payment_option': rec.get('_payment_option', 'NO_UPFRONT'),
                'estimated_utilization': details.get('ExpectedUtilization', 'unknown')
            }]
            
            return CostRecommendation(
                id=rec.get('recommendationId', f"ri_unknown_{datetime.now().timestamp()}"),
                source='cost_explorer',
                category='commitment',
                service='reserved_instances',
                title=rec.get('name', 'Reserved Instance Purchase Recommendation'),
                description=rec.get('description', 'Purchase Reserved Instance to reduce costs'),
                monthly_savings=monthly_savings,
                annual_savings=monthly_savings * 12,
                confidence_level='high',  # RI recommendations are typically high confidence
                implementation_effort='low',  # RI purchase is straightforward
                implementation_steps=implementation_steps,
                required_permissions=[
                    'ec2:DescribeReservedInstances',
                    'ec2:PurchaseReservedInstancesOffering',
                    'ec2:DescribeReservedInstancesOfferings'
                ],
                potential_risks=potential_risks,
                affected_resources=affected_resources,
                resource_count=rec.get('resourceCount', 1),
                priority_score=0.0,  # Will be calculated later
                priority_level='medium',  # Will be calculated later
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
            
        except Exception as e:
            _warn(f"Error normalizing RI recommendation: {str(e)}")
            return None
    
    def process_cost_anomalies(self, anomalies):
        """
        Process cost anomalies into actionable recommendations
        
        Args:
            anomalies: List of cost anomalies from Cost Explorer
            
        Returns:
            List of CostRecommendation objects for anomaly investigation
        """
        anomaly_recommendations = []
        
        for anomaly in anomalies:
            try:
                impact = anomaly.get('Impact', {})
                max_impact = float(impact.get('MaxImpact', 0))
                
                # Only create recommendations for significant anomalies
                if max_impact < 50:  # Skip anomalies under $50
                    continue
                
                # Extract anomaly information
                anomaly_id = anomaly.get('AnomalyId', f"anomaly_{datetime.now().timestamp()}")
                start_date = anomaly.get('AnomalyStartDate', 'unknown')
                end_date = anomaly.get('AnomalyEndDate', 'unknown')
                
                # Determine severity and effort based on impact
                if max_impact >= 1000:
                    severity = 'high'
                    effort = 'high'
                elif max_impact >= 200:
                    severity = 'medium'
                    effort = 'medium'
                else:
                    severity = 'low'
                    effort = 'low'
                
                # Generate investigation steps
                investigation_steps = [
                    f"Review cost anomaly detected from {start_date} to {end_date}",
                    "Analyze service usage patterns during the anomaly period",
                    "Check for unexpected resource provisioning or scaling events",
                    "Review CloudTrail logs for unusual API activity",
                    "Identify root cause and implement preventive measures",
                    "Set up cost alerts to detect similar anomalies in the future"
                ]
                
                # Create recommendation for anomaly investigation
                anomaly_rec = CostRecommendation(
                    id=f"anomaly_{anomaly_id}",
                    source='cost_explorer',
                    category='monitoring',
                    service='cost_anomaly',
                    title=f"Investigate Cost Anomaly - ${max_impact:,.2f} Impact",
                    description=f"Unusual spending pattern detected with ${max_impact:,.2f} impact. Investigation recommended to prevent future occurrences.",
                    monthly_savings=0.0,  # Anomalies don't directly save money but prevent future waste
                    annual_savings=0.0,
                    confidence_level='high',  # Anomalies are factual
                    implementation_effort=effort,
                    implementation_steps=investigation_steps,
                    required_permissions=[
                        'ce:GetAnomalies',
                        'cloudtrail:LookupEvents',
                        'logs:FilterLogEvents'
                    ],
                    potential_risks=[
                        "Ongoing cost anomaly may continue if not addressed",
                        "Similar patterns may occur in other services or regions"
                    ],
                    affected_resources=[{
                        'id': anomaly_id,
                        'type': 'CostAnomaly',
                        'impact': max_impact,
                        'start_date': start_date,
                        'end_date': end_date,
                        'severity': severity
                    }],
                    resource_count=1,
                    priority_score=0.0,  # Will be calculated later
                    priority_level=severity,
                    created_date=datetime.now(),
                    last_updated=datetime.now(),
                    status='new'
                )
                
                anomaly_recommendations.append(anomaly_rec)
                
            except Exception as e:
                _warn(f"Error processing cost anomaly: {str(e)}")
                continue
        
        return anomaly_recommendations
    
    def analyze_usage_trends(self, forecast_data):
        """
        Analyze usage forecast data to identify optimization opportunities
        
        Args:
            forecast_data: Usage forecast data from Cost Explorer
            
        Returns:
            List of trend-based recommendations
        """
        trend_recommendations = []
        
        try:
            if not forecast_data:
                return trend_recommendations
            
            # Analyze spending trends across time periods
            spending_by_service = defaultdict(list)
            
            for result in forecast_data:
                time_period = result.get('TimePeriod', {})
                groups = result.get('Groups', [])
                
                for group in groups:
                    service = group.get('Keys', ['Unknown'])[0]
                    metrics = group.get('Metrics', {})
                    unblended_cost = metrics.get('UnblendedCost', {})
                    amount = float(unblended_cost.get('Amount', 0))
                    
                    spending_by_service[service].append({
                        'period': time_period,
                        'amount': amount
                    })
            
            # Identify services with increasing trends
            for service, spending_data in spending_by_service.items():
                if len(spending_data) < 2:
                    continue
                
                # Calculate trend (simple linear growth)
                amounts = [data['amount'] for data in spending_data]
                if len(amounts) >= 2:
                    growth_rate = (amounts[-1] - amounts[0]) / amounts[0] if amounts[0] > 0 else 0
                    
                    # Create recommendation for services with high growth
                    if growth_rate > 0.2 and amounts[-1] > 100:  # 20% growth and >$100
                        trend_rec = CostRecommendation(
                            id=f"trend_{service}_{datetime.now().timestamp()}",
                            source='cost_explorer',
                            category='monitoring',
                            service=service.lower(),
                            title=f"Review Growing Costs in {service}",
                            description=f"{service} costs are trending upward with {growth_rate*100:.1f}% growth. Review for optimization opportunities.",
                            monthly_savings=0.0,  # Trend analysis doesn't directly save money
                            annual_savings=0.0,
                            confidence_level='medium',
                            implementation_effort='medium',
                            implementation_steps=[
                                f"Analyze {service} usage patterns and growth drivers",
                                "Review resource provisioning and scaling policies",
                                "Identify opportunities for rightsizing or optimization",
                                "Consider Reserved Instances or Savings Plans if applicable",
                                "Implement cost monitoring and alerts"
                            ],
                            required_permissions=[
                                'ce:GetCostAndUsage',
                                f'{service.lower()}:Describe*'
                            ],
                            potential_risks=[
                                "Continued cost growth without optimization",
                                "Budget overruns if trend continues"
                            ],
                            affected_resources=[{
                                'id': f"{service}_trend",
                                'type': 'ServiceTrend',
                                'service': service,
                                'growth_rate': growth_rate,
                                'current_monthly_cost': amounts[-1]
                            }],
                            resource_count=1,
                            priority_score=0.0,
                            priority_level='medium',
                            created_date=datetime.now(),
                            last_updated=datetime.now(),
                            status='new'
                        )
                        
                        trend_recommendations.append(trend_rec)
            
        except Exception as e:
            _warn(f"Error analyzing usage trends: {str(e)}")
        
        return trend_recommendations
    
    def get_cost_explorer_processing_summary(self):
        """
        Get summary of Cost Explorer data processing
        
        Returns:
            Dictionary with processing statistics specific to Cost Explorer
        """
        if not hasattr(self, '_processing_stats'):
            return {'error': 'No processing statistics available'}
        
        ce_stats = self._processing_stats.get('source_breakdown', {}).get('cost_explorer', {})
        
        return {
            'rightsizing_recommendations': len([r for r in self.recommendations if r.source == 'cost_explorer' and r.category == 'compute']),
            'ri_recommendations': len([r for r in self.recommendations if r.source == 'cost_explorer' and r.category == 'commitment']),
            'anomaly_investigations': len([r for r in self.recommendations if r.source == 'cost_explorer' and r.service == 'cost_anomaly']),
            'trend_analyses': len([r for r in self.recommendations if r.source == 'cost_explorer' and r.category == 'monitoring']),
            'total_ce_recommendations': len([r for r in self.recommendations if r.source == 'cost_explorer']),
            'processing_stats': ce_stats,
            'average_monthly_savings': sum(r.monthly_savings for r in self.recommendations if r.source == 'cost_explorer') / max(len([r for r in self.recommendations if r.source == 'cost_explorer']), 1)
        }    
  
  # Additional methods for Task 4.2: Enhanced Savings Plans processing
    
    def _convert_sp_recommendation_to_standard(self, sp_rec, config_key):
        """
        Convert Savings Plans recommendation to standard recommendation format
        
        Args:
            sp_rec: Raw Savings Plans recommendation
            config_key: Configuration key identifying the SP type and terms
            
        Returns:
            Standardized recommendation dictionary
        """
        try:
            # Parse configuration from key
            config_parts = config_key.split('_')
            sp_type = config_parts[0] + '_' + config_parts[1] if len(config_parts) >= 2 else 'COMPUTE_SP'
            term = config_parts[2] if len(config_parts) >= 3 else 'ONE_YEAR'
            payment = config_parts[3] if len(config_parts) >= 4 else 'NO_UPFRONT'
            
            # Extract financial information
            monthly_savings = float(sp_rec.get('EstimatedMonthlySavings', 0))
            
            # Get Savings Plans details
            details = sp_rec.get('SavingsPlansDetails', {})
            hourly_commitment = float(details.get('HourlyCommitment', 0))
            
            # Generate recommendation ID
            rec_id = f"sp_{sp_type.lower()}_{term.lower()}_{datetime.now().timestamp()}"
            
            return {
                'recommendationId': rec_id,
                'EstimatedMonthlySavings': monthly_savings,
                'category': 'commitment',
                'source': 'savings_plans',
                'name': f"Savings Plans Purchase - {sp_type} ({term})",
                'description': f"Purchase {sp_type} Savings Plan with {term} term and {payment} payment option",
                'implementationEffort': 'LOW',
                'resourceCount': 1,
                'SavingsPlansDetails': details,
                '_sp_type': sp_type,
                '_term': term,
                '_payment_option': payment,
                '_hourly_commitment': hourly_commitment,
                '_roi_analysis': sp_rec.get('_roi_analysis', {}),
                '_commitment_analysis': sp_rec.get('_commitment_analysis', {})
            }
        except Exception as e:
            _warn(f"Error converting Savings Plans recommendation: {str(e)}")
            return None
    
    def _convert_sp_opportunity_to_recommendation(self, opportunity):
        """
        Convert Savings Plans optimization opportunity to recommendation format
        
        Args:
            opportunity: Optimization opportunity dictionary
            
        Returns:
            Standardized recommendation dictionary
        """
        try:
            opp_type = opportunity.get('type', 'optimization')
            description = opportunity.get('description', 'Savings Plans optimization opportunity')
            impact = opportunity.get('impact', 'medium')
            action = opportunity.get('action', 'Review Savings Plans configuration')
            
            # Map impact to effort level
            effort_mapping = {
                'high': 'medium',
                'medium': 'medium',
                'low': 'low'
            }
            
            rec_id = f"sp_opt_{opp_type}_{datetime.now().timestamp()}"
            
            return {
                'recommendationId': rec_id,
                'EstimatedMonthlySavings': 0.0,  # Optimization opportunities don't have direct savings
                'category': 'optimization',
                'source': 'savings_plans',
                'name': f"Savings Plans Optimization - {opp_type.replace('_', ' ').title()}",
                'description': description,
                'implementationEffort': effort_mapping.get(impact, 'medium'),
                'resourceCount': 1,
                '_opportunity_type': opp_type,
                '_impact_level': impact,
                '_recommended_action': action
            }
        except Exception as e:
            _warn(f"Error converting Savings Plans opportunity: {str(e)}")
            return None
    
    def _enhance_sp_recommendation_processing(self, raw_data):
        """
        Enhanced processing for Savings Plans recommendations in validation workflow
        
        Args:
            raw_data: Raw Savings Plans data from collection
            
        Returns:
            List of processed recommendations
        """
        processed_recommendations = []
        
        try:
            # Process purchase recommendations
            purchase_recs = raw_data.get('processed_recommendations', [])
            for rec in purchase_recs:
                is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'savings_plans')
                
                if is_valid:
                    enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'savings_plans')
                    normalized = self._normalize_sp_recommendation(enriched_rec)
                    if normalized:
                        processed_recommendations.append(normalized)
            
            # Process optimization recommendations
            opt_recs = raw_data.get('optimization_recommendations', [])
            for rec in opt_recs:
                is_valid, cleaned_rec, errors = self.validate_recommendation_data(rec, 'savings_plans')
                
                if is_valid:
                    enriched_rec = self.enrich_recommendation_metadata(cleaned_rec, 'savings_plans')
                    normalized = self._normalize_sp_optimization_recommendation(enriched_rec)
                    if normalized:
                        processed_recommendations.append(normalized)
            
        except Exception as e:
            _warn(f"Error in enhanced Savings Plans processing: {str(e)}")
        
        return processed_recommendations
    
    def _normalize_sp_optimization_recommendation(self, rec):
        """
        Normalize Savings Plans optimization recommendation to unified format
        
        Args:
            rec: Processed optimization recommendation dictionary
            
        Returns:
            CostRecommendation object for SP optimization
        """
        try:
            opp_type = rec.get('_opportunity_type', 'optimization')
            impact_level = rec.get('_impact_level', 'medium')
            recommended_action = rec.get('_recommended_action', 'Review configuration')
            
            # Generate implementation steps based on opportunity type
            if opp_type == 'underutilization':
                implementation_steps = [
                    "Analyze current Savings Plans utilization patterns",
                    "Review workload usage and scaling patterns",
                    "Consider modifying or exchanging existing Savings Plans",
                    "Implement usage monitoring and alerts",
                    "Optimize resource allocation to improve utilization"
                ]
                potential_risks = [
                    "Continued underutilization may reduce cost savings",
                    "Plan modification may have restrictions or fees"
                ]
            elif opp_type == 'coverage_gap':
                implementation_steps = [
                    "Analyze uncovered usage patterns and costs",
                    "Evaluate additional Savings Plans purchase options",
                    "Compare Savings Plans vs Reserved Instance options",
                    "Plan Savings Plans purchase timing and configuration",
                    "Monitor coverage improvement after purchase"
                ]
                potential_risks = [
                    "Additional financial commitment required",
                    "Usage patterns may change affecting plan effectiveness"
                ]
            else:
                implementation_steps = [
                    "Review current Savings Plans configuration and performance",
                    "Analyze optimization opportunities and potential impact",
                    "Implement recommended configuration changes",
                    "Monitor performance and cost impact after changes"
                ]
                potential_risks = [
                    "Configuration changes may affect existing commitments",
                    "Optimization benefits may vary based on usage patterns"
                ]
            
            # Determine effort level based on impact
            effort_mapping = {
                'high': 'high',
                'medium': 'medium',
                'low': 'low'
            }
            
            return CostRecommendation(
                id=rec.get('recommendationId', f"sp_opt_{datetime.now().timestamp()}"),
                source='savings_plans',
                category='optimization',
                service='savings_plans',
                title=rec.get('name', 'Savings Plans Optimization'),
                description=rec.get('description', 'Optimize Savings Plans configuration'),
                monthly_savings=0.0,  # Optimization recommendations don't have direct savings
                annual_savings=0.0,
                confidence_level='medium',
                implementation_effort=effort_mapping.get(impact_level, 'medium'),
                implementation_steps=implementation_steps,
                required_permissions=[
                    'savingsplans:DescribeSavingsPlans',
                    'ce:GetSavingsPlansUtilization',
                    'ce:GetSavingsPlansCoverage'
                ],
                potential_risks=potential_risks,
                affected_resources=[{
                    'id': f"sp_optimization_{opp_type}",
                    'type': 'SavingsPlansOptimization',
                    'opportunity_type': opp_type,
                    'impact_level': impact_level,
                    'recommended_action': recommended_action
                }],
                resource_count=1,
                priority_score=0.0,  # Will be calculated later
                priority_level=impact_level,  # Use impact as initial priority
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
            
        except Exception as e:
            _warn(f"Error normalizing Savings Plans optimization recommendation: {str(e)}")
            return None
    
    def analyze_sp_vs_ri_comparison(self, sp_data, ri_data):
        """
        Analyze Savings Plans vs Reserved Instance options for optimal commitment strategy
        
        Args:
            sp_data: Savings Plans recommendation data
            ri_data: Reserved Instance recommendation data
            
        Returns:
            List of comparison recommendations
        """
        comparison_recommendations = []
        
        try:
            # Extract SP and RI recommendations for comparison
            sp_recommendations = sp_data.get('processed_recommendations', [])
            ri_recommendations = ri_data.get('ri_recommendations', [])
            
            if not sp_recommendations and not ri_recommendations:
                return comparison_recommendations
            
            # Create comparison analysis
            for sp_rec in sp_recommendations:
                sp_savings = float(sp_rec.get('EstimatedMonthlySavings', 0))
                sp_commitment = float(sp_rec.get('_hourly_commitment', 0)) * 24 * 30  # Monthly commitment
                
                # Find comparable RI recommendations
                comparable_ri = []
                for ri_rec in ri_recommendations:
                    ri_details = ri_rec.get('RecommendationDetails', {})
                    ri_savings = float(ri_details.get('EstimatedMonthlySavingsAmount', 0))
                    
                    # Consider RI comparable if savings are within 50% range
                    if abs(ri_savings - sp_savings) / max(sp_savings, 1) <= 0.5:
                        comparable_ri.append(ri_rec)
                
                if comparable_ri:
                    # Create comparison recommendation
                    comparison_rec = self._create_sp_ri_comparison_recommendation(sp_rec, comparable_ri)
                    if comparison_rec:
                        comparison_recommendations.append(comparison_rec)
            
        except Exception as e:
            _warn(f"Error in SP vs RI comparison analysis: {str(e)}")
        
        return comparison_recommendations
    
    def _create_sp_ri_comparison_recommendation(self, sp_rec, ri_recs):
        """
        Create a comparison recommendation between Savings Plans and Reserved Instances
        
        Args:
            sp_rec: Savings Plans recommendation
            ri_recs: List of comparable RI recommendations
            
        Returns:
            CostRecommendation for SP vs RI comparison
        """
        try:
            sp_savings = float(sp_rec.get('EstimatedMonthlySavings', 0))
            sp_commitment = float(sp_rec.get('_hourly_commitment', 0)) * 24 * 30
            
            # Calculate average RI savings and commitment
            ri_savings_total = sum(
                float(ri.get('RecommendationDetails', {}).get('EstimatedMonthlySavingsAmount', 0))
                for ri in ri_recs
            )
            ri_avg_savings = ri_savings_total / len(ri_recs) if ri_recs else 0
            
            # Determine recommendation
            if sp_savings > ri_avg_savings * 1.1:  # SP is 10% better
                recommendation = "Savings Plans"
                reason = f"Savings Plans offers {sp_savings - ri_avg_savings:.2f} more monthly savings"
            elif ri_avg_savings > sp_savings * 1.1:  # RI is 10% better
                recommendation = "Reserved Instances"
                reason = f"Reserved Instances offer {ri_avg_savings - sp_savings:.2f} more monthly savings"
            else:
                recommendation = "Either option"
                reason = "Both options provide similar savings - choose based on flexibility needs"
            
            return CostRecommendation(
                id=f"sp_ri_comparison_{datetime.now().timestamp()}",
                source='savings_plans',
                category='comparison',
                service='commitment_analysis',
                title=f"Commitment Strategy: Choose {recommendation}",
                description=f"Analysis of Savings Plans vs Reserved Instances. {reason}",
                monthly_savings=max(sp_savings, ri_avg_savings),
                annual_savings=max(sp_savings, ri_avg_savings) * 12,
                confidence_level='high',
                implementation_effort='medium',
                implementation_steps=[
                    "Review detailed comparison analysis of Savings Plans vs Reserved Instances",
                    "Consider flexibility requirements and usage patterns",
                    "Evaluate commitment terms and payment options",
                    "Choose optimal commitment strategy based on analysis",
                    "Implement chosen commitment option",
                    "Monitor performance and adjust strategy as needed"
                ],
                required_permissions=[
                    'savingsplans:DescribeSavingsPlansOfferings',
                    'ec2:DescribeReservedInstancesOfferings',
                    'ce:GetSavingsPlanssPurchaseRecommendation',
                    'ce:GetReservationPurchaseRecommendation'
                ],
                potential_risks=[
                    "Commitment decision affects long-term cost optimization",
                    "Usage pattern changes may impact effectiveness of chosen option"
                ],
                affected_resources=[{
                    'id': 'commitment_strategy_analysis',
                    'type': 'CommitmentComparison',
                    'sp_monthly_savings': sp_savings,
                    'ri_monthly_savings': ri_avg_savings,
                    'recommendation': recommendation,
                    'reason': reason
                }],
                resource_count=1,
                priority_score=0.0,
                priority_level='high',  # Commitment decisions are high priority
                created_date=datetime.now(),
                last_updated=datetime.now(),
                status='new'
            )
            
        except Exception as e:
            _warn(f"Error creating SP vs RI comparison recommendation: {str(e)}")
            return None
    
    def get_savings_plans_processing_summary(self):
        """
        Get summary of Savings Plans data processing
        
        Returns:
            Dictionary with processing statistics specific to Savings Plans
        """
        if not hasattr(self, '_processing_stats'):
            return {'error': 'No processing statistics available'}
        
        sp_stats = self._processing_stats.get('source_breakdown', {}).get('savings_plans', {})
        
        sp_recommendations = [r for r in self.recommendations if r.source == 'savings_plans']
        
        return {
            'purchase_recommendations': len([r for r in sp_recommendations if r.category == 'commitment']),
            'optimization_recommendations': len([r for r in sp_recommendations if r.category == 'optimization']),
            'comparison_analyses': len([r for r in sp_recommendations if r.category == 'comparison']),
            'total_sp_recommendations': len(sp_recommendations),
            'processing_stats': sp_stats,
            'average_monthly_savings': sum(r.monthly_savings for r in sp_recommendations) / max(len(sp_recommendations), 1),
            'total_commitment_potential': sum(
                float(r.affected_resources[0].get('sp_monthly_savings', 0)) 
                for r in sp_recommendations 
                if r.affected_resources and 'sp_monthly_savings' in r.affected_resources[0]
            )
        }    

    # Additional methods for Task 5.1: Advanced aggregation and deduplication
    
    def create_unified_savings_methodology(self):
        """
        Create unified savings calculation methodology across all sources
        
        Returns:
            Dictionary with standardized savings calculation rules
        """
        return {
            'calculation_rules': {
                'monthly_to_annual_multiplier': 12,
                'confidence_adjustments': {
                    'high': 1.0,      # No adjustment for high confidence
                    'medium': 0.9,    # 10% reduction for medium confidence
                    'low': 0.7        # 30% reduction for low confidence
                },
                'source_reliability_factors': {
                    'coh': 1.0,           # Official AWS recommendations - full value
                    'cost_explorer': 1.0, # Official AWS service - full value
                    'savings_plans': 1.0, # Official AWS service - full value
                    'merged': 0.95        # Slight reduction for merged recommendations
                },
                'implementation_effort_adjustments': {
                    'low': 1.0,      # No adjustment for easy implementation
                    'medium': 0.95,  # 5% reduction for moderate effort
                    'high': 0.85     # 15% reduction for high effort
                }
            },
            'aggregation_rules': {
                'duplicate_handling': 'max_savings',  # Use maximum savings when merging
                'confidence_merging': 'highest',      # Use highest confidence level
                'effort_merging': 'conservative',     # Use highest effort estimate
                'risk_merging': 'comprehensive'       # Combine all unique risks
            },
            'validation_rules': {
                'minimum_monthly_savings': 1.0,       # Minimum $1/month to be considered
                'maximum_monthly_savings': 100000.0,  # Maximum $100k/month (sanity check)
                'savings_growth_limit': 2.0           # Annual can't be more than 2x monthly * 12
            }
        }
    
    def apply_unified_savings_calculation(self, recommendations):
        """
        Apply unified savings calculation methodology to all recommendations
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of recommendations with standardized savings calculations
        """
        methodology = self.create_unified_savings_methodology()
        
        for rec in recommendations:
            # Apply confidence adjustments
            confidence_factor = methodology['calculation_rules']['confidence_adjustments'].get(
                rec.confidence_level, 0.9
            )
            
            # Apply source reliability factors
            source_factor = methodology['calculation_rules']['source_reliability_factors'].get(
                rec.source, 1.0
            )
            
            # Apply implementation effort adjustments
            effort_factor = methodology['calculation_rules']['implementation_effort_adjustments'].get(
                rec.implementation_effort, 0.95
            )
            
            # Calculate adjusted savings
            raw_monthly = rec.monthly_savings
            adjusted_monthly = raw_monthly * confidence_factor * source_factor * effort_factor
            
            # Apply validation rules
            min_savings = methodology['validation_rules']['minimum_monthly_savings']
            max_savings = methodology['validation_rules']['maximum_monthly_savings']
            
            adjusted_monthly = max(min_savings, min(max_savings, adjusted_monthly))
            
            # Update recommendation with adjusted values
            rec.monthly_savings = adjusted_monthly
            rec.annual_savings = adjusted_monthly * methodology['calculation_rules']['monthly_to_annual_multiplier']
            
            # Validate annual savings growth
            max_annual = raw_monthly * methodology['validation_rules']['savings_growth_limit']
            rec.annual_savings = min(rec.annual_savings, max_annual)
            
            # Add metadata about adjustments
            rec._savings_adjustments = {
                'original_monthly': raw_monthly,
                'confidence_factor': confidence_factor,
                'source_factor': source_factor,
                'effort_factor': effort_factor,
                'final_monthly': adjusted_monthly
            }
        
        return recommendations
    
    def create_recommendation_conflict_resolver(self):
        """
        Create conflict resolution strategies for overlapping recommendations
        
        Returns:
            Dictionary with conflict resolution strategies
        """
        return {
            'resource_conflicts': {
                'same_resource_different_actions': 'prioritize_highest_savings',
                'overlapping_resources': 'merge_if_compatible',
                'conflicting_commitments': 'choose_optimal_strategy'
            },
            'timing_conflicts': {
                'simultaneous_changes': 'sequence_by_priority',
                'dependency_ordering': 'respect_dependencies',
                'maintenance_windows': 'group_compatible_changes'
            },
            'financial_conflicts': {
                'budget_constraints': 'prioritize_by_roi',
                'commitment_overlaps': 'optimize_total_commitment',
                'cash_flow_timing': 'spread_implementation'
            }
        }
    
    def resolve_recommendation_conflicts(self, recommendations):
        """
        Resolve conflicts between recommendations using intelligent strategies
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of recommendations with conflicts resolved
        """
        resolver = self.create_recommendation_conflict_resolver()
        
        # Group recommendations by potential conflicts
        conflict_groups = self._identify_conflicting_recommendations(recommendations)
        
        resolved_recommendations = []
        processed_ids = set()
        
        for group in conflict_groups:
            if len(group) == 1:
                # No conflicts, add as-is
                resolved_recommendations.extend(group)
                processed_ids.update(rec.id for rec in group)
            else:
                # Resolve conflicts within the group
                resolved_group = self._resolve_group_conflicts(group, resolver)
                resolved_recommendations.extend(resolved_group)
                processed_ids.update(rec.id for rec in resolved_group)
        
        # Add any recommendations that weren't part of conflict groups
        for rec in recommendations:
            if rec.id not in processed_ids:
                resolved_recommendations.append(rec)
        
        return resolved_recommendations
    
    def _identify_conflicting_recommendations(self, recommendations):
        """
        Identify groups of recommendations that may conflict with each other
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of conflict groups (each group is a list of potentially conflicting recommendations)
        """
        conflict_groups = []
        ungrouped = recommendations.copy()
        
        while ungrouped:
            seed = ungrouped.pop(0)
            conflict_group = [seed]
            
            # Find recommendations that conflict with the seed
            remaining = []
            for rec in ungrouped:
                if self._do_recommendations_conflict(seed, rec):
                    conflict_group.append(rec)
                else:
                    remaining.append(rec)
            
            ungrouped = remaining
            conflict_groups.append(conflict_group)
        
        return conflict_groups
    
    def _do_recommendations_conflict(self, rec1, rec2):
        """
        Determine if two recommendations conflict with each other
        
        Args:
            rec1, rec2: CostRecommendation objects to check for conflicts
            
        Returns:
            Boolean indicating if recommendations conflict
        """
        # Check for resource conflicts
        rec1_resources = {res.get('id', '') for res in rec1.affected_resources}
        rec2_resources = {res.get('id', '') for res in rec2.affected_resources}
        
        if rec1_resources.intersection(rec2_resources):
            # Same resources affected - potential conflict
            return True
        
        # Check for commitment conflicts (RI vs SP for same service)
        if (rec1.category == 'commitment' and rec2.category == 'commitment' and
            rec1.service != rec2.service):
            # Different commitment types for potentially same usage
            return True
        
        # Check for implementation timing conflicts
        if (rec1.implementation_effort == 'high' and rec2.implementation_effort == 'high' and
            rec1.service == rec2.service):
            # Multiple high-effort changes to same service
            return True
        
        return False
    
    def _resolve_group_conflicts(self, group, resolver):
        """
        Resolve conflicts within a group of recommendations
        
        Args:
            group: List of conflicting CostRecommendation objects
            resolver: Conflict resolution strategies
            
        Returns:
            List of resolved recommendations (may be fewer than input)
        """
        if len(group) <= 1:
            return group
        
        # Sort by priority score to help with resolution
        group.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Apply conflict resolution strategies
        resolved = []
        
        # Strategy 1: If recommendations target same resources, keep highest savings
        resource_groups = self._group_by_affected_resources(group)
        
        for resource_group in resource_groups:
            if len(resource_group) == 1:
                resolved.extend(resource_group)
            else:
                # Keep the recommendation with highest total impact
                best_rec = max(resource_group, key=lambda r: (
                    r.priority_score,
                    r.monthly_savings,
                    -len(r.potential_risks)  # Fewer risks is better
                ))
                
                # Create a note about the conflict resolution
                best_rec.description += f" (Selected from {len(resource_group)} similar recommendations based on highest impact)"
                resolved.append(best_rec)
        
        return resolved
    
    def _group_by_affected_resources(self, recommendations):
        """
        Group recommendations by their affected resources
        
        Args:
            recommendations: List of CostRecommendation objects
            
        Returns:
            List of resource groups
        """
        resource_map = {}
        
        for rec in recommendations:
            resource_key = frozenset(res.get('id', '') for res in rec.affected_resources)
            if resource_key not in resource_map:
                resource_map[resource_key] = []
            resource_map[resource_key].append(rec)
        
        return list(resource_map.values())
    
    def get_aggregation_statistics(self, original_count, deduplicated_count, final_count):
        """
        Generate statistics about the aggregation and deduplication process
        
        Args:
            original_count: Number of recommendations before processing
            deduplicated_count: Number after deduplication
            final_count: Number after conflict resolution
            
        Returns:
            Dictionary with aggregation statistics
        """
        return {
            'original_recommendations': original_count,
            'after_deduplication': deduplicated_count,
            'after_conflict_resolution': final_count,
            'deduplication_rate': ((original_count - deduplicated_count) / max(original_count, 1)) * 100,
            'conflict_resolution_rate': ((deduplicated_count - final_count) / max(deduplicated_count, 1)) * 100,
            'total_reduction_rate': ((original_count - final_count) / max(original_count, 1)) * 100,
            'processing_efficiency': (final_count / max(original_count, 1)) * 100
        }    

    # Task 5.3: Advanced Cost Optimization Analytics
    
    def calculate_comprehensive_analytics(self):
        """
        Calculate comprehensive cost optimization analytics and metrics
        
        Returns:
            Dictionary with detailed analytics and insights
        """
        if not self.recommendations:
            return self._get_empty_analytics()
        
        analytics = {
            'financial_metrics': self._calculate_financial_metrics(),
            'implementation_analysis': self._analyze_implementation_complexity(),
            'risk_assessment': self._assess_portfolio_risk(),
            'opportunity_matrix': self._create_opportunity_matrix(),
            'roi_analysis': self._calculate_roi_metrics(),
            'timeline_analysis': self._analyze_implementation_timeline(),
            'service_breakdown': self._analyze_by_service(),
            'source_analysis': self._analyze_by_source(),
            'confidence_distribution': self._analyze_confidence_distribution(),
            'optimization_roadmap': self._generate_optimization_roadmap()
        }
        
        # Add meta-analytics
        analytics['meta'] = {
            'total_recommendations': len(self.recommendations),
            'analysis_timestamp': datetime.now().isoformat(),
            'data_quality_score': self._calculate_overall_data_quality(),
            'completeness_score': self._calculate_analytics_completeness(analytics)
        }
        
        return analytics
    
    def _get_empty_analytics(self):
        """Return empty analytics structure when no recommendations exist"""
        return {
            'financial_metrics': {
                'total_monthly_savings': 0,
                'total_annual_savings': 0,
                'average_monthly_savings': 0,
                'median_monthly_savings': 0,
                'savings_distribution': {},
                'high_impact_count': 0,
                'quick_wins_count': 0
            },
            'implementation_analysis': {
                'effort_distribution': {'low': 0, 'medium': 0, 'high': 0},
                'complexity_score': 0,
                'bottlenecks': [],
                'effort_efficiency': {}
            },
            'risk_assessment': {
                'overall_risk_score': 0,
                'savings_at_risk': 0,
                'high_risk_recommendations': []
            },
            'opportunity_matrix': {'insights': {'quick_wins': 0, 'major_projects': 0}},
            'roi_analysis': {'overall_roi_percentage': 0, 'payback_period_months': 0},
            'timeline_analysis': {},
            'service_breakdown': {'by_service': {}, 'service_diversity': 0},
            'source_analysis': {},
            'confidence_distribution': {'overall_confidence_score': 0},
            'optimization_roadmap': {'phases': [], 'milestones': []},
            'meta': {
                'total_recommendations': 0,
                'analysis_timestamp': datetime.now().isoformat(),
                'data_quality_score': 0,
                'completeness_score': 0
            }
        }
    
    def _calculate_financial_metrics(self):
        """Calculate comprehensive financial metrics"""
        total_monthly = sum(rec.monthly_savings for rec in self.recommendations)
        total_annual = sum(rec.annual_savings for rec in self.recommendations)
        
        # Calculate savings distribution
        savings_amounts = [rec.monthly_savings for rec in self.recommendations if rec.monthly_savings > 0]
        
        if not savings_amounts:
            return {
                'total_monthly_savings': 0,
                'total_annual_savings': 0,
                'average_monthly_savings': 0,
                'median_monthly_savings': 0,
                'savings_distribution': {},
                'high_impact_count': 0,
                'quick_wins_count': 0
            }
        
        # Statistical analysis
        savings_amounts.sort()
        median_savings = savings_amounts[len(savings_amounts) // 2]
        average_savings = sum(savings_amounts) / len(savings_amounts)
        
        # Categorize savings amounts
        savings_distribution = {
            'under_50': len([s for s in savings_amounts if s < 50]),
            '50_to_200': len([s for s in savings_amounts if 50 <= s < 200]),
            '200_to_500': len([s for s in savings_amounts if 200 <= s < 500]),
            '500_to_1000': len([s for s in savings_amounts if 500 <= s < 1000]),
            'over_1000': len([s for s in savings_amounts if s >= 1000])
        }
        
        # Identify high-impact and quick wins
        high_impact_count = len([rec for rec in self.recommendations 
                               if rec.monthly_savings >= 200 and rec.priority_level == 'high'])
        quick_wins_count = len([rec for rec in self.recommendations 
                              if rec.implementation_effort == 'low' and rec.monthly_savings >= 50])
        
        return {
            'total_monthly_savings': total_monthly,
            'total_annual_savings': total_annual,
            'average_monthly_savings': average_savings,
            'median_monthly_savings': median_savings,
            'savings_distribution': savings_distribution,
            'high_impact_count': high_impact_count,
            'quick_wins_count': quick_wins_count,
            'savings_concentration': self._calculate_savings_concentration(savings_amounts)
        }
    
    def _calculate_savings_concentration(self, savings_amounts):
        """Calculate how concentrated the savings are (Gini-like coefficient)"""
        if not savings_amounts or len(savings_amounts) < 2:
            return 0
        
        # Sort savings amounts
        sorted_savings = sorted(savings_amounts)
        n = len(sorted_savings)
        total_savings = sum(sorted_savings)
        
        if total_savings == 0:
            return 0
        
        # Calculate concentration index
        cumulative_sum = 0
        concentration_sum = 0
        
        for i, savings in enumerate(sorted_savings):
            cumulative_sum += savings
            concentration_sum += cumulative_sum
        
        # Normalize to 0-1 scale (0 = perfectly distributed, 1 = highly concentrated)
        gini_numerator = 2 * concentration_sum - total_savings * (n + 1)
        gini_denominator = total_savings * n
        
        return gini_numerator / gini_denominator if gini_denominator > 0 else 0
    
    def _analyze_implementation_complexity(self):
        """Analyze implementation complexity across all recommendations"""
        effort_counts = {'low': 0, 'medium': 0, 'high': 0}
        effort_savings = {'low': 0, 'medium': 0, 'high': 0}
        
        for rec in self.recommendations:
            effort = rec.implementation_effort
            effort_counts[effort] = effort_counts.get(effort, 0) + 1
            effort_savings[effort] = effort_savings.get(effort, 0) + rec.monthly_savings
        
        # Calculate complexity metrics
        total_recs = len(self.recommendations)
        complexity_score = (
            effort_counts.get('low', 0) * 1 + 
            effort_counts.get('medium', 0) * 2 + 
            effort_counts.get('high', 0) * 3
        ) / max(total_recs, 1)
        
        # Identify implementation bottlenecks
        bottlenecks = []
        if effort_counts.get('high', 0) > total_recs * 0.3:
            bottlenecks.append("High proportion of high-effort recommendations")
        
        # Calculate effort-to-savings ratio
        effort_efficiency = {}
        for effort in ['low', 'medium', 'high']:
            count = effort_counts.get(effort, 0)
            savings = effort_savings.get(effort, 0)
            effort_efficiency[effort] = savings / max(count, 1)
        
        return {
            'effort_distribution': effort_counts,
            'effort_savings': effort_savings,
            'complexity_score': complexity_score,
            'bottlenecks': bottlenecks,
            'effort_efficiency': effort_efficiency,
            'recommended_sequence': self._recommend_implementation_sequence()
        }
    
    def _recommend_implementation_sequence(self):
        """Recommend optimal implementation sequence"""
        # Sort recommendations by effort and impact
        low_effort_high_impact = [rec for rec in self.recommendations 
                                if rec.implementation_effort == 'low' and rec.monthly_savings >= 100]
        medium_effort_high_impact = [rec for rec in self.recommendations 
                                   if rec.implementation_effort == 'medium' and rec.monthly_savings >= 200]
        
        sequence = []
        if low_effort_high_impact:
            sequence.append({
                'phase': 'Quick Wins',
                'recommendations': len(low_effort_high_impact),
                'estimated_timeline': '1-2 weeks',
                'total_savings': sum(rec.monthly_savings for rec in low_effort_high_impact)
            })
        
        if medium_effort_high_impact:
            sequence.append({
                'phase': 'High Impact Projects',
                'recommendations': len(medium_effort_high_impact),
                'estimated_timeline': '1-2 months',
                'total_savings': sum(rec.monthly_savings for rec in medium_effort_high_impact)
            })
        
        return sequence
    
    def _assess_portfolio_risk(self):
        """Assess overall risk of the optimization portfolio"""
        risk_levels = {'low': 0, 'medium': 0, 'high': 0}
        confidence_levels = {'low': 0, 'medium': 0, 'high': 0}
        
        total_savings_at_risk = 0
        high_risk_recommendations = []
        
        for rec in self.recommendations:
            # Assess risk based on implementation effort and confidence
            if rec.implementation_effort == 'high' or rec.confidence_level == 'low':
                risk_level = 'high'
                total_savings_at_risk += rec.monthly_savings
                high_risk_recommendations.append(rec.id)
            elif rec.implementation_effort == 'medium' and rec.confidence_level == 'medium':
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            risk_levels[risk_level] += 1
            confidence_levels[rec.confidence_level] += 1
        
        # Calculate overall risk score
        total_recs = len(self.recommendations)
        risk_score = (
            risk_levels.get('low', 0) * 1 + 
            risk_levels.get('medium', 0) * 2 + 
            risk_levels.get('high', 0) * 3
        ) / max(total_recs, 1)
        
        return {
            'risk_distribution': risk_levels,
            'confidence_distribution': confidence_levels,
            'overall_risk_score': risk_score,
            'savings_at_risk': total_savings_at_risk,
            'high_risk_recommendations': high_risk_recommendations,
            'risk_mitigation_suggestions': self._generate_risk_mitigation_suggestions(risk_score)
        }
    
    def _generate_risk_mitigation_suggestions(self, risk_score):
        """Generate risk mitigation suggestions based on risk score"""
        suggestions = []
        
        if risk_score >= 2.5:
            suggestions.extend([
                "Consider implementing high-risk recommendations in phases",
                "Establish rollback procedures for high-impact changes",
                "Increase testing and validation for complex implementations"
            ])
        
        if risk_score >= 2.0:
            suggestions.extend([
                "Prioritize low-risk, high-impact recommendations first",
                "Establish monitoring and alerting for implemented changes"
            ])
        
        suggestions.append("Regular review and adjustment of optimization strategy")
        
        return suggestions
    
    def _create_opportunity_matrix(self):
        """Create opportunity matrix (impact vs effort)"""
        matrix = {
            'high_impact_low_effort': [],
            'high_impact_medium_effort': [],
            'high_impact_high_effort': [],
            'medium_impact_low_effort': [],
            'medium_impact_medium_effort': [],
            'medium_impact_high_effort': [],
            'low_impact_low_effort': [],
            'low_impact_medium_effort': [],
            'low_impact_high_effort': []
        }
        
        for rec in self.recommendations:
            # Categorize impact based on savings
            if rec.monthly_savings >= 200:
                impact = 'high'
            elif rec.monthly_savings >= 50:
                impact = 'medium'
            else:
                impact = 'low'
            
            effort = rec.implementation_effort
            key = f"{impact}_impact_{effort}_effort"
            
            matrix[key].append({
                'id': rec.id,
                'title': rec.title,
                'monthly_savings': rec.monthly_savings,
                'service': rec.service,
                'priority_score': rec.priority_score
            })
        
        # Add matrix insights
        matrix['insights'] = {
            'quick_wins': len(matrix['high_impact_low_effort']) + len(matrix['medium_impact_low_effort']),
            'major_projects': len(matrix['high_impact_high_effort']),
            'fill_ins': len(matrix['low_impact_low_effort']),
            'questionable': len(matrix['low_impact_high_effort'])
        }
        
        return matrix
    
    def _calculate_roi_metrics(self):
        """Calculate ROI metrics for the optimization portfolio"""
        # Estimate implementation costs based on effort levels
        effort_costs = {'low': 500, 'medium': 2000, 'high': 5000}  # Estimated costs in USD
        
        total_implementation_cost = 0
        total_annual_savings = 0
        roi_by_effort = {'low': [], 'medium': [], 'high': []}
        
        for rec in self.recommendations:
            impl_cost = effort_costs.get(rec.implementation_effort, 2000)
            annual_savings = rec.annual_savings
            
            total_implementation_cost += impl_cost
            total_annual_savings += annual_savings
            
            if annual_savings > 0:
                roi = (annual_savings - impl_cost) / impl_cost * 100
                roi_by_effort[rec.implementation_effort].append(roi)
        
        # Calculate overall ROI
        overall_roi = 0
        if total_implementation_cost > 0:
            overall_roi = (total_annual_savings - total_implementation_cost) / total_implementation_cost * 100
        
        # Calculate payback period
        payback_months = 0
        if total_annual_savings > 0:
            payback_months = total_implementation_cost / (total_annual_savings / 12)
        
        return {
            'overall_roi_percentage': overall_roi,
            'total_implementation_cost': total_implementation_cost,
            'total_annual_savings': total_annual_savings,
            'payback_period_months': payback_months,
            'roi_by_effort': {effort: sum(rois)/len(rois) if rois else 0 
                            for effort, rois in roi_by_effort.items()},
            'break_even_analysis': self._calculate_break_even_timeline()
        }
    
    def _calculate_break_even_timeline(self):
        """Calculate when the optimization portfolio breaks even"""
        # Sort recommendations by ROI (highest first)
        recs_with_roi = []
        effort_costs = {'low': 500, 'medium': 2000, 'high': 5000}
        
        for rec in self.recommendations:
            impl_cost = effort_costs.get(rec.implementation_effort, 2000)
            if rec.monthly_savings > 0:
                payback_months = impl_cost / rec.monthly_savings
                recs_with_roi.append({
                    'id': rec.id,
                    'monthly_savings': rec.monthly_savings,
                    'implementation_cost': impl_cost,
                    'payback_months': payback_months
                })
        
        # Sort by payback period (shortest first)
        recs_with_roi.sort(key=lambda x: x['payback_months'])
        
        # Calculate cumulative break-even timeline
        cumulative_cost = 0
        cumulative_monthly_savings = 0
        timeline = []
        
        for rec in recs_with_roi:
            cumulative_cost += rec['implementation_cost']
            cumulative_monthly_savings += rec['monthly_savings']
            
            if cumulative_monthly_savings > 0:
                break_even_months = cumulative_cost / cumulative_monthly_savings
                timeline.append({
                    'recommendations_implemented': len(timeline) + 1,
                    'cumulative_cost': cumulative_cost,
                    'monthly_savings': cumulative_monthly_savings,
                    'break_even_months': break_even_months
                })
        
        return timeline
    
    def _analyze_implementation_timeline(self):
        """Analyze optimal implementation timeline"""
        # Group recommendations by implementation effort and priority
        timeline_phases = {
            'immediate': [],  # Low effort, high priority
            'short_term': [],  # Medium effort or medium priority
            'long_term': []   # High effort or complex implementations
        }
        
        for rec in self.recommendations:
            if rec.implementation_effort == 'low' and rec.priority_level in ['high', 'medium']:
                timeline_phases['immediate'].append(rec)
            elif rec.implementation_effort == 'high' or rec.priority_level == 'low':
                timeline_phases['long_term'].append(rec)
            else:
                timeline_phases['short_term'].append(rec)
        
        # Calculate timeline metrics
        timeline_analysis = {}
        phase_durations = {'immediate': 2, 'short_term': 8, 'long_term': 24}  # weeks
        
        for phase, recs in timeline_phases.items():
            if recs:
                timeline_analysis[phase] = {
                    'recommendation_count': len(recs),
                    'total_monthly_savings': sum(rec.monthly_savings for rec in recs),
                    'estimated_duration_weeks': phase_durations[phase],
                    'average_savings_per_rec': sum(rec.monthly_savings for rec in recs) / len(recs),
                    'top_recommendations': [{
                        'id': rec.id,
                        'title': rec.title,
                        'monthly_savings': rec.monthly_savings
                    } for rec in sorted(recs, key=lambda x: x.monthly_savings, reverse=True)[:3]]
                }
        
        return timeline_analysis
    
    def _analyze_by_service(self):
        """Analyze recommendations by AWS service"""
        from collections import defaultdict
        
        service_analysis = defaultdict(lambda: {
            'count': 0,
            'total_savings': 0,
            'avg_savings': 0,
            'effort_distribution': {'low': 0, 'medium': 0, 'high': 0},
            'confidence_distribution': {'low': 0, 'medium': 0, 'high': 0}
        })
        
        for rec in self.recommendations:
            service = rec.service
            service_analysis[service]['count'] += 1
            service_analysis[service]['total_savings'] += rec.monthly_savings
            service_analysis[service]['effort_distribution'][rec.implementation_effort] += 1
            service_analysis[service]['confidence_distribution'][rec.confidence_level] += 1
        
        # Calculate averages and rankings
        for service, data in service_analysis.items():
            data['avg_savings'] = data['total_savings'] / data['count']
        
        # Convert to regular dict and sort by total savings
        service_analysis = dict(service_analysis)
        sorted_services = sorted(service_analysis.items(), 
                               key=lambda x: x[1]['total_savings'], reverse=True)
        
        return {
            'by_service': service_analysis,
            'top_services': sorted_services[:5],
            'service_diversity': len(service_analysis),
            'concentration_analysis': self._analyze_service_concentration(service_analysis)
        }
    
    def _analyze_service_concentration(self, service_analysis):
        """Analyze how concentrated recommendations are across services"""
        total_savings = sum(data['total_savings'] for data in service_analysis.values())
        if total_savings == 0:
            return {'top_service_percentage': 0, 'top_3_percentage': 0}
        
        sorted_services = sorted(service_analysis.items(), 
                               key=lambda x: x[1]['total_savings'], reverse=True)
        
        top_service_pct = sorted_services[0][1]['total_savings'] / total_savings * 100 if sorted_services else 0
        top_3_savings = sum(data['total_savings'] for _, data in sorted_services[:3])
        top_3_pct = top_3_savings / total_savings * 100
        
        return {
            'top_service_percentage': top_service_pct,
            'top_3_percentage': top_3_pct,
            'is_concentrated': top_service_pct > 50
        }
    
    def _analyze_by_source(self):
        """Analyze recommendations by data source"""
        from collections import defaultdict
        
        source_analysis = defaultdict(lambda: {
            'count': 0,
            'total_savings': 0,
            'avg_confidence': 0,
            'categories': set()
        })
        
        for rec in self.recommendations:
            source = rec.source
            source_analysis[source]['count'] += 1
            source_analysis[source]['total_savings'] += rec.monthly_savings
            source_analysis[source]['categories'].add(rec.category)
        
        # Convert sets to lists and calculate averages
        for source, data in source_analysis.items():
            data['categories'] = list(data['categories'])
            data['avg_savings'] = data['total_savings'] / data['count']
        
        return dict(source_analysis)
    
    def _analyze_confidence_distribution(self):
        """Analyze confidence level distribution and its impact"""
        confidence_analysis = {
            'distribution': {'low': 0, 'medium': 0, 'high': 0},
            'savings_by_confidence': {'low': 0, 'medium': 0, 'high': 0},
            'avg_savings_by_confidence': {'low': 0, 'medium': 0, 'high': 0}
        }
        
        confidence_counts = {'low': 0, 'medium': 0, 'high': 0}
        
        for rec in self.recommendations:
            confidence = rec.confidence_level
            confidence_analysis['distribution'][confidence] += 1
            confidence_analysis['savings_by_confidence'][confidence] += rec.monthly_savings
            confidence_counts[confidence] += 1
        
        # Calculate averages
        for confidence in ['low', 'medium', 'high']:
            count = confidence_counts[confidence]
            if count > 0:
                confidence_analysis['avg_savings_by_confidence'][confidence] = \
                    confidence_analysis['savings_by_confidence'][confidence] / count
        
        # Calculate confidence score
        total_recs = len(self.recommendations)
        confidence_score = (
            confidence_analysis['distribution']['low'] * 1 +
            confidence_analysis['distribution']['medium'] * 2 +
            confidence_analysis['distribution']['high'] * 3
        ) / max(total_recs, 1)
        
        confidence_analysis['overall_confidence_score'] = confidence_score
        
        return confidence_analysis
    
    def _generate_optimization_roadmap(self):
        """Generate a comprehensive optimization roadmap"""
        roadmap = {
            'phases': [],
            'milestones': [],
            'success_metrics': [],
            'risk_checkpoints': []
        }
        
        # Phase 1: Quick Wins (0-4 weeks)
        quick_wins = [rec for rec in self.recommendations 
                     if rec.implementation_effort == 'low' and rec.monthly_savings >= 25]
        if quick_wins:
            roadmap['phases'].append({
                'name': 'Quick Wins',
                'duration': '2-4 weeks',
                'recommendations': len(quick_wins),
                'expected_savings': sum(rec.monthly_savings for rec in quick_wins),
                'key_activities': [
                    'Implement low-effort, high-impact optimizations',
                    'Establish baseline metrics and monitoring',
                    'Build momentum and stakeholder confidence'
                ]
            })
        
        # Phase 2: Strategic Implementations (1-3 months)
        strategic_recs = [rec for rec in self.recommendations 
                         if rec.implementation_effort == 'medium' and rec.monthly_savings >= 100]
        if strategic_recs:
            roadmap['phases'].append({
                'name': 'Strategic Implementations',
                'duration': '1-3 months',
                'recommendations': len(strategic_recs),
                'expected_savings': sum(rec.monthly_savings for rec in strategic_recs),
                'key_activities': [
                    'Execute medium-complexity optimizations',
                    'Implement comprehensive monitoring and alerting',
                    'Refine optimization processes based on learnings'
                ]
            })
        
        # Phase 3: Complex Optimizations (3-6 months)
        complex_recs = [rec for rec in self.recommendations 
                       if rec.implementation_effort == 'high']
        if complex_recs:
            roadmap['phases'].append({
                'name': 'Complex Optimizations',
                'duration': '3-6 months',
                'recommendations': len(complex_recs),
                'expected_savings': sum(rec.monthly_savings for rec in complex_recs),
                'key_activities': [
                    'Execute high-complexity, high-impact optimizations',
                    'Implement advanced automation and governance',
                    'Establish continuous optimization processes'
                ]
            })
        
        # Define milestones
        cumulative_savings = 0
        for i, phase in enumerate(roadmap['phases']):
            cumulative_savings += phase['expected_savings']
            roadmap['milestones'].append({
                'phase': phase['name'],
                'target_date': f"End of {phase['duration']}",
                'cumulative_monthly_savings': cumulative_savings,
                'success_criteria': f"Achieve ${cumulative_savings:,.0f}/month in cost savings"
            })
        
        # Define success metrics
        roadmap['success_metrics'] = [
            'Monthly cost savings achieved vs. target',
            'Percentage of recommendations successfully implemented',
            'Time to implement vs. estimated timeline',
            'ROI achieved vs. projected ROI',
            'Number of optimization processes automated'
        ]
        
        # Define risk checkpoints
        roadmap['risk_checkpoints'] = [
            'End of Week 2: Review quick wins implementation success rate',
            'End of Month 1: Assess medium-complexity implementation challenges',
            'End of Month 3: Evaluate complex optimization feasibility',
            'Quarterly: Review overall portfolio performance and adjust strategy'
        ]
        
        return roadmap
    
    def _calculate_overall_data_quality(self):
        """Calculate overall data quality score"""
        if not self.recommendations:
            return 0
        
        quality_scores = []
        for rec in self.recommendations:
            score = 0
            
            # Check completeness
            if rec.monthly_savings > 0: score += 2
            if rec.implementation_steps: score += 1
            if rec.required_permissions: score += 1
            if rec.potential_risks: score += 1
            if rec.affected_resources: score += 1
            
            # Check data consistency
            if rec.annual_savings == rec.monthly_savings * 12: score += 1
            if rec.confidence_level in ['low', 'medium', 'high']: score += 1
            if rec.implementation_effort in ['low', 'medium', 'high']: score += 1
            
            quality_scores.append(min(score, 10))  # Cap at 10
        
        return sum(quality_scores) / len(quality_scores) * 10  # Scale to 0-100
    
    def _calculate_analytics_completeness(self, analytics):
        """Calculate how complete the analytics are"""
        completeness_score = 0
        total_sections = 10
        
        # Check each analytics section
        if analytics.get('financial_metrics', {}).get('total_monthly_savings', 0) > 0:
            completeness_score += 1
        if analytics.get('implementation_analysis', {}).get('effort_distribution'):
            completeness_score += 1
        if analytics.get('risk_assessment', {}).get('overall_risk_score', 0) > 0:
            completeness_score += 1
        if analytics.get('opportunity_matrix', {}).get('insights'):
            completeness_score += 1
        if analytics.get('roi_analysis', {}).get('overall_roi_percentage', 0) != 0:
            completeness_score += 1
        if analytics.get('timeline_analysis'):
            completeness_score += 1
        if analytics.get('service_breakdown', {}).get('by_service'):
            completeness_score += 1
        if analytics.get('source_analysis'):
            completeness_score += 1
        if analytics.get('confidence_distribution', {}).get('overall_confidence_score', 0) > 0:
            completeness_score += 1
        if analytics.get('optimization_roadmap', {}).get('phases'):
            completeness_score += 1
        
        return (completeness_score / total_sections) * 100  
  
    def get_executive_dashboard_data(self):
        """
        Get comprehensive executive dashboard data combining analytics and summary
        
        Returns:
            Dictionary with complete executive dashboard information
        """
        if not self.recommendations:
            return {
                'executive_summary': self._generate_executive_summary(),
                'analytics': self._get_empty_analytics(),
                'dashboard_generated_at': datetime.now().isoformat(),
                'data_status': 'no_recommendations'
            }
        
        # Generate comprehensive analytics
        analytics = self.calculate_comprehensive_analytics()
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary()
        
        # Create executive dashboard combining both
        dashboard_data = {
            'executive_summary': executive_summary,
            'analytics': analytics,
            'dashboard_generated_at': datetime.now().isoformat(),
            'data_status': 'complete',
            'key_metrics': {
                'total_recommendations': len(self.recommendations),
                'total_monthly_savings': sum(rec.monthly_savings for rec in self.recommendations),
                'total_annual_savings': sum(rec.annual_savings for rec in self.recommendations),
                'high_priority_count': len([rec for rec in self.recommendations if rec.priority_level == 'high']),
                'quick_wins_count': len([rec for rec in self.recommendations 
                                       if rec.implementation_effort == 'low' and rec.monthly_savings >= 50]),
                'data_quality_score': analytics['meta']['data_quality_score'],
                'completeness_score': analytics['meta']['completeness_score']
            },
            'executive_insights': self._generate_executive_insights(analytics, executive_summary)
        }
        
        return dashboard_data
    
    def _generate_executive_insights(self, analytics, executive_summary):
        """
        Generate executive-level insights and recommendations
        
        Args:
            analytics: Comprehensive analytics data
            executive_summary: Executive summary data
            
        Returns:
            List of executive insights and recommendations
        """
        insights = []
        
        # Financial insights
        total_monthly = analytics['financial_metrics']['total_monthly_savings']
        if total_monthly > 0:
            insights.append({
                'category': 'Financial Impact',
                'insight': f"Potential to save ${total_monthly:,.0f} per month (${total_monthly * 12:,.0f} annually)",
                'priority': 'high',
                'action_required': 'Review and prioritize high-impact recommendations'
            })
        
        # Quick wins insights
        quick_wins = analytics['financial_metrics']['quick_wins_count']
        if quick_wins > 0:
            quick_wins_savings = sum(rec.monthly_savings for rec in self.recommendations 
                                   if rec.implementation_effort == 'low' and rec.monthly_savings >= 50)
            insights.append({
                'category': 'Quick Wins',
                'insight': f"{quick_wins} quick wins available for ${quick_wins_savings:,.0f}/month in savings",
                'priority': 'high',
                'action_required': 'Implement immediately to build momentum'
            })
        
        # Risk insights
        risk_score = analytics['risk_assessment']['overall_risk_score']
        if risk_score >= 2.5:
            insights.append({
                'category': 'Risk Management',
                'insight': f"Portfolio has elevated risk (score: {risk_score:.1f}/3.0)",
                'priority': 'medium',
                'action_required': 'Implement risk mitigation strategies before proceeding'
            })
        
        # Implementation insights
        complexity_score = analytics['implementation_analysis']['complexity_score']
        if complexity_score >= 2.5:
            insights.append({
                'category': 'Implementation Complexity',
                'insight': f"High implementation complexity detected (score: {complexity_score:.1f}/3.0)",
                'priority': 'medium',
                'action_required': 'Consider phased approach and additional resources'
            })
        
        # ROI insights
        roi = analytics['roi_analysis']['overall_roi_percentage']
        if roi > 200:
            insights.append({
                'category': 'Return on Investment',
                'insight': f"Excellent ROI potential: {roi:.0f}% annual return",
                'priority': 'high',
                'action_required': 'Fast-track implementation to maximize returns'
            })
        elif roi < 50:
            insights.append({
                'category': 'Return on Investment',
                'insight': f"Lower ROI detected: {roi:.0f}% annual return",
                'priority': 'low',
                'action_required': 'Review cost-benefit analysis and prioritization'
            })
        
        # Service concentration insights
        service_concentration = analytics['service_breakdown']['concentration_analysis']
        if service_concentration.get('is_concentrated', False):
            top_service_pct = service_concentration['top_service_percentage']
            insights.append({
                'category': 'Service Concentration',
                'insight': f"Recommendations highly concentrated in one service ({top_service_pct:.0f}% of savings)",
                'priority': 'low',
                'action_required': 'Consider diversifying optimization efforts across services'
            })
        
        # Data quality insights
        data_quality = analytics['meta']['data_quality_score']
        if data_quality < 70:
            insights.append({
                'category': 'Data Quality',
                'insight': f"Data quality score is below optimal ({data_quality:.0f}/100)",
                'priority': 'medium',
                'action_required': 'Improve data collection and validation processes'
            })
        
        return insights
    
    def export_executive_summary_json(self):
        """
        Export executive summary and analytics as JSON for external consumption
        
        Returns:
            JSON string with complete executive dashboard data
        """
        dashboard_data = self.get_executive_dashboard_data()
        
        # Convert datetime objects to ISO strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, ExecutiveSummary):
                return asdict(obj)
            return obj
        
        import json
        return json.dumps(dashboard_data, default=convert_datetime, indent=2)
    
    def get_executive_summary_for_export(self):
        """
        Get executive summary data formatted for CSV/Excel export
        
        Returns:
            Dictionary with flattened data suitable for tabular export
        """
        dashboard_data = self.get_executive_dashboard_data()
        executive_summary = dashboard_data['executive_summary']
        analytics = dashboard_data['analytics']
        
        # Flatten data for export
        export_data = {
            'Report Generated': dashboard_data['dashboard_generated_at'],
            'Total Recommendations': executive_summary.total_recommendations,
            'Total Monthly Savings': executive_summary.total_monthly_savings,
            'Total Annual Savings': executive_summary.total_annual_savings,
            'High Priority Count': executive_summary.high_priority_count,
            'Medium Priority Count': executive_summary.medium_priority_count,
            'Low Priority Count': executive_summary.low_priority_count,
            'Quick Wins Available': analytics['financial_metrics']['quick_wins_count'],
            'High Impact Recommendations': analytics['financial_metrics']['high_impact_count'],
            'Overall Risk Score': analytics['risk_assessment']['overall_risk_score'],
            'Implementation Complexity Score': analytics['implementation_analysis']['complexity_score'],
            'Estimated ROI Percentage': analytics['roi_analysis']['overall_roi_percentage'],
            'Estimated Payback Months': analytics['roi_analysis']['payback_period_months'],
            'Data Quality Score': analytics['meta']['data_quality_score'],
            'Analytics Completeness Score': analytics['meta']['completeness_score']
        }
        
        # Add top categories
        for i, category in enumerate(executive_summary.top_categories[:3]):
            export_data[f'Top Category {i+1}'] = category['category']
            export_data[f'Top Category {i+1} Savings'] = category['total_savings']
            export_data[f'Top Category {i+1} Count'] = category['recommendation_count']
        
        # Add roadmap phases
        for i, phase in enumerate(executive_summary.implementation_roadmap[:3]):
            export_data[f'Phase {i+1} Name'] = phase['phase']
            export_data[f'Phase {i+1} Timeline'] = phase['timeline']
            export_data[f'Phase {i+1} Savings'] = phase['monthly_savings_potential']
            export_data[f'Phase {i+1} Count'] = phase['recommendation_count']
        
        return export_data  
  
    # Task 7.1: Security Impact Assessment
    
    def assess_security_impact(self, recommendations=None):
        """
        Assess security impact of cost optimization recommendations
        
        Args:
            recommendations: List of recommendations to assess (defaults to self.recommendations)
            
        Returns:
            Dictionary with security impact analysis
        """
        if recommendations is None:
            recommendations = self.recommendations
        
        if not recommendations:
            return self._get_empty_security_assessment()
        
        security_assessment = {
            'high_security_impact': [],
            'medium_security_impact': [],
            'low_security_impact': [],
            'compliance_critical': [],
            'security_configuration_changes': [],
            'network_security_impact': [],
            'access_control_impact': [],
            'encryption_impact': [],
            'monitoring_impact': [],
            'security_risk_summary': {},
            'mitigation_strategies': []
        }
        
        for rec in recommendations:
            # Assess security impact for each recommendation
            impact_analysis = self._analyze_recommendation_security_impact(rec)
            
            # Categorize by security impact level
            impact_level = impact_analysis['impact_level']
            security_assessment[f'{impact_level}_security_impact'].append({
                'recommendation_id': rec.id,
                'title': rec.title,
                'service': rec.service,
                'category': rec.category,
                'security_concerns': impact_analysis['security_concerns'],
                'compliance_implications': impact_analysis['compliance_implications'],
                'mitigation_required': impact_analysis['mitigation_required']
            })
            
            # Flag compliance-critical recommendations
            if impact_analysis['compliance_critical']:
                security_assessment['compliance_critical'].append({
                    'recommendation_id': rec.id,
                    'title': rec.title,
                    'compliance_frameworks': impact_analysis['compliance_frameworks'],
                    'risk_level': impact_analysis['compliance_risk_level']
                })
            
            # Categorize by security domain
            for domain in impact_analysis['security_domains']:
                if domain in security_assessment:
                    security_assessment[domain].append({
                        'recommendation_id': rec.id,
                        'title': rec.title,
                        'domain_impact': impact_analysis['domain_impacts'].get(domain, {})
                    })
        
        # Generate security risk summary
        security_assessment['security_risk_summary'] = self._generate_security_risk_summary(security_assessment)
        
        # Generate mitigation strategies
        security_assessment['mitigation_strategies'] = self._generate_security_mitigation_strategies(security_assessment)
        
        return security_assessment
    
    def _get_empty_security_assessment(self):
        """Return empty security assessment structure"""
        return {
            'high_security_impact': [],
            'medium_security_impact': [],
            'low_security_impact': [],
            'compliance_critical': [],
            'security_configuration_changes': [],
            'network_security_impact': [],
            'access_control_impact': [],
            'encryption_impact': [],
            'monitoring_impact': [],
            'security_risk_summary': {
                'total_recommendations': 0,
                'high_risk_count': 0,
                'compliance_critical_count': 0,
                'overall_risk_level': 'low'
            },
            'mitigation_strategies': []
        }
    
    def _analyze_recommendation_security_impact(self, recommendation):
        """
        Analyze security impact of a single recommendation
        
        Args:
            recommendation: CostRecommendation object
            
        Returns:
            Dictionary with security impact analysis
        """
        analysis = {
            'impact_level': 'low',
            'security_concerns': [],
            'compliance_implications': [],
            'compliance_critical': False,
            'compliance_frameworks': [],
            'compliance_risk_level': 'low',
            'mitigation_required': False,
            'security_domains': [],
            'domain_impacts': {}
        }
        
        # Analyze by service type
        service_analysis = self._analyze_service_security_impact(recommendation)
        analysis.update(service_analysis)
        
        # Analyze by recommendation type
        category_analysis = self._analyze_category_security_impact(recommendation)
        self._merge_security_analysis(analysis, category_analysis)
        
        # Analyze affected resources for security implications
        resource_analysis = self._analyze_resource_security_impact(recommendation)
        self._merge_security_analysis(analysis, resource_analysis)
        
        # Determine overall impact level
        analysis['impact_level'] = self._determine_security_impact_level(analysis)
        
        return analysis
    
    def _analyze_service_security_impact(self, recommendation):
        """Analyze security impact based on AWS service"""
        service = recommendation.service.lower()
        analysis = {
            'security_concerns': [],
            'compliance_implications': [],
            'compliance_critical': False,
            'compliance_frameworks': [],
            'security_domains': [],
            'domain_impacts': {}
        }
        
        # EC2 security considerations
        if service == 'ec2':
            analysis['security_concerns'].extend([
                'Instance type changes may affect security group configurations',
                'Rightsizing could impact application security posture',
                'Instance replacement may require security validation'
            ])
            analysis['security_domains'].extend(['access_control_impact', 'network_security_impact'])
            analysis['domain_impacts']['access_control_impact'] = {
                'description': 'EC2 changes may affect IAM roles and security groups',
                'risk_level': 'medium'
            }
            analysis['domain_impacts']['network_security_impact'] = {
                'description': 'Instance changes may affect network security configurations',
                'risk_level': 'medium'
            }
            
            # Check for compliance implications
            if 'rightsize' in recommendation.title.lower():
                analysis['compliance_implications'].append('PCI DSS: Instance changes require security re-validation')
                analysis['compliance_frameworks'].append('PCI DSS')
        
        # S3 security considerations
        elif service == 's3':
            analysis['security_concerns'].extend([
                'Storage class changes may affect encryption settings',
                'Lifecycle policies could impact data retention compliance',
                'Access pattern changes may affect bucket policies'
            ])
            analysis['security_domains'].extend(['encryption_impact', 'access_control_impact'])
            analysis['domain_impacts']['encryption_impact'] = {
                'description': 'S3 optimizations may affect encryption configurations',
                'risk_level': 'high'
            }
            analysis['compliance_critical'] = True
            analysis['compliance_frameworks'].extend(['SOX', 'GDPR', 'HIPAA'])
            analysis['compliance_implications'].extend([
                'GDPR: Data lifecycle changes must maintain privacy controls',
                'HIPAA: Storage modifications require BAA compliance review'
            ])
        
        # RDS security considerations
        elif service == 'rds':
            analysis['security_concerns'].extend([
                'Database instance changes may affect encryption at rest',
                'Performance modifications could impact audit logging',
                'Instance type changes may affect backup encryption'
            ])
            analysis['security_domains'].extend(['encryption_impact', 'monitoring_impact'])
            analysis['compliance_critical'] = True
            analysis['compliance_frameworks'].extend(['SOX', 'PCI DSS', 'HIPAA'])
            analysis['domain_impacts']['encryption_impact'] = {
                'description': 'RDS changes may affect database encryption settings',
                'risk_level': 'high'
            }
        
        # Lambda security considerations
        elif service == 'lambda':
            analysis['security_concerns'].extend([
                'Runtime changes may affect security patches',
                'Memory/timeout changes could impact execution security',
                'VPC configuration changes may affect network isolation'
            ])
            analysis['security_domains'].extend(['access_control_impact', 'network_security_impact'])
        
        # VPC/Networking security considerations
        elif service in ['vpc', 'elb', 'cloudfront', 'route53']:
            analysis['security_concerns'].extend([
                'Network configuration changes may affect security boundaries',
                'Load balancer changes could impact SSL/TLS termination',
                'CDN modifications may affect content security policies'
            ])
            analysis['security_domains'].extend(['network_security_impact', 'encryption_impact'])
            analysis['compliance_critical'] = True
            analysis['compliance_frameworks'].extend(['PCI DSS', 'SOX'])
        
        # IAM security considerations
        elif service == 'iam':
            analysis['security_concerns'].extend([
                'IAM changes directly impact access control',
                'Role modifications affect principle of least privilege',
                'Policy changes may create security vulnerabilities'
            ])
            analysis['security_domains'].append('access_control_impact')
            analysis['compliance_critical'] = True
            analysis['compliance_frameworks'].extend(['SOX', 'PCI DSS', 'GDPR', 'HIPAA'])
            analysis['domain_impacts']['access_control_impact'] = {
                'description': 'IAM changes directly affect access control security',
                'risk_level': 'high'
            }
        
        return analysis
    
    def _analyze_category_security_impact(self, recommendation):
        """Analyze security impact based on recommendation category"""
        category = recommendation.category.lower()
        analysis = {
            'security_concerns': [],
            'compliance_implications': [],
            'security_domains': [],
            'domain_impacts': {}
        }
        
        if category == 'compute':
            analysis['security_concerns'].extend([
                'Compute changes may affect workload isolation',
                'Performance modifications could impact security monitoring'
            ])
            
        elif category == 'storage':
            analysis['security_concerns'].extend([
                'Storage optimizations may affect data classification',
                'Lifecycle changes could impact data retention policies'
            ])
            analysis['security_domains'].append('encryption_impact')
            
        elif category == 'database':
            analysis['security_concerns'].extend([
                'Database changes may affect audit trail integrity',
                'Performance tuning could impact security logging'
            ])
            analysis['security_domains'].extend(['encryption_impact', 'monitoring_impact'])
            
        elif category == 'network':
            analysis['security_concerns'].extend([
                'Network changes may affect security perimeters',
                'Traffic routing modifications could bypass security controls'
            ])
            analysis['security_domains'].append('network_security_impact')
        
        return analysis
    
    def _analyze_resource_security_impact(self, recommendation):
        """Analyze security impact based on affected resources"""
        analysis = {
            'security_concerns': [],
            'compliance_implications': [],
            'security_domains': [],
            'domain_impacts': {}
        }
        
        # Check for security-sensitive resource patterns
        for resource in recommendation.affected_resources:
            resource_id = resource.get('id', '').lower()
            resource_type = resource.get('type', '').lower()
            
            # Check for production resources
            if any(keyword in resource_id for keyword in ['prod', 'production', 'live']):
                analysis['security_concerns'].append(f'Production resource {resource_id} requires enhanced security validation')
                analysis['compliance_implications'].append('Production changes require change management approval')
            
            # Check for security-related resource names
            if any(keyword in resource_id for keyword in ['security', 'auth', 'login', 'admin']):
                analysis['security_concerns'].append(f'Security-related resource {resource_id} requires careful review')
                analysis['security_domains'].append('access_control_impact')
            
            # Check for database resources
            if any(keyword in resource_type for keyword in ['db', 'database', 'rds']):
                analysis['security_concerns'].append(f'Database resource {resource_id} may contain sensitive data')
                analysis['security_domains'].extend(['encryption_impact', 'monitoring_impact'])
        
        return analysis
    
    def _merge_security_analysis(self, base_analysis, additional_analysis):
        """Merge additional security analysis into base analysis"""
        for key in ['security_concerns', 'compliance_implications', 'security_domains']:
            if key in additional_analysis:
                base_analysis[key].extend(additional_analysis[key])
        
        if additional_analysis.get('compliance_critical'):
            base_analysis['compliance_critical'] = True
        
        if additional_analysis.get('compliance_frameworks'):
            base_analysis['compliance_frameworks'].extend(additional_analysis['compliance_frameworks'])
        
        if additional_analysis.get('domain_impacts'):
            base_analysis['domain_impacts'].update(additional_analysis['domain_impacts'])
    
    def _determine_security_impact_level(self, analysis):
        """Determine overall security impact level"""
        # High impact criteria
        if (analysis['compliance_critical'] or 
            len(analysis['security_concerns']) >= 3 or
            any('high' in str(impact.get('risk_level', '')).lower() 
                for impact in analysis['domain_impacts'].values())):
            return 'high'
        
        # Medium impact criteria
        if (len(analysis['security_concerns']) >= 1 or 
            len(analysis['compliance_implications']) >= 1 or
            len(analysis['security_domains']) >= 2):
            return 'medium'
        
        return 'low'
    
    def _generate_security_risk_summary(self, security_assessment):
        """Generate summary of security risks"""
        total_recs = (len(security_assessment['high_security_impact']) + 
                     len(security_assessment['medium_security_impact']) + 
                     len(security_assessment['low_security_impact']))
        
        high_risk_count = len(security_assessment['high_security_impact'])
        compliance_critical_count = len(security_assessment['compliance_critical'])
        
        # Determine overall risk level
        if high_risk_count > total_recs * 0.3:
            overall_risk_level = 'high'
        elif high_risk_count > 0 or compliance_critical_count > total_recs * 0.2:
            overall_risk_level = 'medium'
        else:
            overall_risk_level = 'low'
        
        return {
            'total_recommendations': total_recs,
            'high_risk_count': high_risk_count,
            'medium_risk_count': len(security_assessment['medium_security_impact']),
            'low_risk_count': len(security_assessment['low_security_impact']),
            'compliance_critical_count': compliance_critical_count,
            'overall_risk_level': overall_risk_level,
            'risk_distribution': {
                'high': (high_risk_count / max(total_recs, 1)) * 100,
                'medium': (len(security_assessment['medium_security_impact']) / max(total_recs, 1)) * 100,
                'low': (len(security_assessment['low_security_impact']) / max(total_recs, 1)) * 100
            },
            'compliance_impact_percentage': (compliance_critical_count / max(total_recs, 1)) * 100
        }
    
    def _generate_security_mitigation_strategies(self, security_assessment):
        """Generate security mitigation strategies"""
        strategies = []
        
        # High-risk mitigation strategies
        if security_assessment['high_security_impact']:
            strategies.append({
                'priority': 'high',
                'strategy': 'Enhanced Security Review Process',
                'description': 'Implement mandatory security review for high-impact recommendations',
                'actions': [
                    'Require security team approval before implementation',
                    'Conduct security impact assessment for each recommendation',
                    'Implement rollback procedures for security-sensitive changes',
                    'Establish security monitoring for implemented changes'
                ],
                'applicable_recommendations': len(security_assessment['high_security_impact'])
            })
        
        # Compliance mitigation strategies
        if security_assessment['compliance_critical']:
            strategies.append({
                'priority': 'high',
                'strategy': 'Compliance Validation Framework',
                'description': 'Ensure compliance requirements are met for critical recommendations',
                'actions': [
                    'Map recommendations to applicable compliance frameworks',
                    'Require compliance officer review for critical changes',
                    'Document compliance impact and mitigation measures',
                    'Implement compliance monitoring and reporting'
                ],
                'applicable_recommendations': len(security_assessment['compliance_critical'])
            })
        
        # Encryption impact mitigation
        if security_assessment['encryption_impact']:
            strategies.append({
                'priority': 'medium',
                'strategy': 'Encryption Continuity Assurance',
                'description': 'Ensure encryption settings are maintained during optimization',
                'actions': [
                    'Verify encryption settings before and after changes',
                    'Document encryption key management implications',
                    'Test encryption functionality post-implementation',
                    'Update encryption policies as needed'
                ],
                'applicable_recommendations': len(security_assessment['encryption_impact'])
            })
        
        # Access control mitigation
        if security_assessment['access_control_impact']:
            strategies.append({
                'priority': 'medium',
                'strategy': 'Access Control Validation',
                'description': 'Validate access controls remain effective after optimization',
                'actions': [
                    'Review IAM policies and roles affected by changes',
                    'Test access controls after implementation',
                    'Update security group configurations as needed',
                    'Conduct access review for affected resources'
                ],
                'applicable_recommendations': len(security_assessment['access_control_impact'])
            })
        
        # Network security mitigation
        if security_assessment['network_security_impact']:
            strategies.append({
                'priority': 'medium',
                'strategy': 'Network Security Boundary Maintenance',
                'description': 'Ensure network security boundaries remain intact',
                'actions': [
                    'Review network security group changes',
                    'Validate VPC and subnet configurations',
                    'Test network connectivity and isolation',
                    'Update network security documentation'
                ],
                'applicable_recommendations': len(security_assessment['network_security_impact'])
            })
        
        # Monitoring impact mitigation
        if security_assessment['monitoring_impact']:
            strategies.append({
                'priority': 'low',
                'strategy': 'Security Monitoring Continuity',
                'description': 'Maintain security monitoring capabilities during optimization',
                'actions': [
                    'Verify logging and monitoring configurations',
                    'Update security monitoring rules as needed',
                    'Test alerting mechanisms post-implementation',
                    'Document monitoring changes and impacts'
                ],
                'applicable_recommendations': len(security_assessment['monitoring_impact'])
            })
        
        return strategies
    
    def apply_security_aware_prioritization(self, recommendations=None):
        """
        Apply security-aware prioritization to recommendations
        
        Args:
            recommendations: List of recommendations to prioritize (defaults to self.recommendations)
            
        Returns:
            List of recommendations with updated priority scores
        """
        if recommendations is None:
            recommendations = self.recommendations
        
        if not recommendations:
            return recommendations
        
        # Assess security impact for all recommendations
        security_assessment = self.assess_security_impact(recommendations)
        
        # Create security impact lookup
        security_impact_map = {}
        
        for impact_level in ['high', 'medium', 'low']:
            for item in security_assessment[f'{impact_level}_security_impact']:
                security_impact_map[item['recommendation_id']] = {
                    'impact_level': impact_level,
                    'security_concerns': item['security_concerns'],
                    'compliance_implications': item['compliance_implications']
                }
        
        # Apply security-aware priority adjustments
        for rec in recommendations:
            security_info = security_impact_map.get(rec.id, {'impact_level': 'low'})
            
            # Adjust priority score based on security impact
            if security_info['impact_level'] == 'high':
                # High security impact: reduce priority to encourage careful review
                rec.priority_score = max(0, rec.priority_score - 15)
                # Add security warning to potential risks
                rec.potential_risks.append('HIGH SECURITY IMPACT: Requires security team review before implementation')
                
            elif security_info['impact_level'] == 'medium':
                # Medium security impact: slight priority reduction
                rec.priority_score = max(0, rec.priority_score - 5)
                rec.potential_risks.append('MEDIUM SECURITY IMPACT: Security validation recommended')
            
            # Add compliance warnings for compliance-critical recommendations
            if rec.id in [item['recommendation_id'] for item in security_assessment['compliance_critical']]:
                rec.potential_risks.append('COMPLIANCE CRITICAL: Requires compliance officer review')
                # Further reduce priority for compliance-critical items
                rec.priority_score = max(0, rec.priority_score - 10)
            
            # Update priority level based on new score
            rec.priority_level = self._determine_priority_level(rec.priority_score)
        
        return recommendations  
  
    # Task 7.2: Service Screener Integration
    
    def cross_reference_with_service_screener(self, service_screener_findings=None):
        """
        Cross-reference cost optimization recommendations with Service Screener security findings
        
        Args:
            service_screener_findings: List of Service Screener findings (optional)
            
        Returns:
            Dictionary with integrated analysis and recommendations
        """
        if not self.recommendations:
            return self._get_empty_cross_reference_analysis()
        
        # If no findings provided, attempt to load from Service Screener data
        if service_screener_findings is None:
            service_screener_findings = self._load_service_screener_findings()
        
        cross_reference_analysis = {
            'integrated_recommendations': [],
            'cost_security_conflicts': [],
            'complementary_actions': [],
            'resource_overlap_analysis': {},
            'unified_action_plans': [],
            'cost_impact_of_security_fixes': [],
            'security_impact_of_cost_optimizations': [],
            'prioritized_integrated_actions': [],
            'summary': {}
        }
        
        # Create resource mapping for efficient lookup
        security_findings_by_resource = self._map_security_findings_by_resource(service_screener_findings)
        cost_recommendations_by_resource = self._map_cost_recommendations_by_resource(self.recommendations)
        
        # Find overlapping resources
        overlapping_resources = set(security_findings_by_resource.keys()).intersection(
            set(cost_recommendations_by_resource.keys())
        )
        
        # Analyze each overlapping resource
        for resource_id in overlapping_resources:
            security_findings = security_findings_by_resource[resource_id]
            cost_recommendations = cost_recommendations_by_resource[resource_id]
            
            resource_analysis = self._analyze_resource_overlap(
                resource_id, security_findings, cost_recommendations
            )
            
            cross_reference_analysis['resource_overlap_analysis'][resource_id] = resource_analysis
            
            # Generate integrated recommendations
            integrated_recs = self._generate_integrated_recommendations(
                resource_id, security_findings, cost_recommendations
            )
            cross_reference_analysis['integrated_recommendations'].extend(integrated_recs)
            
            # Identify conflicts
            conflicts = self._identify_cost_security_conflicts(
                resource_id, security_findings, cost_recommendations
            )
            cross_reference_analysis['cost_security_conflicts'].extend(conflicts)
            
            # Find complementary actions
            complementary = self._find_complementary_actions(
                resource_id, security_findings, cost_recommendations
            )
            cross_reference_analysis['complementary_actions'].extend(complementary)
        
        # Analyze cost impact of security fixes
        cross_reference_analysis['cost_impact_of_security_fixes'] = \
            self._analyze_cost_impact_of_security_fixes(service_screener_findings)
        
        # Analyze security impact of cost optimizations
        cross_reference_analysis['security_impact_of_cost_optimizations'] = \
            self._analyze_security_impact_of_cost_optimizations(self.recommendations)
        
        # Generate unified action plans
        cross_reference_analysis['unified_action_plans'] = \
            self._generate_unified_action_plans(cross_reference_analysis)
        
        # Create prioritized integrated actions
        cross_reference_analysis['prioritized_integrated_actions'] = \
            self._prioritize_integrated_actions(cross_reference_analysis)
        
        # Generate summary
        cross_reference_analysis['summary'] = \
            self._generate_cross_reference_summary(cross_reference_analysis)
        
        return cross_reference_analysis
    
    def _get_empty_cross_reference_analysis(self):
        """Return empty cross-reference analysis structure"""
        return {
            'integrated_recommendations': [],
            'cost_security_conflicts': [],
            'complementary_actions': [],
            'resource_overlap_analysis': {},
            'unified_action_plans': [],
            'cost_impact_of_security_fixes': [],
            'security_impact_of_cost_optimizations': [],
            'prioritized_integrated_actions': [],
            'summary': {
                'total_overlapping_resources': 0,
                'conflicts_identified': 0,
                'integrated_recommendations_generated': 0,
                'estimated_cost_impact': 0
            }
        }
    
    def _load_service_screener_findings(self):
        """
        Load Service Screener findings from the current scan
        
        Returns:
            List of Service Screener findings
        """
        # This would integrate with the actual Service Screener data
        # For now, return mock data structure
        return [
            {
                'id': 'SS-EC2-001',
                'service': 'ec2',
                'category': 'security',
                'severity': 'high',
                'title': 'EC2 instance with unrestricted security group',
                'description': 'Security group allows 0.0.0.0/0 access',
                'affected_resources': [{'id': 'i-prod-web-server-001', 'type': 'EC2'}],
                'remediation_steps': ['Update security group rules', 'Restrict access to specific IPs'],
                'compliance_frameworks': ['PCI DSS', 'SOX'],
                'estimated_fix_effort': 'low',
                'business_impact': 'high'
            },
            {
                'id': 'SS-S3-002',
                'service': 's3',
                'category': 'security',
                'severity': 'medium',
                'title': 'S3 bucket without encryption',
                'description': 'Bucket does not have default encryption enabled',
                'affected_resources': [{'id': 'customer-data-bucket', 'type': 'S3'}],
                'remediation_steps': ['Enable default encryption', 'Configure KMS key'],
                'compliance_frameworks': ['GDPR', 'HIPAA'],
                'estimated_fix_effort': 'low',
                'business_impact': 'medium'
            }
        ]
    
    def _map_security_findings_by_resource(self, findings):
        """Map security findings by affected resource ID"""
        resource_map = {}
        
        for finding in findings:
            for resource in finding.get('affected_resources', []):
                resource_id = resource.get('id')
                if resource_id:
                    if resource_id not in resource_map:
                        resource_map[resource_id] = []
                    resource_map[resource_id].append(finding)
        
        return resource_map
    
    def _map_cost_recommendations_by_resource(self, recommendations):
        """Map cost recommendations by affected resource ID"""
        resource_map = {}
        
        for rec in recommendations:
            for resource in rec.affected_resources:
                resource_id = resource.get('id')
                if resource_id:
                    if resource_id not in resource_map:
                        resource_map[resource_id] = []
                    resource_map[resource_id].append(rec)
        
        return resource_map
    
    def _analyze_resource_overlap(self, resource_id, security_findings, cost_recommendations):
        """Analyze overlap between security findings and cost recommendations for a resource"""
        analysis = {
            'resource_id': resource_id,
            'security_findings_count': len(security_findings),
            'cost_recommendations_count': len(cost_recommendations),
            'severity_levels': [finding.get('severity', 'unknown') for finding in security_findings],
            'cost_savings_potential': sum(rec.monthly_savings for rec in cost_recommendations),
            'security_risk_level': self._calculate_combined_security_risk(security_findings),
            'implementation_complexity': self._assess_combined_implementation_complexity(
                security_findings, cost_recommendations
            ),
            'business_impact': self._assess_combined_business_impact(
                security_findings, cost_recommendations
            )
        }
        
        return analysis
    
    def _calculate_combined_security_risk(self, security_findings):
        """Calculate combined security risk level for multiple findings"""
        if not security_findings:
            return 'none'
        
        severity_weights = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        total_weight = sum(severity_weights.get(finding.get('severity', 'low'), 1) 
                          for finding in security_findings)
        
        avg_weight = total_weight / len(security_findings)
        
        if avg_weight >= 3.5:
            return 'critical'
        elif avg_weight >= 2.5:
            return 'high'
        elif avg_weight >= 1.5:
            return 'medium'
        else:
            return 'low'
    
    def _assess_combined_implementation_complexity(self, security_findings, cost_recommendations):
        """Assess combined implementation complexity"""
        effort_weights = {'high': 3, 'medium': 2, 'low': 1}
        
        security_effort = sum(effort_weights.get(finding.get('estimated_fix_effort', 'medium'), 2) 
                             for finding in security_findings)
        cost_effort = sum(effort_weights.get(rec.implementation_effort, 2) 
                         for rec in cost_recommendations)
        
        total_effort = security_effort + cost_effort
        total_items = len(security_findings) + len(cost_recommendations)
        
        if total_items == 0:
            return 'low'
        
        avg_effort = total_effort / total_items
        
        if avg_effort >= 2.5:
            return 'high'
        elif avg_effort >= 1.5:
            return 'medium'
        else:
            return 'low'
    
    def _assess_combined_business_impact(self, security_findings, cost_recommendations):
        """Assess combined business impact"""
        # Security findings typically have higher business impact due to risk
        max_security_impact = max((finding.get('business_impact', 'medium') 
                                 for finding in security_findings), default='low')
        
        # Cost recommendations impact is based on savings potential
        total_savings = sum(rec.monthly_savings for rec in cost_recommendations)
        
        if max_security_impact == 'high' or total_savings >= 1000:
            return 'high'
        elif max_security_impact == 'medium' or total_savings >= 200:
            return 'medium'
        else:
            return 'low'
    
    def _generate_integrated_recommendations(self, resource_id, security_findings, cost_recommendations):
        """Generate integrated recommendations that address both security and cost concerns"""
        integrated_recs = []
        
        for cost_rec in cost_recommendations:
            for security_finding in security_findings:
                # Check if they can be integrated
                if self._can_integrate_actions(cost_rec, security_finding):
                    integrated_rec = {
                        'id': f'integrated_{cost_rec.id}_{security_finding["id"]}',
                        'type': 'integrated',
                        'resource_id': resource_id,
                        'title': f'Integrated optimization: {cost_rec.title} + {security_finding["title"]}',
                        'description': f'Address security finding while implementing cost optimization',
                        'cost_component': {
                            'recommendation_id': cost_rec.id,
                            'monthly_savings': cost_rec.monthly_savings,
                            'implementation_effort': cost_rec.implementation_effort
                        },
                        'security_component': {
                            'finding_id': security_finding['id'],
                            'severity': security_finding.get('severity', 'medium'),
                            'compliance_frameworks': security_finding.get('compliance_frameworks', [])
                        },
                        'integrated_steps': self._create_integrated_implementation_steps(
                            cost_rec, security_finding
                        ),
                        'combined_benefits': [
                            f'Cost savings: ${cost_rec.monthly_savings}/month',
                            f'Security improvement: {security_finding.get("severity", "medium")} risk mitigation',
                            'Reduced implementation overhead through combined effort'
                        ],
                        'priority': self._calculate_integrated_priority(cost_rec, security_finding)
                    }
                    integrated_recs.append(integrated_rec)
        
        return integrated_recs
    
    def _can_integrate_actions(self, cost_rec, security_finding):
        """Determine if cost recommendation and security finding can be integrated"""
        # Check if they affect the same service
        if cost_rec.service != security_finding.get('service'):
            return False
        
        # Check for conflicting actions
        cost_actions = ' '.join(cost_rec.implementation_steps).lower()
        security_actions = ' '.join(security_finding.get('remediation_steps', [])).lower()
        
        # Look for complementary or non-conflicting actions
        conflicting_keywords = [
            ('reduce', 'increase'), ('disable', 'enable'), ('remove', 'add'),
            ('downgrade', 'upgrade'), ('restrict', 'open')
        ]
        
        for cost_keyword, security_keyword in conflicting_keywords:
            if cost_keyword in cost_actions and security_keyword in security_actions:
                return False
        
        return True
    
    def _create_integrated_implementation_steps(self, cost_rec, security_finding):
        """Create integrated implementation steps"""
        steps = []
        
        # Add planning step
        steps.append('Plan integrated implementation to address both cost and security concerns')
        
        # Add security steps first (security takes priority)
        security_steps = security_finding.get('remediation_steps', [])
        for step in security_steps:
            steps.append(f'Security: {step}')
        
        # Add cost optimization steps
        for step in cost_rec.implementation_steps:
            steps.append(f'Cost optimization: {step}')
        
        # Add validation step
        steps.append('Validate both security posture and cost savings after implementation')
        
        return steps
    
    def _calculate_integrated_priority(self, cost_rec, security_finding):
        """Calculate priority for integrated recommendation"""
        # Security severity contributes to priority
        severity_weights = {'critical': 100, 'high': 80, 'medium': 60, 'low': 40}
        security_score = severity_weights.get(security_finding.get('severity', 'medium'), 60)
        
        # Cost savings contribute to priority
        cost_score = min(100, cost_rec.monthly_savings / 10)  # $10/month = 1 point
        
        # Combined priority (weighted toward security)
        combined_score = (security_score * 0.7) + (cost_score * 0.3)
        
        if combined_score >= 80:
            return 'high'
        elif combined_score >= 60:
            return 'medium'
        else:
            return 'low'
    
    def _identify_cost_security_conflicts(self, resource_id, security_findings, cost_recommendations):
        """Identify conflicts between cost optimizations and security requirements"""
        conflicts = []
        
        for cost_rec in cost_recommendations:
            for security_finding in security_findings:
                conflict = self._check_for_conflict(cost_rec, security_finding)
                if conflict:
                    conflicts.append({
                        'resource_id': resource_id,
                        'cost_recommendation_id': cost_rec.id,
                        'security_finding_id': security_finding['id'],
                        'conflict_type': conflict['type'],
                        'description': conflict['description'],
                        'resolution_options': conflict['resolution_options'],
                        'recommended_action': conflict['recommended_action']
                    })
        
        return conflicts
    
    def _check_for_conflict(self, cost_rec, security_finding):
        """Check for specific conflicts between cost recommendation and security finding"""
        # Check for instance type conflicts
        if (cost_rec.service == 'ec2' and 'rightsize' in cost_rec.title.lower() and
            'security group' in security_finding.get('title', '').lower()):
            return {
                'type': 'instance_modification_security_risk',
                'description': 'EC2 rightsizing may affect security group configurations',
                'resolution_options': [
                    'Implement security fixes before rightsizing',
                    'Coordinate both changes in single maintenance window',
                    'Prioritize security fix and defer cost optimization'
                ],
                'recommended_action': 'Implement security fixes first, then proceed with rightsizing'
            }
        
        # Check for storage encryption conflicts
        if (cost_rec.service == 's3' and 'lifecycle' in cost_rec.title.lower() and
            'encryption' in security_finding.get('title', '').lower()):
            return {
                'type': 'storage_lifecycle_encryption_conflict',
                'description': 'S3 lifecycle policies may affect encryption settings',
                'resolution_options': [
                    'Enable encryption before implementing lifecycle policies',
                    'Ensure lifecycle policies maintain encryption',
                    'Implement both changes simultaneously with validation'
                ],
                'recommended_action': 'Enable encryption first, then implement lifecycle with encryption validation'
            }
        
        return None
    
    def _find_complementary_actions(self, resource_id, security_findings, cost_recommendations):
        """Find complementary actions that support both security and cost goals"""
        complementary = []
        
        for cost_rec in cost_recommendations:
            for security_finding in security_findings:
                if self._are_actions_complementary(cost_rec, security_finding):
                    complementary.append({
                        'resource_id': resource_id,
                        'cost_recommendation_id': cost_rec.id,
                        'security_finding_id': security_finding['id'],
                        'complementary_benefits': [
                            'Both actions improve overall resource efficiency',
                            'Implementation can be coordinated for reduced downtime',
                            'Combined validation reduces testing overhead'
                        ],
                        'suggested_approach': 'Implement both changes in coordinated manner'
                    })
        
        return complementary
    
    def _are_actions_complementary(self, cost_rec, security_finding):
        """Check if cost and security actions are complementary"""
        # Both involve configuration changes that can be done together
        cost_involves_config = any(keyword in ' '.join(cost_rec.implementation_steps).lower() 
                                 for keyword in ['configure', 'update', 'modify', 'change'])
        security_involves_config = any(keyword in ' '.join(security_finding.get('remediation_steps', [])).lower() 
                                     for keyword in ['configure', 'update', 'modify', 'change'])
        
        return cost_involves_config and security_involves_config
    
    def _analyze_cost_impact_of_security_fixes(self, security_findings):
        """Analyze potential cost impact of implementing security fixes"""
        cost_impacts = []
        
        for finding in security_findings:
            impact = {
                'finding_id': finding['id'],
                'title': finding.get('title', ''),
                'service': finding.get('service', ''),
                'estimated_cost_impact': self._estimate_security_fix_cost_impact(finding),
                'cost_categories': self._identify_security_fix_cost_categories(finding),
                'ongoing_cost_implications': self._assess_ongoing_cost_implications(finding)
            }
            cost_impacts.append(impact)
        
        return cost_impacts
    
    def _estimate_security_fix_cost_impact(self, finding):
        """Estimate cost impact of implementing a security fix"""
        service = finding.get('service', '').lower()
        severity = finding.get('severity', 'medium').lower()
        
        # Base cost estimates by service and severity
        base_costs = {
            'ec2': {'critical': 500, 'high': 200, 'medium': 50, 'low': 20},
            's3': {'critical': 100, 'high': 50, 'medium': 20, 'low': 10},
            'rds': {'critical': 300, 'high': 150, 'medium': 75, 'low': 25},
            'lambda': {'critical': 50, 'high': 25, 'medium': 10, 'low': 5}
        }
        
        return base_costs.get(service, {}).get(severity, 50)
    
    def _identify_security_fix_cost_categories(self, finding):
        """Identify cost categories affected by security fix"""
        categories = []
        
        service = finding.get('service', '').lower()
        title = finding.get('title', '').lower()
        
        if 'encryption' in title:
            categories.append('KMS key usage costs')
        if 'monitoring' in title or 'logging' in title:
            categories.append('CloudWatch/CloudTrail costs')
        if 'backup' in title:
            categories.append('Backup storage costs')
        if service == 'ec2' and 'security group' in title:
            categories.append('Potential network performance impact')
        
        return categories
    
    def _assess_ongoing_cost_implications(self, finding):
        """Assess ongoing cost implications of security fix"""
        service = finding.get('service', '').lower()
        title = finding.get('title', '').lower()
        
        implications = []
        
        if 'encryption' in title:
            implications.append('Ongoing KMS key usage charges')
        if 'monitoring' in title:
            implications.append('Increased CloudWatch metrics and logs storage')
        if 'backup' in title:
            implications.append('Regular backup storage costs')
        
        return implications
    
    def _analyze_security_impact_of_cost_optimizations(self, recommendations):
        """Analyze security impact of cost optimization recommendations"""
        security_impacts = []
        
        for rec in recommendations:
            impact = {
                'recommendation_id': rec.id,
                'title': rec.title,
                'service': rec.service,
                'security_risk_level': self._assess_cost_optimization_security_risk(rec),
                'security_considerations': self._identify_security_considerations(rec),
                'mitigation_requirements': self._identify_mitigation_requirements(rec)
            }
            security_impacts.append(impact)
        
        return security_impacts
    
    def _assess_cost_optimization_security_risk(self, recommendation):
        """Assess security risk level of cost optimization"""
        service = recommendation.service.lower()
        title = recommendation.title.lower()
        
        # High risk scenarios
        if (service in ['iam', 'kms'] or 
            'security' in title or 
            'encryption' in title or
            any('prod' in res.get('id', '').lower() for res in recommendation.affected_resources)):
            return 'high'
        
        # Medium risk scenarios
        if (service in ['ec2', 'rds', 's3'] or
            'rightsize' in title or
            'lifecycle' in title):
            return 'medium'
        
        return 'low'
    
    def _identify_security_considerations(self, recommendation):
        """Identify security considerations for cost optimization"""
        considerations = []
        
        service = recommendation.service.lower()
        
        if service == 'ec2':
            considerations.extend([
                'Verify security group configurations remain appropriate',
                'Ensure IAM roles and policies are compatible with new instance types',
                'Validate that security monitoring continues to function'
            ])
        elif service == 's3':
            considerations.extend([
                'Confirm encryption settings are maintained across storage classes',
                'Verify access policies remain effective with lifecycle changes',
                'Ensure compliance requirements are met for data retention'
            ])
        elif service == 'rds':
            considerations.extend([
                'Validate encryption at rest continues to function',
                'Ensure backup encryption is maintained',
                'Confirm audit logging settings are preserved'
            ])
        
        return considerations
    
    def _identify_mitigation_requirements(self, recommendation):
        """Identify mitigation requirements for cost optimization"""
        requirements = []
        
        security_risk = self._assess_cost_optimization_security_risk(recommendation)
        
        if security_risk == 'high':
            requirements.extend([
                'Mandatory security team review before implementation',
                'Comprehensive security testing after changes',
                'Rollback plan with security validation'
            ])
        elif security_risk == 'medium':
            requirements.extend([
                'Security checklist validation',
                'Post-implementation security verification'
            ])
        else:
            requirements.append('Basic security validation')
        
        return requirements
    
    def _generate_unified_action_plans(self, cross_reference_analysis):
        """Generate unified action plans that address both cost and security concerns"""
        unified_plans = []
        
        # Group by resource for unified planning
        resources = cross_reference_analysis['resource_overlap_analysis']
        
        for resource_id, analysis in resources.items():
            plan = {
                'resource_id': resource_id,
                'plan_type': 'unified',
                'priority': self._calculate_unified_plan_priority(analysis),
                'phases': [],
                'estimated_timeline': self._estimate_unified_timeline(analysis),
                'total_cost_impact': analysis.get('cost_savings_potential', 0),
                'security_risk_reduction': analysis.get('security_risk_level', 'low'),
                'success_criteria': []
            }
            
            # Phase 1: Security fixes (always first)
            if analysis['security_findings_count'] > 0:
                plan['phases'].append({
                    'phase': 1,
                    'name': 'Security Remediation',
                    'description': 'Address security findings first',
                    'duration': '1-2 weeks',
                    'actions': ['Implement security fixes', 'Validate security posture'],
                    'success_criteria': ['All security findings resolved', 'Security validation passed']
                })
            
            # Phase 2: Cost optimization (after security is addressed)
            if analysis['cost_recommendations_count'] > 0:
                plan['phases'].append({
                    'phase': 2,
                    'name': 'Cost Optimization',
                    'description': 'Implement cost optimizations with security validation',
                    'duration': '1-3 weeks',
                    'actions': ['Implement cost optimizations', 'Validate security is maintained'],
                    'success_criteria': ['Cost savings achieved', 'Security posture maintained']
                })
            
            # Phase 3: Monitoring and validation
            plan['phases'].append({
                'phase': 3,
                'name': 'Monitoring and Validation',
                'description': 'Establish ongoing monitoring for both cost and security',
                'duration': '1 week',
                'actions': ['Set up monitoring', 'Document changes', 'Create maintenance procedures'],
                'success_criteria': ['Monitoring established', 'Documentation complete']
            })
            
            unified_plans.append(plan)
        
        return unified_plans
    
    def _calculate_unified_plan_priority(self, analysis):
        """Calculate priority for unified action plan"""
        security_weight = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'none': 0}
        security_score = security_weight.get(analysis.get('security_risk_level', 'low'), 1)
        
        cost_score = min(4, analysis.get('cost_savings_potential', 0) / 250)  # $250/month = 1 point
        
        combined_score = (security_score * 0.6) + (cost_score * 0.4)
        
        if combined_score >= 3.5:
            return 'critical'
        elif combined_score >= 2.5:
            return 'high'
        elif combined_score >= 1.5:
            return 'medium'
        else:
            return 'low'
    
    def _estimate_unified_timeline(self, analysis):
        """Estimate timeline for unified implementation"""
        complexity = analysis.get('implementation_complexity', 'low')
        
        base_weeks = {
            'low': 2,
            'medium': 4,
            'high': 8
        }
        
        return f"{base_weeks.get(complexity, 4)} weeks"
    
    def _prioritize_integrated_actions(self, cross_reference_analysis):
        """Prioritize integrated actions across all resources"""
        all_actions = []
        
        # Collect all integrated recommendations
        for rec in cross_reference_analysis['integrated_recommendations']:
            all_actions.append({
                'type': 'integrated_recommendation',
                'priority': rec['priority'],
                'resource_id': rec['resource_id'],
                'title': rec['title'],
                'monthly_savings': rec['cost_component']['monthly_savings'],
                'security_severity': rec['security_component']['severity']
            })
        
        # Collect all unified action plans
        for plan in cross_reference_analysis['unified_action_plans']:
            all_actions.append({
                'type': 'unified_plan',
                'priority': plan['priority'],
                'resource_id': plan['resource_id'],
                'title': f"Unified plan for {plan['resource_id']}",
                'monthly_savings': plan['total_cost_impact'],
                'security_risk_reduction': plan['security_risk_reduction']
            })
        
        # Sort by priority and impact
        priority_weights = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        
        all_actions.sort(key=lambda x: (
            priority_weights.get(x['priority'], 1),
            x.get('monthly_savings', 0)
        ), reverse=True)
        
        return all_actions
    
    def _generate_cross_reference_summary(self, cross_reference_analysis):
        """Generate summary of cross-reference analysis"""
        return {
            'total_overlapping_resources': len(cross_reference_analysis['resource_overlap_analysis']),
            'conflicts_identified': len(cross_reference_analysis['cost_security_conflicts']),
            'integrated_recommendations_generated': len(cross_reference_analysis['integrated_recommendations']),
            'unified_plans_created': len(cross_reference_analysis['unified_action_plans']),
            'estimated_total_cost_savings': sum(
                rec['cost_component']['monthly_savings'] 
                for rec in cross_reference_analysis['integrated_recommendations']
            ),
            'security_findings_addressed': sum(
                1 for rec in cross_reference_analysis['integrated_recommendations']
            ),
            'complementary_actions_identified': len(cross_reference_analysis['complementary_actions']),
            'overall_integration_benefit': self._calculate_overall_integration_benefit(cross_reference_analysis)
        }
    
    def _calculate_overall_integration_benefit(self, analysis):
        """Calculate overall benefit of integration"""
        cost_benefit = sum(rec['cost_component']['monthly_savings'] 
                          for rec in analysis['integrated_recommendations'])
        
        security_benefit = len(analysis['integrated_recommendations'])  # Number of security issues addressed
        
        if cost_benefit >= 1000 and security_benefit >= 3:
            return 'high'
        elif cost_benefit >= 200 and security_benefit >= 1:
            return 'medium'
        else:
            return 'low'