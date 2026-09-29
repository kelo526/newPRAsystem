# newPRAsystem 停止全部服务
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "正在停止 newPRAsystem 服务 ..."

Write-Host "[1/2] 停止应用服务（后端 / demo-target / 前端）..."
taskkill /FI "WINDOWTITLE eq newpra-backend*" /T /F | Out-Null
taskkill /FI "WINDOWTITLE eq newpra-demo*" /T /F | Out-Null
taskkill /FI "WINDOWTITLE eq newpra-web*" /T /F | Out-Null
Write-Host "       完成（若服务运行在其他独立窗口，请直接关闭窗口）"

Write-Host "[2/2] 停止 PostgreSQL ..."
& "$root\pg17\bin\pg_ctl.exe" -D "$root\pg17\data" stop -m fast

Write-Host ""
Write-Host "全部服务已停止。"
Read-Host "按回车键退出"
