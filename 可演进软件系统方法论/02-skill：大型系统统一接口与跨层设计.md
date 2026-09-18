# Skill：大型系统统一接口与跨层协作设计

## 1. Skill 目标

在包含前端、后端、数据库、微服务、消息队列、第三方系统等多个部分的软件项目中，建立一套稳定、清晰、可演进的协作机制，使系统具备：

- **接口一致性**
- **模块低耦合**
- **跨团队协作效率**
- **可扩展性**
- **可维护性**
- **可测试性**
- **平滑演进能力**
- **可观测性与可治理性**

本 Skill 的核心目标不是“统一 URL 格式”或“统一返回 JSON”，而是：

> **通过稳定契约让不同模块独立演进，通过清晰边界隔离复杂性，通过规范化治理保证长期协作。**

---

# 2. 核心方法论

## 契约优先 + 边界清晰 + 内核稳定 + 外围可替换 + 演进可治理

可以将大型系统的统一方法论概括为：

> **以统一契约解耦上下游，以清晰边界隔离变化，以抽象接口替代直接依赖，以配置和插件承载差异，以版本、测试和观测保障长期演进。**

它与个人方法论高度一致：

> **稳定内核 + 可变配置 + 可插拔扩展 + 统一协议组合**

在大型系统中的对应关系如下：

| 个人方法论 | 大型系统中的实现                                         |
| ----- | ------------------------------------------------ |
| 稳定内核  | 核心领域模型、关键业务规则、统一接口规范、基础平台能力                      |
| 可变配置  | 环境参数、开关、超时、限流阈值、字段映射、租户策略                        |
| 可插拔扩展 | 支付渠道、通知渠道、数据库实现、认证方式、第三方适配器                      |
| 统一协议  | REST API、OpenAPI、RPC IDL、事件 Schema、Repository 接口 |
| 组件组合  | BFF 聚合、服务编排、工作流、中间件链、事件订阅                        |
| 隔离变化  | 分层架构、模块化、适配器、限界上下文、服务边界                          |
| 演进保障  | 版本管理、契约测试、灰度发布、日志、链路追踪、监控告警                      |

---

# 3. 核心原则

## 3.1 契约优先（Contract First）

在开发前，先定义模块之间如何协作，而不是先分别开发、最后再“联调对接口”。

接口契约应明确：

- 调用路径或服务标识；
- 调用方式；
- 请求参数；
- 响应结构；
- 字段名称和类型；
- 必填与可选规则；
- 枚举取值；
- 业务错误码；
- 鉴权方式；
- 分页、排序、过滤规范；
- 幂等要求；
- 超时、重试与限流规则；
- 版本策略与兼容性要求。

核心认知：

> **接口不是一段 JSON，也不是一份临时文档；接口是上下游共同遵守、能够被验证和演进的契约。**

---

## 3.2 边界优先（Boundary First）

系统复杂的根源并不只是代码多，而是模块之间互相侵入。

因此要先定义边界：

- 前端不能直接访问数据库；
- 服务之间不能直接读写彼此的数据表；
- 业务核心不能直接依赖具体云服务或数据库 SDK；
- 第三方系统不能渗透到核心领域模型；
- 页面展示逻辑不能成为业务规则的唯一载体。

原则：

> **模块之间通过公开契约协作，而不是依赖内部实现、共享数据库或复制业务逻辑。**

---

## 3.3 依赖抽象，不依赖实现

核心业务代码应依赖稳定的接口，而不是某个具体数据库、缓存、消息队列或第三方 SDK。

```python
from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    """支付能力的统一端口。"""

    @abstractmethod
    def create_payment(self, order_id: str, amount: int) -> str:
        raise NotImplementedError
```

不同外部渠道作为适配器实现：

```python
class ChannelAPaymentGateway(PaymentGateway):
    def create_payment(self, order_id: str, amount: int) -> str:
        return f"channel_a_payment_{order_id}"


class ChannelBPaymentGateway(PaymentGateway):
    def create_payment(self, order_id: str, amount: int) -> str:
        return f"channel_b_payment_{order_id}"
```

业务层只依赖抽象：

