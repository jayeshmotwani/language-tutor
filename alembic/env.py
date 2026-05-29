import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure the project root is on sys.path so `app.*` imports resolve when
# Alembic is invoked from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

# Import models so their tables are registered on Base.metadata before
# Alembic generates diffs.
from app.database import Base  # noqa: E402
import app.auth.models  # noqa: F401, E402
import app.chat.models  # noqa: F401, E402

config = context.config

# Override the ini placeholder with the real DATABASE_URL from the environment.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")
# configparser treats % as an interpolation character, so any % in the URL
# (e.g. %40 for @) must be escaped to %% before storing. Alembic unescapes it
# back to % when it reads the value, so SQLAlchemy receives the correct URL.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL script without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live async engine."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
