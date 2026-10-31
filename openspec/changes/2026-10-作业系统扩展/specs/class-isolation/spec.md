# class-isolation：班级与个人数据隔离

本能力是全系统硬约束，覆盖新增 6 个页面与全部新增接口。它不新增页面，但决定每条查询与每个响应的边界。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 班级只来自服务端

系统 MUST 从登录会话（JWT）读取 `class_id`。请求体、查询串、路径参数中的 `class_id` MUST 被忽略，MUST NOT 作为过滤条件或校验依据。

#### Scenario: 篡改请求参数
- **WHEN** A 班用户在请求中传入 B 班 `class_id`
- **THEN** MUST 仍只返回 A 班数据
- **AND** 响应 MUST NOT 因该参数产生任何 B 班内容或错误提示

#### Scenario: 缺少班级归属
- **WHEN** 用户账号没有有效班级归属
- **THEN** MUST 返回 403 与「账号未分配班级」提示，MUST NOT 返回全站数据

### Requirement: R2 数据访问层强制过滤

所有涉及 `assignments`、`submissions`、`wrong_questions`、`audit_logs` 的查询 MUST 在数据访问层带上 `class_id` 条件。MUST NOT 依赖上层业务代码补条件。

#### Scenario: 列表查询
- **WHEN** 任一列表接口被调用
- **THEN** 生成的 SQL MUST 含 `class_id` 条件，`total` MUST 按同一条件统计

#### Scenario: 详情查询
- **WHEN** 按主键查询单条资源
- **THEN** 查询条件 MUST 同时含主键与 `class_id`
- **AND** 主键存在但班级不符时 MUST 视为不存在

### Requirement: R3 跨班一律 404

访问他班资源 MUST 返回 404，MUST NOT 返回 403。原因：403 会暴露「该资源存在」，构成侧信道。

#### Scenario: 猜测编号
- **WHEN** A 班用户直接请求 B 班的作业、提交、错题或材料详情
- **THEN** MUST 返回 404
- **AND** 响应体 MUST NOT 含资源名称、创建者或任何字段

#### Scenario: 列表与总数一致
- **WHEN** A 班用户以仅存在于 B 班的标题或关键词筛选
- **THEN** MUST 返回空列表与 `total: 0`
- **AND** MUST NOT 出现「列表为空但总数非零」的情况

#### Scenario: 跳转不绕过检查
- **WHEN** 用户从检索结果或错题页跳转到材料详情
- **THEN** 目标接口 MUST 重新做班级校验，MUST NOT 因来源可信而跳过

### Requirement: R4 角色越权返回 403

角色不符（学生调用教师接口、教师调用学生专属接口）MUST 返回 403。这与跨班 404 是两条不同规则，MUST NOT 混用。

#### Scenario: 学生调教师接口
- **WHEN** 学生调用 `/api/teacher/*` 下任一接口
- **THEN** MUST 返回 403，且 MUST NOT 改动任何数据

#### Scenario: 教师调学生接口
- **WHEN** 教师调用 `/api/analytics/me` 等学生专属接口
- **THEN** MUST 返回 403 或明确的不适用提示，MUST NOT 返回任意学生数据

### Requirement: R5 个人数据仅本人可见

错题、学情、提交详情、关怀会话 MUST 只对本人可见。同班同学之间 MUST 互不可见。

#### Scenario: 同班学生互查
- **WHEN** 学生乙请求学生甲的错题、画像或提交
- **THEN** MUST 返回 404 或空结果
- **AND** MUST NOT 返回学生甲的任何内容、统计值或数量

#### Scenario: 教师可见范围
- **WHEN** 教师查看本班提交与审计
- **THEN** MUST 能看到本班学生的提交与批改结果
- **AND** MUST NOT 看到学生的关怀式对话内容

### Requirement: R6 5 学科 tab 在新增页面一致

新增 4 个学生页面与 2 个教师页面 MUST 使用与既有页面相同的 5 学科 tab（数学、语文、英语、物理、化学），学科取值 MUST 与数据库一致。

#### Scenario: 学科一致
- **WHEN** 在交作业、错题、作业与改分页面切换学科
- **THEN** MUST 只显示该学科数据，tab 顺序与既有讲义页一致

#### Scenario: 非法学科参数
- **WHEN** 请求传入不在 5 学科内的 `subject`
- **THEN** MUST 返回 400 或空列表，MUST NOT 返回全学科混合数据

### Requirement: R7 侧栏按角色渲染

登录后 MUST 按角色渲染侧栏：教师 5 项、学生 7 项。MUST NOT 出现可点击但无权限的入口。

#### Scenario: 教师侧栏
- **WHEN** 教师登录
- **THEN** MUST 显示 5 项菜单：本班首页、讲义管理、助手配置、作业与改分、审计与统计

#### Scenario: 学生侧栏
- **WHEN** 学生登录
- **THEN** MUST 显示 7 项菜单：本班首页、讲义与检索、助手对话、交作业、错题、关怀式对话、学情分析

#### Scenario: 直接访问越权页面
- **WHEN** 学生直接输入教师页面 URL
- **THEN** MUST 返回 403 或跳转到本班首页，MUST NOT 渲染教师页面内容

### Requirement: R8 越权检查可复跑

仓库 MUST 提供可复跑的隔离检查，覆盖列表、详情、统计与跳转四类路径，输出每条结论与证据。

#### Scenario: 一键检查
- **WHEN** 执行隔离检查脚本
- **THEN** MUST 输出每条检查的通过与否，且失败项 MUST 指明接口与期望状态码

#### Scenario: 未执行不得算通过
- **WHEN** 某项检查因环境缺失无法执行
- **THEN** MUST 标记为「未执行」，MUST NOT 计入通过数
