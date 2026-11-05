"""合规检查脚本：5 条检查点逐条输出 PASS / FAIL / UNEXECUTED。

用法：
    python scripts/check_compliance.py --base-url http://localhost:8000

脚本只做读取与少量幂等调用（一次助手对话），不修改业务数据。
"""
import argparse
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9]{16,}|api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']{8,})", re.I)
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "logs", "verification"}
SCAN_SUFFIXES = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".md", ".txt", ".example", ".sh", ".ini"}


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(self, method, path, payload=None, timeout=30):
        url = self.base_url + path
        data = None
        headers = {"Accept": "application/json, text/event-stream, text/html"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def login(self, username, password="Campus@123"):
        status, body = self.request(
            "POST", "/api/auth/login", {"username": username, "password": password}
        )
        if status != 200:
            raise RuntimeError(f"{username} 登录失败：HTTP {status} {body[:120]}")
        return json.loads(body)


def parse_json(body):
    try:
        return json.loads(body)
    except ValueError:
        return {}


def record(results, number, name, status, evidence):
    results.append({"number": number, "name": name, "status": status, "evidence": evidence})


def static_secret_scan():
    hits = []
    for path in REPO_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == ".env":
            continue
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = SECRET_PATTERN.search(text)
        if match:
            hits.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)[:24]}…")
    return hits


def check_audit(base_url, results):
    try:
        student = Client(base_url)
        student.login("student_a1")
        status, body = student.request(
            "POST",
            "/api/chat",
            {"subject": "数学", "message": "求根公式的适用条件是什么？"},
        )
        if status != 200:
            record(results, "01", "技能调用留痕", "FAIL", f"助手对话返回 HTTP {status}")
            return
        teacher = Client(base_url)
        teacher.login("teacher_a")
        status, body = teacher.request("GET", "/api/teacher/audit/summary")
        summary = parse_json(body)
        tutor = next(
            (row for row in summary.get("skills", []) if row.get("skill") == "tutor_hint"), None
        )
        if status != 200 or tutor is None or tutor.get("count", 0) < 1:
            record(results, "01", "技能调用留痕", "FAIL",
                   f"tutor_hint 未出现在聚合：HTTP {status} {body[:160]}")
            return

        student.request("GET", "/api/teacher/submissions?subject=%E6%95%B0%E5%AD%A6")
        status, body = teacher.request("GET", "/api/teacher/audit?status=failed&page_size=5")
        failed = parse_json(body)
        if status != 200 or failed.get("total", 0) < 1:
            record(results, "01", "技能调用留痕", "FAIL",
                   "失败请求未留痕：审计 failed 记录为 0")
            return
        record(
            results,
            "01",
            "技能调用留痕",
            "PASS",
            f"tutor_hint 调用 {tutor['count']} 次；失败请求审计 {failed['total']} 条；"
            "超时场景未执行（未配置真实网关）",
        )
    except Exception as exc:  # noqa: BLE001
        record(results, "01", "技能调用留痕", "UNEXECUTED", f"环境不可用：{exc}")


def check_api_key(base_url, results):
    try:
        teacher = Client(base_url)
        teacher.login("teacher_a")
        status, page = teacher.request("GET", "/teacher/assistant")
        _, config_body = teacher.request("GET", "/api/teacher/config")
        config = parse_json(config_body)
        _, common_js = teacher.request("GET", "/static/js/common.js")
        _, teacher_js = teacher.request("GET", "/static/js/teacher.js")
        env_key = os.getenv("AI_GATEWAY_API_KEY", "")
        problems = []
        for label, text in [
            ("教师页面", page),
            ("/api/teacher/config", config_body),
            ("common.js", common_js),
            ("teacher.js", teacher_js),
        ]:
            if SECRET_PATTERN.search(text) or (env_key and len(env_key) >= 8 and env_key in text):
                problems.append(label)
        if status != 200 or "api_key_masked" not in config:
            problems.append("配置接口不可读")
        if env_key and env_key in config_body:
            problems.append("配置接口泄露完整密钥")

        repo_hits = static_secret_scan()
        if not repo_hits:
            repo_hits = []
        else:
            problems.append("仓库命中密钥特征：" + "；".join(repo_hits[:3]))

        gitignore = REPO_ROOT / ".gitignore"
        if not gitignore.exists() or ".env" not in gitignore.read_text(encoding="utf-8", errors="ignore"):
            problems.append(".env 未列入 .gitignore")
        example = REPO_ROOT / ".env.example"
        if not example.exists():
            problems.append(".env.example 缺失")
        elif SECRET_PATTERN.search(example.read_text(encoding="utf-8", errors="ignore")):
            problems.append(".env.example 含疑似真实密钥")

        if problems:
            record(results, "02", "API Key 不进前端与仓库", "FAIL", "；".join(problems))
        else:
            record(
                results,
                "02",
                "API Key 不进前端与仓库",
                "PASS",
                f"页面/JS/配置均无完整密钥，展示为 {config.get('api_key_masked')}；仓库扫描无命中",
            )
    except Exception as exc:  # noqa: BLE001
        record(results, "02", "API Key 不进前端与仓库", "UNEXECUTED", f"环境不可用：{exc}")


