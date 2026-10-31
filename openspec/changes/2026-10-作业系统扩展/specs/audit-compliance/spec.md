# audit-compliance：审计、统计与合规收口

本能力覆盖教师端「审计与统计」页面，以及贯穿全系统的 5 条合规检查点。审计 MUST 覆盖全部 `/api/*` 调用与全部技能调用，包括失败与超时。`MUST` 表示必须，`MUST NOT` 表示禁止；`WHEN` 为触发条件，`THEN` 为预期结果。

## ADDED Requirements

### Requirement: R1 全量 API 调用留痕

系统 MUST 通过中间件记录全部 `/api/*` 请求，字段含 `created_at`、`class_id`、`user_id`、`action`（方法 + 路由模板）、`status`、`duration_ms`。`MUST NOT` 遗漏失败请求。

#### Scenario: 正常请求
- **WHEN** 任一已登录用户调用 `/api/*`
- **THEN** MUST 产生一条审计记录，`status` 为成功，`duration_ms` 大于等于 0
- **AND** `class_id`、`user_id` MUST 与当前会话一致

#### Scenario: 失败请求
- **WHEN** 请求返回 4xx 或 5xx，或抛出未捕获异常
- **THEN** MUST 仍产生一条审计记录，`status` 标明失败或错误
- **AND** MUST NOT 因异常导致审计缺失

#### Scenario: 未登录请求
- **WHEN** 未登录用户请求 `/api/*`
- **THEN** MUST 记录 `user_id` 为空、`class_id` 为空的审计记录，MUST NOT 记录请求体正文

### Requirement: R2 技能调用单独留痕

每次技能调用 MUST 单独记录一条，含 `skill`、`tokens`、`status`（`success` / `error` / `timeout`）、`duration_ms`。技能范围至少含 `tutor_hint`、`homework_grade`、`wrong_explain`、`care_chat`。

#### Scenario: 四个技能均可区分
- **WHEN** 教师查看审计聚合
- **THEN** MUST 能分别看到四个技能的调用次数、失败率与总 token
- **AND** MUST NOT 把不同技能合并成一条统计

#### Scenario: 超时留痕
- **WHEN** 某次技能调用超时
- **THEN** MUST 记录 `status = timeout` 并保留 `duration_ms`
- **AND** 失败率 MUST 计入该次调用

#### Scenario: token 缺失
- **WHEN** 网关未返回 usage 信息
- **THEN** `tokens` MUST 记为 `null`，MUST NOT 记为 0
- **AND** 聚合时 MUST 区分「无用量数据」与「用量为 0」

### Requirement: R3 参数脱敏

审计记录的 `params` MUST 为摘要，正文类字段 MUST 只保留前 200 字符与原文长度；密码、token、`Authorization`、`api_key` 等字段 MUST 一律记为 `***`。

#### Scenario: 正文摘要
- **WHEN** 记录一次提交或对话调用的参数
- **THEN** 正文 MUST 被截断为前 200 字符并附总长度
- **AND** MUST NOT 存储完整作答或完整对话

#### Scenario: 敏感字段
- **WHEN** 请求中含 `password`、`token`、`Authorization`、`api_key`
- **THEN** 对应值 MUST 记为 `***`
- **AND** 审计表中 MUST 检索不到任何真实密钥片段

#### Scenario: 脱敏可验证
- **WHEN** 执行合规检查脚本扫描 `audit_logs`
- **THEN** MUST 无法匹配到形如密钥的字符串

### Requirement: R4 按技能聚合统计

系统 MUST 提供 `GET /api/teacher/audit/summary`，按技能聚合调用次数、失败率与总 token，并按 `class_id` 过滤。

#### Scenario: 聚合正确
- **WHEN** 本班有 10 次 `homework_grade` 调用，其中 2 次失败
- **THEN** 聚合 MUST 返回 `count = 10`、`fail_rate = 0.2`、`sum(tokens)` 为该 10 次实际之和

#### Scenario: 无数据技能
- **WHEN** 某技能本班从未调用
- **THEN** MUST 返回 `count = 0`，失败率 MUST 为 `null`
- **AND** MUST NOT 除以 0 或返回 `NaN`

#### Scenario: 班级隔离
- **WHEN** A 班教师查看聚合
- **THEN** MUST 只统计 A 班记录，`count` MUST 与 A 班实际行数一致

### Requirement: R5 流水明细可查询

系统 MUST 提供 `GET /api/teacher/audit`，支持按技能、状态、时间范围筛选与分页，结果 MUST 限于本班。

#### Scenario: 筛选与分页
- **WHEN** 教师按技能筛选并翻页
- **THEN** MUST 返回 `items`、`total`、`page`、`page_size`，翻页不重不漏

#### Scenario: 跨班筛选
- **WHEN** 教师用他班存在的技能记录特征筛选
- **THEN** MUST 返回本班条件下的空结果与 `total: 0`

### Requirement: R6 合规五条可逐条点核

仓库 MUST 提供 `docs/compliance-check.md`，列出 5 条合规检查点，每条含判定方法、证据位置与复跑命令。

#### Scenario: 五条齐全
- **WHEN** 打开 `docs/compliance-check.md`
- **THEN** MUST 含且仅含以下 5 条：①每条技能调用均留痕（含失败/超时）②API Key 不进前端与仓库 ③未命中知识库不伪造来源 ④班级与个人数据隔离 ⑤学生技能只读
- **AND** 每条 MUST 有可执行的核对方式，而不是主观描述

#### Scenario: 逐条可验证
- **WHEN** 按文档步骤逐条执行
- **THEN** 每条 MUST 能得出通过或不通过的明确结论
- **AND** 未执行的检查项 MUST 标注为「未执行」，MUST NOT 预填「通过」

### Requirement: R7 API Key 不进前端与仓库

系统 MUST 只从服务端环境变量读取 AI 网关密钥。前端页面、静态资源、接口响应与仓库文件 MUST NOT 出现完整密钥；前端如需展示，MUST 只显示掩码。

#### Scenario: 前端无密钥
- **WHEN** 抓取任意页面 HTML、JS 与 `/api/*` 响应
- **THEN** MUST 不含完整密钥，配置展示 MUST 为掩码

#### Scenario: 仓库无密钥
- **WHEN** 对仓库全量 grep 密钥特征
- **THEN** MUST 无命中；`.env` MUST 在 `.gitignore` 中
- **AND** `.env.example` MUST 只有占位值

### Requirement: R8 学生技能只读

学生 MUST 只能查看技能名称与触发条件，MUST NOT 修改提示词、开关或 MCP 配置。

#### Scenario: 学生读取
- **WHEN** 学生访问技能列表
- **THEN** MUST 返回技能名称、触发条件与启用状态
- **AND** MUST NOT 返回提示词全文

#### Scenario: 学生写入
- **WHEN** 学生调用技能配置的写接口
- **THEN** MUST 返回 403，配置 MUST 保持不变

### Requirement: R9 审计写入失败不静默

审计写入失败 MUST NOT 阻断业务请求，但 MUST 记录告警并可通过健康检查发现。

#### Scenario: 审计表不可写
- **WHEN** 审计写入抛错
- **THEN** 业务响应 MUST 正常返回
- **AND** MUST 记录 warning 日志，健康检查 MUST 暴露审计失败计数

#### Scenario: 长时间审计缺失
- **WHEN** 连续多次审计写入失败
- **THEN** 教师审计页 MUST 提示「审计数据可能不完整」
- **AND** MUST NOT 在数据缺失时仍显示「流水齐全」
