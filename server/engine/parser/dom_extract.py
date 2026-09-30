"""DOM 提取与清洗：从渲染后的页面抽取候选字段、动作、表格。

策略：注入 JS 一次性抽取静态结构（AntD / Element / 原生三套规则），
下拉选项因渲染在 body 末尾的浮层中，需逐个交互式打开抓取。
"""
from playwright.sync_api import Page

EXTRACT_JS = r"""
() => {
  const out = { fields: [], actions: [], tables: [] };

  // 可见性过滤：隐藏对话框/折叠区域（display:none 祖先 → 尺寸为 0）
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  // 页面导航区域排除：业务筛选字段不应在页头/侧栏/页脚
  const inChrome = (el) => !!el.closest(
    'header, nav, aside, footer, .navbar, .el-header, .el-aside, .el-footer, ' +
    '.ant-layout-header, .ant-layout-sider, .ant-layout-footer'
  );

  const cssPath = (el) => {
    if (el.id) return '#' + el.id;
    const parts = [];
    let node = el;
    while (node && node !== document.body && parts.length < 10) {
      let sel = node.tagName.toLowerCase();
      const stable = [...node.classList].filter(c =>
        /^(ant-|el-|xui-)/.test(c) && !/(active|focus|hover|open|visible|hidden|disabled)/.test(c)
      );
      if (stable.length) sel += '.' + stable.slice(0, 3).join('.');
      // 始终带上同级序号，保证生成的 selector 唯一（同构表单/按钮组场景）
      const parent = node.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter(c => c.tagName === node.tagName);
        if (sibs.length > 1) sel += `:nth-of-type(${sibs.indexOf(node) + 1})`;
      }
      parts.unshift(sel);
      node = parent;
    }
    return parts.join(' > ');
  };

  // ===== Ant Design =====
  document.querySelectorAll('.ant-form-item').forEach((item, idx) => {
    if (!visible(item) || inChrome(item)) return;
    const label = ((item.querySelector('.ant-form-item-label label') || {}).textContent || '').trim();
    const control = item.querySelector('.ant-form-item-control');
    if (!control) return;
    const base = { id: 'f_antd_' + idx, label };

    const sel = control.querySelector('.ant-select');
    if (sel) {
      out.fields.push({
        ...base, component: 'antd_select',
        multiple: !!control.querySelector('.ant-select-multiple'),
        placeholder: ((sel.querySelector('.ant-select-selection-placeholder') || {}).textContent || '').trim(),
        selector: cssPath(sel)
      });
      return;
    }
    const picker = control.querySelector('.ant-picker-range') || control.querySelector('.ant-picker');
    if (picker) {
      out.fields.push({ ...base, component: 'antd_date_range', selector: cssPath(picker) });
      return;
    }
    const input = control.querySelector('input.ant-input')
      || control.querySelector('.ant-input-affix-wrapper input')
      || control.querySelector('input:not([type=hidden])');
    if (input) {
      out.fields.push({ ...base, component: 'antd_input', placeholder: input.placeholder || '', selector: cssPath(input) });
      return;
    }
    const ta = control.querySelector('textarea');
    if (ta) { out.fields.push({ ...base, component: 'antd_textarea', placeholder: ta.placeholder || '', selector: cssPath(ta) }); return; }
    const upload = control.querySelector('input[type=file], .ant-upload');
    if (upload) { out.fields.push({ ...base, component: 'antd_upload', selector: cssPath(control.querySelector('.ant-upload') || control) }); return; }
    const radio = control.querySelector('.ant-radio-group');
    if (radio) { out.fields.push({ ...base, component: 'antd_radio', options: [...radio.querySelectorAll('.ant-radio-wrapper')].map(e => e.textContent.trim()), selector: cssPath(radio) }); return; }
    const check = control.querySelector('.ant-checkbox-group');
    if (check) { out.fields.push({ ...base, component: 'antd_checkbox', options: [...check.querySelectorAll('.ant-checkbox-wrapper')].map(e => e.textContent.trim()), selector: cssPath(check) }); return; }
  });

  // ===== OrangeHRM (oxd) =====
  document.querySelectorAll('.oxd-input-group').forEach((g, idx) => {
    if (!visible(g) || inChrome(g)) return;
    const label = ((g.querySelector('label.oxd-label, label') || {}).textContent || '').trim();
    const base = { id: 'f_oxd_' + idx, label };
    const sel = g.querySelector('.oxd-select-wrapper, .oxd-select-text');
    if (sel) {
      const inner = g.querySelector('input');
      out.fields.push({ ...base, component: 'oxd_select', placeholder: (inner && inner.placeholder) || '', selector: cssPath(sel) });
      return;
    }
    const input = g.querySelector('input.oxd-input, input:not([type=hidden])');
    if (input) {
      out.fields.push({ ...base, component: 'oxd_input', placeholder: input.placeholder || '', selector: cssPath(input) });
    }
  });

  // ===== Element UI =====
  document.querySelectorAll('.el-form-item').forEach((item, idx) => {
    if (!visible(item) || inChrome(item)) return;
    const label = ((item.querySelector('.el-form-item__label') || {}).textContent || '').trim();
    const content = item.querySelector('.el-form-item__content');
    if (!content) return;
    const base = { id: 'f_el_' + idx, label };

    const sel = content.querySelector('.el-select');
    if (sel) {
      out.fields.push({
        ...base, component: 'el_select',
        multiple: !!sel.querySelector('.el-select__tags'),
        placeholder: ((sel.querySelector('.el-input__inner') || {}).placeholder || ''),
        selector: cssPath(sel)
      });
      return;
    }
    const de = content.querySelector('.el-date-editor');
    if (de) { out.fields.push({ ...base, component: 'el_date_range', selector: cssPath(de) }); return; }
    const inner = content.querySelector('input.el-input__inner') || content.querySelector('input');
    if (inner) { out.fields.push({ ...base, component: 'el_input', placeholder: inner.placeholder || '', selector: cssPath(inner) }); return; }
  });

  // ===== Element UI 独立组件（filter-container 等无 label 包裹场景） =====
  document.querySelectorAll('.el-select, .el-date-editor, .el-input').forEach((el, idx) => {
    if (el.closest('.el-form-item')) return; // 已由 form-item 规则覆盖
    if (el.classList.contains('el-input') && el.closest('.el-select, .el-date-editor')) return; // 组件内层去重
    if (!visible(el) || inChrome(el)) return;
    const base = { id: 'f_elx_' + idx, label: '' };
    if (el.classList.contains('el-select')) {
      out.fields.push({
        ...base, component: 'el_select',
        multiple: !!el.querySelector('.el-select__tags'),
        placeholder: ((el.querySelector('.el-input__inner') || {}).placeholder || ''),
        selector: cssPath(el)
      });
      return;
    }
    if (el.classList.contains('el-date-editor')) {
      out.fields.push({ ...base, component: 'el_date_range', selector: cssPath(el) });
      return;
    }
    const inner = el.querySelector('input');
    out.fields.push({ ...base, component: 'el_input', placeholder: (inner && inner.placeholder) || '', selector: cssPath(el) });
  });

  // ===== XUI（荣耀内部组件库，Element UI 同源，xui- 前缀） =====
  document.querySelectorAll('.xui-form-item').forEach((item, idx) => {
    if (!visible(item) || inChrome(item)) return;
    const label = ((item.querySelector('.xui-form-item__label') || {}).textContent || '').trim();
    const content = item.querySelector('.xui-form-item__content');
    if (!content) return;
    const base = { id: 'f_xui_' + idx, label };

    const sel = content.querySelector('.xui-select');
    if (sel) {
      out.fields.push({
        ...base, component: 'xui_select',
        multiple: !!sel.querySelector('.xui-select__tags'),
        placeholder: ((sel.querySelector('.xui-input__inner') || {}).placeholder || ''),
        selector: cssPath(sel)
      });
      return;
    }
    const radio = content.querySelector('.xui-radio-group');
    if (radio) {
      out.fields.push({
        ...base, component: 'xui_radio',
        options: [...radio.querySelectorAll('.xui-radio')].map(e =>
          ((e.querySelector('.xui-radio__label') || {}).textContent || e.textContent).trim()
        ).filter(Boolean),
        selector: cssPath(radio)
      });
      return;
    }
    const check = content.querySelector('.xui-checkbox-group');
    if (check) {
      out.fields.push({
        ...base, component: 'xui_checkbox',
        options: [...check.querySelectorAll('.xui-checkbox')].map(e =>
          ((e.querySelector('.xui-checkbox__label') || {}).textContent || e.textContent).trim()
        ).filter(Boolean),
        selector: cssPath(check)
      });
      return;
    }
    const de = content.querySelector('.xui-date-editor');
    if (de) { out.fields.push({ ...base, component: 'xui_date_range', selector: cssPath(de) }); return; }
    const xinput = content.querySelector('.xui-input');
    const inner = content.querySelector('input.xui-input__inner') || content.querySelector('input:not([type=hidden])');
    if (inner) {
      out.fields.push({
        ...base, component: 'xui_input', placeholder: inner.placeholder || '',
        selector: cssPath(xinput || inner)
      });
      return;
    }
  });

  // ===== 原生表单 =====
  document.querySelectorAll(
    'select, textarea, input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=file])'
  ).forEach((el, idx) => {
    // 排除已被组件库规则覆盖的 input（.el-input/.ant-input/.xui-input 自身及内部）
    if (el.closest('.ant-form-item, .el-form-item, .xui-form-item, .ant-select, .ant-picker, .el-select, .el-date-editor, .ant-upload, .el-input, .ant-input, .ant-input-affix-wrapper, .xui-input, .xui-select, .xui-date-editor, .xui-radio-group, .xui-checkbox-group')) return;
    if (!visible(el) || inChrome(el)) return;
    const comp = el.tagName === 'SELECT' ? 'native_select'
      : el.tagName === 'TEXTAREA' ? 'native_textarea'
      : 'native_input';
    out.fields.push({
      id: 'f_nat_' + idx, label: '', component: comp, placeholder: el.placeholder || '',
      options: el.tagName === 'SELECT' ? [...el.options].map(o => o.textContent.trim()) : undefined,
      selector: cssPath(el)
    });
  });

  // ===== 按钮 =====
  document.querySelectorAll('button').forEach((btn, idx) => {
    const text = btn.textContent.replace(/\s+/g, ' ').trim();
    if (!text) return;
    if (btn.closest('.ant-select-dropdown, .el-select-dropdown, .ant-picker-dropdown, .ant-modal, .el-dialog, .ant-dropdown, .ant-popover, .el-popover')) return;
    if (btn.closest('.el-table, .ant-table')) return; // 表格行内操作按钮
    if (!visible(btn) || inChrome(btn)) return;
    out.actions.push({
      id: 'a_' + idx,
      label: text,
      // 按钮文本本身就是最强的语义定位符，优先于结构 cssPath
      selector: `button:has-text("${text.replace(/"/g, '\\"')}")`,
      css_selector: cssPath(btn)
    });
  });

  // ===== 表格 =====
  document.querySelectorAll('.ant-table, .el-table').forEach((t, idx) => {
    out.tables.push({
      id: 't_' + idx,
      component: t.classList.contains('ant-table') ? 'antd_table' : 'el_table',
      columns: [...t.querySelectorAll('th')].map(th => th.textContent.trim()).filter(Boolean),
      selector: cssPath(t)
    });
  });

  return out;
}
"""


