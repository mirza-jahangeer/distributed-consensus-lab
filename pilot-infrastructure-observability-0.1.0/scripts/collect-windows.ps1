param([string]$Endpoint = 'http://127.0.0.1:5080', [int]$IntervalSeconds = 15, [switch]$Once)
$ErrorActionPreference = 'Stop'
if ($IntervalSeconds -lt 5) { throw 'Interval must be at least 5 seconds' }
if (!$env:PILOT_API_KEY) { throw 'Set PILOT_API_KEY first' }
$uri = [Uri]$Endpoint
if ($uri.Scheme -ne 'https' -and !$uri.IsLoopback) { throw 'Remote collection requires HTTPS' }
# MachineGuid distinguishes hosts even when their display names change.
$machineId = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid
$os = Get-CimInstance Win32_OperatingSystem
while ($true) {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"
        $metrics = @{ memoryPercent = [math]::Round((1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize) * 100, 2) }
        if ($null -ne $cpu) { $metrics.cpuPercent = [double]$cpu }
        if ($disk.Size -gt 0) { $metrics.diskPercent = [math]::Round((1 - $disk.FreeSpace / $disk.Size) * 100, 2) }
        $payload = @{ schemaVersion = 1; id = [guid]::NewGuid().ToString('N'); machineId = $machineId; name = $env:COMPUTERNAME; os = $os.Caption; observedAt = [DateTimeOffset]::UtcNow.ToString('o'); metrics = $metrics } | ConvertTo-Json
        Invoke-RestMethod -Uri "$($Endpoint.TrimEnd('/'))/api/v1/observations" -Method Post -Headers @{ 'X-Pilot-Key' = $env:PILOT_API_KEY } -ContentType 'application/json' -Body $payload -TimeoutSec 10 | Out-Host
    } catch { if ($Once) { throw }; Write-Warning $_.Exception.Message }
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSeconds
}
