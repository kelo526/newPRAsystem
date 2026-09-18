下面按你最初希望的形式，系统介绍**新版 LangChain** 的核心组件、常用函数、对应输入参数，以及配套的 **Pydantic** 组件。示例均采用当前推荐的导入路径。

> 核心原则：  
> 
> - 基础能力优先从 **`langchain_core`** 导入  
> - Agent 从 **`langchain.agents`** 导入  
> - 模型集成从对应的 Provider 包导入，例如 **`langchain_openai`**

---

# 1. LangChain 核心组件概览

LangChain 常见的核心组件包括：

- **Model（模型）**：理解用户输入、生成回复、发起工具调用。
- **Messages（消息）**：保存用户、系统、模型和工具之间的通信内容。
- **Prompt（提示词模板）**：动态组织系统提示词、变量和用户输入。
- **Runnable / LCEL（可组合执行单元）**：通过 `|` 将 Prompt、Model、Parser 等连接为链。
- **Output Parser（输出解析器）**：将模型返回的 `AIMessage` 解析为字符串、JSON 或业务对象。
- **Tools（工具）**：让模型调用 Python 函数、API、检索或内部服务。
- **Agent（智能体）**：自动协调 Model 与 Tools，形成工具调用循环。
- **Memory / State（记忆与状态）**：保存消息历史、会话上下文和业务状态。
- **Middleware（中间件）**：在模型、工具及 Agent 生命周期中插入权限、日志、重试等逻辑。
- **Structured Output（结构化输出）**：用 Pydantic 强约束模型或 Agent 的最终返回结果。

---

# 2. Messages：消息组件

新版消息类从 `langchain_core.messages` 导入：

```python
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
```

## 2.1 `SystemMessage`

用于设定模型角色、行为规则、输出要求和上下文约束。

```python
system_message = SystemMessage(
    content="你是一名专业的 Python 与 LangChain 技术讲师。"
)
```

常见输入参数：

| 参数                  | 类型            | 说明         |
| ------------------- | ------------- | ---------- |
| `content`           | `str` 或内容块列表  | 系统指令内容     |
| `id`                | `str \| None` | 消息唯一标识，可选  |
| `name`              | `str \| None` | 消息发送者名称，可选 |
| `additional_kwargs` | `dict`        | 额外元数据，可选   |
| `response_metadata` | `dict`        | 响应相关元数据，可选 |

## 2.2 `HumanMessage`

表示用户输入。

```python
human_message = HumanMessage(
    content="请解释 LangChain Agent 的工作流程。"
)
```

常见输入参数：

| 参数                  | 类型            | 说明            |
| ------------------- | ------------- | ------------- |
| `content`           | `str` 或内容块列表  | 用户问题、指令或多模态内容 |
| `id`                | `str \| None` | 消息 ID，可选      |
| `name`              | `str \| None` | 用户名称或标识，可选    |
| `additional_kwargs` | `dict`        | 扩展信息，可选       |

## 2.3 `AIMessage`

代表模型输出。模型调用工具时，工具调用请求也会保存在 `AIMessage` 中。

```python
ai_message = AIMessage(
    content="我将调用计算器工具完成计算。"
)
```

常见字段：

| 字段                   | 类型            | 说明                  |
| -------------------- | ------------- | ------------------- |
| `content`            | `str` 或内容块列表  | 模型文本输出              |
| `tool_calls`         | `list`        | 模型请求调用的工具列表         |
| `invalid_tool_calls` | `list`        | 无法解析的工具调用请求         |
| `response_metadata`  | `dict`        | token、模型标识、结束原因等元数据 |
| `usage_metadata`     | `dict`        | 输入、输出及总 token 使用信息  |
| `id`                 | `str \| None` | 消息 ID               |

## 2.4 `ToolMessage`

代表工具执行结果，必须与某个模型发起的工具调用对应。

```python
tool_message = ToolMessage(
    content="计算结果为：80。",
    tool_call_id="call_001",
)
```

常见输入参数：

| 参数             | 类型            | 说明                                       |
| -------------- | ------------- | ---------------------------------------- |
| `content`      | `str`         | 工具执行结果                                   |
| `tool_call_id` | `str`         | **必填**，对应 `AIMessage.tool_calls` 中的调用 ID |
| `name`         | `str \| None` | 工具名称，可选                                  |
| `status`       | `str`         | 工具状态，如 `"success"` 或 `"error"`           |
| `artifact`     | `Any`         | 不需要传给模型的附加原始结果，可选                        |

