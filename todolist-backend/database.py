import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEFAULT_DB_URL = "sqlite:///./todos.db"
_env_url = (os.getenv("DATABASE_URL", "") or "").strip()
DATABASE_URL = _env_url or DEFAULT_DB_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
