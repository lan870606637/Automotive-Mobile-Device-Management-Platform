@echo off
chcp 65001 >nul
echo ============================================
echo   设备管理系统 - 本地域名配置工具
echo ============================================
echo.
echo 此工具将配置本地域名映射：
echo   - device.carbit.com.cn       ^(用户端^)
echo   - admin.device.carbit.com.cn ^(管理后台^)
echo   - mobile.device.carbit.com.cn ^(手机端^)
echo.
echo ============================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 请以管理员身份运行此脚本！
    echo.
    echo 操作方法：
    echo 1. 右键点击此脚本文件
    echo 2. 选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

set "HOSTS_FILE=%SystemRoot%\System32\drivers\etc\hosts"
set "BACKUP_FILE=%SystemRoot%\System32\drivers\etc\hosts.backup.%date:~0,4%%date:~5,2%%date:~8,2%"

echo [1/4] 正在备份原始 hosts 文件...
copy "%HOSTS_FILE%" "%BACKUP_FILE%" >nul 2>&1
if %errorLevel% equ 0 (
    echo       备份成功: %BACKUP_FILE%
) else (
    echo       警告: 备份失败，继续执行...
)
echo.

echo [2/4] 正在检查现有域名配置...
findstr /C:"device.carbit.com.cn" "%HOSTS_FILE%" >nul 2>&1
if %errorLevel% equ 0 (
    echo       发现已存在的 device.carbit.com.cn 配置
    echo       正在更新...
    
    :: 删除旧的配置行
    type "%HOSTS_FILE%" | findstr /V /C:"device.carbit.com.cn" > "%TEMP%\hosts_temp.txt"
    move /Y "%TEMP%\hosts_temp.txt" "%HOSTS_FILE%" >nul 2>&1
)
echo       检查完成
echo.

echo [3/4] 正在添加域名映射...
echo. >> "%HOSTS_FILE%"
echo # 设备管理系统本地域名配置 >> "%HOSTS_FILE%"
echo 127.0.0.1       device.carbit.com.cn >> "%HOSTS_FILE%"
echo 127.0.0.1       admin.device.carbit.com.cn >> "%HOSTS_FILE%"
echo 127.0.0.1       mobile.device.carbit.com.cn >> "%HOSTS_FILE%"
echo       域名映射已添加
echo.

echo [4/4] 正在刷新 DNS 缓存...
ipconfig /flushdns >nul 2>&1
echo       DNS 缓存已刷新
echo.

echo ============================================
echo   配置完成！
echo ============================================
echo.
echo 现在您可以通过以下地址访问系统：
echo.
echo   用户端：   http://device.carbit.com.cn:5000
echo   管理后台： http://admin.device.carbit.com.cn:5001
echo   手机端：   http://mobile.device.carbit.com.cn:5002
echo.
echo 注意：请确保服务已启动（运行 start_services.py）
echo.
echo ============================================
echo.
pause
