# 交叉评审记录 · CampusClaw

> 评审人：zjt0926　记录日期：2026-11-06　被评审记录：`reports/security-precheck.md`（提交 50b59a0）
> 复现环境：本机 Docker 部署，http://127.0.0.1:8000，容器 `group-campusclaw-web-1` 等四服务健康

## 一、评审手段

照任务清单里 SEC-02 / SEC-03 的操作定义独立重跑：先按清单执行命令、只记录本次的实际输出，复现完成后再与原记录的判定和关键数值逐项比对；不引用原记录的结论来指导本次操作，避免「照抄一遍」式复核。

为排除「数据本来就不存在」这类假通过，额外加了两条同班对照：cls-b 学生读自己的提交、cls-b 独有词检索。

## 二、查了什么

从 SEC-01～SEC-07 中抽 2 条：

- **SEC-02 跨班数据隔离**
- **SEC-03 学生修改技能配置（越权写）**

## 三、判据

- **SEC-02**：跨班读提交与读讲义都应为 404（不暴露资源是否存在）；跨班检索结果中不得出现 cls-b 的 `material_id=6`，且同班学生读自己的数据仍为 200 —— 只有这两点同时成立、且与原记录数值一致，才算通过。
- **SEC-03**：学生调用教师接口应为 403，且 `skills` 表 4 行 `name` 在操作前后完全不变 —— 与原记录一致才算通过。

## 四、结果

| 编号 | 本次复现值 | 原记录值 | 比对 |
| --- | --- | --- | --- |
| SEC-02 | 读提交 3 → **404**；读讲义 6 → **404**；检索「集合与常用逻辑用语」→ total=3、全部 `material_id=1`，无 `material_id=6`；检索 cls-b 独有词「空集」→ `total=0`、`items: []`；对照：b1 读提交 3 → **200** | 404；仅命中 cls-a `material_id=1`（3 条片段）、无 cls-b；b1 读同一条 200 | 一致 |
| SEC-03 | `PUT /api/teacher/skills/tutor_hint` → **403** `forbidden`；`skills` 表操作前后 4 行 `name` 完全相同（tutor_hint 仍为「解题引导」） | 403；`skills` 表 4 行未变 | 一致 |

两条复现值与原记录一致，判定一致，结论：**通过**。

## 五、复现命令与输出

登录态复用既有 Cookie 文件（`student_a1.jar`、`student_b1.jar`），均以 `127.0.0.1` 直连本机服务：

```bash
# SEC-02 ①：a1 跨班读 b1 的提交（编号 3）
curl -s -b student_a1.jar http://127.0.0.1:8000/api/submissions/3
```

```
{"error":"提交不存在","error_code":"not_found"}
HTTP:404
```

```bash
# SEC-02 ②：a1 跨班读 cls-b 讲义（编号 6）
curl -s -b student_a1.jar http://127.0.0.1:8000/api/materials/6
```

```
{"error":"讲义不存在","error_code":"not_found"}
HTTP:404
```

```bash
# SEC-02 ③：a1 用 cls-b 讲义原文检索
curl -s -b student_a1.jar -G --data-urlencode "q=集合与常用逻辑用语" \
  http://127.0.0.1:8000/api/materials/search
```

```
{"items":[{"chunk_no":4,"material_id":1,...},{"chunk_no":5,"material_id":1,...},{"chunk_no":6,"material_id":1,...}],"matched":true,"query":"集合与常用逻辑用语","total":3}
HTTP:200
```

```bash
# SEC-02 ④：a1 用 cls-b 独有词检索，应为空结果
curl -s -b student_a1.jar -G --data-urlencode "q=空集" \
  http://127.0.0.1:8000/api/materials/search
```

```
{"items":[],"matched":false,"query":"空集","total":0}
HTTP:200
```

```bash
# SEC-02 ⑤：同班对照，b1 读自己的提交 3
curl -s -b student_b1.jar http://127.0.0.1:8000/api/submissions/3
```

```
{"submission":{"id":3,"student_id":"u-stu-b1","class_id":"cls-b","assignment_id":6,"status":"graded","final_score":45,...}}
HTTP:200
```

```bash
# SEC-03 ①：a1 调用教师接口改技能配置（body：{"name":"改过的技能名"}）
curl -s -X PUT -b student_a1.jar -H "Content-Type: application/json" \
  -d @sec03.json http://127.0.0.1:8000/api/teacher/skills/tutor_hint
```

```
{"error":"无权限访问该资源","error_code":"forbidden"}
HTTP:403
```

```bash
# SEC-03 ②：操作前后各查一次 skills 表
docker exec group-campusclaw-db-1 psql -U campusclaw -d campusclaw \
  -t -A -F " | " -c "SELECT id,skill_key,name FROM skills ORDER BY id;"
```

```
1 | tutor_hint | 解题引导
2 | homework_grade | 作业批改
3 | wrong_explain | 错题讲解
4 | care_chat | 关怀式对话
```

（上述同一查询在 PUT 前后各执行一次，两次输出完全相同。）
