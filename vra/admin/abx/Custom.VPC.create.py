# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import Libraries Here
#===============================================================================
import json
import time


#===============================================================================
# AaManager SDK
#===============================================================================
class AaManager:
    def __init__(self, context): self.context = context
    def toJson(self, response):
        if response['status'] >= 400: raise Exception(response['content'].decode('utf-8'))
        try: return json.loads(response['content'].decode('utf-8'))
        except: return response['content'].decode('utf-8')
    def encode(self, url): return url.replace(' ', '%20').replace('$', '%24').replace("'", '%27').replace('[', '%5B').replace(']', '%5D')
    def get(self, url): return self.toJson(self.context.request(operation='GET', link=self.encode(url), body=''))
    def post(self, url, data): return self.toJson(self.context.request(operation='POST', link=self.encode(url), body=data))
    def put(self, url, data): return self.toJson(self.context.request(operation='PUT', link=self.encode(url), body=data))
    def patch(self, url, data): return self.toJson(self.context.request(operation='PATCH', link=self.encode(url), body=data))
    def delete(self, url, data=''): return self.toJson(self.context.request(operation='DELETE', link=self.encode(url), body=data))
    def getUerp(self, url): return self.get(f'/provisioning/uerp{url}')
    def postUerp(self, url, data): return self.post(f'/provisioning/uerp{url}', data)
    def putUerp(self, url, data): return self.put(f'/provisioning/uerp{url}', data)
    def patchUerp(self, url, data): return self.patch(f'/provisioning/uerp{url}', data)
    def deleteUerp(self, url, data=''): return self.delete(f'/provisioning/uerp{url}', data)
    def runOrchAction(self, projectId, uri, data={}):
        result = self.post(f'/form-service/api/forms/renderer/external-value?projectId={projectId}', {'uri':uri, 'dataSource':'scriptAction', 'parameters':[{'name':k, 'value':v} for k, v in data.items()]})
        if 'data' in result: return result['data']
        elif 'error' in result: raise Exception(result['error']['summaryMessage'])
        else: raise Exception('unknown error')


