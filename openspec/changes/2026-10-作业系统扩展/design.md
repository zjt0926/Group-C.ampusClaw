## Context

沿用 `campusclaw-mygroup` 的前后端一体化架构：Flask 3 + Jinja2 服务端渲染，JWT 认证，RBAC 按 `class_id` 隔离，SQLAlchemy + Alembic，Docker Compose 部署，AI 能力统一走课程网关 `ai-gateway.devops.hello1023.com`。

已有能力（A—E 组）包括：登录与角色、班级与 5 学科底座、12 个路由外壳、讲义入库与词法检索、助手 SSE 对话、技能与 MCP 配置。本次新增的 6 个模块建立在这些能力之上，**不重写它们**。

本设计只描述「怎么做」与「为什么这样做」，可判定的验收条件在 `specs/` 下的 7 个能力文件中；实施计划与检查方法在 `tasks.md`。本仓库当前无业务代码，本设计不描述任何已运行的实现。

## Goals / Non-Goals

**目标**：把作业闭环跑通并可验收——提交有状态、批改有依据、改分有终评、错题有讲解、学情有数字、全程有审计。

**不做**：见 `proposal.md` 的 Non-goals。特别强调不做跨班查看、不做向量检索、不做家长端。

## Decisions

### D1：四张新表与班级隔离字段

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `assignments` | `id`、`class_id`、`subject`、`title`、`description`、`deadline`、`created_by`、`created_at` | 教师布置的作业 |
| `submissions` | `id`、`assignment_id`、`student_id`、`class_id`、`content`、`status`、`ai_score`、`ai_comment`、`ai_evidence`、`teacher_score`、`teacher_comment`、`is_wrong`、`idempotency_key`、`error_message`、`created_at`、`graded_at` | 学生提交与批改结果 |
| `wrong_questions` | `id`、`submission_id`、`student_id`、`class_id`、`subject`、`question_no`、`question_text`、`my_answer`、`error_reason`、`explanation`、`explained_at`、`created_at` | 错题与三段式讲解缓存 |
| `audit_logs` | `id`、`class_id`、`user_id`、`skill`、`action`、`params`、`status`、`duration_ms`、`tokens`、`created_at` | 调用与关键操作流水 |

- 四张表**全部**带 `class_id`，`assignments`、`submissions`、`wrong_questions` 额外建 `(class_id, created_at)` 组合索引，`audit_logs` 建 `(class_id, skill, created_at)`。
- `submissions` 建唯一约束 `(assignment_id, student_id, idempotency_key)`，用数据库约束而不是应用层判重来保证幂等。
- `wrong_questions` 建唯一约束 `(submission_id, question_no)`，同一题的讲解只存一份。
- `status` 用枚举字符串而不是布尔：`pending` / `grading` / `graded` / `failed`。新增 `grading` 是为了让「处理中」可区分「还没轮到」和「正在调模型」，SSE 才能给出有意义的阶段提示。
- `ai_evidence` 存 JSON 数组（讲义标题 + 切片编号 + 相关度），用于前端展示「依据」并支撑「无依据不伪造来源」。

备选方案：把 `wrong_questions` 做成视图而非实体表——放弃，因为需要缓存讲解文本与 `explained_at` 做幂等，视图无法承载。

### D2：异步批改用 Celery + Redis，不用线程池

提交接口只做三件事：校验、落库（`pending`）、投递任务，然后立即返回 `202`。批改在 worker 里做，`pending → grading → graded | failed`。

- 任务以 `submission_id` 为唯一参数，worker 先做一次「状态是否仍为 pending」的条件更新，抢到才继续；这样重复投递不会产生两次模型调用。
- `task_acks_late = True`、`worker_prefetch_multiplier = 1`，worker 崩溃时任务回到队列，不会丢。
- 最多重试 2 次，退避 5s / 20s；仍失败则 `failed` 并写 `error_message`，**不写任何分数**。
- 单次批改超时 90s；超过则视为失败，避免 worker 被单任务长期占用。
- 队列积压时，学生端看到的是「排队中」而不是空白，SSE 会先推一次当前状态。

备选方案：`threading` 或 `BackgroundScheduler`——放弃。Flask 进程内线程在容器重启后任务直接消失，无法满足「状态一定能收敛」的要求，也无法横向扩容。

### D3：SSE 推送，轮询兜底

`GET /api/submissions/<id>/stream` 返回 `text/event-stream`。

- 连接建立时先推一帧当前状态，之后每 2s 检查一次数据库状态，变化才推，25s 无变化发一次心跳注释帧（`: keep-alive`）。
- 终态（`graded` / `failed`）推完即主动关闭连接，前端不再重连。
- 单连接最长 120s，超时关闭；前端收到关闭且状态未终结时退化为 3s 一次轮询 `GET /api/submissions/<id>`，直到终结。
- 连接前校验：登录、`submissions.student_id == 当前用户`、`class_id` 相同；任一不满足返回 404，不返回 403（避免泄露提交是否存在）。
- 反向代理需关闭该路径的缓冲（`X-Accel-Buffering: no`），否则 Nginx 会把流攒成一坨。

