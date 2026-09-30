# newPRAsystem 交接文档

面向接手本项目的工程师。覆盖架构、数据模型、核心机制实现、API、运维与已知问题。

---

## 1. 系统架构

```
┌─ web/ (:5174)              平台前端 React + AntD 5
│    接入向导 / 字段确认 / 任务配置 / 运行历史
│
├─ server/ (:8000)           后端 FastAPI
│    ├─ app/                 平台层：API、调度、桥接、通知、导出
│    └─ engine/              引擎层（M0 起独立，可脱离平台 CLI 运行）
│         ├─ parser/         解析管线：登录→DOM提取→规则识别→LLM语义化→PageProfile
│         └─ executor/      回放引擎：语义定位→组件适配→动作→产物捕获
│
├─ demo-target/ (:5173)      模拟业务系统（React + AntD 5）
├─ pg17/ (:5433)             PostgreSQL 17 便携版，库 newpra
└─ 外部依赖                   GLM API（可选）、SMTP（可选）、飞书 webhook（可选）
```

**数据流**：登记系统 → 发起解析（后台线程）→ `PageProfile` 入库 → 前端字段确认 → 建 `Task`（cron 同步进 APScheduler）→ 手动/定时触发 → 回放引擎执行 → `TaskRun` + artifacts 落盘 → 通知。

**两条执行通道**：
- 平台内托管：`runner_bridge` 起 daemon 线程调 `engine.executor.runner.run`
- 导出脚本：`app/exporter.py` 生成自包含 Python 脚本（内嵌任务 JSON + 档案 + 精简引擎），脱离平台运行

## 2. 目录与关键文件

```
server/
├─ main.py                     FastAPI 入口（lifespan 里 init_db + 调度恢复）
├─ app/
│  ├─ config.py / db.py        环境加载 / SQLAlchemy 引擎与会话
│  ├─ models.py                5 张核心表（见 §3）
│  ├─ schemas.py               Pydantic API 模型
│  ├─ api.py                   全部路由（见 §5）
│  ├─ runner_bridge.py         解析/执行的后台线程桥 + 会话文件管理
│  ├─ scheduler.py             APScheduler 封装（任务增删改即同步 cron）
│  ├─ notify.py                邮件 / 飞书通知
│  ├─ exporter.py              任务导出器（占位符模板生成脚本）
│  └─ crypto.py                Fernet 凭证加解密（密钥自动生成写入 .env）
├─ engine/
│  ├─ parser/
│  │  ├─ browser.py            登录候选链 + 会话复用 + 页面就绪等待
│  │  ├─ dom_extract.py        EXTRACT_JS（四套组件规则 + 交互式选项抓取）
│  │  ├─ rules.py              类型归一与去噪、动作类型猜测
│  │  ├─ llm_semantic.py       GLM 语义化（无 key 自动降级规则命名）
│  │  └─ __main__.py           解析 CLI
│  └─ executor/
│     ├─ matcher.py            定位优先级：selector → label 自愈 → 文本
│     ├─ adapters.py           9 个组件适配器（AntD/El/Oxd/Native）
│     ├─ runner.py             回放主流程（含日期预设解析）
│     └─ __main__.py           回放 CLI
├─ profiles/  tasks/  artifacts/   CLI 时代的档案/任务样例与运行产物
├─ sessions/                   登录态 storage_state（system_<id>.json）
├─ smoke_test.py / smoke_test_m2.py   API 冒烟测试
└─ migrate_to_pg.py            SQLite→PG 一次性迁移脚本
```

## 3. 数据库设计（PostgreSQL，库 newpra）

