"""调度服务：APScheduler 封装，任务增删改时同步 cron。"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .db import SessionLocal
from .models import Task

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _job_id(task_id: int) -> str:
    return f"task_{task_id}"


def sync_task(task: Task):
    """单个任务的调度同步（创建/更新/删除/启停后调用）。"""
    job_id = _job_id(task.id)
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    sched = task.schedule or {}
    cron = (sched.get("cron") or "").strip()
    if not (task.enabled and sched.get("enabled", True) and cron):
        return
    # 平台内执行：手动/定时触发同一桥接层
    scheduler.add_job(
        "app.runner_bridge:start_task_thread",  # 用文本引用避免序列化闭包
        CronTrigger.from_crontab(cron, timezone="Asia/Shanghai"),
        kwargs={"task_id": task.id, "trigger": "scheduled"},
        id=job_id,
        replace_existing=True,
    )


def sync_all():
    """服务启动时从数据库恢复所有任务调度。"""
    with SessionLocal() as session:
        tasks = session.query(Task).filter(Task.enabled == True).all()  # noqa: E712
        for t in tasks:
            sync_task(t)
