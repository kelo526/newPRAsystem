"""M6 冒烟：两步式门户登录（前置点击）+ 任务模板 + 需求中心。"""
import time

import requests

BASE = "http://localhost:8000/api"


def wait_parse(req_id, timeout=180):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/parse-requests/{req_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError


def wait_run(run_id, timeout=240):
    for _ in range(timeout // 3):
        r = requests.get(f"{BASE}/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(3)
    raise TimeoutError


# --- 1. 两步式门户：登录页=门户页，前置点击"进入系统" ---
r = requests.post(f"{BASE}/systems", json={
    "name": "两步式门户演示", "login_url": "http://localhost:5173/portal",
    "username": "admin", "password": "admin123",
    "pre_clicks": ["text=进入系统"],
})
sys_id = r.json()["id"]
assert r.json().get("pre_clicks") == ["text=进入系统"], r.json()
print("[1] 建系统（pre_clicks=['text=进入系统']）")
r = requests.post(f"{BASE}/parse-requests", json={
    "system_id": sys_id, "target_url": "http://localhost:5173/report"})
req = wait_parse(r.json()["id"])
assert req["status"] == "succeeded", req["error"]
prof = requests.get(f"{BASE}/profiles/{req['profile_id']}").json()
print(f"[1] ✓ 经门户页登录+解析成功：{len(prof['fields'])} 字段 / {len(prof['actions'])} 动作")
requests.put(f"{BASE}/profiles/{prof['id']}/confirm",
             json={"fields": prof["fields"], "actions": prof["actions"]})

# 再验证：基于该系统建任务并运行（完整链路走门户）
r = requests.post(f"{BASE}/tasks", json={
    "name": "M6-两步门户任务", "profile_id": prof["id"],
    "config": {"区域": ["华东"]}, "pre_actions": ["查询"], "action": "导出 Excel",
    "schedule": {"enabled": False, "cron": ""}, "delivery": {"type": "none"},
})
tid = r.json()["id"]
requests.post(f"{BASE}/tasks/{tid}/run")
run = wait_run(requests.get(f"{BASE}/runs?task_id={tid}").json()[0]["id"])
assert run["status"] == "succeeded" and run["artifacts"], run.get("error")
print(f"[1] ✓ 门户链路任务运行成功，产物 {run['artifacts']}")

# --- 2. 任务模板：保存 → 列表 → 校验 payload ---
r = requests.post(f"{BASE}/templates", json={
    "task_id": tid, "name": "华东区报表导出模板", "description": "每周导出华东订单"})
tpl = r.json()
assert tpl["payload"]["config"] == {"区域": ["华东"]} and tpl["payload"]["action"] == "导出 Excel"
print(f"[2] ✓ 模板已保存（payload 含条件/前置动作/主动作）")
tpls = requests.get(f"{BASE}/templates").json()
assert any(t["id"] == tpl["id"] for t in tpls)
print(f"[2] ✓ 模板列表 {len(tpls)} 个")

# --- 3. 需求中心：提交 → 受理 → 完成 ---
r = requests.post(f"{BASE}/demands", json={
    "title": "每周一 9 点导出华南区订单周报", "description": "发邮件给运营组", "submitter": "张三"})
d = r.json()
assert d["status"] == "pending"
requests.put(f"{BASE}/demands/{d['id']}", json={"status": "accepted"})
requests.put(f"{BASE}/demands/{d['id']}", json={"status": "done", "note": "已建任务 #4"})
d2 = requests.get(f"{BASE}/demands").json()[0]
assert d2["status"] == "done" and d2["note"]
print(f"[3] ✓ 需求流转：待评估 → 已受理 → 已完成（含跟进备注）")

# 清理
requests.delete(f"{BASE}/tasks/{tid}")
requests.delete(f"{BASE}/templates/{tpl['id']}")
requests.delete(f"{BASE}/demands/{d['id']}")
print("\n=== M6 三能力冒烟全部通过 ===")
