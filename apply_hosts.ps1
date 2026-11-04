# Applies the merged hosts file into the Windows system hosts file.
# Requires Administrator (writes to C:\Windows\System32\drivers\etc\hosts).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File apply_hosts.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File apply_hosts.ps1 -MergedPath C:\path\hosts
#   powershell -NoProfile -ExecutionPolicy Bypass -File apply_hosts.ps1 -Replace  (wipe old content)
param([string]$MergedPath, [switch]$Replace)

$ErrorActionPreference = "Stop"
if (-not $MergedPath) { $MergedPath = Join-Path $PSScriptRoot "hosts" }

$HostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$Begin = "# >>> hosts-merger >>>"
$End   = "# <<< hosts-merger <<<"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Administrator required. Right-click update-hosts.bat -> Run as administrator."
    exit 1
}
if (-not (Test-Path $MergedPath)) {
    Write-Error "Merged file not found: $MergedPath (run merge_hosts.py first)"
    exit 1
}

# CRLF-normalized merged block, no trailing blank line
$merged = ([IO.File]::ReadAllLines($MergedPath) -join "`r`n") + "`r`n"

if ($Replace) {
    # wipe everything: clean file = header only, merged block added below
    Write-Host "REPLACE mode: old hosts content will be discarded (backup kept)."
    $current = "# Windows hosts file, maintained by hosts-merger`r`n"
} else {
    $current = [IO.File]::ReadAllText($HostsPath)
}

# remove previous injected block if present (idempotent re-runs)
$s = $current.IndexOf($Begin)
$e = $current.IndexOf($End)
if ($s -ge 0 -and $e -gt $s) {
    $current = $current.Remove($s, $e - $s + $End.Length)
}

# backup before writing
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item $HostsPath "$HostsPath.bak.$stamp"
# keep only the 5 newest backups
Get-ChildItem "$HostsPath.bak.*" | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 5 | ForEach-Object { Remove-Item $_.FullName -Force }

$new = $current.TrimEnd() + "`r`n`r`n" + $Begin + "`r`n" + $merged + $End + "`r`n"

# hosts must be UTF-8 WITHOUT BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($HostsPath, $new, $utf8NoBom)

ipconfig /flushdns | Out-Null
Write-Host "OK: system hosts updated (backup: hosts.bak.$stamp), DNS cache flushed."