---

# 3. Chat Model：聊天模型组件

不同模型服务商使用不同集成包。以 OpenAI 为例：

```python
from langchain_openai import ChatOpenAI
```

```python
model = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)
```

调用模型：

```python
response = model.invoke(
    [
        SystemMessage(content="你是一名技术助手。"),
        HumanMessage(content="什么是 LangChain？"),
    ]
)

print(response.content)
```

`invoke()` 的输入可以是字符串、消息列表或 Prompt 渲染结果。

常见模型初始化参数：

| 参数            | 类型              | 说明            |
| ------------- | --------------- | ------------- |
| `model`       | `str`           | 模型名称或模型标识     |
| `temperature` | `float`         | 生成随机性；数值越低越稳定 |
| `max_tokens`  | `int \| None`   | 最大生成 token 数  |
| `timeout`     | `float \| None` | 请求超时时间        |
| `max_retries` | `int`           | 最大重试次数        |
| `api_key`     | `str \| None`   | 服务访问凭证        |
| `base_url`    | `str \| None`   | 自定义兼容 API 地址  |
| `streaming`   | `bool`          | 是否启用流式输出      |

模型常用方法：

| 方法                               | 输入                | 输出          | 用途          |
| -------------------------------- | ----------------- | ----------- | ----------- |
| `invoke(input)`                  | 字符串、消息列表等         | `AIMessage` | 单次同步调用      |
| `stream(input)`                  | 同上                | 迭代器         | 增量获取输出      |
| `batch(inputs)`                  | 输入列表              | 结果列表        | 批量调用        |
| `bind_tools(tools)`              | 工具列表              | 新模型实例       | 让模型具备工具调用能力 |
| `with_structured_output(schema)` | Pydantic Schema 等 | 新模型实例       | 约束模型输出结构    |

---

# 4. Prompt：提示词模板

Prompt 的推荐导入方式：

```python
from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    MessagesPlaceholder,
)
```

## 4.1 `ChatPromptTemplate`

适用于聊天模型，可以定义系统消息和用户消息模板。

```python
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名擅长讲解 {topic} 的技术教师。"),
        ("human", "{question}"),
    ]
)
```

执行模板渲染：

```python
prompt_value = prompt.invoke(
    {
        "topic": "LangChain",
        "question": "什么是 Agent？",
    }
)
```

常见创建方法：

| 方法                                           | 输入参数   | 用途          |
| -------------------------------------------- | ------ | ----------- |
| `ChatPromptTemplate.from_messages(messages)` | 消息模板列表 | 从多条消息模板创建   |
| `ChatPromptTemplate(messages)`               | 消息模板列表 | 直接构造模板      |
| `ChatPromptTemplate.from_template(template)` | `str`  | 从单条用户消息模板创建 |

`from_messages()` 的每一项常见形式：

```python
("system", "你是{role}。")
("human", "{question}")
("placeholder", "{chat_history}")
```

## 4.2 `MessagesPlaceholder`

用于在 Prompt 中插入已有聊天记录。

```python
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名客服助手。"),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}"),
    ]
)
```

调用时传入：

```python
prompt_value = prompt.invoke(
    {
        "chat_history": [
            HumanMessage(content="我想了解 Agent。"),
            AIMessage(content="Agent 可以调用工具完成任务。"),
        ],
        "question": "它和普通聊天有什么区别？",
    }
)
```

`MessagesPlaceholder` 常见参数：

| 参数              | 类型     | 说明                      |
| --------------- | ------ | ----------------------- |
| `variable_name` | `str`  | 变量名，例如 `"chat_history"` |
| `optional`      | `bool` | 是否允许调用时不传该变量            |

---

# 5. Runnable 与 LCEL

LCEL 是 LangChain 的链式组合方式，核心写法：

```python
chain = prompt | model | parser
```

常用模块：

```python
from langchain_core.runnables import (
    RunnableLambda,
    RunnablePassthrough,
    RunnableParallel,
)
```

## 5.1 `RunnableLambda`