| 表 | 字段要点 | 说明 |
|---|---|---|
| `target_systems` | name, login_url, username, **password_enc**(Fernet), 三个可选 selector | 目标系统与凭证 |
| `parse_requests` | system_id, target_url, status, error, **profile_id**(可空) | 解析请求；profile_id 非空 = 档案更新（reparse） |
| `page_profiles` | system_id, target_url, **version**, fields/actions/tables(JSON), confirmed | 页面档案；JSON 结构见下 |
| `tasks` | name, profile_id, config(JSON), pre_actions(JSON), action, schedule(JSON), delivery(JSON), enabled | 任务只存业务配置，**不含 selector** |
| `task_runs` | task_id, status, trigger(manual/scheduled), steps/artifacts(JSON), error | 运行记录 |

**PageProfile.fields 单字段结构**（解析产物，前端确认可编辑）：

```json
{
  "key": "f_antd_1", "label": "区域", "semantic_name": "区域",
  "type": "multi_select", "options": ["华东", "..."],
  "included": true, "is_new": false,
  "locator": { "component": "antd_select", "selector": "...", "labels": ["区域"] }
}
```

字段类型：`date_range / select / multi_select / text / textarea / upload / radio / checkbox`；动作 kind：`query / reset / export / upload / submit / other`。

## 4. 核心机制（本项目的技术脊柱）

### 4.1 配置驱动回放
任务不固化 selector。每次执行时：打开页面 → `matcher.field_selector` 先用档案 selector，失效则按 `.ant-form-item` label 自愈；按钮优先文本定位（`button:has-text`），其次 cssPath。这是"网页改版不重录"的实现基础。

### 4.2 相对日期预设
`config` 中日期值可为 `{"preset": "last_week"}`，执行时由 `runner.preset_range()` 解析为绝对区间——周期任务的关键设计，否则每周要改日期。

### 4.3 档案更新合并（reparse）
`runner_bridge._merge_profile`：新旧字段按（网页标签+类型）匹配，命中则保留用户确认的 semantic_name 与 included；未命中的新字段标 `is_new=true, included=false`，等前端差异确认；removed 计入 `profile.meta.last_reparse`。version 自增。

### 4.4 登录候选链与会话复用
- `browser.py` 的 USERNAME/PASSWORD/SUBMIT_CANDIDATES：中英文 placeholder、name 属性、autocomplete、type=email 依次探测，登录按钮同理。用户可在系统配置显式指定 selector 覆盖。
- 会话复用：`open_logged_in_page(state_file=...)` 先用 storage_state 直接访问目标页，被重定向回登录页（`_redirected_to_login`）视为失效自动重登并回写。会话文件在 `server/sessions/system_<id>.json`。
- **人工会话导入（M7）**：验证码类系统无法自动登录时，业务人员在本地浏览器登录后，通过 `PUT /api/systems/{id}/session`（Systems 页「导入会话」）粘贴 Playwright storage_state JSON，写入同一会话文件即可免登录；两步式门户可用系统配置 `pre_clicks` 前置点击。
- 登录失败时会抓取页面错误 toast（`_grab_login_error`）拼进报错。

### 4.5 解析规则（EXTRACT_JS 要点）
- 四套组件规则：`.ant-form-item` / `.el-form-item` + 独立 Element 组件（filter-container 场景）/ `.oxd-input-group`（OrangeHRM）/ 原生表单
- 三层去噪：`visible()`（display:none 祖先过滤隐藏弹窗）、`inChrome()`（页头/侧栏/页脚排除）、表格行内按钮排除
- cssPath 每层带 `nth-of-type` 保证唯一（F1 教训：同构表单生成相同 selector 导致选项串扰）
- 下拉选项交互式抓取（浮层在 body 末尾，需点击后抓取再 Escape）

### 4.6 任务导出器
`exporter.py` 导出 **zip 任务包**：`newpra_task_<任务名>.py`（自包含脚本，不含凭证）+ `task_config.json`（外部配置：username / password / output_dir）。
- 员工在自己的调度平台（小龙虾）上只改配置文件即可，无需动脚本；密码预填与否由导出参数 `embed_credentials` 控制（默认预填，false 则留空自行填写）
- 脚本启动时读同目录 task_config.json：文件缺失自动生成模板并退出提示；读取用 `utf-8-sig`（兼容记事本保存的 BOM）
- 实现注意：模板用 `__PLACEHOLDER__` + str.replace 生成（**不要用 str.format**，模板内大量花括号）；任务/档案 JSON 以 `json.loads(r"""...""")` 内嵌（JSON 的 false/null 不能直接出现在 Python 字面量）；适配器类必须有 `component` 类属性。

