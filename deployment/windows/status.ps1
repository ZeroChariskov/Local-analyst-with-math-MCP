$ErrorActionPreference = 'SilentlyContinue'
Write-Host 'Processes:'
Get-Process -Name llama-server,python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path
Write-Host ''
Write-Host 'Gateway:'
try { Invoke-RestMethod 'http://127.0.0.1:18080/health' | ConvertTo-Json -Depth 5 } catch { Write-Host 'Gateway is not responding.' }
