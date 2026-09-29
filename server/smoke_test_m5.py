"""M5 可靠性三件套冒烟：失败重试 / Webhook 触发 / 连续失败告警路径。"""
import time

import requests

BASE = "http://localhost:8000/api"


def wait_run(run_id, timeout=240):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError


# --- 1. 失败重试：建必失败任务（动作不存在），retry_count=2 ---
r = requests.post(f"{BASE}/tasks", json={
    "name": "M5-重试测试-必失败", "profile_id": 1,
    "config": {}, "pre_actions": [], "action": "不存在的动作",
    "schedule": {"enabled": False, "cron": ""}, "delivery": {"type": "none"},
    "retry_count": 2,
})
t = r.json()
assert t.get("retry_count") == 2, t
print(f"[1] 建任务 #{t['id']}（retry_count=2）")
requests.post(f"{BASE}/tasks/{t['id']}/run")
run = wait_run(requests.get(f"{BASE}/runs?task_id={t['id']}").json()[0]["id"])
retry_steps = [s.get("msg", "") for s in run.get("steps", []) if "自动重试" in s.get("msg", "")]
print(f"    最终状态: {run['status']} | attempt: {run.get('attempt')} | 重试日志: {len(retry_steps)} 条")
assert run["status"] == "failed" and run.get("attempt") == 3 and retry_steps, run
print("[1] ✓ 重试逻辑生效（共执行 3 轮：1 次原始 + 2 次重试）")

# --- 2. Webhook 触发：用任务 #4 的 token ---
task4 = requests.get(f"{BASE}/tasks/4").json()
token = task4["trigger_token"]
r = requests.post(f"{BASE}/trigger/{token}")
assert r.status_code == 202, r.text
print(f"[2] Webhook 202 accepted: {r.json()}")
run = wait_run(requests.get(f"{BASE}/runs?task_id=4").json()[0]["id"])
print(f"    运行触发方式: {run['trigger']} | 状态: {run['status']} | 产物: {run['artifacts']}")
assert run["trigger"] == "webhook" and run["status"] == "succeeded", run
print("[2] ✓ Webhook 外部触发运行成功")

# --- 3. 告警路径：同任务再失败一次（连续 2 次失败达阈值，delivery=none 不发送不报错）---
requests.post(f"{BASE}/tasks/{t['id']}/run")
run2 = wait_run(requests.get(f"{BASE}/runs?task_id={t['id']}").json()[0]["id"])
assert run2["status"] == "failed"
print("[3] ✓ 连续失败告警路径执行无异常（delivery=none 静默跳过发送）")

# 清理测试任务
requests.delete(f"{BASE}/tasks/{t['id']}")
print("\n=== M5 可靠性三件套冒烟全部通过 ===")
