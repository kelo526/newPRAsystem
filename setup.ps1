# newPRAsystem 首次部署：依赖安装 + 数据库初始化
# 前置要求：Node.js 18+ / Python 3.11+ 已安装并加入 PATH
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "============================================"
Write-Host "  newPRAsystem 首次部署"
Write-Host "  前置要求：Node.js 18+ / Python 3.11+（已加入 PATH）"
Write-Host "============================================"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "未检测到 Node.js，请先安装" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "未检测到 Python，请先安装" }
Write-Host "[OK] 环境就绪：" (node --version) "/ " (python --version)
Write-Host ""

Write-Host "[1/6] 后端 Python 依赖 ..."
Set-Location "$root\server"
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

Write-Host "[2/6] Playwright Chromium（约 150MB，首次较慢）..."
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Chromium 下载失败" }

Set-Location $root
if (Test-Path "$root\pg17\bin\initdb.exe") {
    Write-Host "[3/6] PostgreSQL 数据目录初始化 ..."
    if (Test-Path "$root\pg17\data") {
        Write-Host "       数据目录已存在，跳过"
    } else {
        "newpra2026" | Out-File -Encoding ascii "$root\pg_pw.txt"
        & "$root\pg17\bin\initdb.exe" -D "$root\pg17\data" -U postgres -A password --pwfile="$root\pg_pw.txt" -E UTF8 --locale=C
        Remove-Item "$root\pg_pw.txt"
    }

    Write-Host "[4/6] 启动 PostgreSQL 并建库 ..."
    & "$root\pg17\bin\pg_ctl.exe" -D "$root\pg17\data" -l "$root\pg17\pg.log" start
    Start-Sleep -Seconds 3
    $env:PGPASSWORD = "newpra2026"
    & "$root\pg17\bin\psql.exe" -U postgres -h localhost -p 5433 -c "CREATE DATABASE newpra ENCODING 'UTF8';"
    Write-Host "       （库已存在时上面的报错可忽略）"
} else {
    Write-Host "[3/6] 未检测到 pg17\bin\initdb.exe —— PostgreSQL 便携版不随仓库分发，跳过数据库安装"
    Write-Host "[4/6] 默认使用 SQLite（server\newpra.db，零配置），首次启动自动建表"
    if (-not (Test-Path "$root\server\.env")) {
        Set-Content -Path "$root\server\.env" -Value "DATABASE_URL=sqlite:///./newpra.db" -Encoding ascii
        Write-Host "       已生成 server\.env（DATABASE_URL=sqlite:///./newpra.db）"
    }
    Write-Host "       如需 PostgreSQL：自行安装后在 server\.env 配置 DATABASE_URL=postgresql+psycopg2://<用户>:<密码>@<主机>:<端口>/<库名>"
}

Write-Host "[5/6] 前端依赖 ..."
Set-Location "$root\web"; npm install
Write-Host "       （demo-target 为可选的模拟业务系统，用于体验全流程）"
Set-Location "$root\demo-target"; npm install
Set-Location $root

Write-Host "[6/6] 构建前端生产产物（nginx 发布用）..."
Set-Location "$root\web"; npm run build
Set-Location $root

Write-Host ""
Write-Host "============================================"
Write-Host "  部署完成！双击 start.bat 启动："
Write-Host "    主入口（nginx）：http://localhost:9080"
Write-Host "    体验模拟流程：   start.bat dev"
Write-Host "============================================"
Read-Host "按回车键退出"