```python
class PaymentApplicationService:
    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway

    def pay_order(self, order_id: str, amount: int) -> str:
        return self.payment_gateway.create_payment(order_id, amount)
```

这样可以：

- 更换第三方渠道而不修改核心业务；
- 在测试环境替换为 Mock 或 Fake 实现；
- 将外部不稳定因素隔离在系统边缘；
- 降低技术替换和系统升级的成本。

---

# 4. 推荐架构分层

推荐按职责分层，而不是按照“控制器、服务、数据库文件”随意堆放。

```text
客户端 / 前端
    ↓
接入层：API Gateway / BFF
    ↓
应用层：用例编排、权限、事务、流程控制
    ↓
领域层：核心业务规则、领域模型、状态流转
    ↓
端口层：Repository、消息、存储、第三方能力抽象
    ↓
适配器层：数据库、缓存、消息队列、HTTP、第三方 SDK
    ↓
基础设施：网络、存储、监控、配置、部署环境
```

---

## 4.1 前端 / 客户端层

职责：

- 用户交互；
- 页面状态与展示；
- 输入校验和友好提示；
- 调用后端 API；
- 处理页面级缓存与权限展示。

边界：

- 不直接访问数据库；
- 不承担关键业务规则；
- 不自行定义与后端不一致的数据模型；
- 不依赖后端内部实现。

建议：

- 使用 OpenAPI 自动生成 TypeScript 类型和 API Client；
- 对接口返回进行统一错误处理；
- 将页面模型与接口 DTO 适度隔离；
- 不把所有后端字段直接散落在组件中。

---

## 4.2 API Gateway / BFF 层

BFF，即 **Backend For Frontend**。它的作用是为特定终端提供适合其页面和交互方式的接口。

职责：

- 鉴权和权限检查；
- 聚合多个服务的返回；
- 数据裁剪与展示模型转换；
- 请求限流和基础防护；
- 统一错误返回；
- 面向 Web、移动端、管理端提供差异化接口。

边界：

- 不承载长期复杂的核心业务规则；
- 不直接拥有其他领域的数据；
- 不将大量领域逻辑复制到 BFF。

原则：

> **BFF 负责“为客户端组织数据”，领域服务负责“定义业务规则”。**

---

## 4.3 应用层

应用层负责完成一个完整的业务用例，例如：

- 创建订单；
- 发起审批；
- 导出报表；
- 创建自动化任务；
- 执行支付；
- 发送通知。

职责：

- 编排领域对象和领域服务；
- 定义事务边界；
- 组织权限校验；
- 调用仓储、外部端口与消息发布器；
- 返回适合 API 层使用的结果。

应用层不应承载：

- 大量 SQL；
- 具体 HTTP SDK 调用；
- 页面展示判断；
- 与某个具体基础设施强绑定的代码。

---

## 4.4 领域层

领域层是系统的**稳定内核**。

职责：

- 核心业务规则；
- 状态机与状态流转；
- 关键数据校验；
- 领域对象行为；
- 领域服务；
- 领域事件。

例如：

```python
class Order:
    def __init__(self, order_id: str, total_amount: int):
        self.order_id = order_id
        self.total_amount = total_amount
        self.status = "CREATED"

    def pay(self) -> None:
        if self.status != "CREATED":
            raise ValueError("当前订单状态不允许支付")

        self.status = "PAID"
```

原则：

> **领域层表达业务本质，而不是数据库表结构、接口字段格式或页面交互细节。**

---

## 4.5 端口与适配器层

端口是业务核心需要的能力抽象，例如：

- `OrderRepository`
- `PaymentGateway`
- `NotificationSender`
- `MessagePublisher`
- `FileStorage`
- `UserIdentityProvider`

适配器则是这些能力的具体实现，例如：

- MySQL 仓储；
- Redis 缓存；
- Kafka 消息发布器；
- 对象存储客户端；
- 邮件、短信、推送通知渠道；
- 第三方 API Client。

```text
领域 / 应用层
    ↓ 依赖抽象端口
Repository / Gateway / Publisher 接口
    ↑ 由外部具体实现
MySQL / Redis / MQ / 第三方 API / 文件存储
```