把普通 Python 函数包装成链节点。

```python
from langchain_core.runnables import RunnableLambda

to_upper = RunnableLambda(
    lambda text: text.upper()
)

print(to_upper.invoke("hello langchain"))
```

常见输入：

| 参数      | 类型            | 说明             |
| ------- | ------------- | -------------- |
| `func`  | 可调用对象         | 同步处理函数         |
| `afunc` | 可调用对象         | 异步处理函数，可选      |
| `name`  | `str \| None` | Runnable 名称，可选 |

## 5.2 `RunnablePassthrough`

将输入原样透传，常用于在字典链中保留原始输入。

```python
chain = {
    "original": RunnablePassthrough(),
    "uppercase": RunnableLambda(lambda text: text.upper()),
}

print(chain.invoke("hello"))
```

结果：

```python
{
    "original": "hello",
    "uppercase": "HELLO",
}
```

## 5.3 `RunnableParallel`

对同一个输入并行执行多个 Runnable。

```python
from langchain_core.runnables import RunnableParallel

parallel_chain = RunnableParallel(
    uppercase=RunnableLambda(lambda text: text.upper()),
    length=RunnableLambda(lambda text: len(text)),
)

print(parallel_chain.invoke("langchain"))
```

## 5.4 Runnable 的通用方法

所有 Runnable 通常都支持：

| 方法                    | 输入   | 输出         | 说明     |
| --------------------- | ---- | ---------- | ------ |
| `invoke(input)`       | 单个输入 | 单个结果       | 同步执行   |
| `ainvoke(input)`      | 单个输入 | 协程结果       | 异步执行   |
| `batch(inputs)`       | 输入列表 | 输出列表       | 批量执行   |
| `abatch(inputs)`      | 输入列表 | 协程结果       | 异步批量执行 |
| `stream(input)`       | 单个输入 | 迭代器        | 流式输出   |
| `astream(input)`      | 单个输入 | 异步迭代器      | 异步流式输出 |
| `with_config(config)` | 配置字典 | 新 Runnable | 附加运行配置 |

---

# 6. Output Parser：输出解析器

推荐导入：

```python
from langchain_core.output_parsers import (
    StrOutputParser,
    JsonOutputParser,
)
```

## 6.1 `StrOutputParser`

将 `AIMessage` 解析为普通字符串。

```python
from langchain_core.output_parsers import StrOutputParser

parser = StrOutputParser()

text = parser.invoke(
    AIMessage(content="LangChain 用于构建大模型应用。")
)

print(text)
```

它通常用于链的末尾：

```python
chain = prompt | model | StrOutputParser()
```

## 6.2 `JsonOutputParser`

将 JSON 字符串解析为 Python 字典或列表。

```python
from langchain_core.output_parsers import JsonOutputParser

parser = JsonOutputParser()

data = parser.invoke(
    """
    {
        "name": "LangChain",
        "category": "LLM 应用开发框架"
    }
    """
)

print(data["name"])
```

主要风险是：模型可能返回不规范 JSON。因此在需要稳定业务输出时，优先使用后面的 **Pydantic Structured Output**。

---

# 7. Tools：工具组件

推荐导入路径：

```python
from langchain_core.tools import tool
```

## 7.1 使用 `@tool` 定义工具

```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """计算两个整数的乘积。"""
    return a * b
```

直接执行工具：

```python
result = multiply.invoke(
    {
        "a": 6,
        "b": 8,
    }
)

print(result)
```

工具定义中，模型会参考：

- **工具名称**：`multiply`
- **函数 docstring**：工具功能说明
- **参数名与类型注解**：工具参数 Schema
- **参数描述**：如果使用 Pydantic，可以提供更精确的语义说明

## 7.2 `@tool` 常用参数

```python
@tool(
    "employee_search",
    description="根据员工姓名和部门查询员工基础信息。",
)
def search_employee(
    name: str,
    department: str | None = None,
) -> dict:
    """查询员工信息。"""
    return {
        "name": name,
        "department": department,
    }
```

常见参数：

