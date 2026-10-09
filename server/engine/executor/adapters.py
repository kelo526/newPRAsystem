"""组件适配器：把"业务配置值"翻译为对具体组件库的交互操作。

M0 覆盖 AntD 全套 + 原生表单；Element UI 适配器在接入真实靶子时启用。
关键经验：AntD 下拉优先用 title 属性精确匹配选项，浮层用 Escape 关闭。
"""
from playwright.sync_api import Page


class AntDSelectAdapter:
    component = "antd_select"

    def apply(self, page: Page, selector: str, value):
        values = value if isinstance(value, list) else [value]
        dropdown = ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        page.locator(selector).first.click()
        for v in values:
            option = page.locator(f'{dropdown} .ant-select-item-option[title="{v}"]')
            if option.count() == 0:  # title 匹配失败时按文本兜底
                option = page.locator(f"{dropdown} .ant-select-item-option", has_text=v)
            option.first.click()
            page.wait_for_timeout(200)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


class AntDDateRangeAdapter:
    component = "antd_date_range"

    def apply(self, page: Page, selector: str, value):
        start, end = value
        inputs = page.locator(f"{selector} input")
        inputs.first.click()
        inputs.first.fill(start)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        inputs.last.click()
        inputs.last.fill(end)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)


class AntDInputAdapter:
    component = "antd_input"

    def apply(self, page: Page, selector: str, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class NativeSelectAdapter:
    component = "native_select"

    def apply(self, page: Page, selector: str, value):
        v = value[0] if isinstance(value, list) else value
        page.locator(selector).first.select_option(label=v)


class NativeInputAdapter:
    component = "native_input"

    def apply(self, page: Page, selector: str, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class ElSelectAdapter:
    component = "el_select"

    def apply(self, page: Page, selector: str, value):
        values = value if isinstance(value, list) else [value]
        dropdown = ".el-select-dropdown:not([style*='display: none'])"
        for v in values:
            page.locator(selector).first.click()
            page.wait_for_selector(
                f"{dropdown} .el-select-dropdown__item", timeout=5000
            )
            page.locator(
                f"{dropdown} .el-select-dropdown__item", has_text=str(v)
            ).first.click()
            page.wait_for_timeout(300)


class ElInputAdapter:
    component = "el_input"

    def apply(self, page: Page, selector: str, value):
        # selector 指向 .el-input 容器，实际输入目标是内部 input
        page.locator(f"{selector} input").first.fill(str(value))


class OxdSelectAdapter:
    component = "oxd_select"

    def apply(self, page: Page, selector: str, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(selector).first.click()
            option = page.locator(
                ".oxd-select-dropdown .oxd-select-option", has_text=str(v)
            )
            page.wait_for_selector(".oxd-select-dropdown .oxd-select-option", timeout=5000)
            option.first.click()
            page.wait_for_timeout(300)


class OxdInputAdapter:
    component = "oxd_input"

    def apply(self, page: Page, selector: str, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class XuiSelectAdapter:
    component = "xui_select"
    DROPDOWN = ".xui-select-dropdown:not([style*='display: none'])"

    def apply(self, page: Page, selector: str, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(selector).first.click()
            page.wait_for_timeout(600)
            dropdown = page.locator(self.DROPDOWN)
            # 普通下拉项
            option = dropdown.locator(".xui-select-dropdown__item", has_text=str(v))
            if option.count() == 0:
                # 树下拉：节点带单选圈时，点文字行不生效，须点圈
                node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                if node.count() == 0:
                    # 子节点折叠未渲染：用下拉内置筛选框搜索
                    filt = dropdown.locator(".xui-select-dropdown__filter input")
                    if filt.count() > 0:
                        filt.first.fill(str(v))
                        page.wait_for_timeout(300)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(1000)
                        node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                    if node.count() == 0 and filt.count() > 0:
                        # 回车无效则点筛选框的搜索图标
                        icon = dropdown.locator(".xui-select-dropdown__filter .fa-search")
                        if icon.count() > 0:
                            icon.first.click()
                            page.wait_for_timeout(1000)
                            node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                    if node.count() == 0:
                        # 自定义树不响应筛选（如部门树）：逐级展开节点后重找
                        if filt.count() > 0:
                            filt.first.fill("")
                            page.wait_for_timeout(500)
                        for _ in range(5):
                            icons = dropdown.locator(".xui-tree-node__expand-icon")
                            expanded_any = False
                            for i in range(icons.count()):
                                ic = icons.nth(i)
                                cls = ic.get_attribute("class") or ""
                                if "expanded" in cls or "is-leaf" in cls:
                                    continue
                                try:
                                    ic.click(timeout=600)
                                    expanded_any = True
                                    page.wait_for_timeout(200)
                                except Exception:
                                    continue
                            page.wait_for_timeout(400)
                            node = dropdown.locator(".xui-tree-node__content", has_text=str(v))
                            if node.count() > 0 or not expanded_any:
                                break
                circle = node.first.locator(".xui-radio")
                option = circle if circle.count() > 0 else node
            option.first.click()
            page.wait_for_timeout(300)
        # xui 树下拉选中后浮层可能不收起，遮挡下方表单控件：Escape + 再点触发框双保险
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if page.locator(self.DROPDOWN).count() > 0:
            page.locator(selector).first.click()
            page.wait_for_timeout(300)


class XuiInputAdapter:
    component = "xui_input"

    def apply(self, page: Page, selector: str, value):
        # selector 指向 .xui-input 容器，实际输入目标是内部 input
        page.locator(f"{selector} input").first.fill(str(value))


class XuiRadioAdapter:
    component = "xui_radio"

    def apply(self, page: Page, selector: str, value):
        v = value[0] if isinstance(value, list) else value
        page.locator(f"{selector} .xui-radio", has_text=str(v)).first.click()
        page.wait_for_timeout(200)


class XuiCheckboxAdapter:
    component = "xui_checkbox"

    def apply(self, page: Page, selector: str, value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            page.locator(f"{selector} .xui-checkbox", has_text=str(v)).first.click()
            page.wait_for_timeout(200)


class ExtInputAdapter:
    """ExtJS 输入框（selector 直接指向 input.x-form-field）。"""

    component = "ext_input"

    def apply(self, page: Page, selector: str, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))


class ExtComboAdapter:
    """ExtJS 下拉：文本填入触发筛选，候选项出现后点选，否则回车确认。"""

    component = "ext_combo"

    def apply(self, page: Page, selector: str, value):
        page.locator(selector).first.click()
        page.locator(selector).first.fill(str(value))
        page.wait_for_timeout(600)
        option = page.locator(".x-boundlist-item", has_text=str(value))
        if option.count() > 0:
            option.first.click()
        else:
            page.keyboard.press("Enter")
        page.wait_for_timeout(200)


ADAPTERS = {a.component: a() for a in [
    AntDSelectAdapter,
    AntDDateRangeAdapter,
    AntDInputAdapter,
    NativeSelectAdapter,
    NativeInputAdapter,
    ElSelectAdapter,
    ElInputAdapter,
    OxdSelectAdapter,
    OxdInputAdapter,
    XuiSelectAdapter,
    XuiInputAdapter,
    XuiRadioAdapter,
    XuiCheckboxAdapter,
    ExtInputAdapter,
    ExtComboAdapter,
]}


def apply_field_value(page: Page, field, value, selector=None):
    comp = field["locator"]["component"]
    adapter = ADAPTERS.get(comp)
    if adapter is None:
        raise NotImplementedError(f"暂无 {comp} 的回放适配器（字段：{field['semantic_name']}）")
    adapter.apply(page, selector or field["locator"]["selector"], value)
