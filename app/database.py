from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
load_dotenv()
from sqlalchemy.orm import Session

# DB_HOST = os.getenv("DATABASE_HOST")
# DB_PORT = os.getenv("DATABASE_PORT")
# DB_NAME = os.getenv("DATABASE_NAME")
# DB_USER = os.getenv("DATABASE_USER")
# DB_PASSWORD = os.getenv("DATABASE_PASSWORD")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not in your environment file")

engine = create_engine(DATABASE_URL,pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    