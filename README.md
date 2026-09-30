<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="newPRAsystem：业务网页 → 可配置、可复用、可定时运行的机器人任务">
</p>

**一个将企业业务网页自动转化为可配置、可复用、可定时运行的机器人任务的平台。**

业务人员在平台登记目标系统后，平台自动解析网页中的筛选字段与可执行动作，生成可视化任务配置界面；用户像填表单一样配置业务条件，即可创建长期定时运行的自动化任务——**调整业务条件只需改配置，无需重录流程或改代码**。

## 为什么不用录屏 / 传统 RPA

录屏类自动化把操作步骤固化成脚本：网页一改版脚本就失效，改一个查询条件也要整段重录。newPRAsystem 把「执行能力」与「业务意图」分开存：系统解析网页得到字段与动作（能力），任务只保存业务条件（意图）。执行时按语义现场匹配定位元素，网页改版后**更新页面档案**即可自愈，老任务不受影响；条件变化只改配置。

## 快速开始

**前置要求**：Python 3.11+（含 pip）、Node.js 18+（含 npm）。首次部署需下载 Playwright Chromium（约 150MB）。
**数据库零配置**：默认 SQLite（`server/newpra.db`），不装任何数据库即可跑通全部功能；PostgreSQL 为可选升级，两种模式表结构兼容、随时互切。

**1 · 安装依赖**

```bash
# Windows（cmd 或 PowerShell）
cd server && pip install -r requirements.txt && python -m playwright install chromium && cd ..
cd web && npm install && cd ..
cd demo-target && npm install && cd ..

# Linux / macOS
cd server && python3 -m pip install -r requirements.txt && python3 -m playwright install chromium && cd ..
cd web && npm install && cd ..
cd demo-target && npm install && cd ..
```

**2 · 启动服务**（开 3 个终端分别执行）

```bash
# 终端 1 · 后端（SQLite 模式：首次启动自动建表、自动生成凭证加密密钥）
cd server
python -m uvicorn main:app --port 8000        # Windows
python3 -m uvicorn main:app --port 8000      # Linux / macOS

# 终端 2 · 平台前端
cd web && npm run dev          # → http://localhost:5174

# 终端 3 · 模拟业务系统（「三分钟上手」的目标站点）
cd demo-target && npm run dev  # → http://localhost:5173
```

**3 · 验证**：http://localhost:8000/api/health 返回 `{"status": "ok"}`，打开 http://localhost:5174 进入平台即成功。

### 常见问题

| 现象 | 处理 |
| --- | --- |
| Windows 输入 `python` 弹出 Microsoft Store | 用 `py -3` 代替 `python` |
| Linux 报 `externally-managed-environment` | `python3 -m venv .venv && source .venv/bin/activate` 后再安装 |
| Playwright Chromium 下载慢 | Windows：`set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/`；Linux/macOS 用 `export` 同名变量后重试 |
| pip / npm 下载慢（国内网络） | pip 追加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`；npm 用 `npm config set registry https://registry.npmmirror.com` |

### Windows 一键脚本（可选）

仓库另提供 PowerShell 脚本，与上面手动命令完全等价：

