"""M7 冒烟：SSE 实时推送 + 人工会话导入（免登录解析）。"""
import json
import threading
import time
from pathlib import Path

import requests

BASE = "http://localhost:8000/api"
REPORT_URL = "http://localhost:5173/report"
SESSION_FILE = Path(__file__).parent / "sessions" / "system_1.json"

# --- 1. SSE 实时推送：订阅 → 触发任务 #4 → 验证收到 run 事件 ---
received = []
stop_flag = threading.Event()


def listen():
    try:
        with requests.get(f"{BASE}/events", stream=True, timeout=180) as r:
            for line in r.iter_lines(decode_unicode=True):
                if stop_flag.is_set():
                    break
                if line and line.startswith("data:"):
                    try:
                        received.append(json.loads(line[5:].strip()))
                    except Exception:
                        pass
    except Exception:
        pass  # stop 后连接被切断属正常


th = threading.Thread(target=listen, daemon=True)
th.start()
time.sleep(1.5)  # 等待连接建立

requests.post(f"{BASE}/tasks/4/run")
print("[1] 已触发任务 #4 运行，等待 SSE 事件…")
deadline = time.time() + 150
statuses = set()
while time.time() < deadline:
    statuses = {e["status"] for e in received if e.get("task_id") == 4}
    if "running" in statuses and ("succeeded" in statuses or "failed" in statuses):
        break
    time.sleep(1)
stop_flag.set()
print(f"    收到的 run 事件状态: {sorted(statuses)}（共 {len(received)} 条 data 事件）")
assert "running" in statuses, "未收到 running 事件"
assert "succeeded" in statuses or "failed" in statuses, "未收到终态事件"
print("[1] ✓ SSE 实时推送生效（running → 终态全链路到达）")

# --- 2. 会话导入端点校验 ---
r = requests.put(f"{BASE}/systems/999/session", json={"state": {"cookies": []}})
assert r.status_code == 404, r.text
r = requests.put(f"{BASE}/systems/1/session", json={"state": {"foo": 1}})
assert r.status_code == 400, r.text
print("[2] ✓ 会话导入端点校验生效（系统不存在 404 / 载荷不含 cookies|origins 400）")

# --- 3. 导入会话免登录解析：错误密码 + 导入会话 → 解析成功 ---
state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))  # 备份正确会话
assert state.get("cookies") or state.get("origins")

# 3.1 密码改错并删除现有会话文件（模拟"验证码类系统"无法自动登录）
requests.put(f"{BASE}/systems/1", json={"password": "wrong-password-m7"})
SESSION_FILE.unlink(missing_ok=True)
print("[3] 已置错误密码并清空会话文件（若走自动登录必失败）")

# 3.2 通过 API 导入人工会话
r = requests.put(f"{BASE}/systems/1/session", json={"state": state})
assert r.status_code == 200, r.text
assert SESSION_FILE.exists(), "会话文件未落盘"
print(f"    会话已导入并落盘: {r.json()['saved']}")

# 3.3 触发解析：成功即证明导入的会话免登录生效
pr = requests.post(f"{BASE}/parse-requests", json={
    "system_id": 1, "target_url": REPORT_URL,
}).json()
print(f"    解析请求 #{pr['id']} 已提交，轮询结果…")
deadline = time.time() + 180
while time.time() < deadline:
    pr = requests.get(f"{BASE}/parse-requests/{pr['id']}").json()
    if pr["status"] != "running":
        break
    time.sleep(3)
print(f"    解析状态: {pr['status']} | profile_id: {pr.get('profile_id')} | error: {(pr.get('error') or '')[:120]}")
assert pr["status"] == "succeeded", pr
print("[3] ✓ 错误密码下解析成功 —— 导入会话免登录生效")

# --- 恢复：密码改回 ---
requests.put(f"{BASE}/systems/1", json={"password": "admin123"})
print("    系统密码已恢复 admin123")

print("\n=== M7 冒烟（SSE + 人工会话导入）全部通过 ===")
