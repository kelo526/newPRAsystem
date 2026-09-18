# Skill：构建“稳定内核 + 可变配置 + 可插拔扩展”的大型项目

## 1. 适用场景

本 Skill 适用于以下类型的项目：

- 业务规则复杂、需求频繁变化的系统
- 多产品、多客户、多环境、多流程的项目
- 自动化平台、工作流平台、AI 应用平台、运营后台
- 需要长期迭代、多人协作、模块持续增加的大型项目
- 希望提升**可读性、可扩展性、可测试性、可维护性**的代码库

它解决的核心问题是：

> 如何避免大型项目逐渐演变成“逻辑写死、条件分支爆炸、修改一处影响多处、没人敢动”的代码泥潭。

---

# 2. 核心方法论

## 稳定内核 + 可变配置 + 可插拔扩展

> **先识别不变的骨架，再将可变因素参数化；先建立统一契约，再让不同能力自由组合。**

大型项目中，需求看起来千差万别，但通常可以拆成三层：

1. **稳定内核（Kernel）**  
   多数场景都会复用、变化较慢的执行流程、领域规则和基础能力。

2. **配置层（Configuration）**  
   随业务、客户、环境、页面、策略、参数而变化的内容。

3. **插件层（Plugin / Extension）**  
   配置无法充分表达、需要定制代码实现的特殊能力。

可以将它概括为：

> **把变化从代码中移到配置中，把差异从分支判断中移到插件中，把协作从调用细节中提升到统一协议中。**

---

# 3. 从案例中提炼出的工程原则

## 3.1 不要直接为“某个需求”写代码，要先判断它属于哪一类变化

面对一个新需求时，不要立即新增 `if-else`、复制代码或新建一套流程。

先问三个问题：

### 问题一：这是稳定能力，还是一次性业务差异？

例如：

- 登录、鉴权、数据校验、任务调度、日志记录、失败重试：通常是**稳定能力**
- 某个客户的字段名、某个页面的选择器、某个业务的阈值：通常是**配置差异**
- 某个渠道特殊登录流程、某种复杂数据转换：通常是**插件扩展**

### 问题二：未来是否还会出现同类需求？

如果很可能再出现，那么不要只为当前需求写一段逻辑，而应先抽象出通用模型。

### 问题三：配置能否表达？

- **能表达**：使用配置，不要修改核心代码。
- **不能表达，但模式可复用**：定义插件接口。
- **只是一次性特殊逻辑**：局部实现，但要隔离边界，避免污染核心流程。

---

## 3.2 先定义“协议”，再实现“功能”

大型项目可维护性的关键，往往不是类有多少，而是模块之间有没有清晰、稳定的**契约**。

LangChain 的 `Runnable` 就是一个典型案例：不管是模型、提示词、检索器还是解析器，都遵循统一调用方式，因此可以自由组合。

在自己的项目中，也应为核心能力定义统一协议。

例如，一个任务处理系统可以定义：

```python
from abc import ABC, abstractmethod
from typing import Any


class TaskHandler(ABC):
    """所有任务处理器必须遵守的统一协议。"""

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """执行任务并返回标准结果。"""
        raise NotImplementedError
```

不同任务只需要实现这个协议：

```python
class ExportReportHandler(TaskHandler):
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "success",
            "file_path": "/tmp/report.xlsx",
        }


class SendNotificationHandler(TaskHandler):
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "success",
            "message_id": "msg_001",
        }
```

这样做的收益是：

- 调用方不需要知道具体实现细节；
- 新增实现不需要修改原有调用流程；
- 可以轻松替换、组合、测试和模拟实现；
- 每个模块都拥有明确的输入、输出和责任边界。

> **接口不是为了“抽象而抽象”，而是为了让变化被隔离，让组合成为可能。**

---

# 4. 大型项目的推荐架构

建议按“内核、领域、应用、扩展、基础设施”划分，而不是按技术文件类型随意堆叠。

