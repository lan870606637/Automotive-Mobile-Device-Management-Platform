@echo off
chcp 65001 >nul
echo ============================================
echo   Device Management System - Startup Script (with Nginx)
echo ============================================
echo.

:: Check admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [Error] Please run as administrator!
    echo.
    echo Nginx requires port 80, which needs admin privileges.
    echo.
    pause
    exit /b 1
)

:: Set paths
set "NGINX_PATH=%~dp0nginx"
set "PROJECT_PATH=%~dp0"

echo [1/5] Checking Nginx...
if not exist "%NGINX_PATH%\nginx.exe" (
    echo [Error] Nginx not found!
    echo.
    echo Please download Nginx and extract to: %NGINX_PATH%
    echo Download: http://nginx.org/en/download.html
    echo.
    pause
    exit /b 1
)
echo       Nginx found
echo.

echo [2/5] Checking hosts file...
findstr /C:"device.carbit.com.cn" "C:\Windows\System32\drivers\etc\hosts" >nul 2>&1
if %errorLevel% neq 0 (
    echo [Warning] Domain not configured, configuring now...
    call "%PROJECT_PATH%\setup_domains.bat"
)
echo       Domain configured
echo.

echo [3/6] Starting User Service (port 5000)...
start "User Service" cmd /c "cd /d "%PROJECT_PATH%" && python user_service\app.py"
timeout /t 3 /nobreak >nul
echo       User Service started
echo.

echo [4/6] Starting Admin Service (port 5001)...
start "Admin Service" cmd /c "cd /d "%PROJECT_PATH%" && python admin_service\app.py"
timeout /t 3 /nobreak >nul
echo       Admin Service started
echo.

echo [5/6] Starting Mobile Service (port 5002)...
start "Mobile Service" cmd /c "cd /d "%PROJECT_PATH%" && python mobile_service\app.py"
timeout /t 3 /nobreak >nul
echo       Mobile Service started
echo.

echo [6/6] Starting Nginx (port 80)...
cd /d "%NGINX_PATH%"
start "Nginx" nginx.exe
timeout /t 2 /nobreak >nul

:: Verify Nginx started
tasklist | findstr "nginx.exe" >nul
if %errorLevel% equ 0 (
    echo       Nginx started successfully
) else (
    echo [Error] Nginx failed to start!
    echo Please check nginx/logs/error.log for details.
    pause
)
echo.

echo ============================================
echo   All services started!
echo ============================================
echo.
echo Access URLs (no port needed):
echo   User:     http://device.carbit.com.cn
echo   Admin:    http://admin.device.carbit.com.cn
echo   Mobile:   http://mobile.device.carbit.com.cn
echo.
echo Local URLs (with port):
echo   User:     http://127.0.0.1:5000
echo   Admin:    http://127.0.0.1:5001
echo   Mobile:   http://127.0.0.1:5002
echo.
echo --------------------------------------------
echo To stop services:
echo   1. Close this window
echo   2. Or run: taskkill /f /im nginx.exe
echo --------------------------------------------
echo.
pause

:: Cleanup on exit
taskkill /f /im nginx.exe >nul 2>&1
