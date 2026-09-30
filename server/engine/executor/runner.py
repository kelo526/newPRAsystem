"""回放执行引擎：PageProfile + 任务配置 → 网页操作 → 产物收集。

执行链路（对应"配置驱动回放"设计）：
登录 → 打开页面 → 逐字段定位并回填配置 → 触发动作 → 捕获产物/截图录证
"""
# ---------- 复杂导出场景的下载捕获 ----------
# 覆盖四类企业常见导出交互：
#   A. 点击导出直接触发浏览器下载（基础场景）
#   B. 点击后弹出新标签页，在新页里再点下载
#   C. 点击后页内弹出对话框（modal），在弹窗里点下载
#   D. 导出中心/记录列表：异步生成（大数据量等待），生成完出现行内下载入口
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from ..parser import browser
from . import adapters, matcher

DL_TEXT_RE = re.compile(r"下\s*载|download|保存到本地|导出到本地", re.I)
DL_LINK_SEL = 'a[href$=".xlsx"], a[href$=".xls"], a[href$=".csv"], a[download]'
# 导出中心（如荣耀工作台"我的导出"）：下载入口是文件名链接，href 无扩展名，
# 需按链接文本识别；生成中的记录（执行中/生成中）不可点，等状态翻转后再点
DL_FILENAME_RE = re.compile(r"\.(xlsx|xls|csv|zip)\s*$", re.I)
DL_BUSY_RE = re.compile(r"执行中|生成中|排队中|处理中|导出中")
ROW_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _panel_visible(page):
    try:
        return page.locator(".my-export-container").first.is_visible()
    except Exception:
        return False


def _refresh_export_panel(page, step):
    """关闭并重新打开"我的导出"面板以刷新记录状态。

    面板的"执行中/执行成功"文本不自动刷新——服务端文件早已生成完毕，
    前端却仍显示执行中，导致下载入口一直被判定为不可点。
    """
    try:
        if _panel_visible(page):
            closed = False
            for sel in (".my-export-container [class*='close']",
                        ".my-export-container .xui-icon-close",
                        ".my-export-container i"):
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click()
                    page.wait_for_timeout(600)
                    closed = not _panel_visible(page)
                    if closed:
                        break
            if not closed:
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)
        page.locator("span.download.xui-popover__reference").first.click()
        page.wait_for_timeout(1500)
        step("  已刷新「我的导出」面板状态")
    except Exception as e:  # noqa: BLE001 —— 刷新失败不中断，下一轮再试
        step(f"  刷新导出面板失败：{e}")


def _entry_key(el):
    """下载入口指纹：自身文本 + 所在行/容器的文本（区分共享列表中不同记录）。"""
    try:
        row_text = el.evaluate(
            "e => (e.closest('tr') || e.closest('li') || e.closest('.ant-modal') "
            "|| e.closest('.el-dialog') || e.parentElement || e).textContent"
        )
        return ((el.text_content() or "").strip()[:16], (row_text or "").strip()[:80])
    except Exception:
        return (None, None)


def _scan_download_entries(p, t_export=None):
    """返回 [(key, locator, busy)]：页面当前全部可见下载入口（文件链接 + 下载文本按钮）。

    busy=True 表示导出中心里"生成中"的记录：面板打开后状态文本不自动刷新，
    服务端可能早已生成完毕，因此对 busy 入口做限频重试点击，而非干等状态翻转。
    t_export：本次点击导出按钮的时刻，早于它的记录是旧运行遗留，不下载。
    """
    entries = []
    try:
        links = p.locator(DL_LINK_SEL)
        for i in range(min(links.count(), 15)):
            el = links.nth(i)
            try:
                if el.is_visible():
                    entries.append((_entry_key(el), el, False))
            except Exception:
                continue
    except Exception:
        pass
    try:
        for el in p.locator("button, a").all()[:60]:
            try:
                if not el.is_visible():
                    continue
                t = (el.text_content() or "").strip()
                if t and DL_TEXT_RE.search(t):
                    entries.append((_entry_key(el), el, False))
            except Exception:
                continue
    except Exception:
        pass
    # 导出中心条目（如荣耀工作台"我的导出"）：文件名是 div.item-title 而非 <a>，
    # 逐条扫 li.container-item，标题按文件名后缀识别，整行文本判断是否生成中
    try:
        items = p.locator(".my-export-container li.container-item")
        for i in range(min(items.count(), 15)):
            el = items.nth(i)
            try:
                if not el.is_visible():
                    continue
                title = el.locator(".item-title").first
                t = (title.text_content() or "").strip()
                if not t or not DL_FILENAME_RE.search(t):
                    continue
                row_text = (el.text_content() or "").strip()
                # 只认本次导出之后创建的记录（防止捡到旧运行的文件）
                m = ROW_TIME_RE.search(row_text)
                if t_export and m:
                    try:
                        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                        if ts < t_export - 90:
                            continue
                    except Exception:
                        pass
                entries.append(((t[:16], row_text[:80]), title, bool(DL_BUSY_RE.search(row_text))))
            except Exception:
                continue
    except Exception:
        pass
    return entries


