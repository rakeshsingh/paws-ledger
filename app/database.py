from sqlmodel import SQLModel, create_engine, Session
from .models import * # Ensure all models are loaded for table creation

sqlite_file_name = "pawsledger.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