这就是**端口与适配器**或**六边形架构**的核心结构。

---

# 5. API 统一规范

## 5.1 统一资源命名

建议采用清晰、可预测的资源命名。

```text
GET    /api/v1/orders
GET    /api/v1/orders/{orderId}
POST   /api/v1/orders
PATCH  /api/v1/orders/{orderId}
DELETE /api/v1/orders/{orderId}
```

建议：

- 使用名词表达资源；
- 资源名称尽量使用复数；
- 避免使用模糊动词路径，如 `/doOrder`、`/getData`；
- 对特殊业务动作，可使用子资源或动作路径：

```text
POST /api/v1/orders/{orderId}/payment
POST /api/v1/orders/{orderId}/cancel
POST /api/v1/reports/export
```

---

## 5.2 统一响应结构

团队应统一约定响应包装结构，避免每个服务各自定义格式。

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {
    "orderId": "O001",
    "status": "PAID"
  },
  "requestId": "req_abc123"
}
```

字段建议：

- `code`：业务结果码；
- `message`：面向调用方的简短描述；
- `data`：实际业务数据；
- `requestId`：请求链路标识，用于排查问题；
- `timestamp`：可选，用于客户端诊断和对时。

注意：统一包装不代表所有接口必须机械相同。文件下载、流式响应、Webhook 回调等场景可制定专项规范。

---

## 5.3 统一错误码与异常语义

错误码应具备：

- 唯一性；
- 稳定性；
- 可检索性；
- 可定位性；
- 明确的调用方处理方式。

示例：

```text
VALIDATION_ERROR：请求参数不合法
UNAUTHORIZED：未认证或认证失效
FORBIDDEN：无权限访问
RESOURCE_NOT_FOUND：资源不存在
CONFLICT：状态冲突或重复操作
RATE_LIMITED：请求过于频繁
INTERNAL_ERROR：系统内部异常
```

原则：

> **异常不是“报错信息”，而是系统向调用方表达失败语义的标准协议。**

---

## 5.4 分页、排序与过滤统一化

列表接口应统一分页与筛选规则，避免每个接口各自发明参数。

```text
GET /api/v1/orders?page=1&pageSize=20&status=PAID&sortBy=createdAt&sortOrder=desc
```

返回示例：

```json
{
  "code": "SUCCESS",
  "data": {
    "items": [],
    "page": 1,
    "pageSize": 20,
    "total": 0
  },
  "requestId": "req_abc123"
}
```

---

## 5.5 幂等性规范

对于创建、支付、回调、状态变更等可能被重复提交的操作，应支持幂等。

```text
POST /api/v1/orders
Idempotency-Key: 7b852f5c-xxxx
```

原则：

> **同一个业务请求被重复发送，系统应避免重复创建、重复扣减、重复执行。**

---

# 6. 服务间通信方法论

## 6.1 同步调用：适用于需要立即结果的场景

常见方式：

- REST / HTTP；
- RPC；
- GraphQL；
- 内部服务调用协议。

适合：

- 查询详情；
- 用户鉴权；
- 必须同步确认的业务动作；
- 低延迟、明确请求—响应模型的调用。

必须考虑：

- 超时；
- 重试；
- 降级；
- 熔断；
- 限流；
- 幂等；
- 调用链路追踪。

---

## 6.2 异步事件：适用于跨服务协同和削峰解耦

常见方式：

- 消息队列；
- 事件总线；
- 发布订阅；
- 任务队列。

适合：

- 订单创建后通知库存系统；
- 文件导出完成后发送提醒；
- 数据变更后更新搜索索引；
- 审计日志写入；
- 耗时任务异步处理。

示例：

```json
{
  "eventId": "evt_001",
  "eventType": "OrderCreated",
  "occurredAt": "2026-09-17T14:55:00Z",
  "data": {
    "orderId": "O001",
    "userId": "U001",
    "totalAmount": 19900
  }
}
```

事件规范应明确：

- 事件名称；
- 事件版本；
- 事件唯一标识；
- 发生时间；
- 事件来源；
- 载荷结构；
- 重复消费处理方式；
- 失败重试与死信处理方式。

原则：

> **同步接口用于“现在就要答案”，异步事件用于“通知发生了什么”。**

---

# 7. 数据库与数据边界

## 7.1 数据归属原则

每个服务应拥有自己负责的数据边界。

不推荐：

```text
订单服务直接写库存服务的数据表
库存服务直接查询用户服务的内部表
多个服务共享同一张核心业务表
```

推荐：

```text
订单服务 → 维护订单数据
库存服务 → 维护库存数据
用户服务 → 维护用户数据
服务之间 → 通过 API 或事件协作
```

核心原则：

> **数据归属跟随业务边界；跨服务访问通过契约完成，而不是绕过服务直接操作数据。**

---

## 7.2 数据库是实现细节，不是业务接口

业务层不应直接暴露数据库表结构给前端或其他服务。

避免：

```json
{
  "id": 1,
  "created_at": "2026-09-17 14:55:00",
  "is_deleted": 0
}
```

推荐面向业务语义建模：

```json
{
  "orderId": "O001",
  "createdAt": "2026-09-17T14:55:00Z",
  "status": "PAID"
}
```

这样数据库字段、表结构、ORM 实现发生变化时，外部接口可以保持稳定。

---

# 8. 配置、插件与适配器

## 8.1 配置层：表达常规变化

适合配置化的内容包括：

```yaml
service:
  timeoutSeconds: 5
  retryTimes: 3

