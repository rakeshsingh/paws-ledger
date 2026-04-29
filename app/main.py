from fastapi import FastAPI
from fastapi.responses import FileResponse
from nicegui import ui, app as nicegui_app
from .database import create_db_and_tables
from .api.v1.routes import router as api_router
from .ui.pages import init_pages
import os
from dotenv import load_dotenv

load_dotenv()
env = os.getenv("APP_ENV", "beta")
load_dotenv(f".env.{env}")

# Create FastAPI app
fastapi_app = FastAPI(title="PawsLedger API", version="1.0.0")

# Include API routes
fastapi_app.include_router(api_router)

@fastapi_app.get("/")
async def landing_page():
    static_file = os.path.join(os.path.dirname(__file__), "ui/static/index.html")
    return FileResponse(static_file)

@fastapi_app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Initialize NiceGUI pages
init_pages()

# Integrate NiceGUI with FastAPI
ui.run_with(fastapi_app, title="PawsLedger", storage_secret="paws_secret_key")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:fastapi_app", host="0.0.0.0", port=8080, reload=True)