### 4.7 SSE 实时事件流（M7）
`app/events.py` 进程内事件总线：后台执行线程 `events.publish_run(task_id, run_id, status)` → 各订阅者 `queue.Queue`；`GET /api/events` 以 `asyncio.to_thread` 桥接到 StreamingResponse（15s 心跳保活，慢客户端队列满即丢弃——前端有轮询兜底）。前端 TaskDetail/Tasks 用 EventSource 订阅 `run` 事件即时刷新；TaskDetail 另保留 8s 慢轮询兜底。

## 5. API 清单（前缀 /api）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST/GET | `/systems` | 建系统（凭证加密）/ 列表 |
| PUT/DELETE | `/systems/{id}` | 编辑（密码留空不改）/ 删除 |
| PUT | `/systems/{id}/session` | **人工会话导入**（粘贴 storage_state，验证码类系统免登录） |
| GET | `/events` | **SSE 事件流**（run 事件：running/retrying/succeeded/failed + 心跳） |
| POST | `/parse-requests` | 发起解析（后台线程，轮询获取结果） |
| GET | `/parse-requests/{id}` | 状态：running/succeeded/failed |
| GET | `/profiles`、`/profiles/{id}` | 档案查询 |
| PUT | `/profiles/{id}/confirm` | 字段确认（编辑语义名/纳入后保存） |
| POST | `/profiles/{id}/reparse` | 档案更新（见 §4.3） |
| POST/GET | `/tasks`、GET/PUT/DELETE `/tasks/{id}` | 任务 CRUD（更新即同步调度） |
| POST | `/tasks/{id}/run` | 手动运行（202 立即返回） |
| POST | `/tasks/{id}/duplicate` | 任务副本（默认停用调度） |
| POST | `/trigger/{trigger_token}` | **Webhook 外部触发**（202；供小龙虾/外部系统调用，令牌见任务详情页） |
| POST/GET/DELETE | `/templates` | 任务模板（从任务保存 config/pre_actions/action，新建任务可预填） |
| POST/GET/PUT/DELETE | `/demands` | 需求中心（业务提自动化需求，状态 pending/accepted/done/rejected） |
| GET | `/tasks/{id}/export?embed_credentials=` | 导出 zip 任务包（脚本 + task_config.json） |
| GET | `/runs?task_id=&limit=`、`/runs/{id}` | 运行记录 |
| GET | `/runs/{id}/files/{path}` | 产物下载（有防路径穿越校验） |

## 6. 运维手册

### 启停
- 标准命令见 README「快速开始」（跨平台）；Windows 便利脚本 `powershell -ExecutionPolicy Bypass -File start.ps1` / `stop.ps1`（根目录），已在运行的服务自动跳过
- PostgreSQL 单独管理：`.\pg17\bin\pg_ctl.exe -D pg17\data start|stop|status`
- 重启电脑后 PG **不会自启**，先跑 start.ps1（脚本会先拉起 PG；无 `pg17\` 时自动以 SQLite 模式运行）

### server/.env 配置项
| 键 | 说明 |
|---|---|
| `DATABASE_URL` | 当前指向 `postgresql+psycopg2://postgres:newpra2026@localhost:5433/newpra`；改回 `sqlite:///./newpra.db` 可退回 SQLite（表结构兼容） |
| `PLATFORM_FERNET_KEY` | 凭证加密密钥，**首次启动自动生成；丢失后已存密码全部无法解密**，务必备份 |
| `ZHIPUAI_API_KEY` / `ZHIPUAI_MODEL` | GLM 语义化（可选；无 key 自动降级规则命名） |
| `SMTP_*` | 邮件通知（可选） |

