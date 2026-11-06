# 资产类基线 · CampusClaw

> 第三次验证 · 资产类基线
> 文件：`reports/security-baseline.md`　记录日期：2026-11-06
> 提交号：`d777778`　环境：Docker Compose 四容器（web / worker / db / redis），http://localhost:8000
> 扫描对象：**全量提交历史 + 前端产物 + 运行日志**；依赖审计对象：**web 容器内实际运行环境**

---

## 一、密钥扫描（SEC-05）

### 1.1 扫描模式

统一使用一组能命中真实密钥、但不误伤包名（如 `Flask-SQLAlchemy` 会被裸 `sk-` 误报）的规则：

```bash
PAT='sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_KEY=[0-9a-fA-F]{32,}|JWT_SECRET=[0-9a-fA-F]{32,}'
```

### 1.2 全量提交历史

```bash
$ git rev-list --all --count
13

$ git rev-list --all | while read rev; do git grep -n -E "$PAT" "$rev"; done
（无输出）

$ echo "命中 $(git rev-list --all | while read rev; do git grep -n -E "$PAT" "$rev"; done | wc -l)"
命中 0
```

### 1.3 前端产物

```bash
$ find app/static app/templates -type f | wc -l
19

$ grep -rInE "$PAT" app/static app/templates
（无输出）

$ echo "命中 $(grep -rInE "$PAT" app/static app/templates | wc -l)"
命中 0
```

### 1.4 运行日志

```bash
$ docker logs group-campusclaw-web-1 2>&1 | wc -l
29

$ docker logs group-campusclaw-worker-1 2>&1 | wc -l
66

$ for c in group-campusclaw-web-1 group-campusclaw-worker-1; do docker logs "$c" 2>&1 | grep -nE "$PAT"; done
（无输出）

$ echo "命中 $(for c in group-campusclaw-web-1 group-campusclaw-worker-1; do docker logs "$c" 2>&1 | grep -nE "$PAT"; done | wc -l)"
命中 0
```

### 1.5 汇总

```
扫描提交历史 …… 通过（0 命中）| 13 个提交
扫描前端产物 …… 通过（0 命中）| 19 个文件
扫描运行日志 …… 通过（0 命中）| web 29 行 + worker 66 行
退出码 0
```

补充核对：`git ls-files | grep -x ".env"` 无输出，`.env` 未被跟踪，且 `.gitignore` 第 1 行为 `.env`；仓库内只有 `.env.example`，其值为占位符 `change-me-to-a-random-string`。

**判定：绿。**

---

## 二、依赖审计（SEC-06）

### 2.1 命令

```bash
$ docker exec group-campusclaw-web-1 pip install --quiet pip-audit
$ docker exec group-campusclaw-web-1 pip-audit
```

### 2.2 输出原文

