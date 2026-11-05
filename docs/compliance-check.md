# 合规检查点（5 条）

本文件对应 `openspec/changes/2026-10-作业系统扩展/specs/audit-compliance/spec.md` 的 R6。每条都给出判定方法、证据位置与复跑方式；**未执行的检查项一律标注「未执行」，不得预填「通过」。**

## 一键复跑

```bash
# 先启动 Docker Compose
docker compose up -d --build
# 再运行合规检查（默认连接 http://localhost:8000）
python scripts/check_compliance.py --base-url http://localhost:8000
```

脚本逐条输出 `PASS / FAIL / UNEXECUTED`，任一条 `FAIL` 时退出码为 1。

## 01 每条技能调用均留痕（含失败/超时）

- **判定方法**：登录学生账号，调用一次学科助手对话；登录教师账号读取 `GET /api/teacher/audit/summary`，确认 `tutor_hint` 行存在且 `count >= 1`。再触发一次失败请求（例如学生读取他班提交），在 `GET /api/teacher/audit?status=failed` 中确认有失败记录。
- **证据位置**：`audit_logs` 表；教师端「审计与统计」页的「按技能统计」与「操作日志」。
- **复跑命令**：`python scripts/check_compliance.py --base-url http://localhost:8000` 的第 1 项；或 `curl -b cookie.txt http://localhost:8000/api/teacher/audit/summary`。
- **说明**：超时记录需要真实网关超时才会产生；演示环境未配置网关时，该子项标注「未执行」，不计入通过。

## 02 API Key 不进前端与仓库

- **判定方法**：
  1. 抓取任意页面 HTML、`/static/js/*.js` 与 `/api/teacher/config`，检索完整密钥特征无命中，配置展示为掩码；
  2. 全仓库检索密钥特征无命中，`.env` 已列入 `.gitignore`，`.env.example` 只有占位值。
- **证据位置**：`app/adapters/ai_gateway.py` 的 `masked_key()`；`.gitignore`；`.env.example`。
- **复跑命令**：`python scripts/check_compliance.py` 的第 2 项；或 `git grep -nE "sk-[A-Za-z0-9]{16,}"`（无输出即通过）。

## 03 未命中知识库不伪造来源

- **判定方法**：以学生身份检索一个本班讲义中不存在的词，接口必须返回 `matched: false` 且 `items: []`；再发起同一问题的助手对话，SSE 的 `sources` 为空，回答明确说明「未命中」。
- **证据位置**：`GET /api/materials/search`、`POST /api/chat`；`app/adapters/ai_gateway.py` 中所有来源只由 `search_chunks` 的真实命中构造。
- **复跑命令**：`python scripts/check_compliance.py` 的第 3 项。

## 04 班级与个人数据隔离

- **判定方法**：分别登录本班两名学生与外班学生：
  - 列表：学生乙的错题列表不含学生甲的错题；
  - 详情：学生乙请求学生甲的错题讲解返回 404；
  - 跳转：外班学生直接请求本班讲义详情返回 404，用本班专有词检索返回空；
  - 统计：外班学生学情统计不包含本班任何提交或错题；
  - 角色：学生调用 `/api/teacher/*` 返回 403，教师调用学生专属接口返回 403。
- **证据位置**：`app/api/*` 中所有查询的 `class_id` 条件；`app/services/*` 的按班级过滤。
- **复跑命令**：`python scripts/check_compliance.py` 的第 4 项。
- **说明**：仓库只有一个教师账号，跨班教师统计无法直接构造，脚本将该项标为「未执行」。

## 05 学生技能只读

- **判定方法**：学生访问 `GET /api/skills`，返回技能名称、触发条件与启用状态，且不含 `prompt` 字段；学生调用 `PUT /api/skills/<key>` 必须返回 403，随后教师读取的技能提示词保持不变。
- **证据位置**：`app/services/skills.py` 的 `list_student_skills()` 使用 `include_prompt=False`；`app/api/assistant_api.py` 的写接口直接返回 403。
- **复跑命令**：`python scripts/check_compliance.py` 的第 5 项。