featureFlags:
  enableNewExportFlow: false

rateLimit:
  maxRequestsPerMinute: 300

thirdParty:
  paymentChannel: channel_a
```

配置需要具备：

- 类型校验；
- 默认值；
- 必填校验；
- 环境隔离；
- 权限管理；
- 变更审计；
- 灰度能力；
- 文档说明。

---

## 8.2 插件与适配器：表达复杂差异

当不同渠道、客户、外部平台之间存在复杂流程差异时，使用插件或适配器，而不是把差异写入核心流程。

```python
from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, recipient: str, content: str) -> None:
        raise NotImplementedError
```

```python
class EmailNotificationChannel(NotificationChannel):
    def send(self, recipient: str, content: str) -> None:
        ...


class SmsNotificationChannel(NotificationChannel):
    def send(self, recipient: str, content: str) -> None:
        ...
```

选择具体实现可由配置或依赖注入完成：

```python
def build_notification_channel(channel_name: str) -> NotificationChannel:
    channels = {
        "email": EmailNotificationChannel(),
        "sms": SmsNotificationChannel(),
    }
    return channels[channel_name]
```

原则：

> **参数差异使用配置；行为差异使用插件；基础设施差异使用适配器。**

---

# 9. 接口版本与兼容性治理

## 9.1 接口发布即承诺

一旦接口被前端、其他服务或第三方依赖，它就不再只是内部实现，而是稳定承诺。

应遵守：

- 新增可选字段通常兼容；
- 不随意删除字段；
- 不随意修改字段类型；
- 不随意改变字段含义；
- 不随意调整枚举值语义；
- 不轻易改变错误码；
- 不兼容变更通过新版本发布。

例如：

```text
/api/v1/orders
/api/v2/orders
```

---

## 9.2 接口弃用流程

推荐流程：

```text
发布新接口或新版本
    ↓
提供迁移文档与示例
    ↓
通知调用方并设置迁移期限
    ↓
监控旧接口调用量
    ↓
逐步灰度切换
    ↓
确认无依赖后下线旧接口
```

原则：

> **接口升级不是“改完上线”，而是一次受控迁移。**

---

# 10. 自动化质量保障

## 10.1 契约测试

契约测试验证接口是否仍符合约定，而不是只验证某段内部代码是否运行。

应验证：

- 请求参数是否符合 Schema；
- 响应字段是否完整；
- 字段类型是否正确；
- 枚举是否符合约束；
- 错误码是否正确；
- 兼容性是否被破坏。

```python
def test_get_order_contract():
    response = client.get("/api/v1/orders/O001")

    assert response.status_code == 200

    body = response.json()
    assert body["code"] == "SUCCESS"
    assert isinstance(body["requestId"], str)

    order = body["data"]
    assert isinstance(order["orderId"], str)
    assert order["status"] in {"CREATED", "PAID", "CANCELLED"}
