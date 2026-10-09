# newPRAsystem 停止全部服务
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "正在停止 newPRAsystem 服务 ..."

Write-Host "[1/3] 停止应用服务（后端 / Vite 开发前端 / 模拟系统）..."
taskkill /FI "WINDOWTITLE eq newpra-backend*" /T /F | Out-Null
taskkill /FI "WINDOWTITLE eq newpra-web*" /T /F | Out-Null
taskkill /FI "WINDOWTITLE eq newpra-demo*" /T /F | Out-Null
Write-Host "       完成（若服务运行在其他独立窗口，请直接关闭窗口）"

Write-Host "[2/3] 停止 nginx 前端（生产发布 9080）..."
if (Test-Path "$root\nginx-1.28.0\nginx.exe") {
    & "$root\nginx-1.28.0\nginx.exe" -p "$root\nginx-1.28.0" -s stop
    if ($LASTEXITCODE -eq 0) { Write-Host "       nginx 已停止" } else { Write-Host "       nginx 未在运行或已停止" }
} else {
    Write-Host "       未找到 nginx-1.28.0，跳过"
}

Write-Host "[3/3] 停止 PostgreSQL（如安装了 pg17 便携版）..."
if (Test-Path "$root\pg17\bin\pg_ctl.exe") {
    & "$root\pg17\bin\pg_ctl.exe" -D "$root\pg17\data" stop -m fast
} else {
    Write-Host "       未安装（SQLite 模式），跳过"
}

Write-Host ""
Write-Host "全部服务已停止。"
Read-Host "按回车键退出"
