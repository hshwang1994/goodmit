# SG properties : Security group name, Tags, Count, Rules(name,port,access,source,service,portocol,direction,destination), Constraints, Description, Type
# DFW SG properties : Name, Rules, Tags, Request Message, Display Name
# DFW Custom properites : Name, Display Name
# 사용자 입력 : VM, 대상IP, 서비스, Access  => DFW Rule : Source(대상IP), Destination(VM), 서비스, Access, 적용대상(VM)
# VPC 당 DFW Policy 생성 -> Inbound에 대한 Rule 적용

# 1. 프로젝트 생성 시 DFW Custom 생성, 위치 한 프로젝트의 VPC 정보를 가져오며 VPC 당 DFW Policy 생성
# 2. Rule 생성 Action 카탈로그로 Rule을 생성하는 input 받음
# 3. input에서 VM 정보의 연결된 VPC 정보를 통해 Rule이 배치될 DFW 정책이 선택되도록 함



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
def get_label_by_value(data: list, target_value: str):
    """
    주어진 리스트에서 특정 value에 해당하는 label을 반환합니다.
    
    :param data: [{'label': ..., 'value': ...}, ...] 형식의 리스트
    :param target_value: 찾고자 하는 value 문자열
    :return: 해당 value의 label, 없으면 None
    """
    return next((item['label'] for item in data if item['value'] == target_value), None)

def handler(context, inputs):
    apiVersion = '2021-07-15'

    aa = AaManager(context)
    projectId = inputs['__metadata']['project']
    project = aa.get(f'/iaas/api/projects/{projectId}')
    projectName = project['name']
    vpc = aa.get(f"/deployment/api/resources/{inputs['vpcResourceId']}")
    endpointLink = aa.getUerp(vpc['properties']['managedRouter'])['endpointLink']

    results = aa.runOrchAction(projectId,'com.gvp.bp.vpcfw/vpcfwProvision',{ "endpointLink": endpointLink, "managedTier1Path": vpc['properties']['managedTier1'], "routerName": vpc['properties']['routerName']})
    
    print(results)
    
    inputs['rules'] = get_label_by_value(results, "rules")
    inputs['securityPolicyId'] = get_label_by_value(results, "id")
    inputs['securityPolicyPath'] = get_label_by_value(results, "path")
    inputs['scope'] = vpc['properties']['managedTier1']

    

    outputs = inputs
    return outputs
    