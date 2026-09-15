$ErrorActionPreference = "SilentlyContinue"
$exe = Join-Path $env:USERPROFILE 'Desktop\WormGPT\dist\WormGPT.exe'

Write-Output '=== 1. Exe present? ==='
if (Test-Path $exe) {
    $item = Get-Item $exe
    Write-Output ('Name=' + $item.Name + ' Size=' + $item.Length + ' Modified=' + $item.LastWriteTime)
} else {
    Write-Output ('EXE MISSING: ' + $exe)
}

Write-Output '=== 2. Launch + real window state ==='
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 10
$procs = Get-Process -Name 'WormGPT' -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($pr in $procs) {
        Write-Output ('PID ' + $pr.Id + '  MainWindowHandle=' + $pr.MainWindowHandle + "  Title='" + $pr.MainWindowTitle + "'  Responding=" + $pr.Responding)
    }
} else {
    Write-Output 'NO PROCESS - died immediately'
}
Stop-Process -Name 'WormGPT' -Force -ErrorAction SilentlyContinue

Write-Output ''
Write-Output '=== 3. Defender threat detections (WormGPT) ==='
Get-MpThreatDetection -ErrorAction SilentlyContinue |
    Where-Object { $_.Resources -match 'WormGPT' } |
    Select-Object -First 3 |
    ForEach-Object {
        Write-Output ('ThreatID=' + $_.ThreatID + ' Time=' + $_.InitialDetectionTime + ' Res=' + $_.Resources)
    }

Write-Output '=== 4. Recent Application error events ==='
Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000 } -MaxEvents 25 |
    Where-Object { $_.Message -match 'WormGPT' } |
    Select-Object -First 2 |
    ForEach-Object {
        Write-Output ('--- ' + $_.TimeCreated + ' ---')
        $_.Message.Substring(0, [Math]::Min(700, $_.Message.Length))
    }