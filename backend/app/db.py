import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def database_url():
    return os.getenv('DATABASE_URL', 'sqlite:///./dev.db')

_url = database_url()
engine = create_engine(_url, connect_args={'check_same_thread': False} if _url.startswith('sqlite') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
class Base(DeclarativeBase): pass
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