def extract_candidates(page: Page):
    """提取静态结构 + 交互式抓取下拉选项，返回原始候选。"""
    data = page.evaluate(EXTRACT_JS)
    for f in data.get("fields", []):
        if f.get("component") == "antd_select":
            f["options"] = _grab_antd_options(page, f["selector"])
        elif f.get("component") == "el_select":
            f["options"] = _grab_el_options(page, f["selector"])
        elif f.get("component") == "oxd_select":
            f["options"] = _grab_oxd_options(page, f["selector"])
        elif f.get("component") == "xui_select":
            f["options"] = _grab_xui_options(page, f["selector"])
        # 原生 select 的 options 在 EXTRACT_JS 中已直接抓取
    return data


def _grab_xui_options(page: Page, selector: str):
    """交互式抓取 XUI 下拉选项（浮层内联在 .xui-select 内，display 控制显隐）。

    普通下拉抓 .xui-select-dropdown__item；树下拉（如部门选择器）
    无下拉项，退而抓 .xui-tree-node 的节点文本。
    """
    opts = []
    try:
        page.locator(selector).first.click()
        dropdown = ".xui-select-dropdown:not([style*='display: none'])"
        try:
            page.wait_for_selector(dropdown, timeout=5000)
        except Exception:
            # 点击未展开（可能点到了图标区域），再试一次
            page.locator(selector).first.click()
            page.wait_for_selector(dropdown, timeout=3000)
        page.wait_for_timeout(500)
        opts = page.eval_on_selector_all(
            f"{dropdown} .xui-select-dropdown__item",
            "els => els.map(e => e.textContent.trim()).filter(Boolean)",
        )
        if not opts or page.locator(f"{dropdown} .xui-tree").count() > 0:
            # 树下拉：逐级展开折叠节点（含懒加载子级），再收集全部节点文本
            for _ in range(6):
                icons = page.locator(f"{dropdown} .xui-tree-node__expand-icon")
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
                if not expanded_any:
                    break
                page.wait_for_timeout(400)
            opts = page.eval_on_selector_all(
                f"{dropdown} .xui-tree-node__label",
                "els => els.map(e => e.textContent.trim()).filter(Boolean)",
            ) or opts
        # 树节点 label 与 content 可能重复命中同一文本，保序去重
        opts = list(dict.fromkeys(opts))
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        opts = []
    return opts


