# care-dialogue：关怀式对话

本能力覆盖学生端「关怀式对话」页面。它与解题引导、作业批改、错题讲解在**技能、提示词、数据来源**三个层面严格隔离，是本组唯一不接触学科内容的对话能力。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 独立会话且仅本人可见

系统 MUST 提供 `POST /api/care/chat` 与独立页面。会话 MUST 与学科助手对话分离存储，MUST 只对本人可见。

#### Scenario: 独立会话
- **WHEN** 学生在关怀式对话页发言
- **THEN** MUST 写入独立的关怀会话表，MUST NOT 混入学科助手对话历史
- **AND** 回到学科助手对话页时 MUST NOT 看到关怀会话内容

#### Scenario: 同班同学互相看不到
- **WHEN** 学生乙请求关怀会话历史，或指定学生甲的会话编号
- **THEN** MUST 返回空列表或 404，MUST NOT 返回任何对话内容

#### Scenario: 外班访问
- **WHEN** 学生丙（外班）访问该接口或猜测编号
- **THEN** MUST 返回 404，且 MUST NOT 泄露会话是否存在

### Requirement: R2 不调用知识库也不接触讲义

关怀式对话的模型请求 MUST NOT 包含讲义检索结果、切片正文、技能提示词中的学科内容。实现 MUST 在服务端保证这一点，而不是靠提示词劝阻。

#### Scenario: 请求体不含检索内容
- **WHEN** 学生在关怀式对话中提问
- **THEN** 发往模型的请求 MUST NOT 含任何 `knowledge`、`chunks`、`materials` 字段或讲义原文
- **AND** 该次调用 MUST NOT 触发检索接口

#### Scenario: 学科问题不被转成知识问答
- **WHEN** 学生在关怀式对话中提出学科题目问题
- **THEN** 回应 MUST 以情绪与学习状态为主，可建议到「助手对话」提问
- **AND** MUST NOT 返回引用讲义的知识性解答

#### Scenario: 审计可核对
- **WHEN** 查看该次调用的审计记录
- **THEN** 记录的 `skill` MUST 为 `care_chat`，参数摘要 MUST 不含讲义片段

### Requirement: R3 情绪识别与温和回应

系统 MUST 识别焦虑、压力、挫败等情绪状态并给出温和回应；当识别到持续负面情绪时 MUST 建议联系老师或家人。

#### Scenario: 识别到挫败情绪
- **WHEN** 学生表达「这次又考砸了，怎么学都没用」
- **THEN** 回应 MUST 先回应情绪，再给出可执行的小步骤建议
- **AND** MUST NOT 使用说教式、否定式或对比式措辞

#### Scenario: 持续负面情绪
- **WHEN** 同一会话中负面表达反复出现
- **THEN** 回应 MUST 建议联系班主任、心理老师或家人
- **AND** 页面 MUST 展示可获得的求助渠道说明

#### Scenario: 普通问候
- **WHEN** 学生只是打招呼或闲聊
- **THEN** MUST 正常回应，MUST NOT 强行判定为情绪问题

### Requirement: R4 极端情绪兜底

当输入命中自伤、极端情绪等风险关键词时，系统 MUST 返回固定安全提示并建议求助，MUST NOT 交由模型自由发挥。

#### Scenario: 风险关键词
- **WHEN** 学生输入命中风险词表的表达
- **THEN** MUST 返回预置的安全提示文案，并给出求助渠道
- **AND** 该响应 MUST 不依赖模型输出，模型不可用时也必须生效

#### Scenario: 兜底不泄露他人
- **WHEN** 触发兜底
- **THEN** 响应 MUST NOT 包含其他学生的信息或班级排名类内容

### Requirement: R5 教师可关闭

关怀式对话 MUST 有独立开关，关闭后接口 MUST 明确拒绝并给出可读提示。

#### Scenario: 被停用
- **WHEN** 教师在助手配置中关闭关怀式对话，学生进入页面或发言
- **THEN** MUST 返回 HTTP 409 与「该能力已被教师关闭」提示
- **AND** MUST NOT 调用模型，MUST NOT 写入会话记录

#### Scenario: 关闭不影响其他技能
- **WHEN** 关怀式对话被关闭
- **THEN** 解题引导、作业批改、错题讲解 MUST 继续可用

### Requirement: R6 调用留痕

每次关怀式对话调用 MUST 记入 `audit_logs`，含 `skill = "care_chat"`、状态、耗时与 token 用量，并按 `class_id` 隔离。

#### Scenario: 成功与失败均留痕
- **WHEN** 一次关怀对话调用成功或失败
- **THEN** MUST 各产生一条对应 `status` 的审计记录
- **AND** 教师审计页 MUST 能看到该技能的调用次数与失败率

#### Scenario: 跨班不可见
- **WHEN** 教师查看审计聚合
- **THEN** MUST 只统计本班记录，MUST NOT 出现他班数据
