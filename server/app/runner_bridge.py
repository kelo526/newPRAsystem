"""解析与执行的桥接层：把 M0 的 CLI 引擎接入平台服务。

- execute_parse：后台线程执行解析管线，产物写入 PageProfile
- execute_task：后台线程执行任务回放，产物写入 TaskRun + artifacts/
"""
import threading
from pathlib import Path

from . import crypto
from .db import SessionLocal
from .models import PageProfile, ParseRequest, Task, TaskRun, TargetSystem

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
SESSIONS_DIR = Path(__file__).resolve().parents[1] / "sessions"


def _state_file(system) -> str | None:
    """按目标系统持久化登录态（storage_state），跨任务运行复用。"""
    return str(SESSIONS_DIR / f"system_{system.id}.json") if system else None


def start_parse_thread(request_id: int):
    threading.Thread(target=_run_parse, args=(request_id,), daemon=True).start()


def _run_parse(request_id: int):
    from engine.parser import browser, dom_extract, llm_semantic, profile as profile_mod, rules

    with SessionLocal() as session:
        req = session.get(ParseRequest, request_id)
        system = session.get(TargetSystem, req.system_id)
        target_url, system_id = req.target_url, req.system_id
        reparse_profile_id = req.profile_id
        login_cfg = _build_login_cfg(system)
        req.status = "running"
        session.commit()

    pw = br = None
    try:
        pw, br, page = browser.open_logged_in_page(
            target_url, login_cfg, headless=True, state_file=_state_file(system)
        )
        raw = dom_extract.extract_candidates(page)
        fields = rules.normalize_fields(raw["fields"])
        actions = rules.normalize_actions(raw["actions"])
        fields, actions, used_llm = llm_semantic.semanticize(fields, actions)

        with SessionLocal() as session:
            if reparse_profile_id:
                # 档案更新：与旧档案按（网页标签 + 类型）合并，
                # 保留用户确认过的语义名与纳入标记；新字段默认不纳入，待人工确认
                prof = session.get(PageProfile, reparse_profile_id)
                if prof is None:
                    raise ValueError(f"待更新档案 #{reparse_profile_id} 不存在")
                fields, actions, diff = _merge_profile(prof.fields, prof.actions, fields, actions)
                prof.fields = fields
                prof.actions = actions
                prof.tables = raw.get("tables", [])
                prof.version = (prof.version or 1) + 1
                prof.meta = {
                    **(prof.meta or {}),
                    "used_llm": used_llm,
                    "last_reparse": {
                        "added": diff["added"],
                        "removed": diff["removed"],
                        "at": _now().isoformat(),
                    },
                }
                session.flush()
                req = session.get(ParseRequest, request_id)
                req.status = "succeeded"
                req.profile_id = prof.id
                req.finished_at = _now()
                session.commit()
            else:
                prof = PageProfile(
                    system_id=system_id,
                    target_url=target_url,
                    fields=fields,
                    actions=actions,
                    tables=raw.get("tables", []),
                    meta={"used_llm": used_llm},
                    confirmed=False,
                )
                session.add(prof)
                session.flush()
                req = session.get(ParseRequest, request_id)
                req.status = "succeeded"
                req.profile_id = prof.id
                req.finished_at = _now()
                session.commit()
    except Exception as e:  # noqa: BLE001
        with SessionLocal() as session:
            req = session.get(ParseRequest, request_id)
            req.status = "failed"
            req.error = str(e)[:2000]
            req.finished_at = _now()
            session.commit()
    finally:
        if br is not None:
            browser.shutdown(pw, br)


def _field_key(f: dict):
    return ((f.get("label") or f.get("placeholder") or ""), f.get("type"))


def _merge_profile(old_fields, old_actions, new_fields, new_actions):
    """按（网页标签 + 类型）匹配合并：保留旧语义名与纳入标记；新字段标记待纳入。"""
    old_f = {_field_key(f): f for f in (old_fields or [])}
    old_a = {a.get("label"): a for a in (old_actions or [])}

    added, removed = [], []
    merged_fields = []
    for nf in new_fields:
        hit = old_f.get(_field_key(nf))
        if hit:
            nf["semantic_name"] = hit.get("semantic_name") or nf["semantic_name"]
            nf["included"] = hit.get("included", True)
        else:
            nf["included"] = False
            nf["is_new"] = True
            added.append(nf["semantic_name"] or nf["label"] or nf["placeholder"])
        merged_fields.append(nf)

    new_keys = {_field_key(f) for f in new_fields}
    for k, of in old_f.items():
        if k not in new_keys and (of.get("included", True)):
            removed.append(of.get("semantic_name") or str(k))

    merged_actions = []
    for na in new_actions:
        hit = old_a.get(na.get("label"))
        if hit:
            na["semantic_name"] = hit.get("semantic_name") or na["semantic_name"]
            na["included"] = hit.get("included", True)
        else:
            na["is_new"] = True
            na["included"] = True
        merged_actions.append(na)

    return merged_fields, merged_actions, {"added": added, "removed": removed}


def start_task_thread(task_id: int, trigger: str = "manual"):
    threading.Thread(target=_run_task, args=(task_id, trigger), daemon=True).start()


