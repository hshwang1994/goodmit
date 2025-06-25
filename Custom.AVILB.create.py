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
import http.client
from urllib.parse import urlparse
import ssl


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

class RestManager:
    def __init__(self, base_url, headers=None, timeout=10):
        if not base_url:
            raise ValueError("Error [RestManager]: must be set host parameter")
        
        self.base_url = base_url.rstrip('/')
        self.parsed_url = urlparse(self.base_url)
        self.timeout = timeout

        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.headers = {**default_headers, **(headers or {})}

        if self.parsed_url.scheme == "https":
            self.conn = http.client.HTTPSConnection(self.parsed_url.hostname, self.parsed_url.port or 443, timeout=self.timeout, context=ssl._create_unverified_context())
        elif self.parsed_url.scheme == "http":
            self.conn = http.client.HTTPConnection(self.parsed_url.hostname, self.parsed_url.port or 80, timeout=self.timeout)
        else:
            raise ValueError("Unsupported URL scheme: " + self.parsed_url.scheme)

    def _request(self, method, path, data=None):
        url_path = self.parsed_url.path + path

        body = None
        if data is not None:
            body = json.dumps(data)

        try:
            self.conn.request(method, url_path, body=body, headers=self.headers)
            response = self.conn.getresponse()
            response_data = response.read().decode()
            if 200 <= response.status < 300 or response.status == 302:
                return json.loads(response_data) if response_data else None
            else:
                raise Exception(f"HTTP {response.status}: {response_data}")
        except Exception as e:
            raise Exception(f"Request failed: {e}")

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data):
        return self._request("POST", path, data)

    def put(self, path, data):
        return self._request("PUT", path, data)

    def patch(self, path, data):
        return self._request("PATCH", path, data)

    def delete(self, path):
        return self._request("DELETE", path)
    
    def close(self):
        self.conn.close()


#===============================================================================
# Implement Handler Here
# ------------------------------------------------------------------------------
# Default : apiVersion :  2021-07-15
#===============================================================================

