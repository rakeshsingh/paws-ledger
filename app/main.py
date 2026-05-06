from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
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

# Trust proxy headers (X-Forwarded-For, X-Forwarded-Proto) from Nginx
# This ensures request.url shows https:// when behind the reverse proxy
fastapi_app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "localhost"])

# Session Middleware is required for Authlib to store OAuth state
# Note: https_only is False because the internal connection (Nginx → Gunicorn)
# is HTTP. SSL is terminated at Cloudflare. The session cookie is still
# protected by SameSite=lax and the signed cookie value.
fastapi_app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("STORAGE_SECRET", "paws_secret_key"),
    same_site="lax",
    https_only=False,
)

# Include API routes
fastapi_app.include_router(api_router)

# Top-level /auth/callback to match Google OAuth registered redirect URI.
# Delegates to the same logic as /api/v1/auth/callback.
from .api.v1.auth import auth_callback as _auth_callback
fastapi_app.add_api_route("/auth/callback", _auth_callback, methods=["GET"])



@fastapi_app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Initialize NiceGUI pages
init_pages()

# Integrate NiceGUI with FastAPI
storage_secret = os.getenv("STORAGE_SECRET", "paws_secret_key")
ui.run_with(fastapi_app, title="PawsLedger", storage_secret=storage_secret)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:fastapi_app", host="0.0.0.0", port=8080, reload=True)
