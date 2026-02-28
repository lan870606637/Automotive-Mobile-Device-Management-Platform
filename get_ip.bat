@echo off
chcp 65001 >nul
echo ==========================================
echo    车机设备管理系统 - 局域网访问信息
echo ==========================================
echo.
echo 本机IP地址:
ipconfig | findstr "IPv4"
echo.
echo ------------------------------------------
echo 局域网访问地址:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set ip=%%a
    set ip=!ip: =!
    echo   用户端:   http://!ip!:5000
    echo   管理后台: http://!ip!:5001
)
echo ------------------------------------------
echo.
echo 请使用上述 IP 地址在局域网内其他设备上访问
echo ==========================================
pause