```

---

## 10.2 测试分层

建议建立分层测试体系：

| 测试类型  | 关注点                |
| ----- | ------------------ |
| 单元测试  | 单个函数、领域规则、状态流转     |
| 模块测试  | 单个模块内部协作           |
| 集成测试  | 数据库、缓存、消息队列、第三方适配器 |
| 契约测试  | API、RPC、事件格式是否符合协议 |
| 端到端测试 | 用户完整操作流程           |
| 回归测试  | 已修复问题与关键链路不被破坏     |
| 压力测试  | 并发、容量、性能瓶颈         |
| 故障演练  | 超时、重试、降级、依赖异常恢复能力  |

---

# 11. 可观测性与运行治理

统一接口还必须可追踪、可诊断、可治理。

建议每一个请求都携带或生成 `requestId`，并在跨服务调用中透传。

```text
前端请求
  ↓ requestId
API Gateway
  ↓ requestId
订单服务
  ↓ requestId
支付服务
  ↓ requestId
第三方支付渠道
```

应建立：

- 结构化日志；
- 请求 ID；
- 分布式链路追踪；
- 核心业务指标；
- 接口成功率、耗时、错误率监控；
- 超时、限流、熔断、重试监控；
- 告警与故障处理预案；
- 敏感信息脱敏；
- 审计记录。

原则：

> **没有可观测性的接口，在出现问题时就不是可靠的接口。**

---

# 12. 新需求开发决策流程

面对一个新功能、一个新接口或一个新系统集成时，按以下流程判断：

```text
新需求
  ↓
是否已有稳定领域能力可以复用？
  ├── 是：复用现有领域服务、协议和模块
  └── 否：抽象出新的领域能力或应用用例
  ↓
是否仅属于参数、开关、映射或环境差异？
  ├── 是：进入配置层
  └── 否：继续判断
  ↓
是否属于某类渠道、客户或第三方系统的行为差异？
  ├── 是：定义或实现插件 / 适配器
  └── 否：实现独立业务模块
  ↓
是否需要对外或跨服务协作？
  ├── 是：先定义 API / RPC / 事件契约，再并行开发
  └── 否：保持模块内部边界和测试覆盖
  ↓
是否会影响已有调用方？
  ├── 是：执行兼容性评审、版本策略和灰度迁移
  └── 否：按常规发布流程推进
```

---

# 13. 团队接口评审 Checklist

提交新接口、修改已有接口或接入第三方系统前，检查：

- [ ] 是否先完成接口契约设计并经过评审？
- [ ] 请求、响应、错误码、鉴权、分页、幂等规则是否明确？
- [ ] 是否使用统一命名、统一响应结构和统一错误语义？
- [ ] 是否避免向前端或其他服务暴露数据库表结构？
- [ ] 是否避免跨服务直接读写数据库？
- [ ] 是否明确数据归属和服务边界？
- [ ] 是否将核心业务与具体数据库、第三方 SDK、消息中间件解耦？
- [ ] 常规参数变化是否进入配置层？
- [ ] 复杂渠道差异是否通过插件或适配器隔离？
- [ ] 是否存在不断增长的 `if-else`、复制代码或跨模块侵入？
- [ ] 是否考虑超时、重试、限流、熔断、降级和幂等？
- [ ] 是否有接口版本与兼容性方案？
- [ ] 是否补充单元测试、集成测试和契约测试？
- [ ] 是否具备日志、`requestId`、指标与链路追踪能力？
- [ ] 是否明确接口负责人、文档位置、变更记录和废弃计划？

---

# 14. 最终总结

大型系统中“统一前端、后端、数据库、微服务与第三方系统”的本质，不是让所有系统使用完全相同的技术，而是让它们能够在**稳定的协作规则**下独立发展。

最终方法论可以沉淀为：

> **统一接口靠契约，隔离复杂性靠边界，减少耦合靠抽象，容纳差异靠配置与插件，保障演进靠版本、测试、观测与治理。**

一句话版本：

> **让不同团队、不同技术栈、不同系统实现，在清晰边界和稳定契约之上独立演进、自由协作。**
