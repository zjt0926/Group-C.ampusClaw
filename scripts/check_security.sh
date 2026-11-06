#!/usr/bin/env sh
# 一键复查：SEC-05 密钥扫描 + SEC-06 依赖审计
# 用法：make check-security（或 sh scripts/check_security.sh [secrets|deps|all]）
set -u

PATTERN='sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_KEY=[0-9a-fA-F]{32,}|JWT_SECRET=[0-9a-fA-F]{32,}'

# Windows 下 PATH 过长时被截断会导致找不到 docker，按常见安装位置兜底
DOCKER="${DOCKER:-}"
if [ -z "$DOCKER" ]; then
    if command -v docker >/dev/null 2>&1; then
        DOCKER=docker
    else
        for candidate in "/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
            "$(cygpath -u "$LOCALAPPDATA" 2>/dev/null)/Programs/DockerDesktop/resources/bin/docker.exe"; do
            if [ -n "$candidate" ] && [ -x "$candidate" ]; then
                DOCKER="$candidate"
                break
            fi
        done
    fi
fi
[ -n "$DOCKER" ] || DOCKER=docker

WEB_CONTAINER="${WEB_CONTAINER:-$("$DOCKER" ps --filter 'label=com.docker.compose.service=web' --format '{{.Names}}' 2>/dev/null | head -n 1)}"
WORKER_CONTAINER="${WORKER_CONTAINER:-$("$DOCKER" ps --filter 'label=com.docker.compose.service=worker' --format '{{.Names}}' 2>/dev/null | head -n 1)}"

line_count() {
    wc -l | tr -d ' '
}

scan_secrets() {
    fails=0

    printf '扫描提交历史 …… '
    history_hits=$(git rev-list --all | while read -r rev; do
        git grep -n -E "$PATTERN" "$rev" 2>/dev/null
    done)
    if [ -n "$history_hits" ]; then
        printf '命中 %s\n' "$(printf '%s\n' "$history_hits" | line_count)"
        printf '%s\n' "$history_hits"
        fails=1
    else
        printf '通过（0 命中）\n'
    fi

    printf '扫描前端产物 …… '
    frontend_hits=$(grep -rInE "$PATTERN" app/static app/templates 2>/dev/null)
    if [ -n "$frontend_hits" ]; then
        printf '命中 %s\n' "$(printf '%s\n' "$frontend_hits" | line_count)"
        printf '%s\n' "$frontend_hits"
        fails=1
    else
        printf '通过（0 命中）\n'
    fi

    printf '扫描运行日志 …… '
    log_hits=$(
        {
            [ -n "$WEB_CONTAINER" ] && docker logs "$WEB_CONTAINER" 2>&1
            [ -n "$WORKER_CONTAINER" ] && docker logs "$WORKER_CONTAINER" 2>&1
        } | grep -nE "$PATTERN"
    )
    if [ -n "$log_hits" ]; then
        printf '命中 %s\n' "$(printf '%s\n' "$log_hits" | line_count)"
        printf '%s\n' "$log_hits"
        fails=1
    else
        printf '通过（0 命中）\n'
    fi

    return "$fails"
}

audit_deps() {
    if [ -z "$WEB_CONTAINER" ]; then
        printf '依赖审计 …… 未执行（未找到 web 容器，请先 docker compose up -d）\n'
        return 2
    fi
    printf '依赖审计（%s / pip-audit）……\n' "$WEB_CONTAINER"
    if ! "$DOCKER" exec "$WEB_CONTAINER" sh -c \
        'command -v pip-audit >/dev/null 2>&1 || pip install --quiet pip-audit' >/dev/null 2>&1; then
        printf '依赖审计 …… 容器内无法使用 pip-audit\n'
        return 2
    fi
    "$DOCKER" exec "$WEB_CONTAINER" pip-audit
    code=$?
    if [ "$code" -eq 0 ]; then
        printf '依赖审计 …… 通过（0 漏洞）\n'
    else
        printf '依赖审计 …… 发现已知漏洞（退出码 %s），基线见 reports/security-baseline.md\n' "$code"
    fi
    return "$code"
}

target="${1:-all}"
rc=0
case "$target" in
    secrets)
        scan_secrets || rc=$?
        ;;
    deps)
        audit_deps || rc=$?
        ;;
    all)
        scan_secrets || rc=$?
        audit_deps || rc=$?
        ;;
    *)
        printf '未知参数：%s（可用 secrets | deps | all）\n' "$target"
        exit 2
        ;;
esac

exit "$rc"
