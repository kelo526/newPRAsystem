"""核心数据模型：TargetSystem / ParseRequest / PageProfile / Task / TaskRun。

设计要点：
- 凭证只存 Fernet 密文（password_enc）
- PageProfile 存字段/动作的 JSON 模型（M0 验证过的结构）
- Task 只存业务配置与调度/交付，不存任何 selector（配置驱动回放）
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now()


class TargetSystem(Base):
    """目标业务系统：登录方式与凭证。"""
    __tablename__ = "target_systems"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    login_url: Mapped[str] = mapped_column(String(500))
    username: Mapped[str] = mapped_column(String(120))
    password_enc: Mapped[str] = mapped_column(Text, default="")
    # 可选：登录控件自定义定位（真实系统多样化）
    username_selector: Mapped[str] = mapped_column(String(500), default="")
    password_selector: Mapped[str] = mapped_column(String(500), default="")
    submit_selector: Mapped[str] = mapped_column(String(500), default="")
    # 登录前置点击（两步式门户）：如 ["text=进入系统"]，在登录页依次点击后再登录
    pre_clicks: Mapped[list] = mapped_column(JSON, default=list)
    # 登录后切换页面右上角个人权限角色（部分企业系统按角色开放功能，角色是账号级状态且影响功能可用性）
    role_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    profiles: Mapped[list["PageProfile"]] = relationship(back_populates="system")


class ParseRequest(Base):
    """解析请求：异步执行，产物为 PageProfile。"""
    __tablename__ = "parse_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("target_systems.id"))
    target_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/succeeded/failed
    error: Mapped[str] = mapped_column(Text, default="")
    profile_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class PageProfile(Base):
    """页面档案：解析产物，同一页面多任务共享。"""
    __tablename__ = "page_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("target_systems.id"))
    target_url: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    fields: Mapped[list] = mapped_column(JSON, default=list)   # M0 验证的字段模型
    actions: Mapped[list] = mapped_column(JSON, default=list)
    tables: Mapped[list] = mapped_column(JSON, default=list)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # 人工确认后可用于建任务
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    system: Mapped[TargetSystem] = relationship(back_populates="profiles")
    tasks: Mapped[list["Task"]] = relationship(back_populates="profile")


class Task(Base):
    """自动化任务：档案引用 + 业务配置 + 调度 + 交付。"""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    profile_id: Mapped[int] = mapped_column(ForeignKey("page_profiles.id"))
    config: Mapped[dict] = mapped_column(JSON, default=dict)      # semantic_name → 值/预设
    pre_actions: Mapped[list] = mapped_column(JSON, default=list)  # 如 ["查询"]
    action: Mapped[str] = mapped_column(String(120))               # 主动作 semantic_name
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)     # {"cron": "...", "enabled": true}
    delivery: Mapped[dict] = mapped_column(JSON, default=dict)     # {"type": "email", "to": [...]}
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 可靠性配置（影刀借鉴）：失败自动重试次数；外部触发令牌
    retry_count: Mapped[int] = mapped_column(Integer, default=0)   # 失败后自动重试次数
    export_timeout: Mapped[int] = mapped_column(Integer, default=180)  # 导出中心异步生成等待上限（秒）
    trigger_token: Mapped[str] = mapped_column(String(64), unique=True)  # webhook 外部触发
    last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    profile: Mapped[PageProfile] = relationship(back_populates="tasks")
    runs: Mapped[list["TaskRun"]] = relationship(back_populates="task")


class TaskRun(Base):
    """任务运行记录：状态、步骤日志、产物。"""
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/succeeded/failed
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual/scheduled/webhook
    attempt: Mapped[int] = mapped_column(Integer, default=1)  # 自动重试的第几轮
    steps: Mapped[list] = mapped_column(JSON, default=list)
    artifacts: Mapped[list] = mapped_column(JSON, default=list)  # 相对 artifacts 目录的路径
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    task: Mapped[Task] = relationship(back_populates="runs")


class TaskTemplate(Base):
    """任务模板（影刀借鉴的应用市场/沉淀复用）：从任务抽取业务配置，
    跨档案/跨系统复用——新建任务时预填条件。"""
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # {config, pre_actions, action}
    source_task_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Demand(Base):
    """需求中心（影刀借鉴）：业务人员提交自动化需求，管理员跟踪实施。"""
    __tablename__ = "demands"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    submitter: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/accepted/done/rejected
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
