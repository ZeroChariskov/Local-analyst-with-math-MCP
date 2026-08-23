$ErrorActionPreference = 'Stop'
$names = @('llama-server', 'python')
foreach ($name in $names) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        if ($name -eq 'python' -and $_.Path -and $_.Path -notlike '*TitanLocalAI*') { return }
        Write-Host "Stopping $($_.ProcessName) PID $($_.Id)"
        Stop-Process -Id $_.Id -Force
    }
}
Write-Host 'Titan Local AI processes stopped.'
