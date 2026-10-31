# assignment-submission：学生交作业与异步批改

本能力覆盖学生端「交作业」页面与提交后的异步批改链路。前提是 A 组的登录、班级归属、角色与 5 学科底座，以及 B 组的讲义入库与词法检索已可用。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 本班作业列表按学科切分

系统 MUST 只返回登录学生所属班级、且 `deadline` 未过或仍在展示窗口内的作业，并按数学/语文/英语/物理/化学 5 个 tab 切分。班级 MUST 由服务端会话确定，请求参数中的 `class_id` MUST NOT 生效。

#### Scenario: 本班作业可见
- **WHEN** A 班学生在「交作业」页切换到「数学」tab
- **THEN** MUST 只列出 A 班、`subject = 数学` 的作业，含标题、描述、截止时间与本人提交状态

#### Scenario: 他班作业不可见
- **WHEN** A 班学生请求 B 班作业列表，或在请求中传入 B 班 `class_id`
- **THEN** MUST 仍只返回 A 班作业；A 班无该学科作业时返回空列表与 `total: 0`
- **AND** 响应 MUST NOT 包含 B 班任何作业标题、编号或数量

#### Scenario: 未登录
- **WHEN** 未登录用户请求作业列表
- **THEN** MUST 返回 HTTP 401，且不返回任何作业字段

### Requirement: R2 提交文本作答

系统 MUST 接收 `POST /api/assignments/<id>/submit`，正文为 `content`（纯文本，去除首尾空白后 1—5000 字符）与客户端生成的 `idempotency_key`。提交成功 MUST 写入 `submissions`，`status = pending`，并立即返回 HTTP 202。

#### Scenario: 正常提交
- **WHEN** A 班学生在截止前提交合法作答
- **THEN** MUST 返回 202 与 `submission_id`、`status: "pending"`
- **AND** 数据库中 MUST 存在且仅存在一条对应行，`class_id`、`student_id`、`assignment_id` 与当前会话一致

#### Scenario: 内容不合法
- **WHEN** `content` 去空白后为空、超过 5000 字符，或 `idempotency_key` 缺失
- **THEN** MUST 返回 400 与明确提示，且 MUST NOT 写入 `submissions`

#### Scenario: 提交他人或他班的作业
- **WHEN** 学生提交不属于本班、不存在或不属于自己的 `assignment_id`
- **THEN** MUST 返回 404，且 MUST NOT 写入 `submissions`

### Requirement: R3 截止时间控制

系统 MUST 在服务端以 `deadline` 判定是否接收提交；前端置灰 MUST NOT 作为唯一手段。过期提交 MUST 被拒绝并给出明确原因。

#### Scenario: 截止后提交
- **WHEN** 学生在 `deadline` 之后提交
- **THEN** MUST 返回 HTTP 409，`error_code = "assignment_closed"`，提示「已过截止时间，无法提交」
- **AND** MUST NOT 写入 `submissions`，MUST NOT 入队批改

#### Scenario: 截止时刻边界
- **WHEN** 提交时刻与 `deadline` 完全相同
- **THEN** MUST 按「已截止」处理，判定规则在实现与测试中保持一致

### Requirement: R4 异步批改状态机

系统 MUST 用 `pending → grading → graded | failed` 描述一次提交的批改过程，MUST NOT 出现 `graded` 与 `failed` 之间的回退。任何非终态都必须能通过查询接口读到。

#### Scenario: 状态自动流转
- **WHEN** 提交成功且队列与模型服务正常
- **THEN** 状态 MUST 由 `pending` 经 `grading` 到达 `graded`，并写入 `graded_at`
- **AND** 前端 MUST 能在不刷新页面的情况下看到最终状态

#### Scenario: 批改失败
- **WHEN** 模型超时、返回非 2xx 或返回内容无法解析为约定 JSON
- **THEN** MUST 置 `status = failed` 并写入 `error_message`
- **AND** MUST NOT 写入任何 `ai_score` 或 `ai_comment`，MUST NOT 用默认分或空评语占位

#### Scenario: 队列不可用
- **WHEN** Redis 或 worker 不可用，提交无法入队
- **THEN** MUST 返回 503 与通用故障提示，且 MUST NOT 留下长期停留于 `pending` 的孤儿行

