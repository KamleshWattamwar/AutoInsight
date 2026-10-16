# backend/app/db.py
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB = Path(__file__).resolve().parent.parent / "autoinsight.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB.as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()