备选方案：只用轮询——放弃。要求里明确写了 SSE，且轮询在批改耗时 10—30s 时会产生大量空请求。

### D4：三个必做技能的边界

| 技能 | 触发 | 输入 | 输出约束 | 开关 |
| --- | --- | --- | --- | --- |
| 解题引导 | 学生就题目提问 | 问题 + 本班讲义检索片段 | 只给思路提示，默认不给最终答案 | 教师可停用 |
| 作业批改 | 提交入队 | 作答 + 作业描述 + 讲义片段 | 分数 + 评语 + 依据来源 | 必做，不可停用 |
| 错题讲解 | 学生点「请助手讲解」 | 错题 + AI 错因 + 讲义片段 | 三段式，默认不给最终答案 | 教师可停用 |

- 三个技能各自独立的提示词模板与独立的启用开关，存在技能配置表（D 组已建）里，`skill_key` 分别为 `tutor_hint`、`homework_grade`、`wrong_explain`。
- **作业批改与错题讲解严格分离**：批改的提示词不得包含讲解段落，讲解的提示词不得重新打分。这样停用讲解不影响批改。
- 模型输出必须是可解析的 JSON（批改：`{score, comment, evidence[]}`；讲解：`{error_reason, knowledge_points[], advice}`）。解析失败即视为调用失败，不「尽力猜一个分数」。
- 分数区间 0—100 的整数，超出范围按失败处理而不是截断，避免掩盖提示词问题。

### D5：判错、错题入库与讲解幂等

- 判定规则：`ai_score < 60` 或模型在 JSON 中标记该题为错（`is_wrong: true`）→ 写 `wrong_questions`，`submissions.is_wrong = true`。
- 入库以 `(submission_id, question_no)` 去重，批改重试不会产生重复错题。
- 讲解结果写回 `wrong_questions.explanation`（JSON 三段）与 `explained_at`。**第二次点击直接返回已存内容**，不调模型——这是验收清单第 5 条「重复请求不重复调 LLM」的落点。
- 讲解请求用行级条件更新 `explained_at IS NULL` 抢占，两个标签页同时点击只有一个真正调模型，另一个等 2s 后读结果。

### D6：教师终评不覆盖 AI 结果

`teacher_score` / `teacher_comment` 与 `ai_score` / `ai_comment` **分列存放**，改分只写教师列。原因：审计要求能还原「AI 当时给了多少」，覆盖会让审计失去意义。

- 改分可重复执行，每次写一条 `audit_logs`（`action = grade_override`，`params` 含旧值新值）。
- 学生端展示规则：有终评显示终评并标注「教师终评」，无终评显示 AI 分并标注「AI 初评」。
- 教师把 AI 判对的题标记为判错时，补写 `wrong_questions`（`error_reason` 置为 `teacher_marked`），学生错题页立即出现该题。

### D7：学情聚合口径先定死，再写 SQL

验收要「数字与数据库实际行数对账」，所以口径必须先写死：

| 指标 | 口径 |
| --- | --- |
| 累计提问 | 本人在助手对话中 `role = user` 的消息数（不含关怀式对话） |
| 作业提交 | 本人 `submissions` 行数（含 `failed`） |
| 正确率 | `ai_score >= 60` 的提交数 / 已批改（`graded`）提交数；分母为 0 时返回 `null` 而不是 0 |
| 错题累计 | 本人 `wrong_questions` 行数 |
| 学科掌握度 | 按 `subject` 分组，`avg(coalesce(teacher_score, ai_score))`，无数据学科返回 `null` 并在雷达图上留空 |
| 近期趋势 | 最近 10 次已批改提交的时间序列 |

- 分母为 0 一律返回 `null`，前端显示「暂无数据」，**不用 0 冒充**——0% 正确率和没有数据是两件事。
- 聚合查询强制 `WHERE class_id = ? AND student_id = ?`，不接受请求参数传入的学生 ID。
- AI 学习画像基于上述聚合结果生成，提示词里只放聚合数字与错题主题，**不放原始作答全文**，减少泄露面。

### D8：审计中间件与脱敏

- 用 Flask `before_request` / `after_request` 钩子记录全部 `/api/*` 请求：`user_id`、`class_id`、`action`（`METHOD path` 模板化）、`status`、`duration_ms`。
- 技能调用额外记一条：`skill`、`tokens`（网关返回的 usage）、`params` 摘要。参数摘要规则：正文类字段只留前 200 字符 + 原文长度；密码、token、`Authorization`、`api_key` 一律记 `***`。
- 失败与超时**必须**留痕，`status` 记 `error` / `timeout`，这是合规第 1 条「每条技能调用均留痕」的关键。
- 审计写入走独立会话，失败时记 warning 日志但不阻断业务响应；同时把失败计数暴露在健康检查里，避免「审计悄悄挂了没人知道」。
- 聚合接口 `GET /api/teacher/audit/summary` 按 `skill` 分组算 `count`、`fail_rate`、`sum(tokens)`，仍强制 `class_id` 过滤。