### 备份与恢复
- 数据：`pg17\bin\pg_dump.exe -U postgres -h localhost -p 5433 newpra > backup.sql`（恢复用 psql 导入）
- 凭证密钥：备份 `.env`；登录态：`server/sessions/`（可删，会自动重建）
- 任务产物在 `server/artifacts/run_<id>/`

### 日志位置
- 后端：各服务窗口标准输出；解析/运行失败详情在 `parse_requests.error`、`task_runs.error` 与 artifacts 下 `error.png` / `run_summary.json`
- PG：`pg17\pg.log`

## 7. 已知问题与技术债

| # | 问题 | 现状 / 建议 |
|---|---|---|
| 1 | 验证码类系统（JeecgBoot、若依 demo 等）无法自动登录 | **M7 已落地「人工会话导入」先行版**（Systems 页粘贴 storage_state 免登录）；后续可做浏览器插件一键采集会话 |
| 2 | Element 下拉选项偶发抓空（懒加载时序） | 字段确认 UI 可人工补录；根治需改为轮询等待 |
| 3 | ~~运行状态前端为轮询（4s）~~ | **M7 已升级 SSE 实时推送**（TaskDetail 保留 8s 慢轮询兜底） |
| 4 | AntD 下拉键盘可达性差 | 组件库通病，非阻断 |
| 5 | 并发运行无队列控制 | 多任务同时触发会并发起浏览器，量大需引入队列/信号量 |
| 6 | 导出脚本每次登录不复用会话 | 平台内已复用；导出脚本可加本地 state 支持 |
| 7 | LLM 语义化未实测（无 API key） | `llm_semantic.py` 已就绪，填 key 即生效 |
| 8 | 真实系统解析偶发混入折叠面板字段（如 029tec 分类树搜索框） | 字段确认时人工排除；可加折叠容器过滤规则 |

## 8. 里程碑与实测记录

| 阶段 | 内容 | 验证 |
|---|---|---|
| M0 | 引擎原型（解析/回放 CLI） | 双靶子全链路、稳定性 4/4、10 条失败模式沉淀 |
| M1 | 完整平台（5 表/API/调度/通知/前端） | API 冒烟 + 浏览器验收 7/7 |
| M2 | 档案更新、任务编辑/副本、飞书通知 | 改版字段"发现→纳入→配置"闭环验证 + 15 检查点 |
| M3 | 任务导出（小龙虾任务包） | 脱离平台独立运行，筛选真实生效 |
| M4 | 复杂导出引擎（四模式下载 + 行级指纹防误点） | demo-target 四场景 4/4 |
| M5 | 可靠性三件套（失败重试 / Webhook 触发 / 连续失败告警） | `smoke_test_m5.py` 全过 |
| M6 | 两步门户 pre_clicks / 任务模板 / 需求中心 | `smoke_test_m6.py` 全过 + 任务#4 回归 |
| M7 | SSE 实时推送 + 人工会话导入 | `smoke_test_m7.py` 3/3 + 浏览器验收 |
| 基建 | PostgreSQL 17（便携版）、会话复用、oxd 组件体系 | 029tec 生产工单页 10 字段解析验证 |

**真实系统实测**：✅ OrangeHRM / 029tec 苦糖果 MES / vue-element-admin；❌ JeecgBoot（图形验证码）、芋道（登录后营销拦截弹窗）。

## 9. CLI 快捷命令（调试用）

```bash
# 解析（在 server/ 下）
python -m engine.parser --target-url http://localhost:5173/report --login-url http://localhost:5173/login --username admin --password admin123 --out profiles/x.json

# 回放
python -m engine.executor --profile profiles/x.json --task tasks/y.json

# API 冒烟
python smoke_test.py          # M1 全链路
python smoke_test_m2.py stage1|stage2   # 档案更新（两阶段，中间改页面）
```
