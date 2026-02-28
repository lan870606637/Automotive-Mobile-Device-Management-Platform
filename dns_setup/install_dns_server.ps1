# 以管理员身份运行此脚本，安装并配置 Windows DNS 服务器
# 适用于 Windows Server 或 Windows 10/11 专业版

# 检查是否以管理员身份运行
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "请以管理员身份运行此脚本！" -ForegroundColor Red
    pause
    exit
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    安装内网 DNS 服务器" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 获取服务器 IP
$serverIP = Read-Host "请输入本服务器的局域网 IP 地址 (例如: 192.168.1.100)"

# 安装 DNS 服务器功能
Write-Host "正在安装 DNS 服务器..." -ForegroundColor Yellow
Install-WindowsFeature -Name DNS -IncludeManagementTools

# 创建正向查找区域
Write-Host "正在创建 DNS 区域..." -ForegroundColor Yellow
Add-DnsServerPrimaryZone -Name "carbit.com.cn" -ZoneFile "carbit.com.cn.dns" -DynamicUpdate None

# 添加 A 记录
Write-Host "正在添加 DNS 记录..." -ForegroundColor Yellow
Add-DnsServerResourceRecordA -ZoneName "carbit.com.cn" -Name "device" -IPv4Address $serverIP
Add-DnsServerResourceRecordA -ZoneName "carbit.com.cn" -Name "admin.device" -IPv4Address $serverIP

# 配置转发器（用于访问外网）
Write-Host "正在配置 DNS 转发器..." -ForegroundColor Yellow
Set-DnsServerForwarder -IPAddress "8.8.8.8","114.114.114.114"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "    DNS 服务器安装完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "DNS 记录已创建：" -ForegroundColor Cyan
Write-Host "  device.carbit.com.cn       -> $serverIP" -ForegroundColor White
Write-Host "  admin.device.carbit.com.cn -> $serverIP" -ForegroundColor White
Write-Host ""
Write-Host "下一步：" -ForegroundColor Yellow
Write-Host "1. 在公司路由器或 DHCP 服务器中，将 DNS 服务器地址改为: $serverIP" -ForegroundColor White
Write-Host "2. 或者在每台电脑的网卡设置中手动设置 DNS 为: $serverIP" -ForegroundColor White
Write-Host ""
pause
