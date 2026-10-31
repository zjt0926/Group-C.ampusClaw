# learning-analytics：学情分析与学习画像

本能力覆盖学生端「学情分析」页面。所有数字 MUST 来自本班、本人维度的数据库聚合，MUST 可逐项与数据库行数对账。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 聚合口径固定且可对账

系统 MUST 提供 `GET /api/analytics/me`，按下列口径聚合，MUST NOT 在实现中临时改动口径：

| 指标 | 口径 |
| --- | --- |
| 累计提问 | 本人在学科助手对话中 `role = user` 的消息数，不含关怀式对话 |
| 作业提交 | 本人 `submissions` 行数，含 `failed` |
| 正确率 | `ai_score >= 60` 的提交数 ÷ 已 `graded` 的提交数 |
| 错题累计 | 本人 `wrong_questions` 行数 |

#### Scenario: 数字与数据库一致
- **WHEN** 学生打开学情页，同时用 SQL 统计本人在各表的实际行数
- **THEN** 页面四个指标 MUST 与 SQL 结果逐一相等

#### Scenario: 分母为零
- **WHEN** 学生尚无已批改的提交
- **THEN** 正确率 MUST 返回 `null`，页面 MUST 显示「暂无数据」
- **AND** MUST NOT 用 0% 或 100% 代替

#### Scenario: 班级条件不可篡改
- **WHEN** 请求中传入其他学生 `student_id` 或他班 `class_id`
- **THEN** MUST 仍只返回当前登录学生本人的数据
- **AND** MUST NOT 返回任何他班聚合值

### Requirement: R2 图表数据

系统 MUST 提供学科掌握度、近期趋势与学科热力所需的数据结构：按 `subject` 分组的掌握度（无数据学科为 `null`）、最近 10 次已批改提交的时间序列、按学科与周次的提交分布。

#### Scenario: 五学科全覆盖
- **WHEN** 学生只有数学作业数据
- **THEN** 响应 MUST 包含 5 个学科键，无数据学科值为 `null`
- **AND** 雷达图 MUST 在缺失学科处留空，MUST NOT 补 0

#### Scenario: 趋势序列
- **WHEN** 学生有 3 次已批改提交
- **THEN** 折线序列 MUST 含 3 个点，按时间升序，取值为 `coalesce(teacher_score, ai_score)`

#### Scenario: 热力分布
- **WHEN** 学生某学科无提交
- **THEN** 热力数据 MUST 该学科为空，页面 MUST 显示「暂无数据」而不是满格色块

### Requirement: R3 AI 学习画像

系统 MUST 基于聚合结果生成学习画像，含学习风格、强科、待提升三部分与可执行建议。画像 MUST NOT 引用其他学生的数据。

#### Scenario: 画像生成
- **WHEN** 学生有足够数据（已批改提交 ≥ 3）并请求画像
- **THEN** MUST 返回三段式画像与至少一条具体建议
- **AND** 建议 MUST 与本人错题学科或趋势一致，MUST NOT 是通用套话堆叠

#### Scenario: 数据不足
- **WHEN** 已批改提交少于 3 次
- **THEN** MUST 只返回统计数字与「数据不足，暂不生成画像」提示
- **AND** MUST NOT 编造画像内容

#### Scenario: 画像输入范围
- **WHEN** 生成画像
- **THEN** 发往模型的内容 MUST 只含聚合数字与错题主题
- **AND** MUST NOT 含原始作答全文或其他学生信息

### Requirement: R4 画像失败降级

模型不可用或返回异常时，页面 MUST 仍能展示统计数字与图表，MUST NOT 整页失败。

#### Scenario: 模型故障
- **WHEN** 生成画像时模型超时或返回非法内容
- **THEN** MUST 返回 200 与统计数字，画像字段为 `null` 并附失败提示
- **AND** 图表 MUST 正常渲染

#### Scenario: 数据接口故障
- **WHEN** 聚合查询本身失败
- **THEN** MUST 返回 503 与通用故障提示，MUST NOT 返回全 0 的假数据

### Requirement: R5 仅本班且仅本人

学情数据 MUST 只从本班数据聚合，且只对本人可见。同学之间 MUST 互不可见，跨班 MUST 返回 404。

#### Scenario: 同班同学互相看不到
- **WHEN** 学生乙访问学情页
- **THEN** MUST 只看到学生乙本人的数字与画像
- **AND** MUST NOT 出现学生甲的任何统计值

#### Scenario: 外班访问
- **WHEN** 学生丙（外班）访问本班学情接口或猜测学生编号
- **THEN** MUST 返回 404 或仅返回其本人数据，MUST NOT 返回本班任何聚合

#### Scenario: 教师视角
- **WHEN** 教师访问 `/api/analytics/me`
- **THEN** MUST 返回 403 或明确的角色不适用提示，MUST NOT 返回任意学生的画像

### Requirement: R6 页面状态完整

学情页 MUST 展示加载、无数据、部分数据缺失、服务故障四类状态。

#### Scenario: 全空数据
- **WHEN** 新学生首次进入学情页
- **THEN** MUST 显示各指标为 0 或「暂无数据」，图表为空态
- **AND** MUST NOT 出现 `NaN`、`undefined` 或空白图表框

#### Scenario: 登录失效
- **WHEN** 接口返回 401
- **THEN** 页面 MUST 清理已展示数据并回到登录流程
