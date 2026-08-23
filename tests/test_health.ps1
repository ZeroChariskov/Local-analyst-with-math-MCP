param(
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [string]$ApiKey = $env:TITAN_API_KEY
)
$ErrorActionPreference = 'Stop'
Invoke-RestMethod -Uri "$BaseUrl/health"
Invoke-RestMethod -Uri "$BaseUrl/status" -Headers @{ Authorization = "Bearer $ApiKey" }
Invoke-RestMethod -Uri "$BaseUrl/v1/models" -Headers @{ Authorization = "Bearer $ApiKey" }
