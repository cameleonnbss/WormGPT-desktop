$ErrorActionPreference = "SilentlyContinue"

Write-Output '=== Session info ==='
Write-Output ('This shell PID ' + $PID + ' SessionId=' + (Get-Process -Id $PID).SessionId)
Write-Output 'Active console sessions:'
query session 2>$null | Out-String | Write-Output

Write-Output '=== Minimal Tk window visibility (started from this shell) ==='
$p = Start-Process -FilePath 'C:\Users\caméléon\Desktop\WormGPT\.venv\Scripts\python.exe' `
    -ArgumentList 'C:\Users\caméléon\Desktop\WormGPT\tools\min_tk_test.py' -PassThru
Start-Sleep -Seconds 6
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinEnum {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
}
"@
$proc = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output 'test process died' } else {
    Write-Output ('test pid=' + $p.Id + ' session=' + $proc.SessionId)
    $list = New-Object System.Collections.ArrayList
    $cb = [WinEnum+EnumProc]{ param($h, $l)
        $wpid = 0
        [WinEnum]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null
        if ($wpid -eq $p.Id) {
            $sb = New-Object System.Text.StringBuilder 200
            [WinEnum]::GetWindowText($h, $sb, 200) | Out-Null
            $vis = [WinEnum]::IsWindowVisible($h)
            [void]$list.Add("hwnd=$h visible=$vis title='$($sb.ToString())'")
        }
        return $true
    }
    [WinEnum]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
    $list | ForEach-Object { Write-Output $_ }
}
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue