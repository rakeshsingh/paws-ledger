import httpx
import os
import re
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()  # Load default .env if it exists
env = os.getenv("APP_ENV", "beta")
load_dotenv(f".env.{env}")

MANUFACTURER_MAP = {
    # ISO 134.2 kHz — 15-digit chips starting with these 3-digit prefixes
    "900": "Shared/Unassigned",
    "939": "Animal ID",
    "941": "AVID Europe",
    "943": "AVID Europe",
    "945": "Sokymat / EIDAP",
    "953": "Datamars",
    "956": "AVID",
    "965": "Microfindr",
    "968": "AKC Reunite / Trovan",
    "972": "Planet ID",
    "977": "Trovan",
    "978": "Allflex / Digital Angel",
    "981": "Datamars / PetLink",
    "982": "Allflex",
    "984": "Nedap",
    "985": "Datamars / HomeAgain",
    "986": "Microchip ID",
    "988": "Virbac / BackHome",
    "990": "Indexel",
    "991": "Destron Fearing",
    "992": "Cromwell",
    "998": "Microchip4Solutions",
    "999": "Test / Development",
}

# Extended info for the "aha" moment — includes country of origin and registry
MANUFACTURER_DETAILS = {
    "900": {"name": "Shared/Unassigned", "registry": "Various", "country": "International"},
    "939": {"name": "Animal ID", "registry": "Animal ID Systems", "country": "USA"},
    "956": {"name": "AVID", "registry": "PETtrac", "country": "USA"},
    "968": {"name": "AKC Reunite / Trovan", "registry": "AKC Reunite", "country": "USA"},
    "977": {"name": "Trovan", "registry": "Trovan Ltd", "country": "UK"},
    "981": {"name": "Datamars / PetLink", "registry": "PetLink", "country": "USA"},
    "982": {"name": "Allflex", "registry": "Allflex / Destron", "country": "USA"},
    "985": {"name": "Datamars / HomeAgain", "registry": "HomeAgain", "country": "USA"},
    "988": {"name": "Virbac / BackHome", "registry": "BackHome", "country": "Australia"},
}


def get_manufacturer_from_chip(chip_id: str) -> str:
    """Get manufacturer name from chip ID prefix."""
    if not chip_id or len(chip_id) < 3:
        return "Unknown"
    prefix = chip_id[:3]
    return MANUFACTURER_MAP.get(prefix, f"Generic ({prefix})")


def get_chip_prefix_info(partial_chip: str) -> dict:
    """Get real-time prefix info as the user types.
    
    Returns manufacturer details for the first 3+ digits entered,
    providing instant "aha" feedback about the chip's origin.
    """
    if not partial_chip:
        return {"identified": False, "hint": "Enter a microchip number"}

    cleaned = partial_chip.strip().upper()

    # Non-ISO chips (9-10 alphanumeric) — can't identify by prefix
    if not cleaned.isdigit():
        return {
            "identified": True,
            "type": "non-iso",
            "hint": "Non-ISO chip (125/128 kHz)",
            "manufacturer": None,
        }

    # Need at least 3 digits for ISO prefix identification
    if len(cleaned) < 3:
        if cleaned[0] == '9':
            return {"identified": False, "hint": "ISO chip detected — keep typing for manufacturer ID..."}
        return {"identified": False, "hint": "Enter at least 3 digits for identification"}

    prefix = cleaned[:3]
    manufacturer = MANUFACTURER_MAP.get(prefix)
    details = MANUFACTURER_DETAILS.get(prefix)

    if manufacturer:
        result = {
            "identified": True,
            "type": "iso",
            "prefix": prefix,
            "manufacturer": manufacturer,
            "hint": f"Chip by {manufacturer}",
        }
        if details:
            result["registry"] = details.get("registry")
            result["country"] = details.get("country")
        return result

    # Valid ISO format but unknown prefix
    if cleaned[0] == '9':
        return {
            "identified": True,
            "type": "iso",
            "prefix": prefix,
            "manufacturer": f"ISO Registered ({prefix})",
            "hint": f"ISO chip with prefix {prefix}",
        }

    return {"identified": False, "hint": "Unrecognized chip format"}