def _grab_oxd_options(page: Page, selector: str):
    """交互式抓取 OrangeHRM oxd 下拉选项。"""
    opts = []
    try:
        page.locator(selector).first.click()
        dropdown = ".oxd-select-dropdown"
        page.wait_for_selector(f"{dropdown} .oxd-select-option", timeout=4000)
        page.wait_for_timeout(400)
        opts = page.eval_on_selector_all(
            f"{dropdown} .oxd-select-option",
            "els => els.map(e => e.textContent.trim()).filter(Boolean)",
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        opts = []
    return opts


def _grab_antd_options(page: Page, selector: str):
    """交互式抓取 AntD 下拉选项（浮层渲染在 body 末尾，需打开后抓取）。"""
    opts = []
    try:
        page.locator(selector).first.click()
        dropdown = ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        page.wait_for_selector(f"{dropdown} .ant-select-item-option", timeout=3000)
        page.wait_for_timeout(300)  # 等待动画与懒加载选项
        opts = page.eval_on_selector_all(
            f"{dropdown} .ant-select-item-option",
            "els => els.map(e => (e.getAttribute('title') || e.textContent).trim())",
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        opts = []
    return opts


def _grab_el_options(page: Page, selector: str):
    """交互式抓取 Element UI 下拉选项。"""
    opts = []
    try:
        page.locator(selector).first.click()
        dropdown = ".el-select-dropdown:not([style*='display: none'])"
        page.wait_for_selector(f"{dropdown} .el-select-dropdown__item", timeout=5000)
        page.wait_for_timeout(500)
        opts = page.eval_on_selector_all(
            f"{dropdown} .el-select-dropdown__item",
            "els => els.map(e => e.textContent.trim())",
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        opts = []
    return opts
