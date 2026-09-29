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
]}


def apply_field_value(page: Page, field, value, selector=None):
    comp = field["locator"]["component"]
    adapter = ADAPTERS.get(comp)
    if adapter is None:
        raise NotImplementedError(f"暂无 {comp} 的回放适配器（字段：{field['semantic_name']}）")
    adapter.apply(page, selector or field["locator"]["selector"], value)
