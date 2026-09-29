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
from datetime import date, timedelta
from pathlib import Path

from ..parser import browser
from . import adapters, matcher

DL_TEXT_RE = re.compile(r"下\s*载|download|保存到本地|导出到本地", re.I)
DL_LINK_SEL = 'a[href$=".xlsx"], a[href$=".xls"], a[href$=".csv"], a[download]'


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


def _scan_download_entries(p):
    """返回 [(key, locator)]：页面当前全部可见下载入口（文件链接 + 下载文本按钮）。"""
    entries = []
    try:
        links = p.locator(DL_LINK_SEL)
        for i in range(min(links.count(), 15)):
            el = links.nth(i)
            try:
                if el.is_visible():
                    entries.append((_entry_key(el), el))
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
                    entries.append((_entry_key(el), el))
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
    # 基线：点击导出前页面已有的下载入口（如导出中心里他人已生成的记录）
    baseline = {key for key, _ in _scan_download_entries(page)}

    page.locator(action_sel).first.click()

    deadline = time.time() + timeout
    clicked = set()
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

        # 在所有页面中寻找"新增"下载入口并点击
        for np in context.pages:
            try:
                for key, el in _scan_download_entries(np):
                    if key in baseline or key in clicked:
                        continue
                    el.click()
                    clicked.add(key)
                    step(f"  已点击新增下载入口「{key[0] or '文件链接'}」")
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
