# 高风险三查 · 事务 · CampusClaw

> 记录日期：2026-11-06　环境：本机 Docker（`group-campusclaw-web-1 / worker-1 / db-1 / redis-1` 四容器健康），http://127.0.0.1:8000　代码提交：ce38742

## 一、用什么手段查

从三个层面制造重复：

1. **客户端重复提交**：用同一幂等键连发两次，先顺序、再并行。
2. **服务端重复投递**：对一条已完成批改的提交，直接用 Celery 把同一个 `submission_id` 再投一次（模拟 at-least-once 队列的重投）。
3. **结构核对**：查数据库唯一约束定义，确认约束落在「作业 + 学生 + 幂等键」上。

每一步都用 `submissions` 的行数、`ai_score`、`graded_at` 和 `audit_logs` 的成功记录条数比对前后差异。

## 二、查了什么

1. 同一幂等键顺序提交两次：第二次的状态码、返回的 `submission_id` 是否与第一次相同。
2. 同一幂等键两个请求并行：两个响应的状态码与 `submission_id`。
3. 数据库里两个幂等键各留下几行。
4. 人为重复投递后：`status`、`ai_score`、`graded_at` 是否变化；`audit_logs` 中该提交的 `success` 记录是否增加。
5. 唯一约束名称与定义。

## 三、判据

- 同一幂等键提交两次，数据库**只留 1 行**；第二次返回 200 且 `submission_id` 与第一次相同（不是新建一行）。
- 两个请求并行抢同一幂等键时，也只有 1 行，一个 202、一个 200。
- 人为重复投递后，`ai_score` 与 `graded_at` **完全不变**，审计日志中该提交的 `success` 记录**不增加** —— 重复执行不会产生第二次批改结果。
- 唯一约束必须存在，作为数据库层的兜底。

## 四、结果

| 场景 | 实测值 | 判据 | 判定 |
| --- | --- | --- | --- |
| 同键顺序提交 | 第 1 次 **202** `submission_id=27`；第 2 次 **200** `status=graded, submission_id=27` | 只有 1 行、同 id | 通过 |
| 同键并行提交 | A **202** `id=28`；B **200** `id=28` | 只有 1 行、同 id | 通过 |
| 库里行数 | `tx-seq-1` 1 行、`tx-par-1` 1 行，共 **2 行** | 每键 1 行 | 通过 |
| 人为重复投递 | 投递前 `status=graded, ai_score=68, graded_at=2026-11-06 04:57:30.022444`；投递后**四项完全相同** | 不变 | 通过 |
| 审计记录 | `submission_id=27` 的 `homework_grade / success` 记录 **1 条**（id 121），重复投递后未新增 | 不新增 | 通过 |
| 唯一约束 | `uq_submission_idempotency` = `UNIQUE (assignment_id, student_id, idempotency_key)` | 存在 | 通过 |
| 全局状态 | `total_graded=28  total_failed=0` | 无重复失败行 | 通过 |

**结论：事务这一条通过。** 重复提交与重复投递都收敛到同一行、同一份评分，没有出现第二条提交或第二份批改结果。

## 五、复现命令与输出

```bash
# ① 同键顺序提交两次
printf '{"content":"transaction check same key","idempotency_key":"tx-seq-1"}' > /tmp/tx.json
curl -s -b student_a1.jar -H "Content-Type: application/json" -d @/tmp/tx.json \
     -w " %{http_code}\n" http://127.0.0.1:8000/api/assignments/1/submit
curl -s -b student_a1.jar -H "Content-Type: application/json" -d @/tmp/tx.json \
     -w " %{http_code}\n" http://127.0.0.1:8000/api/assignments/1/submit
```

```
{"status":"pending","submission_id":27} 202
{"status":"graded","submission_id":27} 200
```

```bash
# ② 同键并行提交两次（幂等键 tx-par-1）
```

```
A: 202 {"status":"pending","submission_id":28}
B: 200 {"status":"graded","submission_id":28}
```

```bash
# ③ 库里行数
docker exec group-campusclaw-db-1 psql -U campusclaw -d campusclaw \
  -c "SELECT id,idempotency_key,status,ai_score,teacher_score FROM submissions WHERE idempotency_key IN ('tx-seq-1','tx-par-1') ORDER BY id;"
```

```
 id | idempotency_key | status | ai_score | teacher_score
----+-----------------+--------+----------+---------------
 27 | tx-seq-1        | graded |       68 |
 28 | tx-par-1        | graded |       68 |
(2 rows)
```

```bash
# ④ 对已完成批改的提交 27 人为重复投递
docker exec group-campusclaw-worker-1 python -c \
  "from app.tasks import grade_submission_task; print(grade_submission_task.delay(27).id)"
```

```
7038d22f-b10d-447d-ab72-09d42c3e319e

投递前：27 | graded | 68 | 2026-11-06 04:57:30.022444
投递后：27 | graded | 68 | 2026-11-06 04:57:30.022444
```

```bash
# ⑤ 审计中该提交的成功记录条数
docker exec group-campusclaw-db-1 psql -U campusclaw -d campusclaw \
  -c "SELECT id,action,status,params FROM audit_logs WHERE skill='homework_grade' ORDER BY id DESC LIMIT 8;"
```

```
 124 | grade | success | {"submission_id": 28, "score": 68}
 121 | grade | success | {"submission_id": 27, "score": 68}
 119 | grade | success | {"submission_id": 26, "score": 68}
 ...（每个 submission_id 只出现一次）
```

```bash
# ⑥ 唯一约束
docker exec group-campusclaw-db-1 psql -U campusclaw -d campusclaw \
  -c "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='submissions'::regclass AND contype='u';"
```

```
          conname          |                         def
---------------------------+-----------------------------------------------------
 uq_submission_idempotency | UNIQUE (assignment_id, student_id, idempotency_key)
```
