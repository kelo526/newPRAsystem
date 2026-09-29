"""PageProfile：页面档案数据结构（M0 版本）。

页面档案是解析管线的产物、回放引擎的输入：
- fields：页面上可配置的业务字段（含类型、选项、定位 hints）
- actions：可执行的动作（查询/导出/上传等）
- 不固化任何"用户配置值"——配置值属于 Task，不属于 PageProfile
"""
import json
import time


def new_profile(url, fields, actions, tables=None, meta=None):
    return {
        "url": url,
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fields": fields,
        "actions": actions,
        "tables": tables or [],
        "meta": meta or {},
    }


def save(profile, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
