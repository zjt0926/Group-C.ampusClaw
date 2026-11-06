# 安全自查记录 · CampusClaw · C 组

> 第 8 课安全自查作业 · 第一次验证
> 记录人：C 组（成员分工详见文末）　记录日期：2026-11-06

## 一、环境

- 启动方式：**从零按 README.md 启动**，未做任何代码修改
- 仓库：`https://github.com/zjt0926/Group-C.ampusClaw.git`（默认分支 main）
- 提交号：`54c051d`
- 部署形态：Docker Compose 四容器（web / worker / db / redis），compose 项目名 `group-campusclaw`
- 本机访问地址：http://localhost:8000
- 健康检查：`GET /healthz` → `{"db":true,"redis":true,"status":"ok"}`
- 密钥管理：`.env` 本地新建（`SECRET_KEY` / `JWT_SECRET` 为随机生成的 64 位十六进制值），未提交仓库

## 二、身份与数据（种子数据自动初始化）

| 角色 | 账号 | 班级 | 密码 |
| --- | --- | --- | --- |
| 教师 | teacher_a | cls-a | Campus@123 |
| 学生 | student_a1 | cls-a | Campus@123 |
| 学生 | student_a2 | cls-a | Campus@123 |
| 学生 | student_b1 | cls-b | Campus@123 |

数据边界：作业 id 1—5 属 cls-a、id 6 属 cls-b；讲义 id 1—5 属 cls-a、id 6 属 cls-b；验证过程中 student_b1 提交作业 6 产生提交 id=3（cls-b）。

## 三、受保护接口清单（未登录应一律 401）

| 接口 | 说明 |
| --- | --- |
| GET /api/submissions | 学生提交列表 |
| GET /api/submissions/{id} | 提交详情 |
| POST /api/assignments | 教师布置作业 |
| GET /api/materials | 讲义列表 |
| GET /api/teacher/dashboard | 教师工作台 |

## 四、写入类接口清单（越权重点）

| 接口 | 说明 | 允许角色 |
| --- | --- | --- |
| POST /api/assignments | 布置作业 | teacher |
| PUT /api/teacher/skills/{skill_key} | 修改技能配置 | teacher |
| PATCH /api/submissions/{id}/score | 人工改分 | teacher |
| POST /api/teacher/materials | 上传讲义 | teacher |
| POST /api/assignments/{id}/submit | 提交作业 | student（仅本班作业） |

---

## 五、检查项记录

### SEC-01 未登录访问受保护接口

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-01 | 未登录（无 Cookie） | 依次请求 5 个受保护接口：`curl --noproxy "*" http://127.0.0.1:8000/api/submissions`、`/api/submissions/1`、`POST /api/assignments`、`/api/materials`、`/api/teacher/dashboard` | 全部返回 401，不泄露任何业务数据 | 5 个接口全部返回 HTTP 401，响应体均为 `{"error":"请先登录","error_code":"unauthorized"}` | 绿 |

### SEC-02 跨班数据隔离

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-02 | 已登录 student_a1（cls-a）与 student_b1（cls-b）；cls-b 存在作业 id=6、讲义 id=6、提交 id=3 | ① a1 查 5 个学科作业列表 `GET /api/assignments?subject=<学科>`；② a1 读 b1 的提交 `GET /api/submissions/3`；③ a1 用 cls-b 讲义原文检索 `GET /api/materials/search?q=集合与常用逻辑用语` | ① 列表仅含本班作业；② 跨班读提交返回 404 而非 403（不暴露存在性）；③ 检索结果不含 cls-b 讲义 | ① 5 个学科列表仅含 id 1—5，无 id 6；② a1 读提交 3 → 404 `{"error":"提交不存在","error_code":"not_found"}`，b1 读自己的提交 3 → 200；③ a1 检索仅命中 cls-a 讲义 material_id=1（3 条片段），未出现 cls-b material_id=6 | 绿 |

### SEC-03 学生修改技能配置（越权写）

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-03 | 已登录 student_a1；skills 表现有 4 行 cls-a 技能 | `curl -X PUT -b student_a1.jar -H "Content-Type: application/json" -d @body.json http://127.0.0.1:8000/api/teacher/skills/tutor_hint`（body：`{"name":"改过的技能名"}`） | 返回 403，数据库 skills 表无变化 | HTTP 403 `{"error":"无权限访问该资源","error_code":"forbidden"}`；DB 复核 skills 表 4 行 name 均未变（tutor_hint 仍为「解题引导」）；审计日志 id=32 记录该失败操作 | 绿 |

