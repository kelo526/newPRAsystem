"""语义匹配定位：回放时的"配置驱动"核心。

原则：任务不固化 selector——每次执行现场重新定位。
优先级：解析时 selector → 按 label 文本自愈 → （M1 接入 LLM 兜底）。
"""


def field_selector(page, field):
    """返回字段当前可用的 selector；原 selector 失效时按标签自愈。"""
    sel = field["locator"]["selector"]
    if _alive(page, sel):
        return sel

    comp = field["locator"]["component"]
    # comp -> (表单项容器, 标签选择器, 组件选择器)
    layout = {
        "antd_select": (".ant-form-item", ".ant-form-item-label label", ".ant-select"),
        "antd_date_range": (".ant-form-item", ".ant-form-item-label label", ".ant-picker"),
        "antd_input": (".ant-form-item", ".ant-form-item-label label", "input"),
        "antd_textarea": (".ant-form-item", ".ant-form-item-label label", "textarea"),
        "antd_upload": (".ant-form-item", ".ant-form-item-label label", ".ant-upload"),
        "xui_select": (".xui-form-item", ".xui-form-item__label", ".xui-select"),
        "xui_input": (".xui-form-item", ".xui-form-item__label", ".xui-input"),
        "xui_radio": (".xui-form-item", ".xui-form-item__label", ".xui-radio-group"),
        "xui_checkbox": (".xui-form-item", ".xui-form-item__label", ".xui-checkbox-group"),
        "xui_date_range": (".xui-form-item", ".xui-form-item__label", ".xui-date-editor"),
        "ext_input": ("table.x-form-item", ".x-form-item-label", "input.x-form-field"),
        "ext_combo": ("table.x-form-item", ".x-form-item-label", "input.x-form-field"),
    }.get(comp)
    if layout:
        item_sel, label_sel, component_sel = layout
        for label in field["locator"]["labels"]:
            fallback = (
                f'{item_sel}:has({label_sel}:has-text("{label}")) '
                f'{component_sel}'
            )
            if _alive(page, fallback):
                print(f"  [matcher] 「{field['semantic_name']}」selector 失效，已按标签自愈定位")
                return fallback
    return sel  # 交给 adapter 抛出可读错误


def action_selector(page, action):
    """返回动作按钮当前可用的 selector。优先级：文本 selector > 结构 cssPath。"""
    loc = action["locator"]
    if _alive(page, loc["selector"]):
        return loc["selector"]
    css = loc.get("css_selector", "")
    if css and _alive(page, css):
        print(f"  [matcher] 动作「{action['semantic_name']}」文本定位失效，已回退 cssPath")
        return css
    for text in loc["texts"]:
        fallback = f'button:has-text("{text}")'
        if _alive(page, fallback):
            return fallback
    return loc["selector"]


def _alive(page, selector):
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False
