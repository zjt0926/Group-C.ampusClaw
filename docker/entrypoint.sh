#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] 等待数据库..."
  python - <<'PY'
import os
import time

import psycopg2

url = os.getenv("DATABASE_URL", "")
if url.startswith("postgresql"):
    for attempt in range(30):
        try:
            psycopg2.connect(url.replace("postgresql+psycopg2", "postgresql")).close()
            print("[entrypoint] 数据库已就绪")
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("数据库连接超时")
PY
  echo "[entrypoint] 执行数据库迁移..."
  alembic upgrade head
  echo "[entrypoint] 写入种子数据..."
  python -m app.seed
fi

exec "$@"
