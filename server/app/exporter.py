"""任务导出器：Task + PageProfile → 自包含 Python 脚本。

导出的脚本不依赖平台代码，仅需 playwright，可交由"小龙虾"等任意调度平台执行。
默认内嵌凭证（内部交付场景）；更高安全性可传 embed_credentials=False，
运行时从环境变量 NEWPRA_TASK_PASSWORD 读取。

实现说明：模板用 __PLACEHOLDER__ 占位符 + str.replace 生成，
避免 str.format 与脚本内大量花括号冲突。
"""
import json

from . import crypto

TEMPLATE = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""newPRAsystem 导出的自动化任务（自包含脚本 + 外部配置文件）

任务名称：__TASK_NAME__
目标页面：__TARGET_URL__
建议调度：cron "__CRON__"

配置文件：与脚本同目录的 task_config.json
    username   登录账号
    password   登录密码（留空则读环境变量 NEWPRA_TASK_PASSWORD）
    output_dir 产物输出目录（相对路径基于脚本所在目录）
    配置文件缺失时，首次运行会自动生成模板。
    在小龙虾等调度平台上运行时，只改配置文件即可，无需改动本脚本。

依赖安装：
    pip install playwright
    playwright install chromium

运行：
    python 本脚本文件名.py            # 按配置文件的 output_dir 保存产物
    python 本脚本文件名.py --headed   # 有头模式（调试）
