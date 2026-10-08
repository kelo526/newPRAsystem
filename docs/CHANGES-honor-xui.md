# 变更记录：荣耀工作台（XUI 组件库）接入适配

> 本轮变更目标：让平台支持以「荣耀工作台（workplace.hihonor.com）」为代表的使用 **XUI 组件库**（荣耀内部 Element UI 定制版，`xui-` 前缀）与**导出中心**模式的企业系统，端到端跑通「登录 → 角色校验 → 填条件 → 搜索 → 导出中心异步下载」全链路。
>
> 实测环境：制造员工基础信息查询页（`mwsm-employee-base-info-inquiry`），约 650 条记录，全流程 ~45 秒（其中自动化操作约 9 秒，其余为服务端异步生成文件的时间）。

## 一、Bug 修复

### 1. 编辑目标系统时选择器字段被静默丢弃（`app/api.py`）
`SystemUpdate` 模型漏定义 `username_selector / password_selector / submit_selector`，导致编辑弹窗里填写的登录选择器从未持久化（新建时能存、编辑时丢）。已补齐三个字段并在 `update_system` 中持久化（`None=不修改`，空串=清除）。

### 2. 页面就绪等待不覆盖 XUI 且存在 SPA 时序问题（`engine/parser/browser.py`）
- `_wait_page_ready` 的组合选择器增加 `.xui-form-item / .xui-select`；
- 首个控件出现后 SPA 仍会分批异步挂载其余字段，增加 2 秒稳定等待（此前导致单选框等字段漏抓）。

### 3. start.bat 在中文路径下不可用
原 `start.bat` → `start.ps1` 依赖 pyenv 的 `python/uvicorn` shim，而 pyenv-win 的 VBScript shim 在含中文的路径下报「没有权限」。已重写为自包含的 `start.bat`：后端直接调用 pyenv 3.11.4 真实解释器（`python -m uvicorn`），端口占用检测跳过已运行服务，窗口标题保持 `newpra-*` 以兼容 `stop.bat`。文件为 GBK+CRLF 编码，中文 Windows cmd 下正常显示。`start.ps1` 不再被引用，可自行删除。

## 二、新功能：XUI 组件库全链路支持

荣耀工作台等系统使用 `xui-` 前缀的内部组件库（Element UI 同源定制）。此前解析时下拉框被误识别为文本框、标签与选项全部丢失。现已覆盖解析→归一→回放→自愈→导出全链路：

| 文件 | 变更 |
|---|---|
| `engine/parser/dom_extract.py` | 新增 XUI 提取规则（form-item / select / radio / checkbox / date / input），标签取自 `.xui-form-item__label`；`cssPath` 稳定类名过滤增加 `xui-` 前缀；原生表单规则排除 xui 容器防重复抓取；新增 `_grab_xui_options` 交互式抓取下拉选项（浮层内联、display 显隐），树形下拉逐级展开懒加载节点后收集全部节点文本并保序去重 |
| `engine/parser/rules.py` | `xui_select → select`、`xui_input → text`、`xui_radio → radio`、`xui_checkbox → checkbox`、`xui_date_range → date_range` |
| `engine/executor/adapters.py` | 新增 `XuiSelectAdapter / XuiInputAdapter / XuiRadioAdapter / XuiCheckboxAdapter`。树下拉点选要点节点内的**单选圆圈**（点文字行不生效）；选项不可见时四级兜底：可见节点 → 筛选框输入+回车 → 点筛选框搜索图标 → 逐级展开树节点。选完强制收起浮层（Escape + 再点触发框双保险），否则浮层遮挡下方表单控件导致后续点击全部超时 |
| `engine/executor/matcher.py` | 自愈定位重构为 `comp → (表单容器, 标签选择器, 组件选择器)` 映射表，新增 XUI 条目（`.xui-form-item:has(.xui-form-item__label:has-text(…)) …`） |
| `app/exporter.py`（导出脚本模板） | 模板内适配器与定位逻辑同步支持 XUI |
| `web/src/pages/TaskForm.jsx` | select 字段由 Select 改为 AutoComplete（可选择解析选项，也允许手动输入树中未展开的节点）；新增 radio 类型渲染 |

## 三、新功能：导出中心（异步生成）下载捕获

