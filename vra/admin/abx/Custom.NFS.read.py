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
    # bypass resource
    return inputs
    
'''
# ceph volume usage get
def handler(context, inputs):
    aa = AaManager(context)
    projectId = inputs['__metadata']['project']
    data = aa.runOrchAction(projectId,"com.gvp.bp.nfs/nfsRead",{
        "subvolumeName": inputs['subvolumeName'],
        "volumeName": inputs['volumeName']
    })
    
    inputs['usage'] = data
    outputs = inputs
    return outputs
'''