| 命令 | 作用 |
|---|---|
| `powershell -ExecutionPolicy Bypass -File setup.ps1` | 首次部署：装依赖 + Chromium；无 `pg17\` 时自动生成 `server\.env`（SQLite 模式） |
| `powershell -ExecutionPolicy Bypass -File start.ps1` | 一键启动全部服务（已在运行的自动跳过） |
| `powershell -ExecutionPolicy Bypass -File stop.ps1` | 一键停止全部服务 |

### 用 PostgreSQL（可选升级）

- **已有 PostgreSQL**：在 `server/.env` 写 `DATABASE_URL=postgresql+psycopg2://<用户>:<密码>@<主机>:<端口>/<库名>`，重启后端即自动建表
- **便携版（Windows）**：EDB PostgreSQL 17 zip 解压为 `pg17\`，`setup.ps1` 自动完成 initdb、建库 `newpra`（端口 5433）并启动

### 服务地址

| 服务 | 地址 | 说明 |
|---|---|---|
| **平台前端** | http://localhost:5174 | 主入口 |
| 模拟业务系统 | http://localhost:5173 | 登录 admin / admin123，用于体验全流程 |
| 后端 API | http://localhost:8000/api/health | 健康检查 |
| PostgreSQL | localhost:5433 / 库 `newpra` | 仅 PostgreSQL 模式；SQLite 模式为 `server/newpra.db` |

## 三分钟上手（用模拟系统走通全流程）

1. **目标系统** → 新建系统：登录页 URL 填 `http://localhost:5173/login`，账号 `admin` / 密码 `admin123`
2. **接入向导** → 选系统、目标 URL 填 `http://localhost:5173/report` → 开始解析 → 确认字段
3. **任务管理** → 新建任务 → 像填表单一样选条件（日期预设 / 区域多选 / 状态）→ 选动作「导出 Excel」→ 勾选前置动作「查询」→ 选运行频率 → 创建
4. 任务列表 → **立即运行** → 详情页看运行历史、下载导出的 CSV
5. 进阶体验：任务**编辑配置**（改条件直接重跑）、**创建副本**、**更新页面档案**（网页改版后重新解析纳入新字段）、**导出任务包**（生成自包含脚本，可交任意调度平台执行）

## 核心能力

| 能力 | 说明 |
|---|---|
| 网页字段自动发现 | 支持 Ant Design / Element UI / Element Plus / OrangeHRM(oxd) / 原生表单；下拉选项交互式抓取 |
| 自动生成配置面板 | 按档案字段类型动态渲染表单（日期预设 / 多选 / 下拉 / 文本） |
| 配置驱动回放 | 任务只存业务配置不固化 selector，执行时现场语义匹配定位，网页改版可自愈 |
| 档案更新 | 网页新增筛选项 → 重新解析 → diff 确认纳入，老任务不受影响（版本化） |
| 定时调度 | cron 表达式，预设 + 自定义；平台内托管执行 |
| 结果通知 | 邮件 / 飞书群机器人 webhook |
| 任务导出 | zip 任务包（自包含脚本 + 外部 `task_config.json`），脚本仅依赖 playwright；账号密码与输出目录在配置文件中调整，交任意调度平台运行无需改脚本 |
| 登录会话复用 | storage_state 按系统持久化，失效自动重登 |
| 凭证安全 | Fernet 对称加密存储，密钥首次启动自动生成（`server/.env`，请勿提交到版本库） |

## 目录结构

```
newPRAsystem/
├─ setup.ps1 / start.ps1 / stop.ps1   # Windows 一键部署 / 启动 / 停止（可选，与 README 手动命令等价）
├─ demo-target/     # 模拟业务系统（React + AntD 5，含登录/报表/导出）
├─ server/          # 后端（FastAPI + SQLAlchemy + 解析/回放引擎 + 调度）
│   └─ .env.example # 环境变量模板（数据库 / GLM / SMTP，均为可选项）
├─ web/             # 平台前端（React + AntD 5）
├─ pg17/            # PostgreSQL 17 便携版（不入库；自行放置或已装 PG，见方式 B）
└─ docs/            # 文档
   ├─ HANDOVER.md       # 交接文档（架构 / 数据库 / API / 运维）
   └─ PROJECT_GUIDE.md  # 项目说明（产品 / 使用指南 / 能力边界）
```

## 可选增强（不配置自动降级，功能不受阻）

| 配置 | 作用 |
|---|---|
| `ZHIPUAI_API_KEY` | GLM 对网页字段做语义化命名（识别「统计月份」→ 日期范围控件），无 Key 降级为规则命名 |
| `SMTP_*` | 任务完成/失败邮件通知 |
| 飞书 webhook | 任务结果推送飞书群机器人 |

## 文档索引

- **交接文档**（[docs/HANDOVER.md](docs/HANDOVER.md)）：系统架构、数据库设计、核心机制实现、API 清单、运维手册、已知问题——**面向接手开发的工程师**
- **项目说明**（[docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)）：产品定位、能力地图、操作指南、真实系统实测结论、里程碑——**面向使用与评估者**

## 技术栈

React 18 + Ant Design 5 / FastAPI + SQLAlchemy 2 + APScheduler / Playwright (Python) / SQLite（默认）→ PostgreSQL 17 / GLM API（可选，字段语义化）
