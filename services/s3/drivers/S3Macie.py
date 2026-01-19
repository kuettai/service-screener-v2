import urllib.parse
from datetime import date

import boto3
import botocore

from utils.Config import Config
from utils.Policy import Policy
from utils.Tools import _warn
from services.Evaluator import Evaluator

class S3Macie(Evaluator):
    def __init__(self, macieV2Client):
        super().__init__()
        self.macieV2Client = macieV2Client
        
        self._resourceName = 'Macie'

        self.init()
    
    def _checkMacieEnable(self):
        try:
            self.macieV2Client.list_findings()
        except self.macieV2Client.exceptions.AccessDeniedException as e:
            self.results['MacieToEnable'] = [-1, None]
        except botocore.exceptions.EndpointConnectionError as connErr:
            # Handle regions where Macie2 is not available
            _warn(f"Macie2 service not available in this region: {str(connErr)}")
            self.results['MacieNotAvailable'] = [-1, None]
        except Exception as e:
            # Handle any other unexpected errors
            _warn(f"Error checking Macie2 status: {str(e)}")
            self.results['MacieError'] = [-1, None]