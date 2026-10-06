"""
Database Connection and Session Management Module.

This module initializes the SQLAlchemy engine, configures connection pooling,
provides database session lifecycle management for FastAPI dependency injection,
and provides a migration runner to apply SQL migrations on startup.
"""

import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables
load_dotenv()

# ==============================================================================
# Database URL Configuration
# Why: PostgreSQL with pgvector requires psycopg2 or asyncpg driver.
# ==============================================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:postgres@localhost:5432/cctv_attendance"
)

# SQLAlchemy Engine Configuration:
# - pool_size=10: Maintain 10 persistent connections for concurrent API requests and CCTV ingestion workers.
# - max_overflow=20: Allow bursts of up to 20 additional connections during peak classroom recognition bursts.
# - pool_pre_ping=True: Automatically checks if connection is alive before issuing queries, avoiding stale disconnects.
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)

# Session factory bound to engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency that provides a transactional database session per HTTP/WebSocket request.
    
    Why this pattern:
    Ensures that database sessions are cleanly opened and automatically closed
    even if an unhandled exception occurs in an endpoint handler, preventing
    connection pool starvation.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """
    Executes raw SQL migration files located in `backend/database/migrations/`.
    
    Why automated SQL migration runner:
    1. Ensures all tables, pgvector extensions, constraints, and HNSW indexes
       are initialized automatically before services start.
    2. Allows zero-hassle deployment during college hackathon live demos.
    """
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print(f"[DB] Migrations directory not found at: {migrations_dir}")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))
    with engine.begin() as conn:
        for sql_file in migration_files:
            print(f"[DB] Applying migration: {sql_file.name}...")
            sql_content = sql_file.read_text(encoding="utf-8")
            # Execute migration statements
            conn.execute(text(sql_content))
            print(f"[DB] Migration {sql_file.name} applied successfully.")


def check_database_health() -> bool:
    """
    Checks if database connection is alive and vector extension is available.
    
    Returns:
        bool: True if connected and pgvector is ready, False otherwise.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
            has_vector = result.scalar() is not None
            return bool(has_vector)
    except Exception as exc:
        print(f"[DB Health Check Failed] Error: {exc}")
        return False