class DogAPIClient:
    """Client for the Dog CEO API (dog.ceo) — free, no API key required."""
    BASE_URL = "https://dog.ceo/api"

    async def get_breeds(self) -> List[Dict]:
        """Fetch all dog breeds from dog.ceo API.

        Returns a list of dicts with 'name' key for each breed,
        including sub-breeds formatted as 'Sub-breed Parent-breed'.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.BASE_URL}/breeds/list/all")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        breeds = []
                        for breed, sub_breeds in data.get('message', {}).items():
                            # Capitalize breed name
                            breed_name = breed.capitalize()
                            breeds.append({'name': breed_name})
                            # Add sub-breeds as "Sub-breed Breed"
                            for sub in sub_breeds:
                                sub_name = f"{sub.capitalize()} {breed_name}"
                                breeds.append({'name': sub_name})
                        return sorted(breeds, key=lambda b: b['name'])
            except Exception:
                pass
            return []

    async def search_breed(self, name: str) -> List[Dict]:
        """Search breeds by name (client-side filter from full list)."""
        all_breeds = await self.get_breeds()
        query = name.lower()
        return [b for b in all_breeds if query in b['name'].lower()]

class AAHAClient:
    """
    Mock client for the AAHA Universal Pet Microchip Lookup.
    In a production environment, this would use a web scraper or an official API.
    """

    # Known ISO microchip prefixes and their manufacturers
    _MANUFACTURERS = {
        "900": "Shared/Unassigned",
        "985": "Datamars / HomeAgain",
        "981": "Datamars / PetLink",
        "977": "Trovan",
        "956": "AVID",
        "939": "Animal ID",
        "982": "Allflex",
    }

    async def lookup(self, chip_id: str) -> Optional[Dict]:
        # Simulate network latency
        import asyncio
        await asyncio.sleep(0.3)

        if not chip_id or len(chip_id) < 9:
            return None

        # ISO chips: 15 digits starting with 9
        if len(chip_id) == 15 and chip_id[0] == '9' and chip_id.isdigit():
            prefix = chip_id[:3]
            manufacturer = self._MANUFACTURERS.get(prefix, f"ISO Registered ({prefix})")
            return {
                "chip_id": chip_id,
                "found_in_aaha": True,
                "manufacturer": f"{manufacturer} (via AAHA Network)",
                "status": "Registered",
                "last_seen": "2024-01-15",
                "message": "This chip is registered in the AAHA network but not yet claimed on PawsLedger."
            }

        # Non-ISO chips: 9-10 alphanumeric characters (125 kHz / 128 kHz)
        if len(chip_id) in (9, 10):
            return {
                "chip_id": chip_id,
                "found_in_aaha": True,
                "manufacturer": "Non-ISO (125/128 kHz) via AAHA Network",
                "status": "Registered",
                "last_seen": "2024-01-15",
                "message": "This non-ISO chip is registered in the AAHA network but not yet claimed on PawsLedger."
            }

        return None

from fpdf import FPDF

class PDFService:
    @staticmethod
    def generate_vaccination_report(pet_name: str, vaccinations: list, record_hash: str) -> str:
        import tempfile
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(200, 10, txt="PawsLedger Vaccination Record", ln=True, align="C")
        
        # Sanitize pet_name for display only (not used in filename)
        safe_name = re.sub(r'[^\w\s\-]', '', pet_name)[:50]
        
        pdf.set_font("helvetica", "", 12)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Pet Name: {safe_name}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(40, 10, txt="Date", border=1)
        pdf.cell(60, 10, txt="Vaccine", border=1)
        pdf.cell(50, 10, txt="Manufacturer", border=1)
        pdf.cell(40, 10, txt="Expires", border=1)
        pdf.ln()
        
        pdf.set_font("helvetica", "", 10)
        for v in vaccinations:
            pdf.cell(40, 10, txt=str(v.date_given.date()), border=1)
            pdf.cell(60, 10, txt=v.vaccine_name[:30], border=1)
            pdf.cell(50, 10, txt=(v.manufacturer or "")[:25], border=1)
            pdf.cell(40, 10, txt=str(v.expiration_date.date()), border=1)
            pdf.ln()
            
        pdf.ln(10)
        pdf.set_font("helvetica", "I", 8)
        pdf.multi_cell(0, 5, txt=f"Verification Hash (SHA-256): {record_hash}")
        pdf.ln(5)
        pdf.multi_cell(0, 5, txt="This document is a verified digital export from PawsLedger. Authenticity can be verified at https://pawsledger.com/verify")
        
        # Use secure temp file — no user input in path
        fd, output_path = tempfile.mkstemp(suffix='.pdf', prefix='pawsledger_vax_')
        os.close(fd)
        pdf.output(output_path)
        return output_path

import hashlib
import json

class HashService:
    @staticmethod
    def hash_record(record_data: dict) -> str:
        # Create a stable JSON string to hash
        encoded_data = json.dumps(record_data, sort_keys=True, default=str).encode()
        return hashlib.sha256(encoded_data).hexdigest()

class EmailService:
    """Email service using Resend (https://resend.com).

    Set RESEND_API_KEY in your .env file.
    Set EMAIL_FROM to your verified sender (e.g. alerts@pawsledger.com).
    Falls back to logging if RESEND_API_KEY is not configured.
    """

    _api_key = os.getenv("RESEND_API_KEY")
    _from_email = os.getenv("EMAIL_FROM", "PawsLedger <alerts@pawsledger.com>")

    @staticmethod
    async def send_email(to_email: str, subject: str, body: str):
        import logging
        logger = logging.getLogger("pawsledger.email")

        api_key = os.getenv("RESEND_API_KEY")
        from_email = os.getenv("EMAIL_FROM", "PawsLedger <alerts@pawsledger.com>")

        if not api_key:
            logger.warning(f"RESEND_API_KEY not set — email not sent (subject: {subject})")
            return False

        try:
            import resend
            resend.api_key = api_key
            resend.Emails.send({
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "text": body,
            })
            logger.info(f"Email sent: subject='{subject}' (recipient redacted)")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @staticmethod
    async def notify_owner_of_scan(owner_email: str, pet_name: str):
        subject = "ALERT: Your pet's tag was scanned!"
        body = (
            "Hello,\n\n"
            "Your pet's PawsLedger QR/NFC tag was recently scanned. "
            "If your pet is lost, this is a 'proof of life' event.\n\n"
            "Please check your dashboard for more details.\n\n"
            "— PawsLedger"
        )
        await EmailService.send_email(owner_email, subject, body)

    @staticmethod
    async def notify_owner_of_access(owner_email: str, pet_name: str, accessor_info: str):
        subject = "Heartbeat Audit: Pet records were accessed"
        body = (
            "Hello,\n\n"
            "Your pet's medical records were accessed via a shared link.\n\n"
            f"Accessor: {accessor_info}\n\n"
            "This heartbeat notification is part of PawsLedger's managed access service.\n\n"
            "— PawsLedger"
        )
        await EmailService.send_email(owner_email, subject, body)

    @staticmethod
    async def send_nudge_alert(owner_email: str, pet_name: str, sanitized_message: str, dashboard_url: str) -> bool:
        subject = "PawsLedger Alert: Someone found your pet!"
        body = (
            "Hello,\n\n"
            "Great news — a verified PawsLedger user has found a pet registered to your "
            "account and sent you the following message:\n\n"
            "---\n"
            f"{sanitized_message}\n"
            "---\n\n"
            f"Please visit your PawsLedger dashboard to view this nudge:\n"
            f"{dashboard_url}\n\n"
            "Upgrade to Verified to reply securely without revealing your email.\n\n"
            "IMPORTANT: PawsLedger will never ask for your password in this email. "
            "If you did not expect this alert, please ignore it or contact "
            "support@pawsledger.com.\n\n"
            "— PawsLedger (alerts@pawsledger.com)\n"
        )
        return await EmailService.send_email(owner_email, subject, body)

    @staticmethod
    async def send_nudge_alert_verified(
        owner_email: str, pet_name: str, sanitized_message: str,
        callback_url: str, geo_lat=None, geo_lon=None,
    ) -> bool:
        """Send nudge alert to Verified-tier owner with reply callback URL."""
        location_line = ""
        if geo_lat is not None and geo_lon is not None:
            map_url = f"https://www.openstreetmap.org/?mlat={geo_lat}&mlon={geo_lon}#map=15/{geo_lat}/{geo_lon}"
            location_line = f"\nFinder's shared location:\n{map_url}\n"

        subject = "PawsLedger Alert: Someone found your pet!"
        body = (
            "Hello,\n\n"
            "Great news — a verified PawsLedger user has found a pet registered to your "
            "account and sent you the following message:\n\n"
            "---\n"
            f"{sanitized_message}\n"
            "---\n"
            f"{location_line}\n"
            "You can reply securely to this finder (your email stays hidden):\n"
            f"{callback_url}\n\n"
            "This link expires in 48 hours. Do not share it with anyone.\n\n"
            "IMPORTANT: PawsLedger will never ask for your password in this email. "
            "If you did not expect this alert, please ignore it or contact "
            "support@pawsledger.com.\n\n"
            "— PawsLedger (alerts@pawsledger.com)\n"
        )
        return await EmailService.send_email(owner_email, subject, body)

    @staticmethod
    async def send_owner_reply(finder_email: str, pet_name: str, owner_reply: str) -> bool:
        """Send the owner's reply to the finder with masked sender identity."""
        subject = f"PawsLedger Recovery: The owner of {pet_name} replied!"
        body = (
            "Hello,\n\n"
            f"The owner of {pet_name} has replied to your nudge:\n\n"
            "---\n"
            f"{owner_reply}\n"
            "---\n\n"
            "This is a one-time secure relay. The owner's email address is not "
            "shared — please coordinate through the platform if further contact "
            "is needed.\n\n"
            "IMPORTANT: PawsLedger will never ask for your password in this email.\n\n"
            "— PawsLedger Recovery (recovery@pawsledger.com)\n"
        )
        from_email = "PawsLedger Recovery <recovery@pawsledger.com>"
        import logging
        logger = logging.getLogger("pawsledger.email")

        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            logger.warning("RESEND_API_KEY not set — reply email not sent")
            return False

        try:
            import resend
            resend.api_key = api_key
            resend.Emails.send({
                "from": from_email,
                "to": [finder_email],
                "subject": subject,
                "text": body,
            })
            logger.info("Owner reply sent (recipient redacted)")
            return True
        except Exception as e:
            logger.error(f"Failed to send owner reply: {e}")
            return False

    @staticmethod
    async def send_payment_failed_notification(user_email: str, user_name: str) -> bool:
        """Notify user that their subscription payment has failed."""
        base_url = os.getenv("BASE_URL", "https://www.pawsledger.com")
        subject = "PawsLedger: Payment failed — action required"
        body = (
            f"Hi {user_name},\n\n"
            "We were unable to process your most recent subscription payment. "
            "Your account has been marked as past due.\n\n"
            "Please update your payment method to maintain access to your "
            "Verified features:\n"
            f"{base_url}/subscription\n\n"
            "If your payment method is not updated within 7 days, your "
            "subscription will be canceled and features will revert to the "
            "free tier.\n\n"
            "— PawsLedger\n"
        )
        return await EmailService.send_email(user_email, subject, body)

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
            base_url = str(request.base_url).rstrip('/')
            redirect_uri = f"{base_url}/auth/callback"
            # If running behind a proxy (like ngrok/prod), ensure we use https
            if request.headers.get('x-forwarded-proto') == 'https':
                redirect_uri = redirect_uri.replace('http://', 'https://')
        
        response = await oauth.google.authorize_redirect(request, redirect_uri)
        return response.headers.get('location', '/login')

    async def authorize_redirect(self, request: Request):
        if not self.client_id:
            return RedirectResponse(url="/login")
        
        redirect_uri = self.redirect_uri
        if not redirect_uri:
            base_url = str(request.base_url).rstrip('/')
            redirect_uri = f"{base_url}/auth/callback"
            
            # If running behind a proxy (like ngrok/prod), ensure we use https
            if request.headers.get('x-forwarded-proto') == 'https':
                redirect_uri = redirect_uri.replace('http://', 'https://')
        
        return await oauth.google.authorize_redirect(request, redirect_uri)

    async def authorize_access_token(self, request: Request):
        return await oauth.google.authorize_access_token(request)

    async def get_user_info(self, token: Dict) -> Dict:
        return token.get('userinfo')
