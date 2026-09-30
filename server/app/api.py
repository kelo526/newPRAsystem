"""M1 API：目标系统 / 解析请求 / 档案确认 / 任务 / 运行记录。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import crypto, runner_bridge, scheduler
from .db import SessionLocal
from .models import Demand, PageProfile, ParseRequest, Task, TaskRun, TargetSystem, TaskTemplate
from .schemas import (
    DemandCreate,
    DemandOut,
    DemandUpdate,
    ParseRequestCreate,
    ParseRequestOut,
    ProfileConfirm,
    ProfileOut,
    SystemCreate,
    SystemOut,
    TaskCreate,
    TaskOut,
    TaskRunOut,
    TaskUpdate,
    TemplateCreate,
    TemplateOut,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- 目标系统 ----------

@router.post("/systems", response_model=SystemOut, status_code=201)
def create_system(payload: SystemCreate, db: Session = Depends(get_db)):
    system = TargetSystem(
        name=payload.name,
        login_url=payload.login_url,
        username=payload.username,
        password_enc=crypto.encrypt(payload.password),
        username_selector=payload.username_selector,
        password_selector=payload.password_selector,
        submit_selector=payload.submit_selector,
        pre_clicks=payload.pre_clicks,
        role_name=payload.role_name,
    )
    db.add(system)
    db.commit()
    db.refresh(system)
    return system


@router.get("/systems", response_model=list[SystemOut])
def list_systems(db: Session = Depends(get_db)):
    return db.query(TargetSystem).order_by(TargetSystem.id.desc()).all()


class SystemUpdate(BaseModel):
    name: str | None = None
    login_url: str | None = None
    username: str | None = None
    password: str | None = None  # 传空或不传则保持不变
    username_selector: str | None = None  # 显式登录选择器（None=不修改，空串=清除）
    password_selector: str | None = None
    submit_selector: str | None = None
    pre_clicks: list[str] | None = None  # 登录前置点击（两步式门户）
    role_name: str | None = None  # 登录后切换的个人权限角色（空串=清除）


@router.put("/systems/{system_id}", response_model=SystemOut)
def update_system(system_id: int, payload: SystemUpdate, db: Session = Depends(get_db)):
    """编辑目标系统（改密码/换登录页无需删除重建）。"""
    system = db.get(TargetSystem, system_id)
    if not system:
        raise HTTPException(404, "目标系统不存在")
    for field in ("name", "login_url", "username"):
        value = getattr(payload, field)
        if value:
            setattr(system, field, value)
    for field in ("username_selector", "password_selector", "submit_selector"):
        value = getattr(payload, field)
        if value is not None:
            setattr(system, field, value)
    if payload.password:
        system.password_enc = crypto.encrypt(payload.password)
    if payload.pre_clicks is not None:
        system.pre_clicks = payload.pre_clicks
    if payload.role_name is not None:
        system.role_name = payload.role_name.strip()
    db.commit()
    db.refresh(system)
    return system


@router.delete("/systems/{system_id}", status_code=204)
def delete_system(system_id: int, db: Session = Depends(get_db)):
    system = db.get(TargetSystem, system_id)
    if not system:
        raise HTTPException(404, "目标系统不存在")
    if system.profiles:
        raise HTTPException(400, "该系统下存在页面档案，先删除关联任务与档案")
    db.delete(system)
    db.commit()


# ---------- 解析请求（异步） ----------

@router.post("/parse-requests", response_model=ParseRequestOut, status_code=201)
def create_parse_request(payload: ParseRequestCreate, db: Session = Depends(get_db)):
    system = db.get(TargetSystem, payload.system_id)
    if not system:
        raise HTTPException(404, "目标系统不存在")
    req = ParseRequest(system_id=payload.system_id, target_url=payload.target_url)
    db.add(req)
    db.commit()
    db.refresh(req)
    runner_bridge.start_parse_thread(req.id)
    return req


@router.get("/parse-requests/{req_id}", response_model=ParseRequestOut)
def get_parse_request(req_id: int, db: Session = Depends(get_db)):
    req = db.get(ParseRequest, req_id)
    if not req:
        raise HTTPException(404, "解析请求不存在")
    return req


# ---------- 页面档案 ----------

@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return db.query(PageProfile).order_by(PageProfile.id.desc()).all()


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    prof = db.get(PageProfile, profile_id)
    if not prof:
        raise HTTPException(404, "页面档案不存在")
    return prof


@router.put("/profiles/{profile_id}/confirm", response_model=ProfileOut)
def confirm_profile(profile_id: int, payload: ProfileConfirm, db: Session = Depends(get_db)):
    """字段确认：编辑语义名 / 增删选项 / 勾选纳入，确认后才能建任务。"""
    prof = db.get(PageProfile, profile_id)
    if not prof:
        raise HTTPException(404, "页面档案不存在")
    prof.fields = payload.fields
    prof.actions = payload.actions
    prof.confirmed = True
    db.commit()
    db.refresh(prof)
    return prof


@router.post("/profiles/{profile_id}/reparse", response_model=ParseRequestOut, status_code=201)
def reparse_profile(profile_id: int, db: Session = Depends(get_db)):
    """档案更新：目标网页改版/新增筛选项后重新解析。

    与旧档案按（网页标签+类型）合并：保留已确认语义名；新字段默认不纳入，待人工确认。
    """
    prof = db.get(PageProfile, profile_id)
    if not prof:
        raise HTTPException(404, "页面档案不存在")
    req = ParseRequest(
        system_id=prof.system_id,
        target_url=prof.target_url,
        profile_id=prof.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    runner_bridge.start_parse_thread(req.id)
    return req


# ---------- 任务 ----------

@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    prof = db.get(PageProfile, payload.profile_id)
    if not prof:
        raise HTTPException(404, "页面档案不存在")
    if not prof.confirmed:
        raise HTTPException(400, "页面档案未确认，请先完成字段确认")
    import secrets

    task = Task(
        name=payload.name,
        profile_id=payload.profile_id,
        config=payload.config,
        pre_actions=payload.pre_actions,
        action=payload.action,
        schedule=payload.schedule,
        delivery=payload.delivery,
        retry_count=min(max(payload.retry_count or 0, 0), 5),
        export_timeout=max(payload.export_timeout or 180, 30),
        trigger_token=secrets.token_urlsafe(16),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    scheduler.sync_task(task)
    return task


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.id.desc()).all()
    out = []
    for t in tasks:
        d = TaskOut.model_validate(t).model_dump()
        d["profile_url"] = t.profile.target_url if t.profile else ""
        d["schedule_next"] = None
        job = scheduler.scheduler.get_job(f"task_{t.id}")
        if job is not None and job.next_run_time is not None:
            d["schedule_next"] = job.next_run_time.isoformat()
        out.append(d)
    return out


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    d = TaskOut.model_validate(task).model_dump()
    d["profile_url"] = task.profile.target_url if task.profile else ""
    d["profile_version"] = task.profile.version if task.profile else 1
    return d


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    """配置变更而非流程重建：只改配置/调度，立即生效。"""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    for field in ("name", "config", "pre_actions", "action", "schedule", "delivery", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    if payload.retry_count is not None:
        task.retry_count = min(max(payload.retry_count, 0), 5)
    if payload.export_timeout is not None:
        task.export_timeout = max(payload.export_timeout, 30)
    db.commit()
    db.refresh(task)
    scheduler.sync_task(task)
    return task


@router.post("/trigger/{token}", status_code=202)
def trigger_by_webhook(token: str, db: Session = Depends(get_db)):
    """Webhook 外部触发（影刀借鉴的触发器能力）：供外部系统/小龙虾等调度平台调用。

    用法：POST http://<平台>/api/trigger/<trigger_token>
    """
    task = db.query(Task).filter(Task.trigger_token == token).first()
    if not task:
        raise HTTPException(404, "触发令牌无效")
    if not task.enabled:
        raise HTTPException(409, "任务已停用，请先启用")
    runner_bridge.start_task_thread(task.id, trigger="webhook")
    return {"task_id": task.id, "task_name": task.name, "status": "accepted"}


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    try:
        scheduler.scheduler.remove_job(f"task_{task_id}")
    except Exception:
        pass
    for run in task.runs:
        db.delete(run)
    db.delete(task)
    db.commit()


@router.post("/tasks/{task_id}/run", status_code=202)
def run_task_now(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    runner_bridge.start_task_thread(task_id, trigger="manual")
    return {"status": "accepted"}


@router.post("/tasks/{task_id}/duplicate", response_model=TaskOut, status_code=201)
def duplicate_task(task_id: int, db: Session = Depends(get_db)):
    """任务副本：复制配置后微调，即"临时变更"与"多版本任务"的入口。默认停用调度。"""
    src = db.get(Task, task_id)
    if not src:
        raise HTTPException(404, "任务不存在")
    copy = Task(
        name=f"{src.name}-副本",
        profile_id=src.profile_id,
        config=src.config,
        pre_actions=src.pre_actions,
        action=src.action,
        schedule={**(src.schedule or {}), "enabled": False},
        delivery=src.delivery,
        enabled=False,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    scheduler.sync_task(copy)
    return copy


@router.get("/tasks/{task_id}/export")
def export_task(task_id: int, embed_credentials: bool = True, db: Session = Depends(get_db)):
    """导出任务包为 zip：自包含脚本 + 外部配置文件（task_config.json）。

    配置文件含 username / password / output_dir，使用者在小龙虾等调度平台
    上只需改配置文件即可（密码预填与否由 embed_credentials 控制）。
    """
    import io
    import zipfile
    from urllib.parse import quote

    from fastapi.responses import Response

    from . import exporter

    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    profile = db.get(PageProfile, task.profile_id)
    system = db.get(TargetSystem, profile.system_id)

    script = exporter.export_task_script(task, profile, system)
    config = exporter.export_config_file(task, system, embed_credentials=embed_credentials)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(exporter.script_filename(task), script)
        zf.writestr("task_config.json", config)
    # 文件名：ASCII 兜底 + RFC 5987 中文
    safe = "".join(c for c in task.name if c.isascii() and c not in r'\/:*?"<>|').strip()
    display = quote(exporter.script_filename(task).removesuffix(".py") + ".zip")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="newpra_task_{task.id}{safe and "_" + safe}.zip"; '
                f"filename*=UTF-8''{display}"
            )
        },
    )


# ---------- 运行记录 ----------

@router.get("/runs", response_model=list[TaskRunOut])
def list_runs(task_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(TaskRun).order_by(TaskRun.id.desc())
    if task_id:
        q = q.filter(TaskRun.task_id == task_id)
    return q.limit(min(limit, 200)).all()


@router.get("/runs/{run_id}", response_model=TaskRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(TaskRun, run_id)
    if not run:
        raise HTTPException(404, "运行记录不存在")
    return run


@router.get("/runs/{run_id}/files/{file_path:path}")
def get_run_file(run_id: int, file_path: str):
    """下载运行产物（导出文件/截图/运行摘要）。"""
    base = (runner_bridge.ARTIFACTS_DIR / f"run_{run_id}").resolve()
    target = (base / file_path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(400, "非法路径")
    if not target.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(target, filename=target.name)


# ---------- 任务模板（沉淀复用：从任务抽取业务配置，新建任务时预填） ----------

@router.post("/templates", response_model=TemplateOut, status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    """把既有任务保存为模板：抽取 config/pre_actions/action（不含档案绑定与凭证）。"""
    task = db.get(Task, payload.task_id)
    if not task:
        raise HTTPException(404, "源任务不存在")
    tpl = TaskTemplate(
        name=payload.name,
        description=payload.description,
        payload={
            "config": task.config or {},
            "pre_actions": task.pre_actions or [],
            "action": task.action,
        },
        source_task_id=task.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(TaskTemplate).order_by(TaskTemplate.id.desc()).all()


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tpl = db.get(TaskTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "模板不存在")
    db.delete(tpl)
    db.commit()


# ---------- 需求中心（业务提交自动化需求，管理员跟踪实施） ----------

@router.post("/demands", response_model=DemandOut, status_code=201)
def create_demand(payload: DemandCreate, db: Session = Depends(get_db)):
    demand = Demand(
        title=payload.title,
        description=payload.description,
        submitter=payload.submitter,
    )
    db.add(demand)
    db.commit()
    db.refresh(demand)
    return demand


@router.get("/demands", response_model=list[DemandOut])
def list_demands(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Demand).order_by(Demand.id.desc())
    if status:
        q = q.filter(Demand.status == status)
    return q.all()


@router.put("/demands/{demand_id}", response_model=DemandOut)
def update_demand(demand_id: int, payload: DemandUpdate, db: Session = Depends(get_db)):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(404, "需求不存在")
    if payload.status:
        if payload.status not in ("pending", "accepted", "done", "rejected"):
            raise HTTPException(400, "非法状态")
        demand.status = payload.status
    if payload.note is not None:
        demand.note = payload.note
    db.commit()
    db.refresh(demand)
    return demand


@router.delete("/demands/{demand_id}", status_code=204)
def delete_demand(demand_id: int, db: Session = Depends(get_db)):
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(404, "需求不存在")
    db.delete(demand)
    db.commit()


# ---------- SSE 实时事件流（运行状态推送，替代前端轮询） ----------

@router.get("/events")
async def sse_events():
    """Server-Sent Events：run 事件 {task_id, run_id, status, attempt}。

    前端 EventSource 订阅；任务开始/重试/成功/失败即时推送，
    每 15 秒发心跳注释行保活。客户端断开自动取消订阅。
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    from . import events as events_bus

    q = events_bus.subscribe()

    async def stream():
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event, payload = await asyncio.to_thread(q.get, True, 15)
                    yield f"event: {event}\ndata: {payload}\n\n"
                except Exception:  # queue.Empty 超时 → 心跳
                    yield ": ping\n\n"
        finally:
            events_bus.unsubscribe(q)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 人工会话导入（验证码类系统的插件辅助先行版） ----------

class SessionImport(BaseModel):
    state: dict  # Playwright storage_state：{"cookies": [...], "origins": [...]}


@router.put("/systems/{system_id}/session")
def import_session(system_id: int, payload: SessionImport, db: Session = Depends(get_db)):
    """导入登录会话（storage_state JSON）。

    适用：带验证码/扫码/SSO 的系统无法自动登录时，人在浏览器里登录一次，
    用 Cookie 导出工具（如 EditThisCookie）或 DevTools 复制会话粘贴至此。
    平台存为会话文件，解析与任务运行自动复用；失效自动降级重登（无验证码时）。
    """
    system = db.get(TargetSystem, system_id)
    if not system:
        raise HTTPException(404, "目标系统不存在")
    state = payload.state
    if not isinstance(state, dict) or not (state.get("cookies") or state.get("origins")):
        raise HTTPException(400, "会话格式不正确：需要 Playwright storage_state（含 cookies 或 origins）")
    path = runner_bridge.SESSIONS_DIR / f"system_{system_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"system_id": system_id, "saved": str(path)}
