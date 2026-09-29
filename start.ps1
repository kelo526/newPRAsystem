# newPRAsystem 一键启动（已在运行的服务自动跳过）
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Test-Port($p) {
    (Test-NetConnection -ComputerName localhost -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue)
}

Write-Host "============================================"
Write-Host "  newPRAsystem 一键启动"
Write-Host "============================================"

# [1/4] PostgreSQL（5433）——pg17\ 不存在（未随仓库分发）时跳过，后端自动使用 SQLite
if (-not (Test-Path "$root\pg17\bin\pg_ctl.exe")) {
    Write-Host "[1/4] PostgreSQL：未安装（pg17\ 不存在），后端使用 SQLite（server\newpra.db）"
} elseif (Test-Port 5433) {
    Write-Host "[1/4] PostgreSQL：已在运行"
} else {
    & "$root\pg17\bin\pg_ctl.exe" -D "$root\pg17\data" -l "$root\pg17\pg.log" start
    Start-Sleep -Seconds 2
    Write-Host "[1/4] PostgreSQL：已启动"
}

# [2/4] 后端（8000）
if (-not (Test-Port 8000)) {
    Start-Process cmd -ArgumentList "/k title newpra-backend & uvicorn main:app --port 8000" -WorkingDirectory "$root\server"
}
Write-Host "[2/4] 后端已就绪（http://localhost:8000）"

# [3/4] 模拟业务系统（5173）
if (-not (Test-Port 5173)) {
    Start-Process cmd -ArgumentList "/k title newpra-demo & npm run dev" -WorkingDirectory "$root\demo-target"
}
Write-Host "[3/4] 模拟业务系统已就绪（http://localhost:5173）"

# [4/4] 平台前端（5174）
if (-not (Test-Port 5174)) {
    Start-Process cmd -ArgumentList "/k title newpra-web & npm run dev" -WorkingDirectory "$root\web"
}
Write-Host "[4/4] 平台前端已就绪（http://localhost:5174）"

Write-Host ""
Write-Host "============================================"
Write-Host "  全部服务已启动（首次启动请等待 10~20 秒）"
Write-Host ""
Write-Host "  平台前端：     http://localhost:5174"
Write-Host "  模拟业务系统：  http://localhost:5173  （admin / admin123）"
Write-Host "  后端健康检查：  http://localhost:8000/api/health"
if (Test-Path "$root\pg17\bin\pg_ctl.exe") {
    Write-Host "  PostgreSQL：    localhost:5433 / 库 newpra"
} else {
    Write-Host "  数据库：        SQLite（server\newpra.db，零配置）"
}
Write-Host "============================================"
Write-Host ""
Write-Host "提示：停止服务请运行 stop.bat"
Read-Host "按回车键退出"