荣耀工作台的「导出」不直接触发浏览器下载，而是滑出「我的导出」面板创建异步任务。`engine/executor/runner.py` 的 `_hunt_download` 针对该模式增强：

1. **条目识别**：面板文件名是 `div.item-title` 而非 `<a>` 链接，新增按 `.my-export-container li.container-item` 逐条扫描，标题按文件名后缀（`.xlsx/.xls/.csv/.zip`）识别；
2. **状态不自动刷新**：面板的「执行中/执行成功」文本不会自动更新（服务端早已生成完毕，前端仍显示执行中），每 30 秒关闭并重开面板强制刷新（`_refresh_export_panel`）；
3. **限频重试点选**：生成中的条目每 10 秒重试点击（未就绪时点击无副作用），就绪后点击即触发浏览器下载，由 `download` 事件捕获落盘；
4. **归属过滤**：按记录行内时间戳只认「本次点击导出之后」创建的记录（容忍 90 秒时钟偏差），避免误下载旧运行遗留的同名任务文件。

## 四、新功能：登录后自动切换个人权限角色

荣耀工作台的右上角「个人权限」角色（自制BA / 通用查询_自制 / …）是**账号级状态**：任意会话切换会影响所有会话，且决定功能可用性（非「自制BA」角色下导出按钮置灰）。

- `TargetSystem` 新增 `role_name` 字段（模型 / Schema / 创建与编辑 API / 前端表单同步支持）；
- 任务执行时（`runner.apply_role_switch`）：读取 `a.main-role.isActive` 当前角色，与配置不符则点击头部角色胶囊（`#wp_plant_header .navbar-right .xui-dropdown`）选择目标角色，并重新加载目标页；一致则跳过。

## 五、新功能：导出等待超时可配置

`Task` 新增 `export_timeout` 字段（默认 180 秒，UI 范围 30~3600）。此前该值在执行链路中丢失，恒为 180 秒——对导出中心生成耗时数分钟的系统必然超时。已打通 模型 → Schema → API → runner_bridge → runner 全链路，前端「任务编辑 → 可靠性」新增「导出等待上限（秒）」。

## 六、数据库迁移（SQLite 已执行，PostgreSQL 需手动）

```sql
ALTER TABLE tasks ADD COLUMN export_timeout INTEGER DEFAULT 180;
ALTER TABLE target_systems ADD COLUMN role_name VARCHAR(120) DEFAULT '';
```

## 七、实测结论（荣耀工作台 · 制造员工基础信息导出）

| 环节 | 表现 |
|---|---|
| 登录 | storage_state 会话复用，免登录直进（失效自动重登） |
| 角色校验 | 「自制BA」匹配时跳过，异常时自动切换并重载页面 |
| 部门树选择 | 「制造一部」（三级节点）自动展开点选成功 |
| 搜索+导出 | 651 条记录，服务端约 30 秒生成完成 |
| 结果 | `员工基本信息导出*.xlsx`（76KB）落入运行产物目录，任务详情页可下载 |

## 八、已知边界

- 「导出任务包」生成的独立脚本对导出中心模式暂不适配（仍为 `expect_download` 直接下载等待），如需交付外部调度平台需移植本套捕获逻辑；
- XUI 的树形下拉筛选框在本系统不响应输入过滤（自定义组件），回放已用「逐级展开」兜底；其他 XUI 系统若响应筛选则会走更快路径。

## 九、登录候选链扩展与部署脚本更新

- **登录候选链扩展**（`engine/parser/browser.py` / `app/exporter.py`）：`USERNAME_CANDIDATES` 新增 placeholder 邮箱/手机/工号、常见 id（`#username/#user/#account`）与组件库类名兜底（`.el-input__inner / .xui-input__inner`）。荣耀统一门户（placeholder「邮箱地址、手机号码或帐号名」）实测免配置自动命中用户名/密码框；
- **部署方式升级**：平台前端由 Vite 开发服务器改为 **nginx 发布生产构建**（`web/dist`，端口 9080，局域网可访问），`/api` 反向代理 + SSE 透传（`/api/events` 关闭缓冲）。`start.bat` 默认只启动 后端(8000)+nginx(9080)，`start.bat dev` 才额外启动 Vite(5174) 与模拟业务系统(5173)；`setup.bat` 部署时自动 `npm run build`；`stop.ps1` 增加停止 nginx；删除已不被引用的 `start.ps1`。
