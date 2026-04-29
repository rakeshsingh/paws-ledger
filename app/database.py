import os
from sqlmodel import SQLModel, create_engine, Session
from .models import * # Ensure all models are loaded for table creation

database_url = os.getenv("DATABASE_URL", "sqlite:///./pawsledger.db")

engine = create_engine(database_url, echo=False, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
