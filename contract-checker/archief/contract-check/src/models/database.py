from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import config

Base = declarative_base()

engine = create_engine(config.get_db_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database schema and tables."""
    with engine.connect() as conn:
        # Create schema if not exists
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {config.DB_SCHEMA}"))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(bind=engine)


# Alias for convenience
db = SessionLocal
