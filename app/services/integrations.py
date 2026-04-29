import httpx
import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()  # Load default .env if it exists
env = os.getenv("APP_ENV", "beta")
load_dotenv(f".env.{env}")

MANUFACTURER_MAP = {
    "900": "Shared/Unassigned",
    "985": "Datamars / HomeAgain",
    "981": "Datamars / PetLink",
    "977": "Trovan",
    "956": "AVID",
    "939": "Animal ID",
    "982": "Allflex",
}

def get_manufacturer_from_chip(chip_id: str) -> str:
    if not chip_id or len(chip_id) < 3:
        return "Unknown"
    prefix = chip_id[:3]
    return MANUFACTURER_MAP.get(prefix, f"Generic ({prefix})")

class DogAPIClient:
    BASE_URL = "https://api.thedogapi.com/v1"
    
    async def get_breeds(self) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/breeds")
            if response.status_code == 200:
                return response.json()
            return []

    async def search_breed(self, name: str) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/breeds/search?q={name}")
            if response.status_code == 200:
                return response.json()
            return []

class AAHAClient:
    """
    Mock client for the AAHA Universal Pet Microchip Lookup.
    In a production environment, this would use a web scraper or an official API.
    """
    async def lookup(self, chip_id: str) -> Optional[Dict]:
        # Simulate network latency
        import asyncio
        await asyncio.sleep(0.5)
        
        # Mock logic: if chip starts with 985, it's "found" in AAHA but not in our DB
        if chip_id.startswith("985"):
            return {
                "chip_id": chip_id,
                "found_in_aaha": True,
                "manufacturer": "HomeAgain (via AAHA Network)",
                "status": "Registered with HomeAgain",
                "last_seen": "2024-01-15",
                "message": "This chip is registered in the AAHA network but not yet claimed on PawsLedger."
            }
        return None

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from nicegui import app as nicegui_app

oauth = OAuth()

class GoogleAuthService:
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_CALLBACK_URL")
        
        if all([self.client_id, self.client_secret]):
            oauth.register(
                name='google',
                client_id=self.client_id,
                client_secret=self.client_secret,
                server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={
                    'scope': 'openid profile email',
                },
            )

    async def get_authorize_url(self, request: Request) -> str:
        if not self.client_id:
            return "/login"
        
        # If redirect_uri is not set in .env, build it from the current request
        redirect_uri = self.redirect_uri
        if not redirect_uri:
            redirect_uri = str(request.url_for('auth_callback'))
            # If running behind a proxy (like ngrok/prod), ensure we use https
            if request.headers.get('x-forwarded-proto') == 'https':
                redirect_uri = redirect_uri.replace('http://', 'https://')
        
        response = await oauth.google.authorize_redirect(request, redirect_uri)
        return response.headers.get('location', '/login')

    async def authorize_access_token(self, request: Request):
        return await oauth.google.authorize_access_token(request)

    async def get_user_info(self, token: Dict) -> Dict:
        return token.get('userinfo')
