"""M1 API 冒烟测试：系统 → 解析 → 确认 → 建任务（含 cron）→ 手动运行 → 历史查询。"""
import json
import time

import requests

BASE = "http://localhost:8000/api"


def wait_parse(req_id, timeout=180):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/parse-requests/{req_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError("解析超时")


def wait_run(run_id, timeout=180):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError("运行超时")


# 1. 建目标系统
r = requests.post(f"{BASE}/systems", json={
    "name": "订单经营管理系统（演示）",
    "login_url": "http://localhost:5173/login",
    "username": "admin",
    "password": "admin123",
})
r.raise_for_status()
system = r.json()
print(f"[1] 目标系统：#{system['id']} {system['name']}（密码已加密存储）")

# 2. 发起解析（异步）
r = requests.post(f"{BASE}/parse-requests", json={
    "system_id": system["id"],
    "target_url": "http://localhost:5173/report",
})
r.raise_for_status()
parse_req = r.json()
print(f"[2] 解析请求：#{parse_req['id']} 提交，后台执行中 ...")

result = wait_parse(parse_req["id"])
assert result["status"] == "succeeded", f"解析失败：{result['error']}"
profile_id = result["profile_id"]
print(f"[3] 解析完成：档案 #{profile_id}")

# 3. 查看档案并确认
prof = requests.get(f"{BASE}/profiles/{profile_id}").json()
print(f"    字段：{[f['semantic_name'] for f in prof['fields']]}")
print(f"    动作：{[a['semantic_name'] for a in prof['actions']]}")

# 确认前补充一个字段语义名（模拟人工修正）
prof["fields"][1]["semantic_name"] = prof["fields"][1]["semantic_name"]  # 原样
r = requests.put(f"{BASE}/profiles/{profile_id}/confirm", json={
    "fields": prof["fields"],
    "actions": prof["actions"],
})
r.raise_for_status()
assert r.json()["confirmed"] is True
print(f"[4] 档案已确认")

# 4. 建任务：每周一 9 点 + 立即手动运行
r = requests.post(f"{BASE}/tasks", json={
    "name": "华东月度全量导出（M1联调）",
    "profile_id": profile_id,
    "config": {
        "统计日期": {"preset": "last_30_days"},
        "区域": ["华东"],
    },
    "pre_actions": ["查询"],
    "action": "导出 Excel",
    "schedule": {"enabled": True, "cron": "0 9 * * 1"},
    "delivery": {"type": "none"},
})
r.raise_for_status()
task = r.json()
print(f"[5] 任务创建：#{task['id']} {task['name']}（cron 0 9 * * 1）")

# 5. 手动运行
r = requests.post(f"{BASE}/tasks/{task['id']}/run")
r.raise_for_status()
print(f"[6] 手动运行已触发，等待结果 ...")

runs = requests.get(f"{BASE}/runs", params={"task_id": task["id"]}).json()
run = wait_run(runs[0]["id"])
print(f"[7] 运行结果：{run['status']}，产物：{run['artifacts']}")
assert run["status"] == "succeeded", f"失败：{run['error']}"

# 6. 任务列表检查调度信息
tasks = requests.get(f"{BASE}/tasks").json()
t = [x for x in tasks if x["id"] == task["id"]][0]
print(f"[8] 调度同步：next_run = {t['schedule_next']}")

# 7. 产物下载检查
for art in run["artifacts"]:
    resp = requests.get(f"{BASE}/runs/{run['id']}/files/{art}")
    assert resp.status_code == 200, f"产物下载失败：{art}"
    print(f"[9] 产物可下载：{art}（{len(resp.content)} bytes）")

print("\n=== M1 API 全链路冒烟通过 ===")
