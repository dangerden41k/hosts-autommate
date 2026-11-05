# auto_refresh.ps1 - full self-healing cycle, designed for a Windows scheduled
# task with highest privileges (no UAC prompt per run):
#   1. regenerate Spotify fix (functional probe of GeoHide servers, RU vantage)
#   2. regenerate GeoHide block (live servers only, RU vantage)
#   3. merge all sources -> hosts
#   4. apply to system hosts (backup + DNS flush)
#   5. sync everything to GitHub (repo hosts = local hosts)
$ErrorActionPreference = "Continue"
Set-Location "C:\Users\koski\ZCodeProject\hosts-merger"

python -I make_spotify.py
python -I make_geohide.py
python -I merge_hosts.py
if (Test-Path ".\hosts") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\apply_hosts.ps1
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\read_gh_cred.ps1
} else {
    Write-Host "merge failed - nothing applied or uploaded"
}