```text
project/
├── core/                  # 稳定内核：协议、通用模型、执行引擎
│   ├── contracts/         # 接口、抽象类、DTO、事件定义
│   ├── engine/            # 编排、调度、执行、生命周期
│   ├── config/            # 配置加载、校验、默认值处理
│   └── exceptions/        # 统一异常体系
│
├── domain/                # 核心业务领域规则
│   ├── order/
│   ├── customer/
│   └── report/
│
├── application/           # 用例层：协调领域对象完成业务流程
│   ├── services/
│   ├── commands/
│   └── queries/
│
├── plugins/               # 可插拔扩展实现
│   ├── channel_a/
│   ├── channel_b/
│   └── custom_processors/
│
├── infrastructure/        # 外部依赖适配：数据库、消息队列、第三方接口
│   ├── database/
│   ├── cache/
│   ├── http/
│   └── messaging/
│
├── configs/               # 配置文件，不承载核心业务逻辑
│   ├── dev.yaml
│   ├── test.yaml
│   └── production.yaml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── main.py                # 应用装配入口
```

核心思想是：

- `core` 尽量稳定，变更要谨慎；
- `domain` 表达业务本质，而不是数据库或接口细节；
- `application` 负责组织业务用例；
- `plugins` 承担差异化能力；
- `infrastructure` 负责与外部世界交互；
- `configs` 负责参数和规则，而不承担无限复杂的程序逻辑。

---

# 5. 设计准则

## 5.1 单一职责：一个模块只回答一个问题

不好的代码通常会把多个责任揉在一起：

```python
def export_data():
    # 读取配置
    # 查询数据库
    # 清洗数据
    # 生成 Excel
    # 上传文件
    # 发送通知
    # 记录日志
    pass
```

这种代码的问题是：任何一点变化都可能影响整体，测试也困难。

更好的拆分方式：

```python
class DataQueryService:
    def query(self, condition: dict) -> list[dict]:
        ...


class DataTransformer:
    def transform(self, records: list[dict]) -> list[dict]:
        ...


class ReportExporter:
    def export(self, records: list[dict]) -> str:
        ...


class NotificationService:
    def notify(self, file_path: str) -> None:
        ...
```

应用服务负责协调：

```python
class ExportReportUseCase:
    def execute(self, condition: dict) -> str:
        records = self.query_service.query(condition)
        transformed = self.transformer.transform(records)
        file_path = self.exporter.export(transformed)
        self.notification_service.notify(file_path)
        return file_path
```

> **类应该有明确职责，函数应该有明确意图，模块应该有明确边界。**

---

## 5.2 依赖抽象，而不是依赖具体实现

业务代码不要直接绑定数据库、HTTP 客户端、具体厂商 SDK 或某一种消息队列。

错误示例：

```python
class OrderService:
    def create_order(self, data: dict):
        mysql_client.insert("orders", data)
        redis_client.set("latest_order", data["id"])
```

更好的方式是先定义协议：

```python
from abc import ABC, abstractmethod


class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: dict) -> None:
        raise NotImplementedError


class Cache(ABC):
    @abstractmethod
    def set(self, key: str, value: str) -> None:
        raise NotImplementedError
```

业务层只依赖抽象：

```python
class OrderService:
    def __init__(self, repository: OrderRepository, cache: Cache):
        self.repository = repository
        self.cache = cache

    def create_order(self, order: dict) -> None:
        self.repository.save(order)
        self.cache.set("latest_order", order["id"])
```

这样带来的价值：

- 更换数据库或缓存实现时，业务逻辑无需大改；
- 单元测试可以使用内存实现或 Mock；
- 外部依赖不会渗透进核心业务；
- 系统边界更加清晰。

---

## 5.3 用配置表达“参数”，不要用配置伪装“程序”

配置适合表达：

- 环境地址、超时时间、重试次数
- 开关、阈值、字段映射
- 页面选择器、流程参数
- 模板、提示词、模型参数
- 不同客户或渠道的规则差异

例如：

```yaml
report_export:
  query:
    default_days: 30
    max_rows: 100000

  output:
    format: xlsx
    file_name_template: "report_{date}.xlsx"

  retry:
    max_attempts: 3
    interval_seconds: 2
```

但配置不适合表达：

- 多层循环和复杂状态机
- 大量动态条件分支
- 复杂算法
- 依赖外部状态的业务判断
- 难以阅读的脚本语言片段

判断标准：

> **如果一个配置文件已经需要大量注释才能看懂，或者业务人员无法安全修改，它很可能已经不是配置，而是应该被抽成代码或插件的逻辑。**

---

## 5.4 用插件处理“真正的差异”

当场景的差异已经超出简单参数配置时，不要继续往核心逻辑里堆条件判断。