### D9：班级隔离落在数据访问层

- 班级来源只有一个：JWT 里的 `class_id`。请求体/查询串里的 `class_id` **一律忽略**，不做「以参数为准」的兼容。
- `repositories` 层所有查询函数签名强制第一个参数是 `class_id`，SQL 里必须出现该条件；code review 检查项。
- 跨班资源访问返回 **404**（不返回 403），因为 403 等于告诉对方「这个 ID 存在」。
- 角色越权（学生调教师接口）返回 **403**，这是角色问题不是资源问题。
- 列表接口的 `total` 同样按 `class_id` 统计，避免「列表空但总数非空」的侧信道。

### D10：失败与降级矩阵

| 故障 | 表现 | 响应 |
| --- | --- | --- |
| Redis / 队列不可用 | 提交无法入队 | 提交接口返回 503，不落 `pending` 假状态 |
| AI 网关超时或 5xx | 批改失败 | `status = failed`，`error_message` 写明原因，可重试，不写分数 |
| 模型返回非法 JSON | 解析失败 | 同上，按失败处理 |
| SSE 不可用（代理不支持） | 前端无推送 | 自动降级轮询，页面仍能完成 |
| 讲解技能被教师停用 | 按钮不可用 | 接口返回 409 + 明确提示，不静默失败 |
| 关怀式对话被停用 | 页面提示不可用 | 接口返回 409 |
| 审计写入失败 | 业务不受影响 | 记 warning，健康检查暴露计数 |
| 统计数据缺失 | 分母为 0 | 返回 `null`，前端显示暂无数据 |

### D11：部署形态

`docker-compose.yml` 扩为 4 个服务：`web`（Flask，端口由 `WEB_PORT` 控制）、`worker`（Celery，与 web 同镜像不同 command）、`redis`（队列 broker 与 result backend）、`db`（开发 SQLite 挂卷，生产 PostgreSQL）。`worker` 与 `web` 共用 `.env`，密钥只在服务端注入。健康检查覆盖 `web` 的 `/healthz` 与 `redis` 的 `PING`。

### D12：测试与证据分层

- `apitest/`：按模块建 6 个文件，断言 HTTP 状态码 + 返回 JSON 结构 + 数据库行一致（不只断言 200）。
- `pytest`：服务层单测覆盖状态机、幂等、聚合口径、脱敏函数。
- `locust`：压 `POST /api/assignments/<id>/submit`、`GET /api/submissions`、`GET /api/analytics/me`，目标 P95 < 2s（不含异步批改本身耗时）。
- 合规 5 条用脚本验证：`scripts/check_compliance.py` 输出 5 行结论 + 证据位置，人工可复跑。

## Risks / Trade-offs

- **异步带来最终一致**：提交后不是立刻有分。用状态机 + SSE + 轮询兜底消化，代价是前端要多写一条状态分支。
- **SSE 在反向代理下容易被缓冲**：需要显式关闭缓冲，部署文档要写清楚，否则本地正常、线上不动。
- **模型分数不稳定**：同一个作答两次批改可能不同分。用幂等键避免重复批改，并在审计里保留每次调用的 usage，便于复盘。
- **讲解缓存会过期**：讲义更新后旧讲解可能引用已删除内容。本次接受，`explained_at` 与讲义版本一起记录，后续变更再处理失效。
- **审计表增长快**：全量 `/api/*` 落库，量大。本次按课程规模接受，仅建索引；不做归档与分区。
- **终评与 AI 分分列**：前端要处理「有终评/无终评」两种展示，比单列复杂，但换来可审计。

## Migration Plan

1. Alembic 新增 4 张表与索引，向下兼容（不改已有表结构）。
2. 部署增加 `redis` 与 `worker`，`web` 先上线（此时提交会 503，因为队列未就绪，按 D10 处理）。
3. 按 `tasks.md` 顺序实现：数据层 → 提交与状态机 → 批改任务 → SSE → 错题 → 关怀 → 学情 → 教师改分 → 审计。
4. 回退：停用 6 个新页面入口与 3 个技能开关，保留 4 张表数据不动；已有 6 个页面不受影响。

## Open Questions

实施前必须定下来并写进实施版 README：

1. 课程 AI 网关的 `base_url`、模型名、并发配额与计费方式；`ai_score` 是否使用固定温度（建议 0）以保证可复现。
2. 批改的及格线 60 分是写死配置还是按学科可配；本次默认全局 60，可配。
3. 生产环境用 PostgreSQL 时，`ai_evidence` 用 JSONB 还是 TEXT 存 JSON；开发 SQLite 下统一用 TEXT + 应用层解析。
4. 学情页图表用 Chart.js CDN 还是本地打包——离线环境必须本地打包，实施前确认。