```
Name          Version ID                  Fix Versions
------------- ------- ------------------- ------------
flask         3.0.3   PYSEC-2026-2151     3.1.3
flask         3.0.3   PYSEC-2026-2151     3.1.3
pip           24.0    PYSEC-2026-1795     25.3
pip           24.0    PYSEC-2026-1796     26.0
pip           24.0    PYSEC-2026-2875     26.1
pip           24.0    PYSEC-2026-2876     26.1
pip           24.0    PYSEC-2026-196      26.1.2
pip           24.0    PYSEC-2026-1795     25.3
pip           24.0    PYSEC-2026-1796     26.0
pip           24.0    PYSEC-2026-196      26.1.2
pip           24.0    PYSEC-2026-2875     26.1
pip           24.0    PYSEC-2026-2876     26.1
pip           24.0    PYSEC-2026-3721     26.2
pip           24.0    PYSEC-2026-3721     26.2.0
pyjwt         2.8.0   PYSEC-2026-120      2.12.0
pyjwt         2.8.0   PYSEC-2026-120      2.12.0
pyjwt         2.8.0   PYSEC-2025-183
pyjwt         2.8.0   PYSEC-2026-179      2.13.0
pyjwt         2.8.0   PYSEC-2026-175      2.13.0
pyjwt         2.8.0   PYSEC-2026-177      2.13.0
pyjwt         2.8.0   PYSEC-2026-178      2.13.0
pyjwt         2.8.0   PYSEC-2026-177      2.13.0
pyjwt         2.8.0   PYSEC-2026-179      2.13.0
pyjwt         2.8.0   PYSEC-2026-178      2.13.0
pyjwt         2.8.0   PYSEC-2026-4145     2.14.0
pyjwt         2.8.0   PYSEC-2026-4149     2.14.0
pyjwt         2.8.0   PYSEC-2026-4144     2.14.0
pyjwt         2.8.0   PYSEC-2026-4148     2.14.0
pyjwt         2.8.0   PYSEC-2026-4140     2.14.0
pyjwt         2.8.0   PYSEC-2026-4141     2.15.0
pyjwt         2.8.0   PYSEC-2026-4147     2.14.0
pyjwt         2.8.0   PYSEC-2026-4183     2.15.0
pyjwt         2.8.0   GHSA-pxh4-856f-4h89 2.14.0
pytest        8.2.2   PYSEC-2026-1845     9.0.3
pytest        8.2.2   PYSEC-2026-1845     9.0.3
python-dotenv 1.0.1   PYSEC-2026-2270     1.2.2
python-dotenv 1.0.1   PYSEC-2026-2270     1.2.2
requests      2.32.3  PYSEC-2026-1872     2.32.4
requests      2.32.3  PYSEC-2026-2275     2.33.0
requests      2.32.3  PYSEC-2026-1872     2.32.4
requests      2.32.3  PYSEC-2026-2275     2.33.0
setuptools    79.0.1  PYSEC-2026-3447     83.0.0
setuptools    79.0.1  PYSEC-2026-3447     83.0.0
setuptools    79.0.1  GHSA-xmj3-9gf7-h52w 84.1.0
werkzeug      3.0.3   PYSEC-2026-2045     3.0.6
werkzeug      3.0.3   PYSEC-2026-1860     3.0.6
werkzeug      3.0.3   PYSEC-2026-2046     3.1.4
werkzeug      3.0.3   PYSEC-2026-2044     3.1.5
werkzeug      3.0.3   PYSEC-2026-2320     3.1.6
werkzeug      3.0.3   PYSEC-2026-2045     3.0.6
werkzeug      3.0.3   PYSEC-2026-2046     3.1.4
werkzeug      3.0.3   PYSEC-2026-2044     3.1.5
werkzeug      3.0.3   PYSEC-2026-2320     3.1.6
werkzeug      3.0.3   PYSEC-2026-3417     3.0.6
werkzeug      3.0.3   PYSEC-2026-4312     3.1.9
Found 55 known vulnerabilities in 8 packages
```

### 2.3 去重与分级

上表 55 条中同一公告因 PyPI / OSV 多个数据源重复出现，去重后为 **35 个唯一公告**，分布如下：

| 严重性 | 数量 | 代表公告 |
| --- | --- | --- |
| 严重 | 1 | PYSEC-2026-4145（pyjwt，CVSS 3.1 = 9.1） |
| 高危 | 9 | PYSEC-2026-120（pyjwt 7.5）、PYSEC-2026-4183（pyjwt 8.2）、GHSA-pxh4-856f-4h89（pyjwt 7.4）、PYSEC-2026-1860 / 3417（werkzeug 7.5）等 |
| 中危 | 16 | PYSEC-2026-2151（flask 4.3）、PYSEC-2026-1845（pytest 6.8）、PYSEC-2026-2270（python-dotenv 6.6）等 |
| 低危 | 2 | PYSEC-2026-177（pyjwt 3.7）、GHSA-xmj3-9gf7-h52w（setuptools，GHSA 标 LOW） |
| 未分级 | 7 | 仅提供 CVSS 4.0 向量的 PYSEC 公告（pip 4 条、werkzeug 3 条） |

