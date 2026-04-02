from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# --- 2. Be VERY explicit with imports ---
from app.models.database import Base 

# Instead of 'from app import models', import the specific file 
# where User, Booking, Event, etc., are actually written.
from app.models import models  # Ensure this is the file with 'class User(Base):'

# --- 3. Set the metadata ---
target_metadata = Base.metadata

# --- REST OF THE SCRIPT ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 🚨 REMOVE THE 'target_metadata = None' LINE THAT WAS HERE 🚨

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()