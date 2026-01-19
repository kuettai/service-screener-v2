import json
from utils.Config import Config
from utils.CustomPage.CustomObject import CustomObject

import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from collections import defaultdict

class TA(CustomObject):
    # SHEETS_TO_SKIP = ['Info', 'Appendix']
    taFindings = {}
    taError = ''
    ResourcesToTrack = {}
    
    # Class-level cache to prevent duplicate execution
    _cache = {}
    _cache_key = None
    
    def __init__(self):
        super().__init__()
        return
    
    def build(self):
        # Create a cache key based on current session/account
        from utils.Config import Config
        account_id = Config.get('ACCOUNT_ID', 'default')
        regions = Config.get('REGIONS_SELECTED', ['us-east-1'])
        cache_key = f"{account_id}_{'-'.join(regions)}"
        
        # Check if we already have data for this session
        if cache_key in TA._cache:
            print("... Using cached TA data (already collected in this session)")
            cached_data = TA._cache[cache_key]
            self.taFindings = cached_data.get('taFindings', {})
            self.taError = cached_data.get('taError', '')
            return
        
        print("... Running CP - TA, it can takes up to 15 seconds")
        ssBoto = Config.get('ssBoto')
        
        # Handle case where ssBoto is not properly set (e.g., when running standalone)
        if not ssBoto or not hasattr(ssBoto, 'client'):
            try:
                import boto3
                ssBoto = boto3.Session()
                print("Using default boto3 session for TA")
            except Exception as e:
                errMsg = f"Error: TA unable to initialize boto3 session. {str(e)}"
                self.taError = errMsg
                print(errMsg)
                return
        
        # Use newer trustedadvisor service API for fast insights
        try:
            ta_client = ssBoto.client('trustedadvisor', region_name='us-east-1')
            print("Collecting from Trusted Advisor API...")
            api_data = self._build_with_trustedadvisor_api(ta_client)
            
            if api_data:
                self.taFindings = api_data
                print(f"TA data collection complete. Found pillars: {list(self.taFindings.keys())}")
            else:
                errMsg = "Error: TA unable to generate data from Trusted Advisor API."
                self.taError = errMsg
                print(errMsg)
        except Exception as e:
            errMsg = f"Error: TA unable to generate. {str(e)}"
            self.taError = errMsg
            print(errMsg)
        
        # Cache the results for this session
        TA._cache[cache_key] = {
            'taFindings': self.taFindings.copy(),
            'taError': self.taError
        }

    def _build_with_trustedadvisor_api(self, ta_client):
        """Build TA data using the newer trustedadvisor service API"""
        findings = defaultdict(lambda: defaultdict(list))
        api_data = {}
    
        try:
            pillars = ['cost_optimizing', 'security', 'performance', 'fault_tolerance', 'service_limits', 'operational_excellence']

            # First check if user has access to Trusted Advisor
            try:
                # Test API access with a simple call
                ta_client.list_recommendations(pillar='security', maxResults=1)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'SubscriptionRequiredException':
                    errMsg = "Error: TA unable to generate. Your AWS account doesn't have the required Business or Enterprise Support plan for Trusted Advisor access."
                    self.taError = errMsg
                    print(errMsg)
                    return {}
                elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:                    
                    errMsg = "Error: TA unable to generate. " + e.response['Error']['Message']
                    self.taError = errMsg
                    print(errMsg)
                    return {}
                else:
                    raise e

    
            for pillar in pillars:
                try:
                    # Get recommendations for each pillar
                    recommendations = ta_client.list_recommendations(
                        pillar=pillar
                    )['recommendationSummaries']

                    active_recommendations = [
                        recomm for recomm in recommendations 
                        if recomm['status'] not in ['resolved', 'dismissed']
                    ]
                    
                    # Process each recommendation
                    for recomm in active_recommendations:
                        # Get detailed recommendation information
                        detailed_recomm = ta_client.get_recommendation(
                            recommendationIdentifier=recomm['arn']
                        )['recommendation']
                        
                        # Create recommendation data structure
                        recomm_data = {
                            'name': recomm['name'],
                            'description': detailed_recomm.get('description', 'N/A'),
                            'status': recomm['status'],
                            'source': 'trustedadvisor_api',
                            'last_updated': recomm.get('lastUpdatedAt', 'N/A'),
                            'lifecycle_stage': recomm.get('lifecycleStage', 'N/A'),
                            'error_count': recomm.get('resourcesAggregates', {}).get('errorCount', 0),
                            'warning_count': recomm.get('resourcesAggregates', {}).get('warningCount', 0),
                            'ok_count': recomm.get('resourcesAggregates', {}).get('okCount', 0)
                        }
                        
                        # Add cost optimization specific data
                        if pillar == 'cost_optimizing':
                            cost_data = recomm.get('pillarSpecificAggregates', {}).get('costOptimizing', {})
                            recomm_data.update({
                                'estimated_savings': cost_data.get('estimatedMonthlySavings', 0),
                                'estimated_percent_savings': cost_data.get('estimatedPercentMonthlySavings', 0)
                            })
                        
                        # Group by service
                        for service in recomm.get('awsServices', ['UNKNOWN']):
                            findings[pillar][service].append(recomm_data)
                
                except Exception as e:
                    print(f"Error processing pillar {pillar} in newer API: {str(e)}")
                    continue
            
            # Convert findings to the expected format
            for pillar, services in findings.items():
                secTitle = pillar.upper()
                secTotal = {"Error": 0, "Warning": 0, "OK": 0}
                rowInfo = []
                thead = ["Services", "Findings", "# Error", "# Warning", "# OK", "Last Updated"]
                if pillar == 'cost_optimizing':
                    thead.append("Estimated Monthly Savings")
                    thead.append("Estimated Percent Savings")

                for service, recommendations in services.items():
                    total_error = sum(r['error_count'] for r in recommendations)
                    total_warning = sum(r['warning_count'] for r in recommendations)
                    total_ok = sum(r['ok_count'] for r in recommendations)
                    
                    secTotal['Error'] += total_error    
                    secTotal['Warning'] += total_warning
                    secTotal['OK'] += total_ok
                    
                    # Process individual recommendations
                    for recomm in recommendations:
                        detail = [service]

                        statClass = 'success'
                        if recomm['status'] == 'error':
                            statClass = 'danger'
                        elif recomm['status'] == 'warning':
                            statClass = 'warning'
                            
                        statusStr = "<span class='badge badge-{}'>{}</span>".format(statClass, recomm['status'].upper())

                        detail.append(f"{statusStr} {recomm['name']} <i>(Source: {recomm['source']})</i>")
                        detail.append(f"{recomm['error_count']}")
                        detail.append(f"{recomm['warning_count']}")
                        detail.append(f"{recomm['ok_count']}")

                        # Convert datetime to string to avoid JSON serialization issues
                        try:
                            parsed_datetime = datetime.fromisoformat(f"{recomm['last_updated']}")
                            formatted_datetime = parsed_datetime.strftime('%Y-%m-%d %H:%M:%S')
                            detail.append(f"{formatted_datetime} UTC")
                        except (ValueError, TypeError):
                            # Fallback if datetime parsing fails
                            detail.append(f"{recomm['last_updated']}")
                        
                        if pillar == 'cost_optimizing':
                            detail.append(f"${recomm['estimated_savings']:,.2f}")
                            detail.append(f"{recomm['estimated_percent_savings']:.1f}%")

                        detail.append(f"{recomm['description']}")
                        rowInfo.append(detail)

                api_data[secTitle] = [rowInfo, thead, secTotal.copy()]
                
            return api_data

        except Exception as e:
            print(f"Error in newer Trusted Advisor API: {str(e)}")
            return {}

    def _map_check_to_service(self, check_name):
        """Map Trusted Advisor check names to AWS service names"""
        check_name_lower = check_name.lower()
        
        # Service mapping based on check names
        service_mappings = {
            'redshift': 'Amazon Redshift',
            'rds': 'Amazon RDS',
            'ec2': 'Amazon EC2',
            'ebs': 'Amazon EBS',
            's3': 'Amazon S3',
            'cloudfront': 'Amazon CloudFront',
            'elb': 'Elastic Load Balancing',
            'lambda': 'AWS Lambda',
            'dynamodb': 'Amazon DynamoDB',
            'elasticache': 'Amazon ElastiCache',
            'route 53': 'Amazon Route 53',
            'iam': 'AWS IAM',
            'vpc': 'Amazon VPC',
            'cloudwatch': 'Amazon CloudWatch',
            'auto scaling': 'Amazon EC2 Auto Scaling',
            'elastic beanstalk': 'AWS Elastic Beanstalk',
            'cloudformation': 'AWS CloudFormation',
            'kinesis': 'Amazon Kinesis',
            'sqs': 'Amazon SQS',
            'sns': 'Amazon SNS'
        }
        
        # Find matching service
        for keyword, service in service_mappings.items():
            if keyword in check_name_lower:
                return service
        
        # Default to generic service name if no match found
        return 'AWS Service'
    
    @classmethod
    def clear_cache(cls):
        """Clear the TA data cache - useful for testing or forcing refresh"""
        cls._cache.clear()
        print("TA cache cleared")

    def printInfo(self, service):
        """
        Return TA data in JSON format for CustomPage system.
        This method is called by CustomPage.writeOutput() to save TA data.
        
        NOTE: TA data is account-wide, not service-specific, so we don't build here.
        Build happens later in buildPage() after all services are scanned.
        """
        # Check cache first to avoid duplicate builds
        from utils.Config import Config
        account_id = Config.get('ACCOUNT_ID', 'default')
        regions = Config.get('REGIONS_SELECTED', ['us-east-1'])
        cache_key = f"{account_id}_{'-'.join(regions)}"
        
        # If cache exists, load from cache
        if cache_key in TA._cache and not self.taFindings:
            cached_data = TA._cache[cache_key]
            self.taFindings = cached_data.get('taFindings', {})
            self.taError = cached_data.get('taError', '')
        
        # Return None to skip per-service file generation
        # TA data will be generated once during buildPage()
        if not self.taFindings and not self.taError:
            return None
        
        if self.taError:
            # Return error data structure for Cloudscape UI
            error_data = {
                'error': self.taError,
                'pillars': {}
            }
            return json.dumps(error_data)
        
        if not self.taFindings:
            # Return empty data structure for Cloudscape UI
            empty_data = {
                'error': 'No Trusted Advisor data available',
                'pillars': {}
            }
            return json.dumps(empty_data)
        
        # Convert taFindings to format expected by Cloudscape UI
        pillars = {}
        
        # Define all 6 AWS Well-Architected pillars to ensure they all appear
        all_pillars = {
            'COST_OPTIMIZING': 'Cost Optimization',
            'SECURITY': 'Security', 
            'PERFORMANCE': 'Performance',
            'FAULT_TOLERANCE': 'Reliability',
            'SERVICE_LIMITS': 'Service Quotas',
            'OPERATIONAL_EXCELLENCE': 'Operational Excellence'
        }
        
        # Initialize all pillars with empty data
        for pillar_name, pillar_display_name in all_pillars.items():
            pillars[pillar_name] = {
                'headers': ["Services", "Findings", "# Error", "# Warning", "# OK", "Last Updated"],
                'rows': [],
                'totals': {"Error": 0, "Warning": 0, "OK": 0}
            }
            
            # Add cost-specific headers for cost optimization pillar
            if pillar_name == 'COST_OPTIMIZING':
                pillars[pillar_name]['headers'].extend(["Estimated Monthly Savings", "Estimated Percent Savings"])
        
        # Override with actual data where available
        for pillar_name, pillar_data in self.taFindings.items():
            if len(pillar_data) == 3:  # [rowInfo, thead, secTotal]
                rowInfo, thead, secTotal = pillar_data
                pillars[pillar_name] = {
                    'headers': thead,
                    'rows': rowInfo,
                    'totals': secTotal
                }
        
        # Return data structure compatible with Cloudscape UI
        ta_data = {
            'error': '',
            'pillars': pillars
        }
        
        return json.dumps(ta_data)