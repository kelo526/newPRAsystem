"""复杂导出四场景实测：直接下载 / 新窗口 / 弹窗 / 异步导出中心（防误点）。

通过平台 API 全链路验证（等同用户在向导与任务页的操作）。
"""
import time

import requests

BASE = "http://localhost:8000/api"
TARGET = "http://localhost:5173/export-demo"


def wait_parse(req_id, timeout=180):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/parse-requests/{req_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError


def wait_run(run_id, timeout=300):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError


# 1. 建系统 + 解析导出中心演示页
r = requests.post(f"{BASE}/systems", json={
    "name": "复杂导出演示", "login_url": "http://localhost:5173/login",
    "username": "admin", "password": "admin123",
})
sys_id = r.json()["id"]
r = requests.post(f"{BASE}/parse-requests", json={"system_id": sys_id, "target_url": TARGET})
req = wait_parse(r.json()["id"])
assert req["status"] == "succeeded", req["error"]
prof = requests.get(f"{BASE}/profiles/{req['profile_id']}").json()
acts = [a["semantic_name"] for a in prof["actions"]]
print(f"[1] 解析成功：字段 {len(prof['fields'])} 个，动作 {acts}")
requests.put(f"{BASE}/profiles/{prof['id']}/confirm", json={
    "fields": prof["fields"], "actions": prof["actions"]})
print("[2] 档案已确认")

# 2. 四场景任务
SCENARIOS = [
    ("直接下载", "导出 Excel"),
    ("新窗口", "导出（新窗口）"),
    ("弹窗确认", "导出（弹窗确认）"),
    ("异步导出中心", "提交导出任务"),
]
results = {}
for name, action in SCENARIOS:
    r = requests.post(f"{BASE}/tasks", json={
        "name": f"复杂导出-{name}", "profile_id": prof["id"],
        "config": {"区域": ["华东"]},
        "pre_actions": ["查询"], "action": action,
        "schedule": {"enabled": False, "cron": ""},
        "delivery": {"type": "none"},
    })
    task_id = r.json()["id"]
    requests.post(f"{BASE}/tasks/{task_id}/run")
    runs = requests.get(f"{BASE}/runs", params={"task_id": task_id}).json()
    run = wait_run(runs[0]["id"], timeout=260)
    ok = run["status"] == "succeeded"
    arts = run.get("artifacts", [])
    results[name] = (ok, arts)
    print(f"[3] 场景「{name}」: {'✓ 成功' if ok else '✗ 失败 ' + run.get('error', '')[:120]}  产物: {arts}")
    if not ok:
        print("   步骤:", [s.get("msg") for s in run.get("steps", [])])

# 3. 校验：文件名应与场景匹配；异步场景绝不能是"同事"的文件
print("\n===== 校验 =====")
all_ok = True
for name, (ok, arts) in results.items():
    if not ok:
        all_ok = False
        continue
    f = arts[0].split("/")[-1] if arts else ""
    if name == "直接下载":
        expect = "订单报表_直接_"
    elif name == "新窗口":
        expect = "订单报表_新窗口_"
    elif name == "弹窗确认":
        expect = "订单报表_弹窗_"
    else:
        expect = "订单报表_异步任务_"
    hit = expect in f
    wrong = "同事" in f
    print(f"  {name}: 文件 {f} → {'✓ 匹配' if hit else '✗ 不匹配'}{'（误点他人文件！）' if wrong else ''}")
    if not hit or wrong:
        all_ok = False

print("\n" + ("=== 四场景全部通过（含防误点） ===" if all_ok else "=== 存在失败场景，见上 ==="))