不推荐：

```python
if channel == "A":
    ...
elif channel == "B":
    ...
elif channel == "C":
    ...
elif channel == "D":
    ...
```

推荐定义统一插件协议：

```python
from abc import ABC, abstractmethod


class ChannelPlugin(ABC):
    """渠道能力扩展协议。"""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def process(self, payload: dict) -> dict:
        raise NotImplementedError
```

不同渠道独立实现：

```python
class ChannelAPlugin(ChannelPlugin):
    @property
    def name(self) -> str:
        return "channel_a"

    def process(self, payload: dict) -> dict:
        return {
            "channel": self.name,
            "result": "processed_by_a",
        }


class ChannelBPlugin(ChannelPlugin):
    @property
    def name(self) -> str:
        return "channel_b"

    def process(self, payload: dict) -> dict:
        return {
            "channel": self.name,
            "result": "processed_by_b",
        }
```

通过注册中心统一管理：

```python
class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, ChannelPlugin] = {}

    def register(self, plugin: ChannelPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> ChannelPlugin:
        return self._plugins[name]
```

这样新增渠道时，只需：

1. 新增一个插件实现；
2. 注册该插件；
3. 增加对应配置；
4. 补充测试。

而不是修改核心流程中越来越长的条件分支。

---

# 6. 编码规范：让代码更易读

## 6.1 命名要表达业务意图

避免：

```python
def handle(data):
    ...
```

推荐：

```python
def validate_export_request(request: ExportRequest) -> None:
    ...
```

避免：

```python
a = get_data()
b = process(a)
```

推荐：

```python
raw_orders = order_repository.find_pending_orders()
validated_orders = order_validator.validate(raw_orders)
```

命名原则：

- 函数名使用**动词 + 对象**；
- 类名使用**职责名词**；
- 布尔变量以 `is_`、`has_`、`can_`、`should_` 开头；
- 不使用无业务含义的缩写；
- 名称优先表达“为什么”和“是什么”，而不仅是“怎么做”。

---

## 6.2 函数短小，但不要为短而短

建议一个函数只做一件完整且可命名的事情。

```python
def create_export_task(request: ExportRequest) -> ExportTask:
    validate_export_request(request)
    task = build_export_task(request)
    task_repository.save(task)
    publish_task_created_event(task)
    return task
```

如果一个函数需要不断滚动才能看完，或者包含多个层次的业务阶段，应考虑拆分。

但也不要把代码拆成大量只有一两行、上下文跳转严重的小函数。拆分标准是：

> **拆分后，函数名称能帮助读者理解业务步骤。**

---

## 6.3 控制嵌套深度，优先使用提前返回

不推荐：

```python
def process_request(request: dict) -> dict:
    if request:
        if request.get("user_id"):
            if request.get("items"):
                return {"status": "success"}
    return {"status": "failed"}
```

推荐：

```python
def process_request(request: dict) -> dict:
    if not request:
        return {"status": "failed", "reason": "request is empty"}

    if not request.get("user_id"):
        return {"status": "failed", "reason": "user_id is required"}

    if not request.get("items"):
        return {"status": "failed", "reason": "items are required"}

    return {"status": "success"}
```

这样可以减少嵌套，使异常路径和正常路径都更清晰。

---

# 7. 防止大型项目腐化的关键机制

## 7.1 禁止复制粘贴式扩展

当你准备复制一个旧模块再改几个字段时，先停下来问：

- 这两个模块的共同点是什么？
- 差异是否能变成配置？
- 是否应该抽一个接口？
- 是否应该写一个可复用的策略或模板？

复制粘贴的短期效率很高，但长期会形成“多份近似逻辑”。后续修复一个问题时，往往会遗漏其他副本。

---

## 7.2 不要让 `if-else` 成为扩展机制

少量条件判断是正常的；但如果某个核心流程持续因新增类型而修改：

```python
if type == "a":
    ...
elif type == "b":
    ...
elif type == "c":
    ...
```

说明它缺少：

- 策略模式；
- 插件机制；
- 工厂或注册中心；
- 多态实现；
- 工作流节点抽象。

原则：

> **当新增一种类型总需要修改旧代码时，说明系统没有真正对扩展开放。**

---

## 7.3 核心流程要稳定，外围能力要可替换

可以把系统想象成同心圆：

