@echo off
chcp 65001 >nul
echo ==========================================
echo    启动 DNS 服务器 (Docker)
echo ==========================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Docker，请先安装 Docker Desktop
    pause
    exit /b 1
)

REM 获取本机 IP 地址
echo 正在获取本机 IP 地址...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4" ^| findstr /V "192.168.56" ^| head -1') do (
    set IP=%%a
    set IP=!IP: =!
)

if "!IP!"=="" (
    set /p IP="请输入本机 IP 地址: "
)

echo 检测到 IP 地址: %IP%
echo.

REM 更新配置文件中的 IP 地址
powershell -Command "(Get-Content dnsmasq.conf) -replace '192.168.1.100', '%IP%' | Set-Content dnsmasq.conf"

echo 正在启动 DNS 服务器...
docker-compose down 2>nul
docker-compose up -d

echo.
echo ==========================================
echo    DNS 服务器已启动！
echo ==========================================
echo.
echo 管理界面: http://localhost:5380
echo 用户名: admin
echo 密码: admin123
echo.
echo DNS 服务器地址: %IP%
echo.
echo 请将公司设备的 DNS 设置为: %IP%
echo.
pause
