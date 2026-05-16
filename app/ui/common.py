import os
from itsdangerous import URLSafeSerializer
from nicegui import app
from sqlmodel import Session
from starlette.requests import Request
from uuid import UUID
from ..database import engine
from ..models import User
from ..services.integrations import DogAPIClient, GoogleAuthService, EmailService, HashService, PDFService

dog_client = DogAPIClient()
google_auth = GoogleAuthService()
email_service = EmailService()
hash_service = HashService()
pdf_service = PDFService()

# Species display constants — shared across UI modules
SPECIES_ICONS = {'DOG': 'pets', 'CAT': 'emoji_nature'}
SPECIES_ICON_DEFAULT = 'pets'
SPECIES_BG = {'DOG': '#ffdad2', 'CAT': '#ffdea9'}
SPECIES_BG_DEFAULT = '#eaeef5'
SPECIES_FG = {'DOG': '#a03a21', 'CAT': '#7d5800'}
SPECIES_FG_DEFAULT = '#57423d'

# Path to the global stylesheet served at /static
_STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

GLOBAL_CSS_LINK = '<link rel="stylesheet" href="/static/global.css">'

_serializer = URLSafeSerializer(os.getenv("STORAGE_SECRET", "paws_secret_key"))


def try_restore_session(request: Request) -> bool:
    """Restore NiceGUI session storage from the paws_user_id cookie.

    Call this at the top of any authenticated NiceGUI page. If the
    NiceGUI storage already has an email, this is a no-op. Otherwise it
    reads the signed cookie set by the FastAPI auth callback, loads the
    user from the DB, and populates storage so the rest of the page can
    use ``app.storage.user`` as usual.

    Returns True if the user is authenticated after this call.
    """
    if app.storage.user.get('email'):
        return True

    raw_cookie = request.cookies.get('paws_user_id')
    if not raw_cookie:
        return False

    try:
        user_id = _serializer.loads(raw_cookie)
    except Exception:
        return False

    with Session(engine) as session:
        user = session.get(User, UUID(user_id))
        if not user:
            return False

        app.storage.user.update({
            'email': user.email,
            'name': user.name,
            'id': str(user.id),
            'greet_user': True,
        })
    return True
