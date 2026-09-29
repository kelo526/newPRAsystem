"""M2 冒烟测试（两阶段）。

用法：
    python smoke_test_m2.py stage1   # 建系统 + 解析当前页面 + 确认档案
    （此期间人工给 demo-target 增加新字段，模拟网页改版）
    python smoke_test_m2.py stage2   # reparse 发现新增字段 → 纳入 → 建任务运行 → 编辑 → 副本

状态通过 m2_state.json 传递。
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://localhost:8000/api"
STATE = Path("m2_state.json")
NEW_FIELD = "数据范围"  # stage2 之前需在 demo-target 中新增该筛选字段


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


def stage1():
    r = requests.post(f"{BASE}/systems", json={
        "name": "M2档案更新测试",
        "login_url": "http://localhost:5173/login",
        "username": "admin", "password": "admin123",
    })
    sys_id = r.json()["id"]
    r = requests.post(f"{BASE}/parse-requests", json={
        "system_id": sys_id, "target_url": "http://localhost:5173/report",
    })
    req = wait_parse(r.json()["id"])
    assert req["status"] == "succeeded", req["error"]
    profile_id = req["profile_id"]
    prof = requests.get(f"{BASE}/profiles/{profile_id}").json()
    names = [f["semantic_name"] for f in prof["fields"]]
    print(f"[1] 建档：档案 #{profile_id} v{prof['version']}，字段：{names}")
    assert NEW_FIELD not in names

    # 确认档案
    requests.put(f"{BASE}/profiles/{profile_id}/confirm", json={
        "fields": prof["fields"], "actions": prof["actions"],
    })
    STATE.write_text(json.dumps({
        "system_id": sys_id, "profile_id": profile_id,
        "base_version": prof["version"],
    }), encoding="utf-8")
    print(f"[2] 档案已确认。现在请给 demo-target 新增「{NEW_FIELD}」筛选字段，然后运行 stage2")


def stage2():
    st = json.loads(STATE.read_text(encoding="utf-8"))
    profile_id = st["profile_id"]

    # reparse 发现新增字段
    r = requests.post(f"{BASE}/profiles/{profile_id}/reparse")
    req = wait_parse(r.json()["id"])
    assert req["status"] == "succeeded", req["error"]
    prof = requests.get(f"{BASE}/profiles/{profile_id}").json()
    rep = prof["meta"]["last_reparse"]
    print(f"[3] 重解析：v{prof['version']}（原 v{st['base_version']}），新增：{rep['added']}，移除：{rep['removed']}")
    assert prof["version"] == st["base_version"] + 1
    assert any(NEW_FIELD in a for a in rep["added"]), f"{NEW_FIELD} 未识别为新增：{rep}"
    new_fields = [f for f in prof["fields"] if f.get("is_new")]
    assert all(f["included"] is False for f in new_fields), "新字段应默认不纳入"

    # 勾选纳入 + 确认
    for f in prof["fields"]:
        if f.get("is_new"):
            f["included"] = True
    r = requests.put(f"{BASE}/profiles/{profile_id}/confirm", json={
        "fields": prof["fields"], "actions": prof["actions"],
    })
    assert r.json()["confirmed"]
    print(f"[4] 新字段已纳入：{[f['semantic_name'] for f in new_fields]}")

    # 建带新字段条件的任务并运行
    new_name = new_fields[0]["semantic_name"]
    new_value = new_fields[0]["options"][0] if new_fields[0]["options"] else "全部"
    r = requests.post(f"{BASE}/tasks", json={
        "name": f"M2-{new_name}筛选周报",
        "profile_id": profile_id,
        "config": {"统计日期": {"preset": "last_30_days"}, new_name: new_value},
        "pre_actions": ["查询"],
        "action": "导出 Excel",
        "schedule": {"enabled": True, "cron": "0 9 * * 1"},
        "delivery": {"type": "none"},
    })
    task = r.json()
    requests.post(f"{BASE}/tasks/{task['id']}/run")
    runs = requests.get(f"{BASE}/runs", params={"task_id": task["id"]}).json()
    run = wait_run(runs[0]["id"])
    assert run["status"] == "succeeded", run["error"]
    print(f"[5] 带新字段任务运行成功（{new_name}={new_value}），产物：{run['artifacts']}")

    # 编辑任务：换新字段的值（配置变更而非流程重建）
    alt_value = new_fields[0]["options"][1] if len(new_fields[0]["options"]) > 1 else new_value
    r = requests.put(f"{BASE}/tasks/{task['id']}", json={
        "config": {"统计日期": {"preset": "last_30_days"}, new_name: alt_value},
    })
    assert r.status_code == 200
    requests.post(f"{BASE}/tasks/{task['id']}/run")
    runs = requests.get(f"{BASE}/runs", params={"task_id": task["id"]}).json()
    run2 = wait_run(runs[0]["id"])
    assert run2["status"] == "succeeded", run2["error"]
    print(f"[6] 任务配置已改（{new_name}={alt_value}）并成功重跑")

    # 任务副本
    r = requests.post(f"{BASE}/tasks/{task['id']}/duplicate")
    copy = r.json()
    assert copy["enabled"] is False and copy["schedule"]["enabled"] is False
    print(f"[7] 任务副本：#{copy['id']}（默认停用调度）")

    print("\n=== M2 API 冒烟全部通过 ===")


if __name__ == "__main__":
    {"stage1": stage1, "stage2": stage2}[sys.argv[1]]()
