# CampusClaw 小组学期项目

## 一、项目简介

CampusClaw 是一个面向高中班级的 AI 学科助手系统：

- **教师**：管理讲义、配置 AI 技能与 MCP 工具、发布作业、审核 AI 批改结果、查看审计与统计
- **学生**：检索讲义、按学科与 AI 助手流式对话、交作业看 AI 批改、积累错题并获得三段式讲解、查看个人学情画像

## 二、技术栈与架构约定

- 后端：Flask + Jinja2 服务端渲染
- 认证：JWT 登录（具体账号体系与登录规则在开发时自行设计，见「三、账号与角色」的最低要求）
- 部署：Docker Compose，Web 服务端口经环境变量配置
- AI 能力：课程 AI 网关（密钥只从环境变量读，不进代码、不进前端）
- 分层：`app/api | services | repositories | adapters`
- 开发流程：每组功能先走 OpenSpec 变更四件套，再写代码

## 三、账号与角色

不预设具体账号。开发时自行设计账号体系与登录要求，但**必须满足以下最低配置**，否则班级隔离和数据隔离无从验收：

- **教师账号 ≥ 1 个**：能进教师端 5 个页面
- **同班学生账号 ≥ 2 个**：验证「错题、学情画像等个人数据仅本人可见，同班同学互相看不到」
- **另一个班的学生账号 ≥ 1 个**：验证「跨班访问一律 404，看不到别的班任何数据」
- 登录后按角色渲染不同侧栏：教师 5 项菜单，学生 7 项菜单

## 四、功能需求总览（12 个页面）

**教师端 5 页**：本班首页 / 讲义管理 / 助手配置 / 作业与改分 / 审计与统计
**学生端 7 页**：本班首页 / 讲义与检索 / 助手对话 / 交作业 / 错题 / 关怀式对话 / 学情分析

### 贯穿全局的 5 条设计（每页都必须体现）

1. **5 学科 tab**：数学 / 语文 / 英语 / 物理 / 化学，讲义、对话、作业、错题都按学科切分
2. **班级隔离**：只能看自己班的数据，跨班访问一律 404
3. **学生技能只读**：学生能看到技能名称与触发条件，不能改技能提示词
4. **API Key 脱敏**：前端只显示掩码，完整 Key 不进前端、不进仓库
5. **无依据不伪造来源**：AI 引用来源只引用真实检索命中，检索为空就明说"未命中"

### 九组能力（按实施顺序）

| 组 | 能力 | 覆盖页面 | 优先级 |
| --- | --- | --- | --- |
| A | 认证 + 班级/学科底座 + 页面外壳（12 个路由先立起来） | 全部 | P0 |
| B | 讲义入库（标题+多行正文，每行一切片）与词法检索（来源+相关度+标签） | 教师讲义管理 / 学生讲义与检索 | P0 |
| C | 学科助手流式对话（SSE + 技能状态横条 + AI 执行过程面板 + 来源引用） | 学生助手对话 | P0 |
| D | 技能与智能体配置（skill.json 四要素、zip 包注册、内置 4 工具、三个必做技能） | 教师助手配置 | P0 |
| E | MCP 接入与执行可视化（服务器卡片、工具名@服务器名、工具调用痕迹） | 教师助手配置 / 学生对话 | P0 |
| F | 作业异步批改与改分（处理中→已完成、AI 评分带依据、教师终评、幂等键） | 教师作业与改分 / 学生交作业 | P0 |
| G | 错题本与三段式讲解（错因/相关知识点/修正建议，仅本人可见） | 学生错题 | P1 |
| H | 关怀式对话 + 学情分析（独立会话、本人维度聚合画像） | 学生关怀式对话 / 学情分析 | P1 |
| I | 审计与合规收口（技能调用全落审计流水、合规五条文档化） | 教师审计与统计 | P1 |

三个必做技能（seed 进初始化脚本）：

- **解题引导**：不给最终答案，先给思路提示，学生追问逐步推进
- **作业批改**：按题目评分点打分并给出引用讲义的依据
- **错题讲解**：三段式——错因分析 / 相关知识点（带来源）/ 修正建议

## 五、验收口径（最终走查清单）

以下用「教师 / 学生甲（本班）/ 学生乙（本班）/ 学生丙（外班）」指代第三节要求的测试账号：

1. 教师发布数学作业「用求根公式解 x^2-5x+6=0」，并入库含该例题的讲义
2. 学生甲检索「求根公式」命中来源与相关度
3. 学生甲助手对话提问：技能横条 + 流式 + 执行过程 + 来源引用齐全；绑 MCP 工具后能看到工具痕迹
4. 学生甲故意答错交作业：状态「处理中」→「已完成」，出 AI 分/评语/依据；教师改分落终评
5. 学生甲错题页出现该题，三段式讲解带来源；重复请求不重复调 LLM
6. 学生甲学情页数字与数据库实际行数对账
7. 学生乙看不到学生甲的错题与画像；学生丙全程看不到本班任何数据
8. 教师审计页流水齐全；`docs/compliance-check.md` 合规五条可逐条点核
9. 全仓库 grep：无 API Key 明文；接口层无越权数据出口

