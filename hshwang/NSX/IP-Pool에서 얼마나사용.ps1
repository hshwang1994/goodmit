# 변수 설정
$server = "10.100.14.124"
$username = "admin"
$password = "VMware1!"
$ippool = "IP-Pool"

# 자격 증명 생성
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($username, $securePassword)

# SSL 인증서 검증 무시 설정
Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;

public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint srvPoint, X509Certificate certificate,
        WebRequest request, int certificateProblem) {
        return true;
    }
}
"@

[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy

# API 호출
$uri = "https://$server/policy/api/v1/infra/ip-pools/$ippool/"
$authHeader = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${username}:${password}"))

$response = Invoke-RestMethod -Uri $uri -Method Get -Headers @{Authorization=$authHeader}

# 호출 내용 중 필요한 내용 만 추출
$total_ips = $response.pool_usage.total_ips
$requested_ips = $response.pool_usage.requested_ip_allocations
$allocated_ips = $response.pool_usage.allocated_ip_allocations
$available_ips = $response.pool_usage.available_ips

# 결과 출력
Write-Host "현재 IP 풀 이름" $ippool "에서 사용중인 IP 갯수 내역을 출력합니다"
Write-Host "총 사용 가능한 IP 수: $total_ips"
Write-Host "요청 중인 IP 수: $requested_ips"
Write-Host "사용 중인 IP 수: $allocated_ips"
Write-Host "사용 가능한 IP 수: $available_ips"
