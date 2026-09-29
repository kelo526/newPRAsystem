"""LLM 语义化：用 GLM 把规则识别的字段/动作翻译为业务化名称。

设计原则：LLM 是"草稿生成器"，不是"决策者"——
- 无 API key 或调用失败时，自动降级为规则命名（label 原文），流程不中断
- 产出交由人工确认（M1 的字段确认界面）
"""
import json
import os

from .envcfg import load_env

BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_MODEL = "glm-4.6"

SYSTEM_PROMPT = """你是企业网页自动化平台的字段语义识别器。
给定目标网页解析出的字段与动作候选（JSON 数组），为每个候选补充：
- semantic_name：面向业务人员的简洁中文名称。优先使用网页原文标签；标签缺失时按组件类型与选项内容推断（如"文本输入"、"日期范围"）。动作保持原文（如"导出 Excel"）。
- description：一句话业务含义。

严格保持候选的 id 与顺序不变，不要编造不存在的候选，只输出 JSON 数组。"""

USER_PROMPT = "候选列表如下：\n{candidates}\n\n请输出补充 semantic_name 与 description 后的 JSON 数组。"


def semanticize(fields, actions):
    """原地填充 semantic_name，返回 (fields, actions, used_llm)。"""
    load_env()
    api_key = os.environ.get("ZHIPUAI_API_KEY", "").strip()
    if not api_key:
        return _rule_based_naming(fields, actions, reason="未配置 ZHIPUAI_API_KEY")

    try:
        from openai import OpenAI

        model = os.environ.get("ZHIPUAI_MODEL", "").strip() or DEFAULT_MODEL
        client = OpenAI(api_key=api_key, base_url=BASE_URL)

        candidates = (
            [{"id": f["key"], "类型": f["type"], "网页标签": f["label"], "选项": f["options"][:8]}
             for f in fields]
            + [{"id": a["key"], "类型": "动作", "网页标签": a["label"], "猜测": a["kind"]}
               for a in actions]
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(candidates=json.dumps(candidates, ensure_ascii=False))},
            ],
            temperature=0.1,
        )
        content = _extract_json_array(resp.choices[0].message.content)
        mapping = {item["id"]: item for item in content}
        for f in fields:
            hit = mapping.get(f["key"])
            if hit:
                f["semantic_name"] = hit.get("semantic_name") or f["label"]
                f["description"] = hit.get("description", "")
        for a in actions:
            hit = mapping.get(a["key"])
            if hit:
                a["semantic_name"] = hit.get("semantic_name") or a["label"]
                a["description"] = hit.get("description", "")
        return fields, actions, True
    except Exception as e:  # noqa: BLE001 —— LLM 失败不阻塞解析流程
        print(f"  [llm] 语义化调用失败，降级为规则命名：{e}")
        return _rule_based_naming(fields, actions, reason=str(e))


def _rule_based_naming(fields, actions, reason=""):
    if reason:
        print(f"  [llm] 规则命名模式（{reason}）")
    type_default = {
        "date_range": "日期范围", "select": "下拉选择", "multi_select": "多选筛选",
        "text": "文本输入", "textarea": "文本域", "upload": "文件上传",
        "radio": "单选", "checkbox": "复选",
    }
    for f in fields:
        f["semantic_name"] = f["label"] or type_default.get(f["type"], f["type"])
    for a in actions:
        a["semantic_name"] = a["label"]
    return fields, actions, False


def _extract_json_array(text):
    """从模型输出中提取 JSON 数组（容错 markdown 代码块）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("输出中未找到 JSON 数组")
    return json.loads(text[start : end + 1])