"""
import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

# 任务与档案以 JSON 文本内嵌，运行时解析（避免 JSON 的 false/null 与 Python 字面量冲突）
TASK = json.loads(r"""
__TASK_JSON__
""")
PROFILE = json.loads(r"""
__PROFILE_JSON__
""")

# ---------------- 外部配置文件（与脚本同目录的 task_config.json） ----------------
# 凭证与输出目录不写死在脚本里：员工拿到自己的调度平台（如小龙虾）上运行时，
# 修改配置文件即可，无需改动脚本。配置缺失时自动生成模板并退出。
CONFIG_FILE = Path(__file__).resolve().parent / "task_config.json"


def _load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps({
            "username": TASK["login"]["username"],
            "password": "",
            "output_dir": "exports"
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"未找到配置文件，已生成模板：{CONFIG_FILE}")
        print("请填写 password（账号/输出目录按需调整）后重新运行。")
        sys.exit(2)
    # utf-8-sig：兼容 Windows 记事本等工具保存的带 BOM 配置文件
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))


CFG = _load_config()
TASK["login"]["username"] = CFG.get("username") or TASK["login"]["username"]
TASK["login"]["password"] = CFG.get("password") or os.environ.get("NEWPRA_TASK_PASSWORD", "")
OUTPUT_DIR = CFG.get("output_dir") or "exports"

# ---------------- 登录候选链（生成时由平台注入，与 engine/parser/browser.py 单源同步） ----------------
LOGIN_CANDIDATES = json.loads(r"""
__LOGIN_CANDIDATES__
""")
USERNAME_CANDIDATES = LOGIN_CANDIDATES["username"]
PASSWORD_CANDIDATES = LOGIN_CANDIDATES["password"]
SUBMIT_CANDIDATES = LOGIN_CANDIDATES["submit"]


def pick_selector(page, candidates, label, timeout_each=2500):
    for sel in candidates:
        try:
            if page.wait_for_selector(sel, timeout=timeout_each, state="visible"):
                return sel
        except Exception:
            continue
    raise RuntimeError(f"登录页未探测到{label}")


def perform_login(page, login_cfg):
    user_sels = [login_cfg["username_selector"]] if login_cfg.get("username_selector") else USERNAME_CANDIDATES
    pwd_sels = [login_cfg["password_selector"]] if login_cfg.get("password_selector") else PASSWORD_CANDIDATES
    submit_sels = [login_cfg["submit_selector"]] if login_cfg.get("submit_selector") else SUBMIT_CANDIDATES

    page.goto(login_cfg["url"], wait_until="domcontentloaded", timeout=60000)

    # 登录前置点击（两步式门户）：先依次点击入口元素，真实登录表单出现后再走候选链
    for click_sel in login_cfg.get("pre_clicks") or []:
        page.locator(click_sel).first.click(timeout=10000)
        page.wait_for_timeout(1500)

    user_sel = pick_selector(page, user_sels, "用户名输入框")
    pwd_sel = pick_selector(page, pwd_sels, "密码输入框")
    submit_sel = pick_selector(page, submit_sels, "登录按钮")
    page.wait_for_timeout(2000)
    page.fill(user_sel, login_cfg["username"])
    page.fill(pwd_sel, login_cfg["password"])
    if page.input_value(user_sel) != login_cfg["username"]:
        page.wait_for_timeout(1000)
        page.fill(user_sel, login_cfg["username"])
        page.fill(pwd_sel, login_cfg["password"])
    page.locator(submit_sel).first.click()

    # 登录成功判定（与平台 engine/parser/browser.py 同步）：
    # 以"提交登录那一刻的页面"为基准——URL 离开该页或用户名输入框消失即成功。
    # 不能用配置的登录入口 URL 判定：两步式门户（pre_clicks）下提交时已在
    # 真实登录表单页，以入口 URL 判定会立刻误判成功。连续两次采样一致才认为稳定。
    submit_url = page.url
    login_base = login_cfg["url"].split("?")[0]
    deadline = time.time() + 15
    last_url = None
    while time.time() < deadline:
        url = page.url
        user_gone = page.locator(user_sel).count() == 0
        left_login = user_gone or (url != submit_url and login_base not in url and "auth/login" not in url.lower())
        if left_login:
            if url == last_url:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                return
            last_url = url
        time.sleep(0.5)
    raise RuntimeError("登录后页面未跳转（15s）：请检查账号密码或登录页附加必选项")


# ---------------- 相对日期预设 ----------------
def preset_range(preset):
    today = date.today()
    if preset == "today":
        return today, today
    if preset == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if preset == "last_7_days":
        return today - timedelta(days=6), today
    if preset == "last_30_days":
        return today - timedelta(days=29), today
    if preset == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        return last_monday, last_monday + timedelta(days=6)
    if preset == "last_month":
        first = today.replace(day=1)
        end = first - timedelta(days=1)
        return end.replace(day=1), end
    if preset == "month_to_date":
        return today.replace(day=1), today
    raise ValueError(f"未知日期预设：{preset}")


def resolve_value(field, value):
    if field["type"] == "date_range":
        if isinstance(value, dict) and "preset" in value:
            start, end = preset_range(value["preset"])
            return [start.isoformat(), end.isoformat()]
        if isinstance(value, list) and len(value) == 2:
            return value
        raise ValueError(f"字段「{field['semantic_name']}」日期配置无法解析")
    return value


# ---------------- 组件适配器 ----------------
ANT_DROPDOWN = ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
EL_DROPDOWN = ".el-select-dropdown:not([style*='display: none'])"


class AntDSelect:
    component = "antd_select"

    def apply(self, page, selector, value):
        values = value if isinstance(value, list) else [value]
        page.locator(selector).first.click()
        for v in values:
            opt = page.locator(f'{ANT_DROPDOWN} .ant-select-item-option[title="{v}"]')
            if opt.count() == 0:
                opt = page.locator(f"{ANT_DROPDOWN} .ant-select-item-option", has_text=v)
            opt.first.click()
            page.wait_for_timeout(200)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


class AntDDateRange:
    component = "antd_date_range"

    def apply(self, page, selector, value):
        start, end = value
        inputs = page.locator(f"{selector} input")
        inputs.first.click()
        inputs.first.fill(start)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        inputs.last.click()
        inputs.last.fill(end)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)


class AntDInput:
    component = "antd_input"

    def apply(self, page, selector, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class ElSelect:
    component = "el_select"

    def apply(self, page, selector, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(selector).first.click()
            page.wait_for_selector(f"{EL_DROPDOWN} .el-select-dropdown__item", timeout=5000)
            page.locator(f"{EL_DROPDOWN} .el-select-dropdown__item", has_text=str(v)).first.click()
            page.wait_for_timeout(300)


class ElInput:
    component = "el_input"

    def apply(self, page, selector, value):
        page.locator(f"{selector} input").first.fill(str(value))


class OxdSelect:
    component = "oxd_select"

    def apply(self, page, selector, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(selector).first.click()
            page.wait_for_selector(".oxd-select-dropdown .oxd-select-option", timeout=5000)
            page.locator(".oxd-select-dropdown .oxd-select-option", has_text=str(v)).first.click()
            page.wait_for_timeout(300)


class OxdInput:
    component = "oxd_input"

    def apply(self, page, selector, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class NativeSelect:
    component = "native_select"

    def apply(self, page, selector, value):
        v = value[0] if isinstance(value, list) else value
        page.locator(selector).first.select_option(label=v)


class NativeInput:
    component = "native_input"

    def apply(self, page, selector, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class XuiSelect:
    component = "xui_select"
    DROPDOWN = ".xui-select-dropdown:not([style*='display: none'])"

    def apply(self, page, selector, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(selector).first.click()
            page.wait_for_timeout(600)
            dropdown = page.locator(self.DROPDOWN)
            opt = dropdown.locator(".xui-select-dropdown__item", has_text=str(v))
            if opt.count() == 0:
                # 树下拉：节点带单选圈时，点文字行不生效，须点圈
                node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                if node.count() == 0:
                    # 子节点折叠未渲染：用下拉内置筛选框搜索
                    filt = dropdown.locator(".xui-select-dropdown__filter input")
                    if filt.count() > 0:
                        filt.first.fill(str(v))
                        page.wait_for_timeout(300)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(1000)
                        node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                    if node.count() == 0 and filt.count() > 0:
                        icon = dropdown.locator(".xui-select-dropdown__filter .fa-search")
                        if icon.count() > 0:
                            icon.first.click()
                            page.wait_for_timeout(1000)
                            node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                    if node.count() == 0:
                        # 自定义树不响应筛选（如部门树）：逐级展开节点后重找
                        if filt.count() > 0:
                            filt.first.fill("")
                            page.wait_for_timeout(500)
                        for _ in range(5):
                            icons = dropdown.locator(".xui-tree-node__expand-icon")
                            expanded_any = False
                            for i in range(icons.count()):
                                ic = icons.nth(i)
                                cls = ic.get_attribute("class") or ""
                                if "expanded" in cls or "is-leaf" in cls:
                                    continue
                                try:
                                    ic.click(timeout=600)
                                    expanded_any = True
                                    page.wait_for_timeout(200)
                                except Exception:
                                    continue
                            page.wait_for_timeout(400)
                            node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                            if node.count() > 0 or not expanded_any:
                                break
                circle = node.first.locator(".xui-radio")
                opt = circle if circle.count() > 0 else node
            opt.first.click()
            page.wait_for_timeout(300)
        # xui 树下拉选中后浮层可能不收起，遮挡下方表单控件：Escape + 再点触发框双保险
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if page.locator(self.DROPDOWN).count() > 0:
            page.locator(selector).first.click()
            page.wait_for_timeout(300)


class XuiInput:
    component = "xui_input"

    def apply(self, page, selector, value):
        page.locator(f"{selector} input").first.fill(str(value))


class XuiRadio:
    component = "xui_radio"

    def apply(self, page, selector, value):
        v = value[0] if isinstance(value, list) else value
        page.locator(f"{selector} .xui-radio", has_text=str(v)).first.click()
        page.wait_for_timeout(200)


class XuiCheckbox:
    component = "xui_checkbox"

    def apply(self, page, selector, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(f"{selector} .xui-checkbox", has_text=str(v)).first.click()
            page.wait_for_timeout(200)


ADAPTERS = {c.component: c() for c in [
    AntDSelect, AntDDateRange, AntDInput, ElSelect, ElInput,
    OxdSelect, OxdInput, NativeSelect, NativeInput,
    XuiSelect, XuiInput, XuiRadio, XuiCheckbox,
]}


# ---------------- 定位与查找 ----------------
def field_selector(page, field):
    sel = field["locator"]["selector"]
    try:
        if page.locator(sel).count() > 0:
            return sel
    except Exception:
        pass
    layout = {
        "antd_select": (".ant-form-item", ".ant-form-item-label label", ".ant-select"),
        "antd_date_range": (".ant-form-item", ".ant-form-item-label label", ".ant-picker"),
        "antd_input": (".ant-form-item", ".ant-form-item-label label", "input"),
        "xui_select": (".xui-form-item", ".xui-form-item__label", ".xui-select"),
        "xui_input": (".xui-form-item", ".xui-form-item__label", ".xui-input"),
        "xui_radio": (".xui-form-item", ".xui-form-item__label", ".xui-radio-group"),
        "xui_checkbox": (".xui-form-item", ".xui-form-item__label", ".xui-checkbox-group"),
    }.get(field["locator"]["component"])
    if layout:
        item_sel, label_sel, comp_sel = layout
        for label in field["locator"]["labels"]:
            fallback = f'{item_sel}:has({label_sel}:has-text("{label}")) {comp_sel}'
            try:
                if page.locator(fallback).count() > 0:
                    return fallback
            except Exception:
                continue
    return sel


def action_selector(page, action):
    loc = action["locator"]
    try:
        if page.locator(loc["selector"]).count() > 0:
            return loc["selector"]
    except Exception:
        pass
    css = loc.get("css_selector", "")
    if css and page.locator(css).count() > 0:
        return css
    for text in loc.get("texts", []):
        fb = f'button:has-text("{text}")'
        try:
            if page.locator(fb).count() > 0:
                return fb
        except Exception:
            continue
    return loc["selector"]


def find_field(name):
    for f in PROFILE["fields"]:
        if name in (f.get("semantic_name"), f.get("label")):
            return f
    raise KeyError(f"字段「{name}」不在档案中")


def find_action(name):
    for a in PROFILE["actions"]:
        if name in (a.get("semantic_name"), a.get("label")):
            return a
    raise KeyError(f"动作「{name}」不在档案中")


# ---------------- 主流程 ----------------
def run(out_dir: Path, headless: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    steps = []

    def step(msg):
        entry = time.strftime("[%H:%M:%S]") + " " + msg
        steps.append(entry)
        print("  " + entry)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    try:
        if TASK["login"]:
            perform_login(page, TASK["login"])
        # SPA hash 路由：完整重载以目标路由初始化
        page.goto("about:blank")
        page.goto(PROFILE["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(
            ".ant-form-item, .el-form-item, .xui-form-item, .el-select, .xui-select, .oxd-input-group, select, input:not([type=hidden])",
            timeout=30000, state="attached")
        page.screenshot(path=str(out_dir / "01_opened.png"))

        for name, value in TASK["config"].items():
            field = find_field(name)
            resolved = resolve_value(field, value)
            sel = field_selector(page, field)
            step(f"填写「{name}」= {resolved}")
            adapter = ADAPTERS.get(field["locator"]["component"])
            if adapter is None:
                raise NotImplementedError(f"组件 {field['locator']['component']} 暂无适配器")
            adapter.apply(page, sel, resolved)
        page.screenshot(path=str(out_dir / "02_filled.png"))

        for pre in TASK["pre_actions"]:
            step(f"前置动作：{pre}")
            page.locator(action_selector(page, find_action(pre))).first.click()
            page.wait_for_timeout(1500)

        action = find_action(TASK["action"])
        sel = action_selector(page, action)
        if action["kind"] == "export":
            step(f"点击「{TASK['action']}」并等待导出")
            with page.expect_download(timeout=30000) as dl:
                page.locator(sel).first.click()
            f = out_dir / dl.value.suggested_filename
            dl.value.save_as(str(f))
            step(f"导出文件：{f.name}")
        else:
            step(f"点击「{TASK['action']}」")
            page.locator(sel).first.click()
            page.wait_for_timeout(1500)

        page.screenshot(path=str(out_dir / "03_action_done.png"))
        (out_dir / "run_summary.json").write_text(json.dumps(
            {"task": TASK["name"], "status": "success", "steps": steps},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ 任务执行成功，产物目录：{out_dir}")
        return 0
    except Exception as e:
        (out_dir / "run_summary.json").write_text(json.dumps(
            {"task": TASK["name"], "status": "failed", "steps": steps, "error": str(e)},
            ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            page.screenshot(path=str(out_dir / "error.png"))
        except Exception:
            pass
        print(f"\n✗ 任务失败：{e}\n  证据目录：{out_dir}")
        return 1
    finally:
        browser.close()
        pw.stop()


def main():
    ap = argparse.ArgumentParser(description="newPRAsystem 导出任务")
    ap.add_argument("--out", default=None, help="产物目录（默认取配置文件 output_dir）")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    if args.out:
        out = Path(args.out)
    else:
        base = Path(OUTPUT_DIR)
        out = base if base.is_absolute() else Path(__file__).resolve().parent / base
        out = out / (TASK["name"] + "_" + time.strftime("%Y%m%d_%H%M%S"))
    print(f"执行任务：{TASK['name']}  目标：{PROFILE['url']}")
    sys.exit(run(out, headless=not args.headed))


if __name__ == "__main__":
    main()
'''


def export_task_script(task, profile, system) -> str:
    """生成自包含任务脚本内容（不含凭证，凭证在外部 task_config.json）。"""
    # 候选链单源：从平台 browser.py 取值注入，避免模板与平台两处维护漂移
    from engine.parser.browser import PASSWORD_CANDIDATES, SUBMIT_CANDIDATES, USERNAME_CANDIDATES

    login = {
        "url": system.login_url,
        "username": system.username,
        "password": "",
    }
    # 显式登录选择器 / 两步式门户前置点击一并导出，独立脚本行为与平台一致
    for key in ("username_selector", "password_selector", "submit_selector", "pre_clicks"):
        value = getattr(system, key, None)
        if value:
            login[key] = value
    task_data = {
        "name": task.name,
        "login": login,
        "config": task.config,
        "pre_actions": task.pre_actions,
        "action": task.action,
    }
    profile_data = {
        "url": profile.target_url,
        "fields": [f for f in (profile.fields or []) if f.get("included", True)],
        "actions": profile.actions or [],
    }
    cron = (task.schedule or {}).get("cron", "")
    candidates = {
        "username": USERNAME_CANDIDATES,
        "password": PASSWORD_CANDIDATES,
        "submit": SUBMIT_CANDIDATES,
    }
    return (
        TEMPLATE
        .replace("__TASK_NAME__", task.name)
        .replace("__TARGET_URL__", profile.target_url)
        .replace("__CRON__", cron)
        .replace("__TASK_JSON__", json.dumps(task_data, ensure_ascii=False, indent=2))
        .replace("__PROFILE_JSON__", json.dumps(profile_data, ensure_ascii=False, indent=2))
        .replace("__LOGIN_CANDIDATES__", json.dumps(candidates, ensure_ascii=False, indent=2))
    )


def export_config_file(task, system, embed_credentials=True) -> str:
    """生成外部配置文件内容（与脚本同目录的 task_config.json）。

    embed_credentials=true 时预填密码（内部交付便利）；
    false 时密码留空，由使用者在小龙虾等调度平台侧自行填写。
    """
    password = crypto.decrypt(system.password_enc) if embed_credentials else ""
    return json.dumps(
        {
            "username": system.username,
            "password": password,
            "output_dir": "exports",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def script_filename(task) -> str:
    """导出脚本文件名（中文任务名转拼音不必要，保留中文但清理非法字符）。"""
    safe = "".join(c for c in task.name if c not in r'\/:*?"<>|').strip() or "task"
    return f"newpra_task_{safe}.py"