| 参数                           | 类型                        | 说明                             |
| ---------------------------- | ------------------------- | ------------------------------ |
| `name_or_callable`           | `str` 或函数                 | 工具名称，或直接传入函数                   |
| `description`                | `str \| None`             | 工具说明，模型依赖它判断调用时机               |
| `args_schema`                | `type[BaseModel] \| None` | Pydantic 输入参数模型                |
| `return_direct`              | `bool`                    | 为 `True` 时，部分执行框架可直接将工具结果返回    |
| `parse_docstring`            | `bool`                    | 是否解析 Google 风格 docstring 的参数说明 |
| `error_on_invalid_docstring` | `bool`                    | docstring 格式不合法时是否抛错           |

---

# 8. Pydantic：工具参数与结构化数据模型

Pydantic 是 LangChain 中最重要的配套数据验证组件之一。

推荐导入：

```python
from typing import Literal

from pydantic import BaseModel, Field
```

## 8.1 `BaseModel`

用于定义一个结构化对象。

```python
from pydantic import BaseModel

class UserQuestion(BaseModel):
    question: str
    user_id: str | None = None
```

验证字典：

```python
data = {
    "question": "什么是 LangChain？",
    "user_id": "user_001",
}

user_question = UserQuestion.model_validate(data)
print(user_question)
```

转换回字典：

```python
print(user_question.model_dump())
```

## 8.2 `Field`

用于补充字段描述、默认值、约束与示例。

```python
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="检索关键词或用户问题",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="最多返回的结果数量，取值范围为 1 到 20",
    )
```

`Field()` 常见参数：

| 参数                          | 说明                        |
| --------------------------- | ------------------------- |
| `default`                   | 默认值                       |
| `...`                       | 代表字段必须传入                  |
| `default_factory`           | 用函数生成默认值，例如 `list`、`dict` |
| `description`               | 字段语义说明；对工具调用尤其重要          |
| `title`                     | 字段标题                      |
| `examples`                  | 示例值                       |
| `min_length` / `max_length` | 字符串、列表长度约束                |
| `ge` / `gt`                 | 大于等于 / 大于数值约束             |
| `le` / `lt`                 | 小于等于 / 小于数值约束             |
| `pattern`                   | 字符串正则校验                   |
| `exclude`                   | 序列化时是否排除字段                |

## 8.3 `Literal`

用于限制字段只能从指定枚举中选取。

```python
from typing import Literal

class ReportInput(BaseModel):
    language: Literal["zh", "en"] = "zh"
    detail_level: Literal["brief", "normal", "detailed"] = "normal"
```

## 8.4 可选类型

```python
class EmployeeInput(BaseModel):
    name: str
    department: str | None = None
```

其中 `department` 是可选字段。

## 8.5 嵌套 Pydantic 模型

```python
class DateRange(BaseModel):
    start_date: str = Field(
        description="开始日期，格式为 YYYY-MM-DD"
    )
    end_date: str = Field(
        description="结束日期，格式为 YYYY-MM-DD"
    )


class SalesQueryInput(BaseModel):
    region: str = Field(
        description="销售区域"
    )
    date_range: DateRange = Field(
        description="数据查询时间范围"
    )
```

对应输入：

```python
payload = {
    "region": "华北",
    "date_range": {
        "start_date": "2026-09-01",
        "end_date": "2026-09-17",
    },
}

query = SalesQueryInput.model_validate(payload)
print(query.model_dump())
```

---

# 9. Pydantic + Tool：定义严格工具入参

这是实际开发中非常常见的组合。

```python
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.tools import tool
```

```python
class CalculatorInput(BaseModel):
    a: float = Field(
        description="第一个参与运算的数字"
    )
    b: float = Field(
        description="第二个参与运算的数字"
    )
    operation: Literal["add", "subtract", "multiply", "divide"] = Field(
        description="运算类型：add、subtract、multiply 或 divide"
    )
```

```python
@tool(args_schema=CalculatorInput)
def calculator(
    a: float,
    b: float,
    operation: str,
) -> float:
    """执行加、减、乘、除基础运算。"""

    if operation == "add":
        return a + b

    if operation == "subtract":
        return a - b

    if operation == "multiply":
        return a * b

    if operation == "divide":
        if b == 0:
            raise ValueError("除数不能为 0。")
        return a / b

    raise ValueError(f"不支持的运算类型：{operation}")
```

调用：