#===============================================================================
# Implement Handler Here
#===============================================================================
def handler(context, inputs):
    apiVersion = '2021-07-15'

    aa = AaManager(context)

    name = inputs['name']
    displayName = inputs['displayName']
    projectId = inputs['__metadata']['project']
    project = aa.get(f'/iaas/api/projects/{projectId}')
    projectName = project['name']

    vpcTagCategory = inputs['vpcTagCategory']
    vpcInfraProfileLink = inputs['vpcInfraProfile']
    vpcInfraProfile = aa.getUerp(vpcInfraProfileLink)
    vpcInfraProfileName = vpcInfraProfile['desc']
    transitSubnetLink = vpcInfraProfile['subnetLinks'][0]
    transitSubnet = aa.getUerp(transitSubnetLink)
    transitSegmentPath = transitSubnet['customProperties']['__path']
    transitPrefix = transitSubnet['subnetCIDR'].split('/')[1]
    managedGatewayLink = inputs['managedGateway']
    managedGateway = aa.getUerp(managedGatewayLink)
    managedRouterLink = managedGateway['routerStateLink']
    managedRouter = aa.getUerp(managedRouterLink)
    routerName = managedRouter['name']
    endpointLink = managedRouter['endpointLink']
    managedTier1Path = aa.getUerp(managedRouterLink)['customProperties']['__path']
    managedNetworkLink = inputs['managedNetwork']
    managedNetwork = aa.getUerp(managedNetworkLink)
    managedSubnetLink = managedNetwork['subnetLink']
    managedSubnet = aa.getUerp(managedSubnetLink)
    managedSegmentPath = managedSubnet['customProperties']['__path']
    managedLoadBalancerLink = inputs['managedLoadBalancer']
    managedLoadBalancer = aa.getUerp(managedLoadBalancerLink)

    for transitRangeLink, transitRange in aa.getUerp(f"/resources/subnet-ranges?expand&$filter=subnetLinks.item eq '{transitSubnetLink}'")['documents'].items():
        transitRangeId = transitRangeLink.split("/subnet-ranges/")[1]
        ipTaskLink = aa.post(f'/iaas/api/network-ip-ranges/{transitRangeId}/ip-addresses/allocate?apiVersion={apiVersion}', {"numberOfIps": 1})['selfLink'];
        for _ in range(0, 10):
            time.sleep(1)
            ipTask = aa.get(ipTaskLink)
            if ipTask['status'] == 'FINISHED':
                ipId = ipTask['resources'][0].split("/ip-addresses/")[1]
                transitIpAddressLink = aa.getUerp(f"/resources/ip-addresses?$filter=id eq '{ipId}'")['documentLinks'][0]
                transitIpAddress = aa.getUerp(transitIpAddressLink)
                transitAddress = transitIpAddress['ipAddress']
                aa.runOrchAction(projectId, 'com.bvp.bp.vpc/vpcProvision', {
                    'endpointLink': endpointLink,
                    'managedRouterLink': managedRouterLink,
                    'managedTier1Path': managedTier1Path,
                    'transitSegmentPath': transitSegmentPath,
                    'transitAddressLink': transitIpAddressLink,
                    'transitPrefix': transitPrefix
                })
                break
        else: raise Exception('could not allocate transit address')
        break
    else: raise Exception('could not find transit address range')

    domain = managedSubnet['domain']
    projectDomain = f'{projectName}.{domain}'

    managedSubnet['domain'] = projectDomain
    managedSubnet['dnsSearchDomains'] = [projectDomain]
    managedSubnet = aa.putUerp(managedSubnetLink, managedSubnet)
    managedNetwork['customProperties']['domain'] = projectDomain
    managedNetwork['customProperties']['dnsSearchDomains'] = f'[{projectDomain}]'
    managedNetwork = aa.putUerp(managedNetworkLink, managedNetwork)
    managedIpAddress = aa.getUerp(f"/resources/ip-addresses?expand&$filter=connectedResourceLink eq '{managedSubnetLink}'")
    managedIpAddressLink = managedIpAddress['documentLinks'][0]
    managedIpAddress = managedIpAddress['documents'][managedIpAddressLink]
    managedAddress = managedIpAddress['ipAddress']

    vpcProfile = {
        'name': name,
        'desc': displayName,
        'provisioningRegionLink': vpcInfraProfile['provisioningRegionLink'],
        'isolationType': 'SUBNET',
        'isolationNetworkLink': vpcInfraProfile['isolationNetworkLink'],
        'isolationExternalSubnetLink': vpcInfraProfile['isolationExternalSubnetLink'],
        'isolationNetworkCIDR': vpcInfraProfile['isolationNetworkCIDR'],
        'isolatedSubnetCIDRPrefix': vpcInfraProfile['isolatedSubnetCIDRPrefix'],
        'customProperties': {
            'onDemandNetworkIPAssignmentType': 'static',
            'edgeClusterRouterStateLink': vpcInfraProfile['customProperties']['edgeClusterRouterStateLink'],
            'tier0LogicalRouterStateLink': vpcInfraProfile['customProperties']['tier0LogicalRouterStateLink'],
            'vpcProjectId': projectId,
            'vpcProjectName': projectName,
            'vpcProjectDomain': projectDomain,
            'vpcRouterName': routerName,
            'vpcManagedGatewayLink': managedGatewayLink,
            'vpcManagedRouterLink': managedRouterLink,
            'vpcManagedTier1Path': managedTier1Path,
            'vpcManagedNetworkLink': managedNetworkLink,
            'vpcManagedSubnetLink': managedSubnetLink,
            'vpcManagedSegmentPath': managedSegmentPath,
            'vpcManagedIpAddressLink': managedIpAddressLink,
            'vpcManagedAddress': managedAddress,
            'vpcManagedLoadBalancerLink': managedLoadBalancerLink,
            'vpcInfraProfileLink': vpcInfraProfileLink,
            'vpcTransitSubnetLink': transitSubnetLink,
            'vpcTransitSegmentPath': transitSegmentPath,
            'vpcTransitIpAddressLink': transitIpAddressLink,
            'vpcTransitAddress': transitAddress,
            'vpcDnsServerAddresses': json.dumps(managedSubnet['dnsServerAddresses']),
        },
        'subnets': [managedSubnet],
        'subnetLinks': [managedSubnetLink],
        'loadBalancers': [managedLoadBalancer],
        'loadBalancerLinks': [managedLoadBalancerLink],
        'securityGroups': [],
        'securityGroupLinks': []
    }

    vpcProfile = aa.postUerp('/provisioning/resources/network-profiles', vpcProfile)
    vpcProfileLink = vpcProfile['documentSelfLink']
    vpcId = vpcProfileLink.split('/network-profiles/')[1]

    vpcIdTag = aa.getUerp(f"/resources/tags?expand&$filter=((key eq 'vpcId') and (value eq '{vpcId}'))")
    if vpcIdTag['documentLinks']: vpcIdTag = vpcIdTag['documents'][vpcIdTag['documentLinks'][0]]
    else:
        vpcIdTag = aa.postUerp('/resources/tags?expand', {
            'key': vpcTagCategory,
            'value': vpcId,
            'isSaved': True,
            'origins': ['USER_DEFINED']
        })

    vpcProfile['tags'] = [vpcIdTag]
    vpcProfile['tagLinks'] = [vpcIdTag['documentSelfLink']]
    vpcProfile = aa.putUerp(vpcProfileLink, vpcProfile)

    inputs['id'] = vpcId
    inputs['projectName'] = projectName
    inputs['infraName'] = vpcInfraProfileName
    inputs['routerName'] = routerName
    inputs['projectDomain'] = projectDomain
    inputs['vpcProfile'] = vpcProfileLink
    inputs['managedRouter'] = managedRouterLink
    inputs['managedTier1'] = managedTier1Path
    inputs['managedSubnet'] = managedSubnetLink
    inputs['managedSegment'] = managedSegmentPath
    inputs['managedIpAddress'] = managedIpAddressLink
    inputs['managedAddress'] = managedAddress
    inputs['transitSubnet'] = transitSubnetLink
    inputs['transitSegment'] = transitSegmentPath
    inputs['transitIpAddress'] = transitIpAddressLink
    inputs['transitAddress'] = transitAddress
    
    outputs = inputs
    return outputs
