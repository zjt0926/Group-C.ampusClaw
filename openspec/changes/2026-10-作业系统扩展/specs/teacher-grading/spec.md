# teacher-grading：作业与改分

本能力覆盖教师端「作业与改分」页面。核心是**终评权在教师**：AI 只给初评，教师可覆盖，覆盖过程留痕且不破坏 AI 原始结果。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 本班提交列表按学科切分

系统 MUST 提供 `GET /api/teacher/submissions`，按 5 学科 tab 列出本班全部作业的提交，含学生、作答、状态、AI 分、终评与改分入口。班级 MUST 由服务端确定。

#### Scenario: 本班列表
- **WHEN** A 班教师切换到「数学」tab
- **THEN** MUST 列出 A 班数学作业的全部提交，含 `student`、`content`、`status`、`ai_score`、`teacher_score`
- **AND** 每条 MUST 可进入改分

#### Scenario: 跨班不可见
- **WHEN** 教师请求他班提交列表，或在参数中传入他班 `class_id`
- **THEN** MUST 仍只返回本班数据；他班提交 MUST NOT 出现在列表或 `total` 中

#### Scenario: 待处理与已完成可分
- **WHEN** 列表中存在 `pending`、`grading`、`graded`、`failed` 四种状态
- **THEN** MUST 可区分显示，且 `failed` MUST 提供重试入口

### Requirement: R2 教师终评覆盖

系统 MUST 提供 `PATCH /api/submissions/<id>/score`，写入 `teacher_score`（0—100 整数）与 `teacher_comment`（≤ 500 字符）。教师字段 MUST 与 AI 字段分列存放，MUST NOT 覆盖 `ai_score`、`ai_comment`、`ai_evidence`。

#### Scenario: 覆盖终评
- **WHEN** 教师对一条已 `graded` 的提交改分并填写评语
- **THEN** MUST 写入 `teacher_score` 与 `teacher_comment`，`ai_*` 字段 MUST 保持原值
- **AND** 学生端 MUST 在刷新后看到终评，并标注「教师终评」

#### Scenario: 重复改分
- **WHEN** 教师对同一提交多次改分
- **THEN** 每次 MUST 覆盖上一次的 `teacher_*`，并各写一条 `audit_logs`（`action = grade_override`）
- **AND** 审计记录 MUST 含改前值与改后值

#### Scenario: 参数非法
- **WHEN** `teacher_score` 不是 0—100 整数，或 `teacher_comment` 超过 500 字符
- **THEN** MUST 返回 400 与明确提示，MUST NOT 写入任何字段

#### Scenario: 提交尚未批改
- **WHEN** 教师对 `pending`、`grading` 或 `failed` 的提交改分
- **THEN** MUST 返回 409 与「该提交尚未完成 AI 批改」提示，MUST NOT 写入终评

### Requirement: R3 教师判错补录

教师 MUST 能把 AI 判对的题目标记为判错，该题 MUST 进入学生错题本，且与自动判错的错题共用同一套讲解与幂等规则。

#### Scenario: 标记判错
- **WHEN** 教师对一条 `graded` 提交执行「标记为错」
- **THEN** MUST 写入 `wrong_questions`，`error_reason` 标明来源为教师判定
- **AND** 学生错题页 MUST 出现该题

#### Scenario: 重复标记
- **WHEN** 教师对同一提交重复标记判错
- **THEN** MUST 仍只有一条对应错题记录，MUST NOT 产生重复条目

#### Scenario: 撤销标记
- **WHEN** 教师撤销判错
- **THEN** MUST 移除或失效该错题记录，学生错题页 MUST 不再显示该题
- **AND** 已生成的讲解内容 MUST 一并失效，避免残留

### Requirement: R4 权限

学生 MUST NOT 调用任何改分接口；教师 MUST NOT 操作他班提交。越权 MUST 返回明确状态码，且 MUST NOT 改动数据。

#### Scenario: 学生越权
- **WHEN** 学生调用 `PATCH /api/submissions/<id>/score`
- **THEN** MUST 返回 403，且 `teacher_score` MUST 保持为空

#### Scenario: 教师跨班
- **WHEN** A 班教师对 B 班提交改分
- **THEN** MUST 返回 404，且 MUST NOT 改动任何字段

#### Scenario: 未登录
- **WHEN** 未登录请求改分接口
- **THEN** MUST 返回 401

### Requirement: R5 学生端同步可见

终评结果 MUST 在学生端同步可见，且学生 MUST 能区分「AI 初评」与「教师终评」。

#### Scenario: 展示规则
- **WHEN** 提交已有终评
- **THEN** 学生端 MUST 显示 `teacher_score` 并标注「教师终评」
- **AND** 无终评时 MUST 显示 `ai_score` 并标注「AI 初评」

#### Scenario: 改分后即时生效
- **WHEN** 教师在改分后，学生刷新「交作业」或提交详情
- **THEN** MUST 看到新的终评分与评语，MUST NOT 需要重新提交

### Requirement: R6 改分全程留痕

每次改分与判错操作 MUST 记入 `audit_logs`，含操作人、`class_id`、`submission_id`、改前改后值与耗时。

#### Scenario: 改分留痕
- **WHEN** 教师完成一次改分
- **THEN** MUST 存在一条可查的审计记录，教师审计页 MUST 能按时间查到该操作

#### Scenario: 审计不可篡改
- **WHEN** 教师再次改分
- **THEN** MUST 追加新记录，MUST NOT 覆盖或删除历史记录

### Requirement: R7 页面状态完整

「作业与改分」页面 MUST 展示空列表、加载中、改分成功、改分失败与权限不足五类状态。

#### Scenario: 空列表
- **WHEN** 本班该学科尚无任何提交
- **THEN** MUST 显示空态文案，MUST NOT 显示空白表格或报错

#### Scenario: 改分失败
- **WHEN** 改分请求返回 400 或 409
- **THEN** MUST 在页面就地提示原因，且表单 MUST 保留用户已填内容
