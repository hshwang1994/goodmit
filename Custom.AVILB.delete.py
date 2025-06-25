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
    endpointLink = aa.get(vpcGatewayLink)['endpointLinks'][0]

    rest.delete(f"/api/virtualservice/{inputs['vsUuid']}")
    rest.delete(f"/api/vsvip/{inputs['vsvipUuid']}")
    rest.delete(f"/api/pool/{inputs['poolUuid']}")
    aa.runOrchAction(projectId,"com.gvp.bp.avi/detachPoolIp",{
        "endpointLink": endpointLink,
        "pools": json.dumps(inputs['pool']),
        "vpcManagedTier1Path": vpcManagedTier1Path
    })
    releaseAddresses = []
    for p in inputs['pool']:
        releaseAddresses.append(p['poolIp'])
    requestLink = aa.post(f'/iaas/api/network-ip-ranges/{inputs["ipRangeId"]}/ip-addresses/release?apiVersion=2025-06-05', {
        'ipAddresses': releaseAddresses
    })['selfLink']
    for _ in range(0, 10):
        time.sleep(1)
        request = aa.get(requestLink)
        if request['status'] == 'FINISHED': break
    else: raise Exception('could not release ip address')
    return {}