分级方法：以 `pip-audit -f json` 取得公告 ID，逐个调用 OSV API `GET https://api.osv.dev/v1/vulns/{id}` 取 CVSS 3.1 向量，按 CVSS 3.1 官方公式计算基础分（严重 ≥9.0、高危 7.0—8.9、中危 4.0—6.9、低危 <4.0）；仅给 CVSS 4.0 向量且无 GHSA 等级的记为「未分级」，不臆测。

### 2.4 修复情况与处置

- 35 个公告中 **34 个有修复版本**，唯一无修复版本的是 `pyjwt 2.8.0 / PYSEC-2025-183`（表中 Fix Versions 列为空）。
- 本次**不升级**，仅建立基线；处置理由：课程项目为内部局域网部署、无对外输入面，升级需回归认证链路（pyjwt 涉及 `app/auth.py` 的 JWT 签发与校验），留到后续课次统一升级后复测并更新本文件。
- 待升级清单：flask 3.0.3 → 3.1.3；werkzeug 3.0.3 → 3.1.9；pyjwt 2.8.0 → 2.15.0；requests 2.32.3 → 2.33.0；python-dotenv 1.0.1 → 1.2.2；pytest 8.2.2 → 9.0.3；setuptools 79.0.1 → 84.1.0；pip 24.0 → 26.2.0。**此项含 1 个严重、9 个高危，判定：红。**

---

## 三、复跑入口

仓库已提供一键入口：`make check-security`（等价 `sh scripts/check_security.sh`），覆盖 SEC-05 三段扫描与 SEC-06 依赖审计；分项为 `make check-secrets` / `make audit-deps`，README 7.5 已注明。底层命令仍如下（Linux / macOS 原样执行）：

```bash
# SEC-05 密钥扫描：提交历史 / 前端产物 / 运行日志
PAT='sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_KEY=[0-9a-fA-F]{32,}|JWT_SECRET=[0-9a-fA-F]{32,}'
git rev-list --all | while read rev; do git grep -n -E "$PAT" "$rev"; done
grep -rInE "$PAT" app/static app/templates
for c in group-campusclaw-web-1 group-campusclaw-worker-1; do docker logs "$c" 2>&1 | grep -nE "$PAT"; done

# SEC-06 依赖审计
docker exec group-campusclaw-web-1 pip install --quiet pip-audit
docker exec group-campusclaw-web-1 pip-audit
```

一键入口实测输出（2026-11-06，本机已安装 GNU Make 4.4.1）：

```
$ make --version
GNU Make 4.4.1
Built for Windows32

$ make check-secrets
扫描提交历史 …… 通过（0 命中）
扫描前端产物 …… 通过（0 命中）
扫描运行日志 …… 通过（0 命中）
（退出码 0）

$ make check-security
扫描提交历史 …… 通过（0 命中）
扫描前端产物 …… 通过（0 命中）
扫描运行日志 …… 通过（0 命中）
依赖审计（group-campusclaw-web-1 / pip-audit）……
Found 55 known vulnerabilities in 8 packages
Name          Version ID                  Fix Versions
------------- ------- ------------------- ------------
（与第二节相同的 55 条）
依赖审计 …… 发现已知漏洞（退出码 1），基线见 reports/security-baseline.md
make: *** [Makefile:12: audit-deps] Error 1
（退出码 2）
```

- 三段扫描应全部**无输出**；依赖审计应输出上表同样 55 条、末行 `Found 55 known vulnerabilities in 8 packages`。
- 依赖审计发现漏洞时脚本按非 0 退出，与本节红项一致；`check_compliance.py`（README 7.5）只覆盖合规五条，不含密钥扫描与依赖审计，故两项单独记录。
- 容器未启动时依赖审计直接报「未执行」，不会把没跑过的检查记为通过。

> 注（Windows 本机）：GNU Make 4.4.1 通过 `winget install --id ezwinports.make -e` 安装，`make check-security` 已在真实 make 下实跑（输出见上）。本机 PATH 过长时，子进程中的 PATH 会被截断导致找不到 `docker`，脚本已按 Docker Desktop 常见安装位置兜底后再调用。`docker logs` 读取 stdin 时需 `2>&1`，否则 stderr 不参与扫描。
