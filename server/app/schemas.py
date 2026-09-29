"""Pydantic API 模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- TargetSystem ----------

class SystemCreate(BaseModel):
    name: str
    login_url: str
    username: str
    password: str
    username_selector: str = ""
    password_selector: str = ""
    submit_selector: str = ""
    pre_clicks: list[str] = Field(default_factory=list)  # 登录前置点击（两步式门户）


class SystemOut(BaseModel):
    id: int
    name: str
    login_url: str
    username: str
    username_selector: str
    password_selector: str
    submit_selector: str
    pre_clicks: list
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- ParseRequest ----------

class ParseRequestCreate(BaseModel):
    system_id: int
    target_url: str


class ParseRequestOut(BaseModel):
    id: int
    system_id: int
    target_url: str
    status: str
    error: str
    profile_id: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------- PageProfile ----------

class ProfileOut(BaseModel):
    id: int
    system_id: int
    target_url: str
    version: int
    fields: list
    actions: list
    tables: list
    meta: dict
    confirmed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfileConfirm(BaseModel):
    """字段确认：编辑语义名、增删选项、勾选纳入。"""
    fields: list[dict]
    actions: list[dict]


# ---------- Task ----------

class TaskCreate(BaseModel):
    name: str
    profile_id: int
    config: dict[str, Any] = Field(default_factory=dict)
    pre_actions: list[str] = Field(default_factory=list)
    action: str
    schedule: dict = Field(default_factory=lambda: {"enabled": False, "cron": ""})
    delivery: dict = Field(default_factory=lambda: {"type": "none"})
    retry_count: int = 0  # 失败自动重试次数（0~5）


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    pre_actions: Optional[list[str]] = None
    action: Optional[str] = None
    schedule: Optional[dict] = None
    delivery: Optional[dict] = None
    enabled: Optional[bool] = None
    retry_count: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    name: str
    profile_id: int
    config: dict
    pre_actions: list
    action: str
    schedule: dict
    delivery: dict
    enabled: bool
    retry_count: int
    trigger_token: str
    last_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- TaskRun ----------

class TaskRunOut(BaseModel):
    id: int
    task_id: int
    status: str
    trigger: str
    attempt: int
    steps: list
    artifacts: list
    error: str
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------- TaskTemplate ----------

class TemplateCreate(BaseModel):
    """从既有任务保存为模板：服务端读取任务配置。"""
    task_id: int
    name: str
    description: str = ""


class TemplateOut(BaseModel):
    id: int
    name: str
    description: str
    payload: dict
    source_task_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Demand ----------

class DemandCreate(BaseModel):
    title: str
    description: str = ""
    submitter: str = ""


class DemandUpdate(BaseModel):
    status: Optional[str] = None  # pending/accepted/done/rejected
    note: Optional[str] = None


class DemandOut(BaseModel):
    id: int
    title: str
    description: str
    submitter: str
    status: str
    note: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