def _hunt_download(page, action_sel, out_dir, step, timeout=180):
    """点击导出动作后，多源轮询捕获下载文件；返回保存的文件路径或 None。

    覆盖四类企业导出交互：
      A. 点击直接触发浏览器下载（download 事件）
      B. 弹出新标签页，在新页里再点下载
      C. 页内弹出对话框（modal），在弹窗里点下载
      D. 导出中心/记录列表：异步生成，完成后出现行内下载入口

    共享导出中心防误点：点击导出前对页面下载入口做基线快照（行级指纹），
    之后只点击"新增"的下载入口——即等待自己文件的生成，而非点他人已有文件。
    """
    context = page.context
    downloads = []
    known_pages = {id(page): page}

    def _on_download(d):
        downloads.append(d)

    page.on("download", _on_download)
    t_export = time.time()
    # 基线：点击导出前页面已有的下载入口（如导出中心里他人已生成的记录）
    baseline = {key for key, _, _ in _scan_download_entries(page)}

    page.locator(action_sel).first.click()

    deadline = time.time() + timeout
    clicked = {}  # key -> 上次点击时间（busy 入口限频重试，就绪入口只点一次）
    last_refresh = time.time()
    while time.time() < deadline:
        if downloads:
            d = downloads.pop(0)
            fname = d.suggested_filename or f"export_{int(time.time())}.bin"
            path = out_dir / fname
            d.save_as(str(path))
            return path

        # 新标签页接入监听（新页基线为空：其中出现的下载入口即目标）
        for np in context.pages:
            if id(np) not in known_pages:
                known_pages[id(np)] = np
                np.on("download", _on_download)
                step(f"  检测到新页面：{(np.url or '')[:80]}")

        # 定期刷新导出面板（其状态文本不自动刷新）
        if time.time() - last_refresh > 30:
            _refresh_export_panel(page, step)
            last_refresh = time.time()

        # 在所有页面中寻找"新增"下载入口并点击
        for np in context.pages:
            try:
                for key, el, busy in _scan_download_entries(np, t_export=t_export):
                    if key in baseline:
                        continue
                    # 就绪入口只点一次；生成中入口每 10s 重试（面板状态不自动刷新，
                    # 服务端可能已生成完毕，点击就绪即触发下载，未就绪则无副作用）
                    min_interval = 10 if busy else 3600
                    if time.time() - clicked.get(key, 0) < min_interval:
                        continue
                    el.click()
                    clicked[key] = time.time()
                    step(f"  已点击下载入口「{key[0] or '文件链接'}」"
                         f"{'（生成中，限频重试）' if busy else ''}")
                    break
            except Exception:
                continue
        page.wait_for_timeout(2000)
    return None


# ---------- 相对时间预设（周期任务的关键设计） ----------

def _preset_range(preset: str):
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
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    if preset == "month_to_date":
        return today.replace(day=1), today
    raise ValueError(f"未知日期预设：{preset}")


def resolve_value(field, value):
    """把任务配置值解析为回放用的具体值（相对日期 → 绝对日期区间）。"""
    if field["type"] == "date_range":
        if isinstance(value, dict) and "preset" in value:
            start, end = _preset_range(value["preset"])
            return [start.isoformat(), end.isoformat()]
        if isinstance(value, list) and len(value) == 2:
            return value
        raise ValueError(f"字段「{field['semantic_name']}」的日期配置无法解析：{value}")
    return value


# ---------- 档案查找 ----------

def find_field(profile, name):
    for f in profile["fields"]:
        if name in (f.get("semantic_name"), f.get("label")):
            return f
    return None


def find_action(profile, name):
    for a in profile["actions"]:
        if name in (a.get("semantic_name"), a.get("label")):
            return a
    return None


# ---------- 登录后角色切换 ----------