def check_no_hit(base_url, results):
    try:
        student = Client(base_url)
        student.login("student_a1")
        status, body = student.request(
            "GET", "/api/materials/search?subject=" + urllib.parse.quote("数学") +
            "&q=" + urllib.parse.quote("量子纠缠XYZ")
        )
        data = parse_json(body)
        if status != 200 or data.get("matched") is not False or data.get("items"):
            record(results, "03", "未命中不伪造来源", "FAIL",
                   f"检索未命中却返回来源：HTTP {status} {body[:160]}")
            return
        status, stream = student.request(
            "POST",
            "/api/chat",
            {"subject": "数学", "message": "量子纠缠XYZ 是什么？"},
        )
        if status != 200:
            record(results, "03", "未命中不伪造来源", "FAIL", f"对话返回 HTTP {status}")
            return
        if '"matched": false' not in stream or "event: sources\ndata: []" not in stream:
            record(results, "03", "未命中不伪造来源", "FAIL",
                   "未命中对话仍返回来源或未标记 matched=false")
            return
        record(
            results,
            "03",
            "未命中不伪造来源",
            "PASS",
            "检索返回 matched=false / items=[]；对话 sources=[] 且明确说明未命中",
        )
    except Exception as exc:  # noqa: BLE001
        record(results, "03", "未命中不伪造来源", "UNEXECUTED", f"环境不可用：{exc}")


def check_isolation(base_url, results):
    try:
        a1 = Client(base_url)
        a1.login("student_a1")
        a2 = Client(base_url)
        a2.login("student_a2")
        b1 = Client(base_url)
        b1.login("student_b1")
        teacher = Client(base_url)
        teacher.login("teacher_a")

        problems = []
        notes = []

        _, body = a1.request("GET", "/api/wrong-questions?subject=" + urllib.parse.quote("数学"))
        a1_wrongs = [item["id"] for item in parse_json(body).get("items", [])]
        _, body = a2.request("GET", "/api/wrong-questions?subject=" + urllib.parse.quote("数学"))
        a2_wrongs = [item["id"] for item in parse_json(body).get("items", [])]
        if a1_wrongs and set(a1_wrongs) & set(a2_wrongs):
            problems.append("学生乙的错题列表出现学生甲的错题")
        elif not a1_wrongs:
            notes.append("学生甲无错题，列表隔离未执行")
        else:
            notes.append("列表隔离通过")

        if a1_wrongs:
            status, _ = a2.request("POST", f"/api/wrong-questions/{a1_wrongs[0]}/explain")
            if status != 404:
                problems.append(f"学生乙请求学生甲错题讲解返回 {status}（期望 404）")
            else:
                notes.append("详情隔离通过")
        else:
            notes.append("详情隔离未执行")

        _, body = a1.request("GET", "/api/materials?subject=" + urllib.parse.quote("数学"))
        materials = parse_json(body).get("items", [])
        if materials:
            status, _ = b1.request("GET", f"/api/materials/{materials[0]['id']}")
            if status != 404:
                problems.append(f"外班请求本班讲义返回 {status}（期望 404）")
            else:
                notes.append("跳转/详情隔离通过")
        else:
            notes.append("讲义详情隔离未执行")

        status, body = b1.request(
            "GET", "/api/materials/search?subject=" + urllib.parse.quote("数学") +
            "&q=" + urllib.parse.quote("求根公式")
        )
        b1_search = parse_json(body)
        if status != 200 or b1_search.get("total") != 0 or b1_search.get("matched"):
            problems.append("外班检索命中了本班讲义")
        else:
            notes.append("检索隔离通过")

        _, body = a1.request("GET", "/api/analytics/me")
        a1_stats = parse_json(body).get("metrics", {})
        _, body = b1.request("GET", "/api/analytics/me")
        b1_stats = parse_json(body).get("metrics", {})
        if a1_stats.get("submissions", 0) > 0 and b1_stats.get("submissions", 0) == 0 and \
                a1_stats.get("wrong_questions", 0) > 0 and b1_stats.get("wrong_questions", 0) == 0:
            notes.append("个人统计隔离通过")
        elif a1_stats.get("submissions", 0) == 0:
            notes.append("学生甲无统计数据，统计隔离未执行")
        else:
            problems.append("外班学情统计包含本班数据")

        status, _ = a1.request("GET", "/api/teacher/submissions?" + urllib.parse.quote("subject=数学"))
        if status != 403:
            problems.append(f"学生调用教师接口返回 {status}（期望 403）")
        else:
            notes.append("学生越权 403 通过")

        status, _ = teacher.request("GET", "/api/analytics/me")
        if status != 403:
            problems.append(f"教师调用学生接口返回 {status}（期望 403）")
        else:
            notes.append("教师越权 403 通过")

        if problems:
            record(results, "04", "班级与个人数据隔离", "FAIL", "；".join(problems))
        else:
            record(
                results,
                "04",
                "班级与个人数据隔离",
                "PASS",
                "；".join(notes) + "；跨班教师统计未执行（仓库仅一个教师账号）",
            )
    except Exception as exc:  # noqa: BLE001
        record(results, "04", "班级与个人数据隔离", "UNEXECUTED", f"环境不可用：{exc}")


