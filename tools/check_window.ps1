$ErrorActionPreference = "SilentlyContinue"
param([string]$File, [string]$Name)

$p = Start-Process -FilePath $File -PassThru
Start-Sleep -Seconds 12
$procs = Get-Process -Name $Name -ErrorAction SilentlyContinue
if ($procs) {
    $shown = 0
    foreach ($pr in $procs) {
        Write-Output ('PID ' + $pr.Id + '  Handle=' + $pr.MainWindowHandle + "  Title='" + $pr.MainWindowTitle + "'")
        if ($pr.MainWindowHandle -ne 0) { $shown++ }
    }
    Write-Output ('WINDOWS_SHOWN=' + $shown + ' / ' + $procs.Count)
} else {
    Write-Output 'NO PROCESS'
}
Stop-Process -Name $Name -Force -ErrorAction SilentlyContinue