import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# По умолчанию используется локальный файл SQLite - ничего дополнительно
# устанавливать не нужно, идеально для разработки и учебного проекта.
# Когда сайт будет размещаться на Render, задай переменную окружения
# DATABASE_URL со строкой подключения к настоящему PostgreSQL
# (например, полученной от Supabase/Neon) - код менять не придётся.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tutor_site.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
