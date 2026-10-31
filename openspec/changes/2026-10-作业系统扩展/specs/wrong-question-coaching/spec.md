# wrong-question-coaching：错题本与三段式讲解

本能力覆盖学生端「错题」页面、错题入库规则与错题讲解技能。前提是 `assignment-submission` 已能产出 `graded` 的提交与 AI 错因。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 判错自动入库且不重复

批改结果为 `graded` 且满足判错条件时，系统 MUST 写入 `wrong_questions`，并置 `submissions.is_wrong = true`。判错条件为 `ai_score < 60` 或模型在结构化结果中标记该题为错。同一 `(submission_id, question_no)` MUST 只有一条错题记录。

#### Scenario: 判错入库
- **WHEN** 学生甲的提交批改完成且分数低于及格线
- **THEN** MUST 生成错题记录，含 `question_text`、`my_answer`、`error_reason`、`subject`、`class_id`
- **AND** `submissions.is_wrong` MUST 为真

#### Scenario: 批改重试不重复入库
- **WHEN** 同一提交因失败重试后再次批改成功
- **THEN** MUST 仍只有一条对应错题记录，MUST NOT 出现重复条目

#### Scenario: 批改失败不产生错题
- **WHEN** 提交状态为 `failed`
- **THEN** MUST NOT 产生任何错题记录，MUST NOT 以空错因占位

### Requirement: R2 错题列表仅本人可见

系统 MUST 提供 `GET /api/wrong-questions`，按 5 学科 tab 展示本人错题。列表 MUST 只含当前学生本人数据，班级条件 MUST 由服务端确定。

#### Scenario: 本人错题
- **WHEN** 学生甲打开错题页并切换学科
- **THEN** MUST 只列出学生甲在该学科下的错题，含题目、我的作答、AI 错因与讲解状态

#### Scenario: 同班同学互相看不到
- **WHEN** 学生乙请求错题列表，或指定学生甲的 `wrong_question_id`
- **THEN** MUST 返回空列表或 404，MUST NOT 返回学生甲任何错题内容

#### Scenario: 外班访问
- **WHEN** 学生丙（外班）访问本班错题接口或猜测编号
- **THEN** MUST 返回 404，且 MUST NOT 泄露错题是否存在

### Requirement: R3 三段式讲解

系统 MUST 提供 `POST /api/wrong-questions/<id>/explain`，调用错题讲解技能，输出 MUST 含三段：错因分析、相关知识点（带讲义来源）、修正建议。讲解 MUST NOT 直接给出最终答案。

#### Scenario: 三段齐全
- **WHEN** 学生甲对自己的一条错题点击「请助手讲解」且技能已启用
- **THEN** 响应 MUST 同时包含 `error_analysis`、`knowledge_points`、`advice` 三段且均非空
- **AND** `knowledge_points` 的每条 MUST 带可定位的讲义来源

#### Scenario: 不给最终答案
- **WHEN** 讲解生成完成
- **THEN** 输出 MUST NOT 包含完整最终答案或可直接抄写的解题步骤结论
- **AND** MUST 以引导重做思路为主，措辞需能被「是否出现最终数值答案」这一规则检查

#### Scenario: 讲解时检索未命中
- **WHEN** 讲解过程中本班讲义未命中相关知识点
- **THEN** `knowledge_points` MUST 为空并附「未命中讲义」说明
- **AND** MUST NOT 编造讲义标题、切片编号或引用页码

### Requirement: R4 讲解结果缓存与幂等

讲解结果 MUST 写回 `wrong_questions.explanation` 与 `explained_at`。对同一条错题再次请求讲解时，系统 MUST 返回已存内容，MUST NOT 再次调用模型。

#### Scenario: 重复请求
- **WHEN** 学生对同一错题连续点击两次「请助手讲解」
- **THEN** MUST 只发生一次模型调用，两次响应内容一致
- **AND** 审计中 `wrong_explain` 技能记录 MUST 只有一条成功调用

#### Scenario: 并发请求
- **WHEN** 同一错题在两个标签页同时请求讲解
- **THEN** MUST 只有一个请求真正调用模型，另一个等待后读到同一结果
- **AND** MUST NOT 产生两份不同讲解

#### Scenario: 重试已失败的讲解
- **WHEN** 上次讲解因模型故障失败，`explanation` 仍为空
- **THEN** 再次请求 MUST 重新调用模型，MUST NOT 把失败结果当作已缓存

### Requirement: R5 讲解技能受教师开关控制

错题讲解技能 MUST 有独立启用开关，与作业批改技能互不影响。开关关闭时接口 MUST 明确拒绝而不是静默失败。

#### Scenario: 技能被停用
- **WHEN** 教师在助手配置中停用错题讲解技能后，学生点击「请助手讲解」
- **THEN** MUST 返回 HTTP 409 与「该技能已被教师停用」提示
- **AND** MUST NOT 调用模型，MUST NOT 写入讲解内容

#### Scenario: 停用讲解不影响批改
- **WHEN** 错题讲解技能被停用
- **THEN** 作业提交与批改 MUST 继续正常工作

#### Scenario: 学生不能改技能
- **WHEN** 学生尝试通过任何接口修改技能提示词或开关
- **THEN** MUST 返回 403，且技能配置 MUST 保持不变

### Requirement: R6 讲解调用留痕

每次讲解调用 MUST 记录到 `audit_logs`，含 `skill = "wrong_explain"`、`class_id`、`user_id`、状态、耗时与 token 用量。

#### Scenario: 成功留痕
- **WHEN** 一次讲解调用成功
- **THEN** MUST 存在一条 `status = success` 的审计记录，`tokens` 与网关返回一致

#### Scenario: 失败留痕
- **WHEN** 讲解调用超时或模型返回异常
- **THEN** MUST 存在一条 `status` 为 `timeout` 或 `error` 的审计记录
- **AND** 学生端 MUST 看到失败提示，MUST NOT 看到空白讲解

### Requirement: R7 教师判错补录进入同一错题本

教师把 AI 判对的题目标记为判错后，该题 MUST 出现在学生错题本中，且 `error_reason` MUST 标明来源为教师判定。

#### Scenario: 教师补录
- **WHEN** 教师对一条 `graded` 提交执行判错
- **THEN** 学生错题页 MUST 出现该题，`error_reason` 标注为教师判定
- **AND** 该题 MUST 可按 R3 请求讲解，且与自动判错的错题共用同一套幂等规则
