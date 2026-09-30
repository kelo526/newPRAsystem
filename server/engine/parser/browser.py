"""Playwright 会话管理：凭证代填登录 + 页面打开 + 登录态复用。

登录采用"候选链探测"：中英文 placeholder / name 属性 / type 特征多重匹配，
覆盖国内外常见系统；定位不到时可用 login_cfg 显式指定 selector。

会话复用：传入 state_file 时，优先用持久化的 storage_state 直接访问目标页；
被重定向回登录页视为失效，自动重新登录并更新会话文件。
"""
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

# 用户名输入框候选链（依次探测，第一个可见者胜出）
# 末尾的 id / 组件库类名是兜底：Element UI / XUI 登录页（如企业统一门户
# "邮箱地址、手机号码或账号名"）常无 name 属性，且 placeholder 多样
USERNAME_CANDIDATES = [
    "input[placeholder*='用户名']",
    "input[placeholder*='账号']",
    "input[placeholder*='用户' i]",
    "input[placeholder*='邮箱']",
    "input[placeholder*='手机']",
    "input[placeholder*='工号']",
    "input[name='username' i]",
    "input[name='user' i]",
    "input[name='account' i]",
    "input[name='loginname' i]",
    "input[autocomplete='username']",
    "input[type='email']",
    "#username",
    "#user",
    "#account",
    "input.el-input__inner",
    "input.xui-input__inner",
]
PASSWORD_CANDIDATES = [
    "input[type='password']",
    "input[placeholder*='密码']",
]
SUBMIT_CANDIDATES = [
    "button[type='submit']",
    "button:has-text('登 录')",
    "button:has-text('登录')",
    "button:has-text('Login')",
    "button:has-text('Sign in')",
    "input[type='submit']",
]


