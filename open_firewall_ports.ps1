# 以管理员身份运行此脚本，开放防火墙端口
# 用户服务端口
New-NetFirewallRule -DisplayName "Device Management User Service" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
# 管理服务端口
New-NetFirewallRule -DisplayName "Device Management Admin Service" -Direction Inbound -Protocol TCP -LocalPort 5001 -Action Allow
# 手机端服务端口
New-NetFirewallRule -DisplayName "Device Management Mobile Service" -Direction Inbound -Protocol TCP -LocalPort 5002 -Action Allow

Write-Host "防火墙规则已添加！"
Write-Host "端口 5000 (用户服务)、5001 (管理服务) 和 5002 (手机端服务) 已开放"