def apply_role_switch(page, url, role_name, step):
    """切换页面右上角个人权限角色（如荣耀工作台"自制BA"）。

    角色是账号级状态（任意会话切换会影响所有会话），且决定功能可用性
    （如导出按钮置灰）。角色不符时自动点击头部角色胶囊切换，并重新加载目标页。
    """
    try:
        active = page.evaluate(
            "() => { const a = document.querySelector('a.main-role.isActive');"
            " return a ? a.textContent.trim() : ''; }"
        )
    except Exception:
        active = ""
    if active == role_name:
        step(f"个人权限角色已是「{role_name}」，跳过切换")
        return
    step(f"切换个人权限角色：{active or '(未知)'} → {role_name}")
    trigger = (
        "#wp_plant_header .navbar-right .xui-dropdown, "
        "[class*='change-dropdown'] .xui-dropdown"
    )
    page.locator(trigger).first.click()
    page.wait_for_timeout(800)
    page.locator("a.main-role", has_text=role_name).first.click()
    page.wait_for_timeout(2000)
    # 切换角色通常伴随页面刷新，重新进入目标页
    try:
        page.goto("about:blank")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        browser._wait_page_ready(page)
    except Exception as e:  # noqa: BLE001 —— 重载失败不阻断，交给后续步骤报错
        step(f"角色切换后重新加载页面异常：{e}")


# ---------- 主流程 ----------

def run(task, profile, out_dir, headless=True, state_file=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = {"task": task["name"], "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": []}

    def step(msg, **extra):
        entry = {"time": time.strftime("%H:%M:%S"), "msg": msg, **extra}
        log["steps"].append(entry)
        print(f"  [{entry['time']}] {msg}")

    pw = br = page = None
    try:
        pw, br, page = browser.open_logged_in_page(
            profile["url"], task.get("login"), headless=headless, state_file=state_file
        )
        page.screenshot(path=str(out / "01_opened.png"))

        # 0. 登录后角色切换（配置了目标角色且当前不符时）
        if task.get("role_switch"):
            apply_role_switch(page, profile["url"], task["role_switch"], step)
            page.screenshot(path=str(out / "01b_role_switched.png"))

        # 1. 逐字段回填（现场重新定位，不用缓存的旧 selector）
        for name, value in task["config"].items():
            field = find_field(profile, name)
            if field is None:
                raise KeyError(f"任务配置的字段「{name}」在页面档案中不存在。可用字段："
                               f"{[f['semantic_name'] for f in profile['fields']]}")
            resolved = resolve_value(field, value)
            sel = matcher.field_selector(page, field)
            step(f"填写「{name}」= {resolved}", field_key=field["key"])
            adapters.apply_field_value(page, field, resolved, selector=sel)
        page.screenshot(path=str(out / "02_filled.png"))

        # 2. 前置动作链（如"先查询后导出"的业务依赖：导出读取查询后的结果集）
        for pre_name in task.get("pre_actions", []):
            pre = find_action(profile, pre_name)
            if pre is None:
                raise KeyError(f"前置动作「{pre_name}」在页面档案中不存在。可用动作："
                               f"{[a['semantic_name'] for a in profile['actions']]}")
            step(f"前置动作：点击「{pre_name}」")
            page.locator(matcher.action_selector(page, pre)).first.click()
            page.wait_for_timeout(1500)

        # 3. 主动作
        action = find_action(profile, task["action"])
        if action is None:
            raise KeyError(f"任务配置的动作「{task['action']}」在页面档案中不存在。可用动作："
                           f"{[a['semantic_name'] for a in profile['actions']]}")
        action_sel = matcher.action_selector(page, action)
        artifacts = []

        if action["kind"] == "export":
            export_timeout = task.get("export_timeout", 180)
            step(f"点击「{task['action']}」，多源捕获下载（新页/弹窗/导出中心，最长 {export_timeout}s）...")
            saved = _hunt_download(page, action_sel, out, step, timeout=export_timeout)
            if saved is None:
                raise TimeoutError(
                    f"导出等待超时（{export_timeout}s）：未捕获到下载文件。"
                    "可能是文件生成过慢（可在任务配置增大 export_timeout）或下载入口未被识别。"
                )
            artifacts.append(str(saved))
            step(f"导出文件已保存：{saved}", artifact=str(saved))
        else:
            step(f"点击「{task['action']}」")
            page.locator(action_sel).first.click()
            page.wait_for_timeout(1500)

        page.screenshot(path=str(out / "03_action_done.png"))
        log["status"] = "success"
        log["artifacts"] = artifacts
        return log
    except Exception as e:  # noqa: BLE001 —— 失败也要留证据
        log["status"] = "failed"
        log["error"] = str(e)
        try:
            page.screenshot(path=str(out / "error.png"))
        except Exception:
            pass
        raise
    finally:
        log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (out / "run_summary.json").write_text(
            json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if page is not None:
            browser.shutdown(pw, br)
