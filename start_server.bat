@echo off
rem EczemaRecipe launcher: Docker compose stack + Cloudflare tunnel
rem Remote URL: https://eczemarecipe.paulli09.xyz   Local: http://localhost:3000
rem Close the "EczemaRecipe Tunnel" window to stop the tunnel;
rem close this window to exit (docker containers keep running).

cd /d "%~dp0"

rem --- 1. Docker Desktop must be running ---
docker info >nul 2>&1
if not errorlevel 1 goto stack

echo Starting Docker Desktop ...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
set tries=0

:waitdocker
ping -n 6 127.0.0.1 >nul
docker info >nul 2>&1
if not errorlevel 1 goto stack
set /a tries+=1
if %tries% lss 36 goto waitdocker
echo ERROR: Docker Desktop did not become ready in 3 minutes.
pause
exit /b 1

:stack
rem --- 2. Bring up the stack (prod) ---
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

rem --- 3. Cloudflare tunnel: start only if not already running ---
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter 'Name=''cloudflared.exe''' | Where-Object { $_.CommandLine -match 'tunnel run' }) { exit 0 } else { exit 1 }"
if errorlevel 1 goto starttunnel
echo Cloudflare tunnel already running - skipping (no double tunnel).
goto done

:starttunnel
start "EczemaRecipe Tunnel" /min "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run pockettcm
echo Cloudflare tunnel started.

:done
echo.
echo EczemaRecipe stack is up: https://eczemarecipe.paulli09.xyz
pause