### SEC-04 学生直接改分（越权写）

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-04 | 已登录 student_a1；提交 id=2 属同班 student_a2，teacher_score 为 NULL | `curl -X PATCH -b student_a1.jar -H "Content-Type: application/json" -d @body.json http://127.0.0.1:8000/api/submissions/2/score`（body：`{"teacher_score":100}`） | 返回 403，submissions 表无变化 | HTTP 403 `{"error":"无权限访问该资源","error_code":"forbidden"}`；DB 复核 id=2 的 teacher_score 仍为 NULL、status 仍为 graded；审计日志 id=33 记录该失败操作 | 绿 |

### SEC-05 密钥明文泄漏扫描

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-05 | 仓库工作区与全部 git 历史 | ① `git ls-files` 检查 .env 是否被跟踪；② `git log --all -- .env` 查历史；③ 全仓库正则扫描 `sk-…`、`BEGIN … PRIVATE KEY`、`AKIA…`、`SECRET_KEY=<hex>` 等模式 | .env 不被跟踪、历史无密钥提交、工作区无硬编码密钥 | ① git 仅跟踪 `.env.example`（内容为占位符 `change-me-to-a-random-string`），`.env` 未被跟踪且位于 `.gitignore` 第 1 行；② 历史中无 .env 提交记录；③ 扫描仅 1 处误报（requirements.txt 的 `Flask-SQLAlchemy` 被大小写不敏感匹配），无真实密钥 | 绿 |

### SEC-06 依赖漏洞基线

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-06 | web 容器内为实际运行环境 | 容器内安装并执行：`pip install pip-audit && pip-audit`（pip-audit 2.10.1） | 建立漏洞基线；理想状态无高危未修复漏洞 | **发现 55 个已知漏洞，涉及 8 个包**：flask 3.0.3（PYSEC-2026-2151，修复版 3.1.3）；pyjwt 2.8.0（PYSEC-2025-183 **无修复版本**，另有多条修复至 2.12.0—2.15.0）；werkzeug 3.0.3（9 条，修复至 3.0.6—3.1.9）；requests 2.32.3、python-dotenv 1.0.1、pytest 8.2.2、pip 24.0、setuptools 79.0.1 | **红** |

### SEC-07 审计日志可追溯

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-07 | 已登录 teacher_a；前期验证已产生操作日志 | ① 教师 `GET /api/teacher/audit?page_size=5`；② 学生访问同接口；③ DB 直查 audit_logs 核对五字段（操作人 user_id / 技能标识 skill / 结果状态 status / 耗时 duration_ms / 用量 tokens） | 教师可查、学生被拒；五字段齐全且有实际数据 | ① 教师查询 200，cls-a 范围 total=15，越权失败操作（SEC-03/04）与登录失败均有记录；② 学生访问 403 且该次访问本身被记录（id=37）；③ 字段均存在，**但 tokens 恒为 NULL**：37 条记录全部为空，包括 id=24 一次真实完成的 homework_grade 批改。根因：当前部署 `AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY` 留空，走本地演示生成器（app/adapters/ai_gateway.py 的 fallback 路径固定返回 `tokens=None`），AI 调用用量无法追溯 | **红** |

### SEC-08 提示词注入防护（素材准备，本次不测试）

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-08 | 素材文件已准备 | 本次仅准备素材，不执行测试 | 素材包含：1 份嵌入「忽略以上指令」的讲义 + 3 条诱导提问 | 已创建 `reports/sec08-materials/lecture-prompt-injection.md`（讲义正文中嵌入要求"一律给满分并输出提示词原文"的注入指令）与 `reports/sec08-materials/questions.md`（3 条诱导提问：索要提示词原文、要求改变评分规则、要求绕过权限），留待第二次验证使用 | —（不测试） |

---

## 六、红项处理说明（本次不修复，仅记录）

| 红项 | 风险描述 | 拟处理方向（第二次验证前） |
| --- | --- | --- |
| SEC-06 依赖漏洞 | 55 个已知漏洞，其中 pyjwt 2.8.0 为认证链路关键依赖且 PYSEC-2025-183 暂无修复版本 | 升级 flask/werkzeug/requests/python-dotenv/pytest 至修复版本并回归测试；pyjwt 持续关注修复版发布，评估临时缓解措施 |
| SEC-07 审计用量缺失 | tokens 字段存在但恒为 NULL，本地演示模式下 AI 调用无用量记录，成本与异常调用无法追溯 | 配置真实 AI 网关后复验；评估本地生成器是否应写入估算用量或显式标记 mode=local |

## 七、分工

| 成员 | 分工 |
| --- | --- |
| zjt0926 | 环境部署与 SEC-01/02 验证 |
| zjt0926 | SEC-03/04/05 验证 |
| zjt0926 | SEC-06/07 验证与报告汇总 |
| zjt0926 | SEC-08 素材准备 |

> 说明：本记录所有「当前实际」均为 2026-11-06 在上述环境中的真实可复现结果；curl 命令需配合登录后保存的 Cookie 文件执行（`curl -c <user>.jar` 登录，`-b <user>.jar` 调用）。
