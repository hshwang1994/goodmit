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
def convert_rules(rules: list[dict], scope) -> list[dict]:
    converted_rules = []

    for rule in rules:
        tcpServices = rule.get("tcpServices", [])
        udpServices = rule.get("udpServices", [])
        service_entries = []

        # TCP만 있는 경우
        if tcpServices and not udpServices:
            services_list = ["ANY"]
            service_entries.append({
                "l4_protocol": "TCP",
                "destination_ports": tcpServices,
                "resource_type": "L4PortSetServiceEntry",
                "display_name": "TCP"
            })

        # UDP만 있는 경우
        elif udpServices and not tcpServices:
            services_list = ["ANY"]
            service_entries.append({
                "l4_protocol": "UDP",
                "destination_ports": udpServices,
                "resource_type": "L4PortSetServiceEntry",
                "display_name": "UDP"
            })

        # 둘 다 있는 경우
        elif tcpServices and udpServices:
            services_list = ["ANY"]
            service_entries.append({
                "l4_protocol": "TCP",
                "destination_ports": tcpServices,
                "resource_type": "L4PortSetServiceEntry",
                "display_name": "TCP"
            })
            service_entries.append({
                "l4_protocol": "UDP",
                "destination_ports": udpServices,
                "resource_type": "L4PortSetServiceEntry",
                "display_name": "UDP"
            })

        # 아무것도 없는 경우
        else:
            services_list = ["ANY"]

        converted_rule = {
            "action": rule["action"],
            "id": rule["id"],
            "sequence_number": rule["sequenceNumber"],
            "source_groups": rule.get("source", []),
            "destination_groups": rule.get("destination", []),
            "services": services_list,
            "scope": [scope],
            "direction": "IN_OUT"
        }

        if service_entries:
            converted_rule["service_entries"] = service_entries

        converted_rules.append(converted_rule)

    return converted_rules


def find_deleted_rules(old_rules, updated_rules):
    # updated_rules에 존재하지 않는 id를 old_rules에서 찾는다
    updated_ids = {rule['id'] for rule in updated_rules}
    deleted_rules = [rule for rule in old_rules if rule['id'] not in updated_ids]
    return deleted_rules

def handler(context, inputs):
    apiVersion = '2021-07-15'

    aa = AaManager(context)
    projectId = inputs['__metadata']['project']
    project = aa.get(f'/iaas/api/projects/{projectId}')
    projectName = project['name']
    vpc = aa.get(f"/deployment/api/resources/{inputs['vpcResourceId']}")
    endpointLink = aa.getUerp(vpc['properties']['managedRouter'])['endpointLink']
    
    deleted = find_deleted_rules(inputs['rules'], inputs['vpcfwRules'])
    deletedRules = json.dumps(deleted)
    if not deleted:
        print("삭제된 항목이 없습니다.")
    else:
        print("삭제된 항목이 있습니다.")
        aa.runOrchAction(projectId,'com.gvp.bp.vpcfw/vpcfwRulesRemoval',{ "endpointLink": endpointLink, "securityPolicyPath": inputs['securityPolicyPath'], "rules": deletedRules})
    
    
    convertRules = convert_rules(inputs['vpcfwRules'],inputs['scope'])
    rules = json.dumps(convertRules)
    results = aa.runOrchAction(projectId,'com.gvp.bp.vpcfw/vpcfwUpdate',{ "endpointLink": endpointLink, "securityPolicyPath": inputs['securityPolicyPath'], "rules": rules})
    
    inputs['rules'] = inputs['vpcfwRules']
    

    outputs = inputs
    outputs.pop('vpcfwRules')
    outputs.pop('vpcfwId')
    return outputs
    