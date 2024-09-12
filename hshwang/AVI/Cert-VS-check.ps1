# AVI Controller 정보
$aviController = "https://10.100.14.250"
$username = "admin"
$password = "VMware1!"

# 세션 생성
function Get-AuthToken {
    param (
        [string]$aviController,
        [string]$username,
        [string]$password
    )

    $loginUrl = "$aviController/login"
    $loginData = @{
        username = $username
        password = $password
    }

    $response = Invoke-RestMethod -Method Post -Uri $loginUrl -Body $loginData -SkipCertificateCheck -ContentType "application/json"
    if ($response.StatusCode -ne 200) {
        throw "Failed to log in to the AVI controller"
    }
    return $response
}

$authToken = Get-AuthToken -aviController $aviController -username $username -password $password

# 인증서 정보 조회
$certificatesUrl = "$aviController/api/sslkeyandcertificate"
$certificatesResponse = Invoke-RestMethod -Method Get -Uri $certificatesUrl -Headers @{ "Authorization" = "Bearer $authToken" } -SkipCertificateCheck
$certificates = $certificatesResponse.results

# 가상 서비스 정보 조회
$virtualServicesUrl = "$aviController/api/virtualservice"
$virtualServicesResponse = Invoke-RestMethod -Method Get -Uri $virtualServicesUrl -Headers @{ "Authorization" = "Bearer $authToken" } -SkipCertificateCheck
$virtualServices = $virtualServicesResponse.results

# 인증서와 가상 서비스 매핑
$certificateVsMapping = @{}

foreach ($cert in $certificates) {
    $certName = $cert.name
    $certUuid = $cert.uuid
    $certificateVsMapping[$certName] = @()

    foreach ($vs in $virtualServices) {
        if ($vs.ssl_key_and_certificate_refs) {
            foreach ($certRef in $vs.ssl_key_and_certificate_refs) {
                if ($certRef -contains $certUuid) {
                    $certificateVsMapping[$certName] += $vs.name
                }
            }
        }
    }
}

# 결과 출력
foreach ($certName in $certificateVsMapping.Keys) {
    Write-Output "▶ 인증서 이름 : $certName"
    if ($certificateVsMapping[$certName].Count -gt 0) {
        Write-Output "이 인증서가 적용된 가상 서비스는 다음과 같습니다:"
        foreach ($vsName in $certificateVsMapping[$certName]) {
            Write-Output "    - $vsName"
        }
    } else {
        Write-Output "이 인증서를 사용하는 가상 서비스가 없습니다"
    }
    Write-Output "`n"
}
