from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import ROOT_DIR, settings

database_url = make_url(settings.database_url)
if (
    database_url.get_backend_name() == "sqlite"
    and database_url.database not in {None, ":memory:"}
    and not Path(database_url.database).expanduser().is_absolute()
):
    database_path = (ROOT_DIR / "backend" / database_url.database).resolve()
    database_url = database_url.set(database=str(database_path))
connect_args = {"check_same_thread": False} if database_url.get_backend_name() == "sqlite" else {}
if database_url.get_backend_name() == "sqlite" and database_url.database not in {None, ":memory:"}:
    Path(database_url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