def handler(context, inputs):
    aa = AaManager(context)
    projectId = inputs['__metadata']['project']
    aviHostname = aa.get("/iaas/api/cloud-accounts-avilb?apiVersion=2025-05-31")['content'][0]['hostName']
    cookie = aa.runOrchAction(projectId,"com.gvp.bp.avi/aviControllerLogin",{"endpoint" : aviHostname})
    cookieInfos = cookie.split(";")
    csrftoken = next(
        (cookie.split("=")[1] for cookie in cookieInfos if cookie.startswith("csrftoken=")),
        None
    )
    rest = RestManager(f"https://{aviHostname}",{"Cookie": cookie, "X-CSRFToken": csrftoken, "Referer": f"https://{aviHostname}" })

    vpcInfo = aa.get(f"/deployment/api/resources/{inputs['vpcId']}")
    vpcGatewayLink = vpcInfo['properties']['managedGateway']
    vpcManagedTier1Path = vpcInfo['properties']['managedTier1']
    vpcInfraTag = aa.get(vpcInfo['properties']['vpcInfraProfile'])['expandedTags'][0]['tag']
    vpcInfraTagKey = vpcInfraTag.split('\n')[0]
    vpcInfraTagValue = vpcInfraTag.split('\n')[1]
    tagId = aa.get(f"/iaas/api/tags?$filter=key eq '{vpcInfraTagKey}'&$filter=value eq '{vpcInfraTagValue}'")['content'][0]['id']
    data = aa.post("/iaas/api/tags/tags-usage?apiVersion=2025-06-01",{"tagIds": [tagId]})['documents']
    vraNetwork = [value for key, value in data.items() if "sub-networks" in key]
    endpointLink = aa.get(vpcGatewayLink)['endpointLinks'][0]
    nsxHostName = aa.getUerp(endpointLink)['endpointProperties']['hostName']
    cloudList = rest.get("/api/cloud")['results']
    for cloud in cloudList:
        if cloud.get('nsxt_configuration'):
            if cloud['nsxt_configuration']['nsxt_url'] == nsxHostName:
                cloudRef = cloud['url']
                cloudName = cloud['name']

    aviNetwork = rest.get(f"/api/network?cloud_ref.name={cloudName}&name.in={vraNetwork[0]['name']}")['results'][0]
    networkRef = aviNetwork['url']
    vrfRef = aviNetwork['vrf_context_ref']

    vsvip = rest.post("/api/vsvip", {
        "cloud_ref": cloudRef,
        "name": inputs['name'],
        "vrf_context_ref": vrfRef,
        "vip": [
            {
                "auto_allocate_ip": True,
                "ipam_network_subnet": {
                    "network_ref": networkRef
                    }
            }
        ]
    })
    vsvipRef = vsvip['url']
    
    networkProfileRef = rest.get("/api/networkprofile?name=System-TCP-Fast-Path")['results'][0]['url'] if inputs['serviceProtocol'] == "TCP" else rest.get("/api/networkprofile?name=System-UDP-Fast-Path")['results'][0]['url']
    appProfileRef = rest.get("/api/applicationprofile?name=System-L4-Application")['results'][0]['url']
    segroupRef = rest.get(f"/api/serviceenginegroup?cloud_ref.name={cloudName}")['results'][0]['url']
    services = []
    for port in inputs['servicePort']:
        services.append({
            "port": port
        })

    vs = rest.post("/api/virtualservice", {
        "application_profile_ref": appProfileRef,
        "cloud_ref": cloudRef,
        "name": inputs['name'],
        "network_profile_ref": networkProfileRef,
        "se_group_ref": segroupRef,
        "services": services,
        "vrf_context_ref": vrfRef,
        "vsvip_ref": vsvipRef
    })
    
    if inputs['vmList'] != []:
        ipRangeId = aa.get("/iaas/api/network-ip-ranges?$filter=name eq 'lb-pool-ip-range'")['content'][0]['id']
        requestId = aa.post(f"/iaas/api/network-ip-ranges/{ipRangeId}/ip-addresses/allocate?apiVersion=2025-06-05",{"numberOfIps": len(inputs['vmList'])})['id']
        for _ in range(0, 10):
            time.sleep(1)
            request = aa.get(f"/iaas/api/request-tracker/{requestId}")
            if request['status'] == 'FINISHED':
                iaasLinks = request['resources']
                poolIps = []
                for iaasLink in iaasLinks:
                    poolIps.append(aa.get(f"{iaasLink}?apiVersion=2025-06-05")['ipAddress'])
                break
        else: raise Exception('could not allocate ip address')
        pools = []
        for i in range(0, len(poolIps)):
            pools.append({
                "vmId": inputs['vmList'][i],
                "vmIp": aa.get(f"/iaas/api/machines/{inputs['vmList'][i]}")['address'],
                "poolIp": poolIps[i]
            })
        aa.runOrchAction(projectId, 'com.gvp.bp.avi/attachPoolIp', {
            "endpointLink": endpointLink,
            "pools": json.dumps(pools),
            "vpcManagedTier1Path": vpcManagedTier1Path
        })
        
        servers = []
        for pool in pools:
            servers.append({
                "ip": {
                    "addr": pool['poolIp'],
                    "type": "V4"
                }
            })
        aviPool = rest.post("/api/pool", {
            "cloud_ref": cloudRef,
            "default_server_port": inputs['vmPort'],
            "servers": servers,
            "vrf_ref": vrfRef,
            "name": inputs['name']
        })

        rest.patch(f"/api/virtualservice/{vs['uuid']}", {
            "add":{
                "pool_ref": aviPool['url']
            }
            
        })
    

    inputs['ipRangeId'] = ipRangeId
    inputs['vip'] = vsvip['vip'][0]['ip_address']['addr']
    inputs['pool'] = pools
    inputs['vsvipUuid'] = vsvip['uuid']
    inputs['vsUuid'] = vs['uuid']
    inputs['poolUuid'] = aviPool['uuid']
    rest.post("/logout",None)
    rest.close()
    
    
    

    

    outputs = inputs
    return outputs