def _run_task(task_id: int, trigger: str):
    from engine.executor import runner

    with SessionLocal() as session:
        task = session.get(Task, task_id)
        profile = session.get(PageProfile, task.profile_id)
        system = session.get(TargetSystem, profile.system_id)

        # 转换为 M0 执行引擎的输入格式
        task_dict = {
            "name": task.name,
            "login": _build_login_cfg(system),
            "config": task.config,
            "pre_actions": task.pre_actions,
            "action": task.action,
            "export_timeout": getattr(task, "export_timeout", None) or 180,
            "role_switch": getattr(system, "role_name", "") or None,
        }
        profile_dict = {
            "url": profile.target_url,
            "fields": profile.fields,
            "actions": profile.actions,
            "tables": profile.tables,
        }
        run = TaskRun(task_id=task_id, status="running", trigger=trigger)
        session.add(run)
        session.flush()
        run_id = run.id
        delivery = task.delivery or {}
        task_name = task.name
        retry_count = min(int(task.retry_count or 0), 5)
        state_file = _state_file(system)
        session.commit()

    out_dir = ARTIFACTS_DIR / f"run_{run_id}"

    # 失败自动重试（影刀借鉴的异常处理能力）：最多重试 retry_count 轮，
    # 每轮重试前清空会话缓存（登录态失效是常见失败原因）
    from . import events
    events.publish_run(task_id, run_id, "running")
    last_err = ""
    for attempt in range(1, retry_count + 2):
        if attempt > 1:
            run.status = "retrying"
            with SessionLocal() as session:
                r = session.get(TaskRun, run_id)
                r.steps = [{"msg": f"第 {attempt - 1} 次执行失败，自动重试（{attempt}/{retry_count + 1}）..."}]
                session.commit()
            events.publish_run(task_id, run_id, "retrying", attempt)
            print(f"[retry] 任务 {task_id} 第 {attempt} 轮执行")
        try:
            log = runner.run(task_dict, profile_dict, out_dir, state_file=state_file)
            # 产物路径统一为相对本次 run 目录、正斜杠分隔（便于前端直接拼接下载 URL）
            rel_artifacts = []
            for a in log.get("artifacts", []):
                p = Path(a)
                try:
                    rel = p.resolve().relative_to(out_dir.resolve())
                except ValueError:
                    rel = p
                rel_artifacts.append(rel.as_posix())
            with SessionLocal() as session:
                run = session.get(TaskRun, run_id)
                run.status = "succeeded"
                run.attempt = attempt
                run.steps = log.get("steps", [])
                run.artifacts = rel_artifacts
                run.error = ""
                run.finished_at = _now()
                _touch_task(session, task_id)
                session.commit()
            events.publish_run(task_id, run_id, "succeeded", attempt)
            _notify(delivery, task_name, run_id, True, "")
            return
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt <= retry_count:
                state_file = None if attempt == 1 else state_file  # 首次失败后下一轮弃用会话
                continue
            break

    # 最终失败：记录 + 连续失败告警
    with SessionLocal() as session:
        run = session.get(TaskRun, run_id)
        run.status = "failed"
        run.attempt = 1 if retry_count == 0 else retry_count + 1
        run.error = last_err[:2000]
        run.finished_at = _now()
        _touch_task(session, task_id)
        session.commit()
    events.publish_run(task_id, run_id, "failed")
    _notify(delivery, task_name, run_id, False, last_err)
    _alert_if_consecutive_fail(task_id, task_name, delivery, last_err)


ALERT_FAIL_THRESHOLD = 2  # 连续失败达到此次数触发告警


def _alert_if_consecutive_fail(task_id: int, task_name: str, delivery: dict, error: str):
    """连续失败告警（影刀借鉴的监控告警能力）：达到阈值时发一次通知。

    只在"刚刚达到阈值"时发（前一次成功或次数恰为阈值），避免重复轰炸。
    """
    try:
        with SessionLocal() as session:
            recent = (
                session.query(TaskRun)
                .filter(TaskRun.task_id == task_id)
                .order_by(TaskRun.id.desc())
                .limit(ALERT_FAIL_THRESHOLD)
                .all()
            )
            fails = [r for r in recent if r.status == "failed"]
            if len(recent) < ALERT_FAIL_THRESHOLD or len(fails) < len(recent):
                return  # 未达阈值 / 中间有成功
        from . import notify
        notify.notify_task_result(
            delivery, f"[告警] {task_name}（连续 {ALERT_FAIL_THRESHOLD} 次失败，请检查目标页面或凭证）",
            None, False, error[:500],
        )
    except Exception as e:  # noqa: BLE001 —— 告警失败不影响主流程
        print(f"[alert] 连续失败告警发送失败：{e}")


def _build_login_cfg(system: TargetSystem):
    if system is None:
        return None
    cfg = {
        "url": system.login_url,
        "username": system.username,
        "password": crypto.decrypt(system.password_enc),
    }
    if system.username_selector:
        cfg["username_selector"] = system.username_selector
    if system.password_selector:
        cfg["password_selector"] = system.password_selector
    if system.submit_selector:
        cfg["submit_selector"] = system.submit_selector
    if getattr(system, "pre_clicks", None):
        cfg["pre_clicks"] = system.pre_clicks
    return cfg


def _touch_task(session, task_id: int):
    task = session.get(Task, task_id)
    if task:
        task.last_run_at = _now()


def _notify(delivery: dict, task_name: str, run_id: int, success: bool, error: str):
    try:
        from . import notify
        notify.notify_task_result(delivery, task_name, run_id, success, error)
    except Exception as e:  # noqa: BLE001 —— 通知失败不影响任务状态
        print(f"[notify] 通知发送失败：{e}")


def _now():
    from datetime import datetime
    return datetime.now()
