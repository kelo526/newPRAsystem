"""规则识别：将原始 DOM 候选归一化为业务字段类型 + 动作类型。"""


def normalize_fields(raw_fields):
    """原始字段 → PageProfile.fields 条目（去噪 + 类型归一）。"""
    type_map = {
        "antd_select": "select",
        "el_select": "select",
        "oxd_select": "select",
        "xui_select": "select",
        "native_select": "select",
        "antd_date_range": "date_range",
        "el_date_range": "date_range",
        "xui_date_range": "date_range",
        "antd_input": "text",
        "el_input": "text",
        "oxd_input": "text",
        "xui_input": "text",
        "native_input": "text",
        # ExtJS：文本/下拉统一按 text 处理（下拉以文本输入触发筛选）
        "ext_input": "text",
        "ext_combo": "text",
        "antd_textarea": "textarea",
        "native_textarea": "textarea",
        "antd_upload": "upload",
        "antd_radio": "radio",
        "antd_checkbox": "checkbox",
        "xui_radio": "radio",
        "xui_checkbox": "checkbox",
    }

    fields = []
    for f in raw_fields:
        comp = f.get("component", "")
        ftype = type_map.get(comp)
        if not ftype:
            continue
        # 去噪：无标签、无占位符、无选项的隐藏/无意义控件不纳入
        label = (f.get("label") or "").strip()
        placeholder = (f.get("placeholder") or "").strip()
        options = f.get("options") or []
        if not label and not placeholder and not options:
            continue
        if ftype == "select" and f.get("multiple"):
            ftype = "multi_select"

        labels = [x for x in (label, placeholder) if x]
        fields.append({
            "key": f["id"],
            "label": label or placeholder,
            "semantic_name": None,  # 由 LLM 语义化填充，降级时填 label
            "type": ftype,
            "placeholder": placeholder,
            "options": options if ftype in ("select", "multi_select", "radio", "checkbox") else [],
            "required": False,
            "locator": {
                "component": comp,
                "selector": f["selector"],
                "labels": labels,
            },
        })
    return fields


def normalize_actions(raw_actions):
    """原始按钮 → PageProfile.actions 条目（动作类型猜测）。"""
    actions = []
    for a in raw_actions:
        label = (a.get("label") or "").strip()
        if not label:
            continue
        actions.append({
            "key": a["id"],
            "label": label,
            "semantic_name": None,
            "kind": guess_action_kind(label),
            "locator": {
                "selector": a["selector"],
                "css_selector": a.get("css_selector", ""),
                "texts": [label],
            },
        })
    return actions


def guess_action_kind(label):
    text = label.lower()
    if any(k in text for k in ("查询", "搜索", "search")):
        return "query"
    if any(k in text for k in ("重置", "清空", "reset")):
        return "reset"
    if any(k in text for k in ("导出", "下载", "export", "download")):
        return "export"
    if any(k in text for k in ("上传", "导入", "upload", "import")):
        return "upload"
    if any(k in text for k in ("提交", "保存", "确定", "submit", "save")):
        return "submit"
    return "other"
