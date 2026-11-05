# auto_refresh.ps1 - full self-healing cycle, designed for a Windows scheduled
# task with highest privileges (no UAC prompt per run):
#   1. regenerate Spotify fix (functional probe of GeoHide servers, RU vantage)
#   2. regenerate GeoHide block (live servers only, RU vantage)
#   3. merge all sources -> hosts
#   4. apply to system hosts (backup + DNS flush)
#   5. sync everything to GitHub (repo hosts = local hosts)
#   6. write last_status.txt (health snapshot for quick diagnostics)
$ErrorActionPreference = "Continue"
Set-Location "C:\Users\koski\ZCodeProject\hosts-merger"

python -I make_spotify.py;  $spotify = $LASTEXITCODE
python -I make_geohide.py;  $geohide = $LASTEXITCODE
python -I merge_hosts.py;   $merge   = $LASTEXITCODE

$applied = "skip"
$synced  = "skip"
if (Test-Path ".\hosts") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\apply_hosts.ps1
    if ($LASTEXITCODE -eq 0) { $applied = "OK" } else { $applied = "FAIL($LASTEXITCODE)" }
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\read_gh_cred.ps1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $synced = "OK" } else { $synced = "FAIL($LASTEXITCODE)" }
} else {
    Write-Host "merge failed - nothing applied or uploaded"
}

$status = @(
    ("time       : " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    ("spotify    : " + $(if ($spotify -eq 0) { "OK" } else { "kept previous file (exit $spotify)" })),
    ("geohide    : " + $(if ($geohide -eq 0) { "OK" } else { "kept previous file (exit $geohide)" })),
    ("merge      : " + $(if ($merge -eq 0) { "OK" } else { "FAIL" })),
    ("systemapply: " + $applied),
    ("githubsync : " + $synced),
    ("hosts mtime: " + $(if (Test-Path ".\hosts") { (Get-Item ".\hosts").LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "none" }))
) -join "`r`n"
$status | Set-Content -Path "last_status.txt" -Encoding UTF8
Write-Host $status