- 中心：核心领域规则、关键协议、基础数据模型；
- 中间：业务用例、流程编排；
- 外围：数据库、HTTP、文件、第三方服务、消息队列、UI；
- 最外层：环境配置、渠道定制、客户差异化逻辑。

越靠近中心，越要稳定、少改动；越靠近外围，越应该允许替换、扩展和配置化。

---

# 8. 需求开发决策流程

当收到一个新需求时，按以下顺序分析：

```text
新需求
  ↓
是否已有相同的稳定能力？
  ├── 有：复用
  └── 没有：是否会被多个场景复用？
              ├── 会：沉淀为核心能力或通用组件
              └── 不会：局部实现，但保持边界隔离
  ↓
差异是否仅仅是参数、规则、映射或开关？
  ├── 是：新增或调整配置
  └── 否：是否属于明确的一类扩展能力？
              ├── 是：实现插件 / 策略
              └── 否：实现独立业务模块
```

可以进一步总结成一句执行准则：

> **复用已有能力优先于新增代码；新增配置优先于修改核心流程；新增插件优先于扩散条件分支。**

---

# 9. 代码评审 Checklist

提交代码前，可以逐项检查：

- [ ] 这个需求的变化点是否应该放入配置？
- [ ] 是否出现了可预见会持续增长的 `if-else` 或 `switch-case`？
- [ ] 是否可以定义统一接口，让不同实现可替换？
- [ ] 是否存在复制粘贴后只改少数字段的重复代码？
- [ ] 核心业务是否依赖了具体数据库、HTTP 客户端或第三方 SDK？
- [ ] 模块职责是否清晰，是否混合了业务、存储、接口和展示逻辑？
- [ ] 配置是否有校验、默认值、版本兼容和清晰说明？
- [ ] 新插件能否做到“新增文件 + 注册 + 配置”，而无需修改核心代码？
- [ ] 是否补充了单元测试、异常场景测试和关键集成测试？
- [ ] 日志、错误码、监控指标是否足以定位问题？
- [ ] 代码命名是否能让不了解上下文的人理解其业务意图？

---

# 10. 个人方法论

## 我的工程化方法论

> **稳定内核 + 可变配置 + 可插拔扩展 + 统一协议组合**

### 第一原则：先找不变，再处理变化

任何需求开始前，先区分：

- 哪些是长期稳定、可复用的核心能力；
- 哪些是经常变化、适合参数化的业务差异；
- 哪些是复杂特殊、需要代码扩展的能力。

### 第二原则：先定义契约，再编写实现

组件之间应通过清晰的输入、输出和行为约定协作，而不是直接依赖对方的内部实现。

### 第三原则：配置承载常规差异，插件承载复杂差异

- 字段、阈值、开关、映射、选择器、环境参数：放配置；
- 复杂算法、外部系统适配、特殊流程、定制策略：写插件；
- 不要让配置文件成为难以维护的“隐藏代码”。

### 第四原则：核心保持稳定，变化隔离在边缘

核心协议、核心领域模型和执行引擎要谨慎修改；客户、渠道、环境和外部系统的变化，应尽可能隔离在配置、适配器和插件层。

### 第五原则：新增能力应尽量“加法式”完成

优秀的扩展方式应该是：

- 新增一个配置；
- 新增一个模块；
- 新增一个插件；
- 新增一个实现；

而不是：

- 修改多个旧文件；
- 给核心流程继续添加分支；
- 复制旧逻辑再修补；
- 让原有模块承担越来越多职责。

---

# 11. 最终总结

大型项目真正需要追求的，不是“代码看起来高级”，而是让系统面对变化时仍然保持秩序。

> **将稳定能力沉淀为内核，将业务差异外置为配置，将复杂定制封装为插件，将模块协作建立在统一协议之上。**

这样做的结果是：

- **可读性强**：每个模块职责明确，代码表达业务意图；
- **可扩展性强**：新增场景以配置和插件为主，而非改动核心代码；
- **可维护性强**：变化被隔离，问题定位更容易，修改影响范围更可控；
- **可测试性强**：依赖可替换，核心逻辑可独立验证；
- **协作效率高**：团队成员知道新需求应该落在内核、配置还是插件层。

一句话沉淀：

> **不要把项目写成一堆完成需求的代码；要把它设计成一个能够持续容纳变化的系统。**
