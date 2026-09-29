"""回放 CLI。

用法：
    python -m engine.executor --profile profiles/demo_report.json \
        --task tasks/weekly_east.json [--out artifacts/run1] [--headed]
"""
import argparse
import json
import sys
import time

from ..parser import profile as profile_mod
from . import runner


def main():
    ap = argparse.ArgumentParser(description="PageProfile + 任务配置 → 回放执行")
    ap.add_argument("--profile", required=True, help="PageProfile JSON 路径")
    ap.add_argument("--task", required=True, help="任务配置 JSON 路径")
    ap.add_argument("--out", default=None, help="产物输出目录（默认 artifacts/<任务名>_<时间戳>）")
    ap.add_argument("--headed", action="store_true", help="有头模式（调试用）")
    args = ap.parse_args()

    prof = profile_mod.load(args.profile)
    with open(args.task, "r", encoding="utf-8") as f:
        task = json.load(f)

    out = args.out or f"artifacts/{task['name']}_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"开始执行任务：{task['name']}")
    print(f"目标页面：{prof['url']}")
    try:
        log = runner.run(task, prof, out, headless=not args.headed)
        print(f"\n✓ 任务执行成功，产物目录：{out}")
        for a in log.get("artifacts", []):
            print(f"  - {a}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"\n✗ 任务执行失败：{e}")
        print(f"  失败证据见：{out}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