def open_logged_in_page(target_url, login_cfg, headless=True, state_file=None):
    """启动浏览器 →（复用或新建）登录 → 打开目标页面，返回 (playwright, browser, page)。

    state_file：Playwright storage_state 文件路径。存在则直接复用登录态；
    失效（被重定向回登录页）时自动降级为重新登录，并回写会话文件。
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    try:
        return _open_logged_in_page_impl(pw, browser, target_url, login_cfg, state_file)
    except Exception:
        # 失败时释放 playwright 句柄：sync API 的事件循环在同一进程内
        # 若不清理，后续再次 start() 会报 "Sync API inside the asyncio loop"
        try:
            browser.close()
            pw.stop()
        finally:
            raise


def _open_logged_in_page_impl(pw, browser, target_url, login_cfg, state_file):
    # 1. 尝试复用已有会话
    if state_file and Path(state_file).exists() and login_cfg:
        try:
            context = browser.new_context(
                accept_downloads=True, storage_state=str(state_file)
            )
            page = context.new_page()
            page.goto("about:blank")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            if not _redirected_to_login(page, login_cfg):
                _wait_page_ready(page)
                return pw, browser, page
            context.close()  # 会话失效，丢弃
        except Exception:
            pass

    # 2. 正常登录流程
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    if login_cfg:
        perform_login(page, login_cfg)
        if state_file:
            try:
                Path(state_file).parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(state_file))
            except Exception:
                pass

    # SPA hash 路由：从登录后页面 goto 目标 hash 是 same-document 导航，
    # Vue Router 异步切换、无法可靠等待；先到空白页再完整加载目标 URL，
    # 让应用直接以目标路由初始化（登录态在 cookie/localStorage，重载保留）。
    # 登录后应用可能还有一次 JS 层跳转，导航冲突时重试一次。
    for _ in range(2):
        try:
            page.goto("about:blank")
            break
        except Exception:
            continue
    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    _wait_page_ready(page)
    return pw, browser, page


def _redirected_to_login(page: Page, login_cfg) -> bool:
    """判断当前页是否被重定向回了登录页（会话失效的典型表现）。

    登录入口按路径边界匹配：配置 https://x.com/app 时不应误匹配
    https://x.com/app2/... 的目标页（子串判断会每次都误判会话失效）。
    """
    url = page.url
    login_base = login_cfg["url"].split("?")[0].rstrip("/")
    path = url.split("?")[0].rstrip("/")
    if path == login_base or path.startswith(login_base + "/"):
        return True
    return "auth/login" in url.lower() or path.endswith("/login")


def _pick_selector(page: Page, candidates, label: str, timeout_each=2500):
    """逐个候选探测，返回第一个可见元素的选择器。"""
    for sel in candidates:
        try:
            el = page.wait_for_selector(sel, timeout=timeout_each, state="visible")
            if el is not None:
                return sel
        except Exception:
            continue
    raise RuntimeError(
        f"登录页未探测到{label}。已尝试：{candidates}。"
        f"请在目标系统中为该系统显式配置对应 selector。"
    )


def perform_login(page: Page, login_cfg):
    user_sels = (
        [login_cfg["username_selector"]] if login_cfg.get("username_selector")
        else USERNAME_CANDIDATES
    )
    pwd_sels = (
        [login_cfg["password_selector"]] if login_cfg.get("password_selector")
        else PASSWORD_CANDIDATES
    )
    submit_sels = (
        [login_cfg["submit_selector"]] if login_cfg.get("submit_selector")
        else SUBMIT_CANDIDATES
    )

    page.goto(login_cfg["url"], wait_until="domcontentloaded", timeout=60000)

    # 登录前置点击（两步式门户，如 Dolibarr 演示站）：
    # 先依次点击入口元素，真实登录表单出现后再走候选链
    for click_sel in login_cfg.get("pre_clicks") or []:
        page.locator(click_sel).first.click(timeout=10000)
        page.wait_for_timeout(1500)

    user_sel = _pick_selector(page, user_sels, "用户名输入框")
    pwd_sel = _pick_selector(page, pwd_sels, "密码输入框")
    submit_sel = _pick_selector(page, submit_sels, "登录按钮")

    # 稳定期：等框架完成挂载与事件绑定（值若被组件初始化重置，下方校验会重试）
    page.wait_for_timeout(2000)
    page.fill(user_sel, login_cfg["username"])
    page.fill(pwd_sel, login_cfg["password"])
    if page.input_value(user_sel) != login_cfg["username"]:
        page.wait_for_timeout(1000)
        page.fill(user_sel, login_cfg["username"])
        page.fill(pwd_sel, login_cfg["password"])

    page.locator(submit_sel).first.click()
    # 登录成功判定：以"提交登录那一刻的页面"为基准——URL 离开该页面，
    # 或用户名输入框从页面消失（SPA 不跳 URL 的场景）。
    # 注意不能用 login_base（配置的登录入口）：两步式门户（pre_clicks）下
    # 提交时已在真实登录表单页（如 /login），若以门户 URL 判定会立刻误判成功。
    # 连续两次采样一致才认为跳转稳定（登录后应用可能还有一次 JS 层重定向）
    submit_url = page.url
    login_base = login_cfg["url"].split("?")[0]
    import time as _time
    deadline = _time.time() + 15
    last_url = None
    while _time.time() < deadline:
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
        _time.sleep(0.5)
    # 超时：抓取登录页上的错误提示（组件库 toast / 通用错误块），给出可诊断信息
    hint = _grab_login_error(page)
    raise RuntimeError(
        "点击登录后页面未跳转（15s）。"
        + (f"页面提示：{hint}。" if hint else "")
        + "常见原因：账号密码错误、登录页存在额外必选项（如需先选择客户端/验证码/短信验证），或登录逻辑依赖浏览器插件。"
    )


def _grab_login_error(page: Page) -> str:
    """采集登录页可能出现的错误提示文本（Element/AntD/oxd/通用）。"""
    selectors = [
        ".el-message--error .el-message__content",
        ".ant-message-error .ant-message-notice-content",
        ".oxd-alert-error, .oxd-input-field-error-message",
        "[class*='toast'][class*='error']",
        "[class*='error'][class*='message']",
    ]
    texts = []
    for sel in selectors:
        try:
            for el in page.locator(sel).all()[:3]:
                t = (el.text_content() or "").strip()
                if t:
                    texts.append(t)
        except Exception:
            continue
    return " / ".join(dict.fromkeys(texts))[:200]


def _wait_page_ready(page: Page, timeout=30000):
    """等待任意可配置元素渲染完成（组合选择器一次等待，覆盖 AntD/Element/XUI/原生）。"""
    ready = ".ant-form-item, .el-form-item, .xui-form-item, .el-select, .xui-select, select, input:not([type=hidden])"
    try:
        # 解析提取只关心 DOM 挂载，不要求可见（首个 input 常为 el-select 只读触发框）
        page.wait_for_selector(ready, timeout=timeout, state="attached")
        # SPA 表单项分批异步挂载：首个控件出现后，再等其余字段渲染完成
        page.wait_for_timeout(2000)
    except Exception as e:
        raise TimeoutError("页面未检测到任何可配置元素") from e


def shutdown(pw, browser):
    try:
        browser.close()
    finally:
        # close 异常也必须停掉 playwright，否则同进程后续 start() 会报
        # "Sync API inside the asyncio loop"
        pw.stop()