## 六、开发规范

- 每组功能 = 一条 OpenSpec 变更（proposal + design + tasks + spec），先评审再实现
- 提示词与文档细节：见组内飞书文档（链接在群公告/任务评论里）
- 提交信息格式：`feat: xxx` / `fix: xxx` / `docs: xxx` / `chore: xxx`
- 禁止提交：`.env`、任何 API Key、`logs/`、本地数据库文件

## 七、实施版启动与验收

### 7.1 Docker Compose 启动

```bash
cp .env.example .env          # 按需修改密钥；.env 已在 .gitignore 中
docker compose build
docker compose up -d
docker compose ps             # web / worker / redis / db 四个服务
```

- 访问地址：`http://localhost:8000`（`WEB_PORT` 可改）
- 健康检查：`GET /healthz` 返回 `db`、`redis` 与 `audit_failures`
- 首次启动由 `web` 容器执行 `alembic upgrade head` 与 `python -m app.seed`；`worker` 不重复迁移

### 7.2 测试账号（seed 写入，密码统一为 `Campus@123`）

| 账号 | 角色 | 班级 | 用途 |
| --- | --- | --- | --- |
| `teacher_a` | 教师 | 高一（3）班 `cls-a` | 教师端 5 页、改分、审计 |
| `student_a1` | 学生 | `cls-a` | 本班学生甲（含一条已批改数学提交） |
| `student_a2` | 学生 | `cls-a` | 本班学生乙（个人数据隔离对照） |
| `student_b1` | 学生 | 高一（5）班 `cls-b` | 外班学生（跨班 404 对照） |

登录页为正常用户名 / 密码表单，登录成功写入 HttpOnly JWT Cookie，按角色渲染 5 / 7 项侧栏。

### 7.3 本地直跑（不依赖 Docker）

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set CELERY_ALWAYS_EAGER=1      # PowerShell: $env:CELERY_ALWAYS_EAGER="1"
.venv\Scripts\python -m app.seed
.venv\Scripts\python -m flask --app app.wsgi run -p 8000
.venv\Scripts\python -m pytest apitest -q
```

本地无 Redis 时，`CELERY_ALWAYS_EAGER=1` 会在请求内同步执行批改，便于走查；Docker 环境使用 `worker` 异步执行。

### 7.4 关键配置项（`.env`）

- `SECRET_KEY` / `JWT_SECRET`：会话与 JWT 签名密钥，部署时必须替换
- `DATABASE_URL`：默认 Compose 内 `postgresql+psycopg2://...`，本地可留空使用 SQLite
- `REDIS_URL`：Celery broker / backend
- `AI_GATEWAY_BASE_URL`、`AI_GATEWAY_API_KEY`、`AI_GATEWAY_MODEL`：留空时启用本地演示生成器，链路完整可走，来源仍只引用真实检索命中
- `AI_TIMEOUT_SECONDS`：网关超时，默认 90 秒
- `PASS_SCORE`：判错及格线，默认 60
- `COOKIE_SECURE`：HTTPS 部署时设为 1
- `WEB_PORT`：宿主端口，默认 8000

### 7.5 验收命令

```bash
python scripts/check_compliance.py --base-url http://localhost:8000
make check-security
```

`check_compliance.py` 按 5 条合规检查点输出 `PASS / FAIL / UNEXECUTED`；未执行项不会被标记为通过。

`make check-security` 一键复查安全基线（SEC-05 密钥扫描 + SEC-06 依赖审计），分项为 `make check-secrets` / `make audit-deps`。无 GNU Make 时等价执行 `sh scripts/check_security.sh`；依赖审计要求容器已 `docker compose up -d`，发现已知漏洞时退出码非 0。

### 7.6 已知限制

- 词法检索为轻量实现（中文单字 + 双字 bigram + 英文/数字 token），不是向量检索；未命中时明确返回空来源，不伪造引用。
- 未配置 AI 网关时使用本地演示生成器，分数与评语为固定规则结果，仅用于链路演示。
- 改分与判错操作写入 `audit_logs` 的 `action`（`grade_override` / `mark_wrong` / `undo_mark_wrong`），技能调用写入 `skill` 字段；教师审计页默认流水可查到上述操作。
- Docker 基础镜像需可访问镜像仓库；网络受限时可先从可用镜像源预拉取 `python:3.11-slim`、`postgres:16-alpine`、`redis:7-alpine` 并打上同名 tag。
- `locust` 压测（任务 9.3）尚未执行，保持未勾选。

