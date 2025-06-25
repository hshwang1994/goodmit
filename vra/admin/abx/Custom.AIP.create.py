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
# ------------------------------------------------------------------------------
# Default : apiVersion :  2021-07-15
#===============================================================================
def handler(context, inputs):
    apiVersion = '2021-07-15'

    aa = AaManager(context)

    address = inputs['address'] if 'address' in inputs and inputs['address'] else ''
    vpcProfileLink = inputs['vpc']
    vpcProfile = aa.getUerp(vpcProfileLink)
    subnetLink = vpcProfile['isolationExternalSubnetLink']
    subnet = aa.getUerp(subnetLink)
    subnetRange = aa.getUerp(f"/resources/subnet-ranges?expand&$filter=subnetLink eq '{subnetLink}'")
    subnetRange = subnetRange['documents'][subnetRange['documentLinks'][0]]
    subnetRangeLink = subnetRange['documentSelfLink']
    subnetRangeId = subnetRangeLink.split('/subnet-ranges/')[1]

    requestLink = aa.post(f'/iaas/api/network-ip-ranges/{subnetRangeId}/ip-addresses/allocate?apiVersion={apiVersion}', {
        'ipAddresses': [address]
    } if address else {
        'numberOfIps': 1
    })['selfLink']

    for _ in range(0, 10):
        time.sleep(1)
        request = aa.get(requestLink)
        if request['status'] == 'FINISHED':
            iaasLink = request['resources'][0]
            iaasIp = aa.get(f'{iaasLink}?apiVersion={apiVersion}')
            iaasIpId = iaasIp['id']
            ipAddress = aa.getUerp(f"/resources/ip-addresses?expand&$filter=id eq '{iaasIpId}'")
            ipAddress = ipAddress['documents'][ipAddress['documentLinks'][0]]
            ipAddressLink = ipAddress['documentSelfLink']
            address = ipAddress['ipAddress']
            break
    else: raise Exception('could not allocate ip address')
    
    projectId = inputs['__metadata']['project']
    computeLink = inputs['compute']
    compute = aa.getUerp(computeLink);
    interfaceLink = inputs['interface']
    interfaceAddress = aa.runOrchAction(projectId, 'com.gvp.bp.aip/attachAccessIp', { #원래 bvp 였음
        'interfaceLink': interfaceLink,
        'accessIpId': iaasIpId,
        'destinationIp': address
    })
    #inputs['compute'] = computeLink
    #inputs['interface'] = interfaceLink
    inputs['interfaceAddress'] = interfaceAddress
    inputs['computeName'] = compute['name']
    
    inputs['id'] = iaasIpId
    inputs['address'] = address
    inputs['ipAddress'] = ipAddressLink
    inputs['subnet'] = subnetLink
    inputs['subnetName'] = subnet['name']
    inputs['subnetRange'] = subnetRangeLink
    inputs['subnetRangeName'] = subnetRange['name']
    #inputs['compute'] = 'NONE'
    #inputs['interface'] = 'NONE'
    outputs = inputs
    return outputs
