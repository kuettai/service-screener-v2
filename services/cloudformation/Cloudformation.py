import botocore

from utils.Tools import _pi
from services.Service import Service

from services.cloudformation.drivers.CloudformationStack import CloudformationStack


class Cloudformation(Service):
    """
    AWS CloudFormation service scanner.

    Discovery: describe_stacks (paginated), filtered to stacks in a settled
    state. All checks are per-stack, so there is one driver.

    Hydration calls (all read-only):
      - describe_stacks      (paginated; includes DriftInformation and Tags)
      - get_stack_policy     (per stack)

    READ-ONLY NOTE: this service deliberately does NOT call detect_stack_drift.
    That operation is a WRITE: its only output is a StackDriftDetectionId, and it
    initiates an asynchronous, billed, rate-limited detection run that mutates
    stack state. Drift status is instead read from the DriftInformation field
    that describe_stacks already returns. Verified against real stacks, whose
    common value is NOT_CHECKED.
    """

    ACCESS_DENIED_CODES = (
        'AccessDenied', 'AccessDeniedException', 'AuthorizationError',
        'UnrecognizedClientException', 'ValidationError',
    )

    ## Stacks in a settled state. A stack mid-operation (CREATE_IN_PROGRESS) has
    ## a configuration that is about to change, so evaluating it is noise; a
    ## DELETE_COMPLETE stack no longer exists.
    SETTLED_STATUS_PREFIXES = ('CREATE_COMPLETE', 'UPDATE_COMPLETE',
                               'UPDATE_ROLLBACK_COMPLETE', 'IMPORT_COMPLETE',
                               'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED',
                               'UPDATE_ROLLBACK_FAILED', 'UPDATE_FAILED',
                               'CREATE_FAILED')

    def __init__(self, region):
        super().__init__(region)
        ssBoto = self.ssBoto
        self.cfnClient = ssBoto.client('cloudformation', config=self.bConfig)

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def getResources(self):
        stacks = []
        try:
            paginator = self.cfnClient.get_paginator('describe_stacks')
            for page in paginator.paginate():
                for stack in page.get('Stacks', []) or []:
                    name = stack.get('StackName')
                    status = stack.get('StackStatus') or ''
                    if not name:
                        continue
                    if not status.startswith(self.SETTLED_STATUS_PREFIXES):
                        continue

                    ## Nested stacks are governed by their parent's template, so
                    ## their configuration is not independently actionable and
                    ## reporting them multiplies findings across a single
                    ## logical deployment.
                    if stack.get('ParentId'):
                        continue

                    tags = stack.get('Tags') or []
                    if self.tags and not self.resourceHasTags(tags):
                        continue

                    stack['_region'] = self.region
                    stack['_tags'] = tags
                    stack['_stackPolicy'] = self._getStackPolicy(name)
                    _pi('Cloudformation', f"Stack: {name}")
                    stacks.append(stack)
        except botocore.exceptions.ClientError as e:
            self._logClientError('describe_stacks', e)
        except botocore.exceptions.EndpointConnectionError as e:
            print(f"CloudFormation not available in region {self.region}: {e}")
        return stacks

    def _getStackPolicy(self, name):
        """
        Return the stack policy body, '' when none is set, or None when it could
        not be read — so the check can tell "no policy" from "unknown".
        """
        try:
            resp = self.cfnClient.get_stack_policy(StackName=name)
            return resp.get('StackPolicyBody') or ''
        except botocore.exceptions.ClientError as e:
            code = e.response.get('Error', {}).get('Code', '')
            if code in ('ValidationError',):
                return ''
            self._logClientError(f'get_stack_policy({name})', e)
            return None

    # ------------------------------------------------------------------ #
    # Advise
    # ------------------------------------------------------------------ #
    def advise(self):
        objs = {}
        for stack in self.getResources():
            name = stack.get('StackName', 'unknown')
            try:
                obj = CloudformationStack(stack, self.cfnClient)
                obj.run(self.__class__)
                objs[f"CloudFormation Stack::{name}"] = obj.getInfo()
                del obj
            except Exception as e:
                print(f"Error processing CloudFormation stack {name}: {e}")
        return objs

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _logClientError(self, where, error):
        code = error.response.get('Error', {}).get('Code', 'Unknown')
        if code in self.ACCESS_DENIED_CODES:
            return
        msg = error.response.get('Error', {}).get('Message', str(error))
        print(f"Cloudformation {where}: {code} - {msg}")
