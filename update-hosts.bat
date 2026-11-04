@echo off
cd /d "%~dp0"
echo === Merging hosts sources ===
python merge_hosts.py
if errorlevel 1 goto err

echo.
echo === Applying to system hosts (UAC prompt will appear) ===
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%~dp0apply_hosts.ps1' -Wait"
if errorlevel 1 goto err

echo.
echo Done. Press any key to close.
pause >nul
exit /b 0

:err
echo.
echo Something failed - see messages above.
pause
exit /b 1
