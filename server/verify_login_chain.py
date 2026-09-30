# -*- coding: utf-8 -*-
"""验证登录候选链：在荣耀统一门户登录页上只探测、不提交。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright
from engine.parser.browser import USERNAME_CANDIDATES, PASSWORD_CANDIDATES

LOGIN_URL = "https://authex.hihonor.com/uniportal1/"

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True)
    page = br.new_context().new_page()
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    for label, candidates in (("用户名", USERNAME_CANDIDATES), ("密码", PASSWORD_CANDIDATES)):
        hit = None
        for sel in candidates:
            try:
                el = page.wait_for_selector(sel, timeout=1500, state="visible")
                if el is not None:
                    hit = sel
                    break
            except Exception:
                continue
        print(f"{label}: 命中 → {hit}")
        if hit:
            el = page.locator(hit).first
            print(f"   实际元素: {el.evaluate('e => e.outerHTML.slice(0, 120)')}")
    br.close()