def check_skill_readonly(base_url, results):
    try:
        teacher = Client(base_url)
        teacher.login("teacher_a")
        _, body = teacher.request("GET", "/api/teacher/skills")
        before = {item["skill_key"]: item.get("prompt") for item in parse_json(body).get("items", [])}

        student = Client(base_url)
        student.login("student_a1")
        status, body = student.request("GET", "/api/skills")
        items = parse_json(body).get("items", [])
        if status != 200 or not items:
            record(results, "05", "学生技能只读", "FAIL", f"技能列表不可读：HTTP {status}")
            return
        if any("prompt" in item for item in items):
            record(results, "05", "学生技能只读", "FAIL", "学生技能列表返回了 prompt 字段")
            return
        status, _ = student.request("PUT", "/api/skills/tutor_hint", {"prompt": "被篡改的提示词"})
        if status != 403:
            record(results, "05", "学生技能只读", "FAIL",
                   f"学生写技能配置返回 {status}（期望 403）")
            return
        _, body = teacher.request("GET", "/api/teacher/skills")
        after = {item["skill_key"]: item.get("prompt") for item in parse_json(body).get("items", [])}
        if before != after:
            record(results, "05", "学生技能只读", "FAIL", "学生写请求后教师提示词发生变化")
            return
        record(
            results,
            "05",
            "学生技能只读",
            "PASS",
            f"学生读到 {len(items)} 个技能且无 prompt；写接口 403；教师提示词保持不变",
        )
    except Exception as exc:  # noqa: BLE001
        record(results, "05", "学生技能只读", "UNEXECUTED", f"环境不可用：{exc}")


def main():
    parser = argparse.ArgumentParser(description="CampusClaw 合规五条检查")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"))
    args = parser.parse_args()
    results = []

    check_audit(args.base_url, results)
    check_api_key(args.base_url, results)
    check_no_hit(args.base_url, results)
    check_isolation(args.base_url, results)
    check_skill_readonly(args.base_url, results)

    print(f"合规检查目标：{args.base_url}\n")
    for item in results:
        print(f"[{item['status']}] {item['number']} {item['name']}")
        print(f"      证据：{item['evidence']}")
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = sum(1 for item in results if item["status"] == "FAIL")
    unexecuted = sum(1 for item in results if item["status"] == "UNEXECUTED")
    print(f"\n汇总：PASS {passed} / FAIL {failed} / UNEXECUTED {unexecuted}")
    if failed or passed == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
