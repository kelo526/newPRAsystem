"""解析管线 CLI。

用法：
    python -m engine.parser --target-url http://localhost:5173/report \
        --login-url http://localhost:5173/login --username admin --password admin123 \
        --out profiles/demo_report.json [--headed]

流程：登录 → DOM 提取（含交互式下拉选项抓取）→ 规则识别 → LLM 语义化 → PageProfile
"""
import argparse
import sys
from pathlib import Path

from . import browser, dom_extract, llm_semantic, profile, rules


def main():
    ap = argparse.ArgumentParser(description="目标页面解析 → PageProfile")
    ap.add_argument("--target-url", required=True, help="目标报表页面 URL")
    ap.add_argument("--login-url", default=None, help="登录页 URL（不传则直接打开目标页）")
    ap.add_argument("--username", default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--username-selector", default=None, help="登录页用户名输入框选择器（覆盖默认的中文 placeholder 匹配）")
    ap.add_argument("--password-selector", default=None, help="登录页密码输入框选择器")
    ap.add_argument("--out", required=True, help="PageProfile 输出路径")
    ap.add_argument("--headed", action="store_true", help="有头模式（调试用）")
    args = ap.parse_args()

    login_cfg = None
    if args.login_url:
        if not (args.username and args.password):
            sys.exit("--login-url 需要同时提供 --username / --password")
        login_cfg = {
            "url": args.login_url,
            "username": args.username,
            "password": args.password,
        }
        if args.username_selector:
            login_cfg["username_selector"] = args.username_selector
        if args.password_selector:
            login_cfg["password_selector"] = args.password_selector

    print("[1/4] 打开浏览器并登录 ...")
    pw, br, page = browser.open_logged_in_page(args.target_url, login_cfg, headless=not args.headed)
    try:
        print("[2/4] 提取页面元素（含交互式下拉选项抓取）...")
        raw = dom_extract.extract_candidates(page)
        print(f"  原始候选：字段 {len(raw['fields'])} 个，动作 {len(raw['actions'])} 个，表格 {len(raw['tables'])} 个")

        print("[3/4] 规则识别：类型归一与去噪 ...")
        fields = rules.normalize_fields(raw["fields"])
        actions = rules.normalize_actions(raw["actions"])
        print(f"  有效字段 {len(fields)} 个，有效动作 {len(actions)} 个")

        print("[4/4] LLM 语义化命名 ...")
        fields, actions, used_llm = llm_semantic.semanticize(fields, actions)

        prof = profile.new_profile(
            url=args.target_url,
            fields=fields,
            actions=actions,
            tables=raw["tables"],
            meta={"used_llm": used_llm, "login_url": args.login_url},
        )
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        profile.save(prof, out_path)

        print(f"\n✓ PageProfile 已生成：{out_path}")
        print("  字段：")
        for f in fields:
            opts = f"（{len(f['options'])} 个选项）" if f["options"] else ""
            print(f"    - {f['semantic_name']}  [{f['type']}]{opts}")
        print("  动作：")
        for a in actions:
            print(f"    - {a['semantic_name']}  [{a['kind']}]")
    finally:
        browser.shutdown(pw, br)


if __name__ == "__main__":
    main()
