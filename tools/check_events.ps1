$ErrorActionPreference = "SilentlyContinue"
Get-WinEvent -FilterHashtable @{LogName = "Application"; Id = 1000, 1026 } -MaxEvents 30 |
    Where-Object { $_.Message -match "WormGPT" } |
    Select-Object -First 4 |
    ForEach-Object {
        "===== $($_.TimeCreated) ====="
        $_.Message.Substring(0, [Math]::Min(900, $_.Message.Length))
        ""
    }