```python
result = calculator.invoke(
    {
        "a": 25.6,
        "b": 3.2,
        "operation": "divide",
    }
)

print(result)
```

这里 Pydantic 的价值包括：

1. **定义工具参数结构**；
2. **自动校验类型与限制**；
3. **通过 `description` 告诉模型每个参数的真实含义**；
4. **限制模型只能传入指定枚举值**；
5. **让工具 Schema 更清晰、更稳定**。

---

# 10. Agent：智能体组件

新版 Agent 创建入口：

```python
from langchain.agents import create_agent
```

创建 Agent：

```python
agent = create_agent(
    model=model,
    tools=[calculator],
    system_prompt=(
        "你是一名计算助手。"
        "当用户提出计算问题时，优先调用 calculator 工具。"
    ),
)
```

调用 Agent：

```python
from langchain_core.messages import HumanMessage

result = agent.invoke(
    {
        "messages": [
            HumanMessage(content="请计算 256.8 除以 3.2。")
        ]
    }
)

print(result["messages"][-1].content)
```

Agent 的典型执行过程：

```text
HumanMessage
    ↓
Chat Model
    ↓
AIMessage（可能携带 tool_calls）
    ↓
Tool 执行
    ↓
ToolMessage
    ↓
Chat Model 再次处理
    ↓
AIMessage（最终回答）
```

## 10.1 `create_agent()` 常用参数

| 参数                | 类型                             | 说明             |
| ----------------- | ------------------------------ | -------------- |
| `model`           | 模型实例或模型标识                      | Agent 的主模型     |
| `tools`           | `list`                         | 可被调用的工具列表      |
| `system_prompt`   | `str \| SystemMessage \| None` | 系统级行为规则        |
| `middleware`      | `list`                         | 生命周期增强逻辑       |
| `response_format` | Pydantic Schema 等              | 最终结构化输出规范      |
| `checkpointer`    | 状态存储对象                         | 保存及恢复会话状态      |
| `state_schema`    | Schema                         | 自定义 Agent 状态字段 |
| `context_schema`  | Pydantic Schema                | 约束运行时上下文       |
| `name`            | `str \| None`                  | Agent 名称       |

## 10.2 Agent 的主要运行方法

| 方法                     | 输入                  | 说明                 |
| ---------------------- | ------------------- | ------------------ |
| `agent.invoke(input)`  | 状态字典，通常含 `messages` | 同步执行至完成            |
| `agent.stream(input)`  | 状态字典，通常含 `messages` | 流式返回 Agent 执行过程或结果 |
| `agent.ainvoke(input)` | 状态字典                | 异步执行               |
| `agent.astream(input)` | 状态字典                | 异步流式执行             |

最基础的输入形式：

```python
{
    "messages": [
        HumanMessage(content="用户问题")
    ]
}
```

---

# 11. Agent + Pydantic：结构化输出

除了约束 Tool 入参，也可以约束 Agent 最终返回内容。

先定义 Pydantic 响应模型：

```python
from pydantic import BaseModel, Field

class TravelAdvice(BaseModel):
    city: str = Field(
        description="城市名称"
    )
    weather_summary: str = Field(
        description="天气概述"
    )
    clothing_suggestion: str = Field(
        description="穿衣建议"
    )
    umbrella_needed: bool = Field(
        description="是否建议携带雨具"
    )
```

创建 Agent 时传入：

```python
agent = create_agent(
    model=model,
    tools=[],
    system_prompt="你是一名出行建议助手。",
    response_format=TravelAdvice,
)
```

调用：

```python
result = agent.invoke(
    {
        "messages": [
            HumanMessage(
                content="请为北京的晴天生成出行建议。"
            )
        ]
    }
)

structured_result = result["structured_response"]

print(structured_result.city)
print(structured_result.clothing_suggestion)
print(structured_result.umbrella_needed)
```

对应的结构化对象类似：

```python
TravelAdvice(
    city="北京",
    weather_summary="天气晴朗，体感舒适。",
    clothing_suggestion="建议穿着轻薄外套，早晚注意保暖。",
    umbrella_needed=False,
)
```

---

# 12. State 与 Context：状态和运行上下文

## 12.1 State

**State** 是 Agent 执行过程中会保存、累积或变化的数据。最重要的默认字段是：

```python
messages: list
```

