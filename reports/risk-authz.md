# 高风险三查 · 权限 · CampusClaw

> 第二次验证 · 跨班一条展开整理
> 文件：`reports/risk-authz.md`　记录日期：2026-11-06
> 环境：Docker Compose 四容器（web / worker / db / redis），提交号 `50b59a0`，地址 http://localhost:8000
> 账号：student_a1（cls-a）、student_b1（cls-b），密码统一 `Campus@123`

## 一、用什么手段查

**接口用例。** 学生 A1（cls-a）的登录态（`access_token` HttpOnly Cookie）调用班级 B（cls-b）的资源，做「跨班访问」；再用班级 B 讲义的原文片段作检索词，做「跨班检索」。同时用班级 B 学生 B1 做正向对照，证明 404 与空结果来自班级过滤，而非数据不存在。

## 二、查了什么

1. 跨班讲义是否可读：`GET /api/materials/6`（material id=6「集合与常用逻辑用语」属 cls-b）。
2. 跨班知识库检索是否泄漏别班内容：`GET /api/materials/search?q=空集`（「空集」取自 cls-b 讲义第 2 片段原文「注意空集是任何集合的子集…」）。
3. 附带核对同类资源：跨班读提交 `GET /api/submissions/3`（cls-b 学生 B1 的提交）；本班讲义列表 `GET /api/materials?subject=数学`。

## 三、判据

- 跨班访问一律 **404**（服务端先按 `class_id` 过滤再取数，不以 403 暴露资源是否存在）；
- 跨班检索返回**空结果，条数为 0**；
- 同一资源由本班学生访问时应为 **200**，且检索有命中（反向对照）。

## 四、结果：绿

| # | 用例 | 请求 | 期望 | 当前实际 |
| --- | --- | --- | --- | --- |
| 1 | 跨班读讲义 | A1 → `GET /api/materials/6` | 404 | **HTTP 404**，`{"error":"讲义不存在","error_code":"not_found"}` |
| 2 | 跨班检索 | A1 → `GET /api/materials/search?q=空集` | `{"items":[],"total":0}` | **total=0**，`{"items":[],"matched":false,"query":"空集","total":0}` |
| 3 | 对照：本班读讲义 | B1 → `GET /api/materials/6` | 200 | **HTTP 200**（讲义 6 确实存在且属 cls-b） |
| 4 | 对照：本班检索 | B1 → `GET /api/materials/search?q=空集` | 有命中 | **total=2**，命中 material_id=6 的片段 2、片段 1 |
| 5 | 跨班读提交 | A1 → `GET /api/submissions/3` | 404 | **HTTP 404**，`{"error":"提交不存在","error_code":"not_found"}` |
| 6 | 本班讲义列表 | A1 → `GET /api/materials?subject=数学` | 仅 cls-a | 仅返回 `id=1`（cls-a），无 `id=6`，`total=1` |

结论：跨班访问返回 404，跨班检索返回 `{"items":[]}` 共 0 条；同一资源由本班学生访问为 200 且有命中，说明隔离由 `class_id` 过滤实现，不依赖资源是否存在的差异。**判定：绿。**

## 五、复测命令（可整段复制执行）

```bash
# 依赖：curl。在 Linux / macOS 上原样执行即可；Windows PowerShell 见文末注。
BASE=http://localhost:8000
TMP=/tmp/campusclaw-authz && mkdir -p "$TMP"

# 1) 学生 A1（cls-a）登录，Cookie 写入 a1.jar
curl -s -c "$TMP/a1.jar" -H "Content-Type: application/json" \
  -d '{"username":"student_a1","password":"Campus@123"}' \
  "$BASE/api/auth/login" > /dev/null

# 2) 跨班读 cls-b 讲义（material id = 6）——期望输出 404
curl -s -o /dev/null -w "%{http_code}\n" -b "$TMP/a1.jar" "$BASE/api/materials/6"

# 3) 跨班检索 cls-b 讲义原文片段「空集」——期望输出 {"items":[],...,"total":0}
curl -s -b "$TMP/a1.jar" -G --data-urlencode "q=空集" "$BASE/api/materials/search"

# 4) 对照：班级 B 学生读同一讲义并检索同一片段——期望 200 / total>0
curl -s -c "$TMP/b1.jar" -H "Content-Type: application/json" \
  -d '{"username":"student_b1","password":"Campus@123"}' \
  "$BASE/api/auth/login" > /dev/null
curl -s -o /dev/null -w "%{http_code}\n" -b "$TMP/b1.jar" "$BASE/api/materials/6"
curl -s -b "$TMP/b1.jar" -G --data-urlencode "q=空集" "$BASE/api/materials/search"
```

实测输出（2026-11-06，本机）：

```
404
{"items":[],"matched":false,"query":"空集","total":0}
200
{"items":[{"chunk_no":2,...,"material_id":6,...,"relevance":1.0,...},{"chunk_no":1,...,"material_id":6,...,"relevance":0.31,...}],"matched":true,"query":"空集","total":2}
```

> 注（Windows 本机）：系统代理会拦截请求、`localhost` 可能走 IPv6 挂起，需给每条 curl 加 `--noproxy "*"` 并把 `localhost` 换成 `127.0.0.1`，判定结果相同。
