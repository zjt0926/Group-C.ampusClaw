# 高风险三查 · 并发 · CampusClaw

> 记录日期：2026-11-06　环境：本机 Docker（`group-campusclaw-web-1 / worker-1 / db-1 / redis-1` 四容器健康），http://127.0.0.1:8000　代码提交：19b9327

## 一、用什么手段查

对同一份作业（`assignment_id=1`，cls-a 数学）用学生账号 `student_a1` 连续提交 20 次，每次换一个幂等键（`conc-20261106-1` … `conc-20261106-20`），用 `curl -w "%{http_code} %{time_total}"` 逐个记录状态码与端到端耗时，再把 20 个样本排序取 P95。

另做一次中断对照：先停掉消费者容器 `worker-1`，再提交 3 次，观察是否仍能返回、任务是否堆在队列里；重启 worker 后观察是否自动补齐。队列长度用 `redis-cli LLEN celery` 读取，消费结果直接查 `submissions` 表。

## 二、查了什么

1. 提交接口的响应码、响应体、P95 延迟（20 个样本）。
2. 响应里有没有出现分数（`ai_score` / `teacher_score` 字段）。
3. 队列长度变化：提交期间 `LLEN celery`、批改完毕后 `LLEN celery` 与 `LLEN unacked`。
4. 消费耗时：`graded_at - created_at`。
5. 重试次数与死信：`submissions.status='failed'` 的行数、Celery 重试配置（`max_retries=2`、`task_acks_late=True`）。
6. 消费者停机期间提交是否丢失。

## 三、判据

- 提交接口应为 **202**，响应体只含 `submission_id` 与 `status`，不含分数 —— 说明请求没有等待批改执行。
- 20 次提交的 **P95 ≤ 800 ms**。
- 20 条提交最终全部为 `graded`，`pending`、`failed` 均为 0，队列回落到 0 —— 任务全部被消费，无死信。
- 停掉消费者后提交仍返回 202 且队列长度等于提交数；重启后应全部补齐、一条不丢。

## 四、结果

| 观察项 | 实测值 | 判据 | 判定 |
| --- | --- | --- | --- |
| 响应码 | 20/20 均为 **202** | 全部 202 | 通过 |
| 响应体 | `{"status":"pending","submission_id":N}`，20 条中**含 score 关键字的 0 条** | 不含分数 | 通过 |
| 提交耗时 | 中位数 **0.024 s**，**P95 0.090 s**，最大 0.637 s | P95 ≤ 800 ms | 通过 |
| 最终状态 | `graded=20 / pending=0 / failed=0`（id 4–23） | 全部完成、无死信 | 通过 |
| 队列 | 批改完成后 `LLEN celery = 0`、`LLEN unacked = 0` | 无积压、无未确认任务 | 通过 |
| 消费耗时 | `graded_at - created_at` 区间 **0.07–0.64 s**，均值约 0.18 s | — | 观测值 |
| 单次批改执行耗时 | 审计日志 `duration_ms`：26 条样本 **11–39 ms**，均值 16.3 ms | — | 观测值 |
| 停机对照 | worker 停止后 3 次提交均 **202**（0.024–0.038 s）；`LLEN celery = 3`；重启后 **3/3 graded**，消费耗时 4.18–4.48 s（含容器启动），队列归 0 | 不丢任务 | 通过 |

**结论：并发这一条通过。**

补充说明两点观测事实：

- 本机 `AI_GATEWAY_BASE_URL` 为空，评分走本地演示分支（`mode=local-demo`），单次批改本体只需 11–39 ms，因此这台机器上「同步改异步」带来的耗时差并不明显，P95 的参考意义主要在「响应在批改完成前就返回」——证据是 20 条响应全部为 `pending` 且不含分数，而批改结果在响应之后由 worker 写入。
- 仓库 `submissions` 表没有 `attempts` 字段，也没有独立任务表，重试次数无法按行读取；本次以 Celery 的 `max_retries=2` 配置、`task_acks_late=True` 与 `failed` 行数（0）作为可观测替代，未臆造 attempts 数值。

## 五、复现命令与输出

```bash
# 连续提交 20 次（每次换幂等键），记录状态码与耗时
for i in $(seq 1 20); do
  printf '{"content":"concurrency check submission #%s answer text","idempotency_key":"conc-20261106-%s"}' "$i" "$i" > /tmp/conc.json
  curl -s -b student_a1.jar -H "Content-Type: application/json" -d @/tmp/conc.json \
       -w " %{http_code} %{time_total}\n" -o /dev/null \
       http://127.0.0.1:8000/api/assignments/1/submit
done
```

```
202 0.089571
202 0.023999
202 0.024960
202 0.030893
202 0.034742
202 0.022976
202 0.023443
202 0.024171
202 0.636553
202 0.026633
202 0.033222
202 0.025090
202 0.024883
202 0.023726
202 0.020300
202 0.023172
202 0.022412
202 0.021349
202 0.022522
202 0.021323

P95 = 0.0896 s　中位数 = 0.0242 s　最大 = 0.6366 s
202 计数 = 20/20　含 score 关键字的响应 = 0
```

```bash
# 批改结果与消费耗时
docker exec group-campusclaw-db-1 psql -U campusclaw -d campusclaw \
  -c "SELECT id,status,ai_score,round(EXTRACT(EPOCH FROM (graded_at-created_at))::numeric,2) AS consume_sec FROM submissions WHERE id BETWEEN 4 AND 23 ORDER BY id;"
```

```
 id | status | ai_score | consume_sec
----+--------+----------+-------------
  4 | graded |       68 |        0.39
 ...（共 20 行，均为 graded、ai_score=68）
 23 | graded |       68 |        0.07
graded=20 pending=0 failed=0
```

```bash
# 队列长度
docker exec group-campusclaw-redis-1 redis-cli LLEN celery      # 0
docker exec group-campusclaw-redis-1 redis-cli LLEN unacked     # 0
```

```bash
# 停机对照：停消费者 → 提交 3 次 → 看队列 → 启消费者
docker stop group-campusclaw-worker-1
# 提交 #1/#2/#3（键 dur-20261106-1..3）
docker exec group-campusclaw-redis-1 redis-cli LLEN celery      # 3
docker start group-campusclaw-worker-1
```

```
#1  HTTP 202 0.037673  {"status":"pending","submission_id":24}
#2  HTTP 202 0.023085  {"status":"pending","submission_id":25}
#3  HTTP 202 0.024504  {"status":"pending","submission_id":26}
queue length while worker down = 3
graded 3/3

 id | status | ai_score | consume_sec
----+--------+----------+-------------
 24 | graded |       68 |        4.48
 25 | graded |       68 |        4.27
 26 | graded |       68 |        4.18
queue length after drain = 0
```