你可以加入业务字段，例如用户 ID、任务 ID：

```python
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage

class CustomAgentState(BaseModel):
    messages: list[BaseMessage] = Field(
        default_factory=list,
        description="会话消息历史"
    )
    user_id: str | None = Field(
        default=None,
        description="当前用户标识"
    )
    task_id: str | None = Field(
        default=None,
        description="任务标识"
    )
```

## 12.2 Context

**Context** 通常用于一次运行中相对固定的环境信息，例如：

- 用户身份；
- 权限范围；
- 租户信息；
- 数据库连接；
- 请求追踪 ID；
- 产品配置。

```python
class RuntimeContext(BaseModel):
    user_id: str = Field(
        description="当前用户 ID"
    )
    tenant_id: str = Field(
        description="租户 ID"
    )
    user_role: str = Field(
        description="用户角色"
    )
```

两者区别：

| 概念        | 是否变化            | 典型内容            |
| --------- | --------------- | --------------- |
| `State`   | 会随 Agent 执行不断更新 | 消息历史、工具结果、任务进度  |
| `Context` | 通常在一次执行中固定      | 用户身份、权限、配置、依赖对象 |

---

# 13. Middleware：中间件

Middleware 用于增强 Agent 的执行过程，常用于：

- 模型调用前注入系统上下文；
- 工具调用前做参数校验；
- 工具调用后处理结果；
- 统一日志、追踪、审计；
- 权限控制；
- 异常处理、限流、重试；
- 根据不同任务切换模型。

创建 Agent 时传入：

```python
agent = create_agent(
    model=model,
    tools=[calculator],
    middleware=[],
)
```

其逻辑位置大致如下：

```text
用户输入
  ↓
Middleware：输入预处理
  ↓
Model：推理或请求工具调用
  ↓
Middleware：工具调用前处理
  ↓
Tool：执行
  ↓
Middleware：工具调用后处理
  ↓
Model：整合工具结果
  ↓
最终输出
```

---

# 14. 一份完整的最小示例

下面示例串联了：**Pydantic、Tool、Chat Model、Agent、Messages**。

```python
from typing import Literal

from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


class CalculatorInput(BaseModel):
    """
    计算器工具的输入参数。
    """

    a: float = Field(
        description="第一个数字"
    )
    b: float = Field(
        description="第二个数字"
    )
    operation: Literal["add", "subtract", "multiply", "divide"] = Field(
        description="运算类型"
    )


@tool(args_schema=CalculatorInput)
def calculator(
    a: float,
    b: float,
    operation: str,
) -> float:
    """
    执行加、减、乘、除基础运算。
    """

    if operation == "add":
        return a + b

    if operation == "subtract":
        return a - b

    if operation == "multiply":
        return a * b

    if operation == "divide":
        if b == 0:
            raise ValueError("除数不能为 0。")
        return a / b

    raise ValueError(f"不支持的运算类型：{operation}")


model = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)

agent = create_agent(
    model=model,
    tools=[calculator],
    system_prompt=(
        "你是一名计算助手。"
        "涉及数学运算时，必须调用 calculator 工具。"
    ),
)

result = agent.invoke(
    {
        "messages": [
            HumanMessage(
                content="请计算 125.6 除以 3.2。"
            )
        ]
    }
)

print(result["messages"][-1].content)
```

---

# 15. 最终记忆清单

你可以把下面这些作为新版 LangChain 的核心导入模板：

```python
# Messages
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)

# Prompt
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)

# LCEL / Runnable
from langchain_core.runnables import (
    RunnableLambda,
    RunnablePassthrough,
    RunnableParallel,
)

# Parser
from langchain_core.output_parsers import (
    StrOutputParser,
    JsonOutputParser,
)

# Tool
from langchain_core.tools import tool

# Agent
from langchain.agents import create_agent

# Pydantic
from pydantic import BaseModel, Field

# 模型示例
from langchain_openai import ChatOpenAI
```

**一句话理解它们的关系：**

```text
Messages / Prompt
        ↓
      Model
        ↓
Runnable / LCEL 负责组合
        ↓
Tool 提供外部执行能力
        ↓
Agent 自动规划并调用 Tool
        ↓
Pydantic 约束工具参数与结构化输出
```