### Requirement: R5 幂等

同一 `(assignment_id, student_id, idempotency_key)` MUST 只产生一条提交记录与一次模型调用。重复请求 MUST 返回同一条结果，而不是新建记录。

#### Scenario: 重复点击提交
- **WHEN** 学生在网络重试或双击的情况下用同一 `idempotency_key` 提交两次
- **THEN** MUST 只有一条 `submissions` 行，第二次请求返回 200 与同一 `submission_id`
- **AND** 审计中 MUST 只有一次 `homework_grade` 技能调用

#### Scenario: 任务重复投递
- **WHEN** worker 因重试或崩溃恢复收到同一 `submission_id` 的两次任务
- **THEN** MUST 通过状态条件更新只让一个任务继续执行，另一次直接返回
- **AND** MUST NOT 产生第二次模型调用或覆盖已有结果

### Requirement: R6 结果推送与降级

系统 MUST 提供 `GET /api/submissions/<id>/stream` 的 SSE 推送；SSE 不可用时前端 MUST 降级为轮询并仍能收敛到终态。

#### Scenario: 推送正常
- **WHEN** 学生打开自己的提交详情并保持连接
- **THEN** MUST 在状态变化时收到事件，事件内容含 `status` 与终态下的 `ai_score`、`ai_comment`、依据
- **AND** 进入终态后连接 MUST 由服务端主动关闭

#### Scenario: 推送不可用
- **WHEN** 代理缓冲导致 SSE 无数据，或连接被中断
- **THEN** 前端 MUST 自动退化为轮询并最终显示终态，页面 MUST NOT 永久停留于「处理中」

#### Scenario: 订阅他人提交
- **WHEN** 学生订阅同班同学的提交，或订阅他班提交
- **THEN** MUST 返回 404，且 MUST NOT 推送任何状态或内容

### Requirement: R7 结果字段与依据来源

批改成功 MUST 写入 `ai_score`（0—100 整数）、`ai_comment` 与 `ai_evidence`（引用讲义标题、切片编号、相关度）。依据 MUST 来自真实检索命中；检索为空时 MUST 明说未命中。

#### Scenario: 有依据的批改
- **WHEN** 批改时本班讲义检索命中相关内容
- **THEN** `ai_evidence` MUST 至少含一条可点开的真实讲义来源
- **AND** 每条来源 MUST 能在本班讲义中定位到对应切片

#### Scenario: 无依据的批改
- **WHEN** 批改时本班讲义检索未命中任何内容
- **THEN** `ai_comment` MUST 明确说明「未命中讲义」，`ai_evidence` MUST 为空数组
- **AND** MUST NOT 编造讲义标题、页码或引用编号

#### Scenario: 分数越界
- **WHEN** 模型返回的分数不是 0—100 的整数
- **THEN** MUST 按批改失败处理，MUST NOT 截断后入库

### Requirement: R8 学生只能看到自己的提交

学生 MUST 只能读取自己的提交与其批改结果。同班同学之间的提交 MUST 互不可见。

#### Scenario: 同班同学互相看不到
- **WHEN** 学生乙请求学生甲的 `submission_id`
- **THEN** MUST 返回 404，且 MUST NOT 返回作答内容、分数或评语

#### Scenario: 外班访问
- **WHEN** 学生丙（外班）请求 A 班任意提交
- **THEN** MUST 返回 404，且响应 MUST NOT 泄露该提交是否存在

### Requirement: R9 提交详情页状态完整

「交作业」页面 MUST 展示 `pending`（排队中）、`grading`（批改中）、`graded`（已完成）、`failed`（失败可重试）四种状态，且每种状态都有可读文案。

#### Scenario: 状态展示
- **WHEN** 学生查看自己不同状态的提交
- **THEN** 页面 MUST 显示与数据库一致的状态文案
- **AND** `failed` 状态 MUST 提供重试入口，重试 MUST 复用同一 `idempotency_key` 语义并重新入队

#### Scenario: 登录失效
- **WHEN** 接口返回 401
- **THEN** 页面 MUST 清理已展示的受保护内容并回到登录流程
