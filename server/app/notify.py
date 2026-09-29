"""结果通知：SMTP 邮件 / 飞书群机器人 webhook（未配置则跳过）。"""
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from .config import env


def _build_text(task_name: str, run_id: int, success: bool, error: str) -> str:
    status_text = "执行成功" if success else "执行失败"
    detail = (
        "产物已保存至平台，可在运行历史中下载。"
        if success
        else f"失败原因：{error}"
    )
    return (
        f"任务「{task_name}」{status_text}\n\n"
        f"运行编号：{run_id}\n{detail}\n\n—— newPRAsystem 自动化任务平台"
    )


def notify_task_result(delivery: dict, task_name: str, run_id: int, success: bool, error: str):
    delivery = delivery or {}
    dtype = delivery.get("type")
    text = _build_text(task_name, run_id, success, error)

    if dtype == "email":
        _send_email(delivery, text, task_name, success)
    elif dtype == "feishu":
        _send_feishu(delivery, text, task_name, run_id)
    else:
        return


def _send_email(delivery: dict, text: str, task_name: str, success: bool):
    host = env("SMTP_HOST")
    to_list = delivery.get("to") or []
    if not host or not to_list:
        print(f"[notify] SMTP 或收件人未配置，跳过发送（{task_name} "
              f"{'成功' if success else '失败'}）")
        return

    status_text = "执行成功" if success else "执行失败"
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = Header(f"[newPRAsystem] {task_name} {status_text}", "utf-8")
    msg["From"] = env("SMTP_FROM") or env("SMTP_USER")
    msg["To"] = ", ".join(to_list)

    port = int(env("SMTP_PORT", "465"))
    user, pwd = env("SMTP_USER"), env("SMTP_PASS")
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    try:
        if user:
            server.login(user, pwd)
        server.sendmail(msg["From"], to_list, msg.as_string())
    finally:
        server.quit()
    print(f"[notify] 已发送任务结果邮件 → {to_list}")


def _send_feishu(delivery: dict, text: str, task_name: str, run_id: int):
    webhook = (delivery or {}).get("webhook", "").strip()
    if not webhook:
        print(f"[notify] 未配置飞书 webhook，跳过发送（任务 {task_name} 运行 #{run_id}）")
        return
    import requests

    resp = requests.post(
        webhook,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=15,
    )
    ok = resp.status_code == 200 and resp.json().get("code") in (0, None)
    print(f"[notify] 飞书通知{'成功' if ok else '失败'}：{resp.text[:200]}")
