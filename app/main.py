from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from nicegui import ui, app as nicegui_app
from .database import create_db_and_tables
from .api.v1.routes import router as api_router
from .ui.pages import init_pages
import os
from dotenv import load_dotenv

load_dotenv()
env = os.getenv("APP_ENV", "beta")
load_dotenv(f".env.{env}")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app):
    create_db_and_tables()
    yield


# Create FastAPI app
fastapi_app = FastAPI(title="PawsLedger API", version="1.0.0", lifespan=lifespan)
fastapi_app.state.limiter = limiter
fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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


# ── SEO: robots.txt and sitemap.xml ──
from fastapi.responses import PlainTextResponse

@fastapi_app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard\n"
        "Disallow: /owner/\n"
        "Disallow: /register\n"
        "Disallow: /api/\n"
        "\n"
        "Sitemap: https://www.pawsledger.com/sitemap.xml\n"
    )


@fastapi_app.get("/sitemap.xml", response_class=PlainTextResponse)
async def sitemap_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://www.pawsledger.com/</loc><priority>1.0</priority><changefreq>weekly</changefreq></url>\n'
        '  <url><loc>https://www.pawsledger.com/faq</loc><priority>0.8</priority><changefreq>monthly</changefreq></url>\n'
        '  <url><loc>https://www.pawsledger.com/pricing</loc><priority>0.8</priority><changefreq>monthly</changefreq></url>\n'
        '  <url><loc>https://www.pawsledger.com/login</loc><priority>0.6</priority><changefreq>monthly</changefreq></url>\n'
        '</urlset>\n'
    )


# Initialize NiceGUI pages
init_pages()

# Integrate NiceGUI with FastAPI
storage_secret = os.getenv("STORAGE_SECRET", "paws_secret_key")
ui.run_with(fastapi_app, title="PawsLedger", storage_secret=storage_secret, favicon="/static/favicon.svg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:fastapi_app", host="0.0.0.0", port=8080, reload=True)
