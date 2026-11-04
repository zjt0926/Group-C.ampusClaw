import os

from alembic import context

from app import create_app
from app.extensions import db
from app import models  # noqa: F401 确保模型注册到 metadata

config = context.config
app = create_app()
target_metadata = db.metadata


def _database_url():
    return os.getenv("DATABASE_URL") or app.config["SQLALCHEMY_DATABASE_URI"]


def run_migrations_offline():
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import create_engine

    connectable = create_engine(_database_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
