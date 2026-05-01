from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User, LedgerEvent, Vaccination, SharedAccess
from ..services.integrations import get_manufacturer_from_chip, DogAPIClient, GoogleAuthService, EmailService, HashService, PDFService
from datetime import datetime, timedelta
import uuid

dog_client = DogAPIClient()
google_auth = GoogleAuthService()
email_service = EmailService()
hash_service = HashService()
pdf_service = PDFService()

COMMON_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

    :root {
        --primary: #d97706;
        --primary-hover: #b45309;
        --bg: #fffcf9;
        --card-bg: #ffffff;
        --text-main: #451a03;
        --text-muted: #78350f;
        --border: #fde6d2;
        --accent: #f59e0b;
    }

    body {
        font-family: 'Outfit', sans-serif;
        background-color: var(--bg);
        color: var(--text-main);
    }

    .logo {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--primary) !important;
        text-decoration: none;
        letter-spacing: -0.05em;
    }

    .logo span {
        color: var(--text-muted) !important;
        font-weight: 400;
    }

    .nicegui-header {
        background-color: rgba(255, 252, 249, 0.8) !important;
        backdrop-filter: blur(8px);
        color: var(--text-main) !important;
    }

    .q-btn {
        border-radius: 12px !important;
        text-transform: none !important;
        font-weight: 600 !important;
    }

    .q-card {
        border-radius: 20px !important;
        box-shadow: 0 10px 25px -5px rgba(217, 119, 6, 0.05) !important;
        border: 1px solid var(--border) !important;
    }

    footer {
        padding: 2rem;
        text-align: center;
        font-size: 0.875rem;
        color: var(--text-muted);
        border-top: 1px solid var(--border);
        background: #fffcf9;
        margin-top: auto;
    }
</style>
"""

def init_pages():
    ui.add_head_html(COMMON_STYLE)
    @ui.page("/")
    async def index_page():
        nav_header()
        with ui.column().classes("w-full items-center p-8 md:p-24"):
            with ui.column().classes("w-full max-w-3xl items-center text-center"):
                ui.label("Secure Pet Identity Ledger").classes("text-5xl md:text-7xl font-black mb-4").style("line-height: 1; letter-spacing: -0.02em;")
                ui.label("Link your pet's physical microchip to a secure digital history.").classes("text-xl text-orange-900 opacity-70 mb-12")
                
                with ui.card().classes("w-full p-8 bg-white"):
                    with ui.row().classes("w-full gap-4"):
                        chip_input = ui.input("15-digit Microchip ID").classes("flex-grow").props('outlined rounded color="amber-9" bg-color="orange-1"')
                        search_btn = ui.button("Verify Identity", on_click=lambda: do_lookup()).classes("h-14 px-8 bg-amber-9 text-white shadow-lg")
                    
                    results_card = ui.column().classes("w-full mt-8 text-left").style("display: none")
                    status_badge = ui.label("").classes("px-4 py-1 rounded-full text-xs font-bold uppercase mb-2 inline-block")
                    result_title = ui.label("").classes("text-2xl font-bold")
                    result_desc = ui.label("").classes("text-orange-900 opacity-70 mb-6")
                    result_details = ui.column().classes("w-full pt-4 border-t border-orange-100")
                    
                    async def do_lookup():
                        chip_id = chip_input.value
                        if not chip_id:
                            ui.notify("Please enter a Chip ID", type="warning", color="amber-9")
                            return
                        
                        search_btn.disable()
                        search_btn.text = "Verifying..."
                        
                        try:
                            with Session(engine) as session:
                                pet = session.exec(select(Pet).where(Pet.chip_id == chip_id)).first()
                                results_card.style("display: block")
                                if pet:
                                    status_badge.text = "Verified PawsLedger Record"
                                    status_badge.style("background-color: #fef3c7; color: #92400e")
                                    result_title.text = f"{pet.name} • {pet.pet_species}"
                                    result_desc.text = f"Breed: {pet.breed} | Status: {pet.identity_status}"
                                    
                                    result_details.clear()
                                    with result_details:
                                        ui.button("View Full Ledger", on_click=lambda: ui.navigate.to(f"/pet/{pet.id}")).classes("w-full bg-amber-9 text-white mt-4")
                                else:
                                    from ..api.v1.routes import aaha_client
                                    aaha_data = await aaha_client.lookup(chip_id)
                                    if aaha_data:
                                        status_badge.text = "AAHA Nationwide Network"
                                        status_badge.style("background-color: #fff7ed; color: #9a3412")
                                        result_title.text = "Identity Found Externally"
                                        result_desc.text = aaha_data["message"]
                                        result_details.clear()
                                        with result_details:
                                            ui.label("Protect this pet with a PawsLedger Identity.").classes("text-sm italic mb-4")
                                            ui.button("Claim Identity / Register", on_click=lambda: ui.navigate.to("/register")).classes("w-full bg-orange-9 text-white")
                                    else:
                                        ui.notify("No registration found for this ID.", type="negative", color="deep-orange-9")
                                        results_card.style("display: none")
                        finally:
                            search_btn.enable()
                            search_btn.text = "Verify Identity"

        nav_footer()

    def nav_header():
        with ui.header().classes('bg-white text-orange-9 px-8 py-6 justify-between items-center border-b border-orange-50'):
            with ui.link(target='/').classes('logo'):
                ui.label('Paws').style('display: inline')
                ui.label('Ledger').style('display: inline; color: var(--text-muted)')
            
            with ui.row().classes('gap-8 items-center'):
                ui.link('About', '/about').classes('text-orange-900 font-medium opacity-70 hover:opacity-100 transition-opacity')
                ui.link('Contact', '/contact').classes('text-orange-900 font-medium opacity-70 hover:opacity-100 transition-opacity')
                if app.storage.user.get('email'):
                    ui.link('Dashboard', '/dashboard').classes('text-orange-900 font-medium')
                    ui.button('Logout', on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/'))).props('flat color="amber-9"')
                else:
                    ui.button('Sign In', on_click=lambda: ui.navigate.to('/login')).classes('bg-amber-9 text-white px-6')

    def nav_footer():
        with ui.footer().classes('bg-white border-t border-orange-50 p-12 text-center'):
             ui.label('© 2026 PawsLedger • The Source of Truth for Pet Identity • ISO 11784 Compliant').classes('text-orange-900 opacity-50')


    @ui.page('/about')
    async def about_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('About PawsLedger').classes('text-4xl font-bold mb-6')
            ui.markdown("""
            PawsLedger is a hybrid identity platform that provides a **"Single Source of Truth"** for pet records. 
            We link physical identifiers (Microchip or QR Tag) to a secure, cloud-based digital ledger.

            ### Our Mission
            - **Decoupled Identity:** Separate pet records from proprietary manufacturer databases.
            - **Trusted Transfer:** Securely manage ownership changes.
            - **Seamless Access:** Provide time-bound access for vets and caregivers.
            """)
        nav_footer()

    @ui.page('/faq')
    async def faq_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Frequently Asked Questions').classes('text-4xl font-bold mb-6')
            with ui.expansion('What is PawsLedger?', icon='help').classes('w-full border rounded'):
                ui.label('PawsLedger is a decentralized registry for pet identity and health records.')
            with ui.expansion('How does the Microchip lookup work?', icon='search').classes('w-full border rounded mt-2'):
                ui.label('We check our internal ledger first, then query the nationwide AAHA network to find registration details.')
            with ui.expansion('Is my data secure?', icon='security').classes('w-full border rounded mt-2'):
                ui.label('Yes, PawsLedger uses industry-standard encryption and obfuscates owner PII until an emergency state is toggled.')
        nav_footer()

    @ui.page('/shared/{token}')
    async def shared_profile(token: str):
        nav_header()
        with Session(engine) as session:
            statement = select(SharedAccess).where(SharedAccess.token == token)
            shared_access = session.exec(statement).first()
            
            if not shared_access or shared_access.expires_at < datetime.utcnow():
                with ui.column().classes('w-full items-center p-8'):
                    ui.label('Access Expired or Invalid').classes('text-2xl text-red-500')
                    ui.label('This shared link is no longer active.').classes('text-gray-500')
                return

            pet = shared_access.pet
            
            # Log Heartbeat Audit
            event = LedgerEvent(
                pet_id=pet.id,
                event_type="HEARTBEAT_ACCESS",
                description="Shared records accessed via time-bound link"
            )
            session.add(event)
            session.commit()
            
            # Notify owner
            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_access(pet.owner.email, pet.breed or "Pet", "Service Provider (Shared Link)")

            with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
                ui.label(f'Care Guide & Records: {pet.breed}').classes('text-3xl font-bold mb-6')
                
                with ui.row().classes('w-full gap-4'):
                    with ui.card().classes('flex-1 p-6'):
                        ui.label('Vaccination History').classes('text-xl font-bold mb-4 border-b')
                        if not pet.vaccinations:
                            ui.label('No vaccination records found.').classes('italic text-gray-500')
                        else:
                            for v in pet.vaccinations:
                                with ui.row().classes('justify-between w-full mb-2'):
                                    with ui.column():
                                        ui.label(v.vaccine_name).classes('font-bold')
                                        ui.label(f"Given: {v.date_given.date()}").classes('text-xs text-gray-500')
                                    ui.label(f"Expires: {v.expiration_date.date()}").classes('text-xs font-bold text-blue-600')

                    with ui.card().classes('w-64 p-6'):
                        ui.label('Quick Info').classes('font-bold border-b mb-2')
                        ui.label(f'Species: {pet.pet_species}')
                        ui.label(f'Breed: {pet.breed}')
                        ui.label(f'DOB: {pet.dob.date() if pet.dob else "Unknown"}')
                        ui.separator().classes('my-2')
                        ui.label('Access Status').classes('text-xs text-gray-400')
                        ui.label('Active').classes('text-green-600 font-bold')
                        ui.label(f"Expires: {shared_access.expires_at.strftime('%Y-%m-%d %H:%M')}").classes('text-xs text-gray-500')
        nav_footer()

    @ui.page('/login')
    async def login_page(request: Request):
        if app.storage.user.get('email'):
            ui.navigate.to('/dashboard')
            return
        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            with ui.card().classes('w-full max-w-sm p-6 items-center'):
                ui.label('Welcome Back').classes('text-2xl font-bold mb-4')
                ui.label('Secure login for PawsLedger').classes('text-gray-500 mb-6 text-center')
                
                # Google Login Button
                def login_google():
                    ui.navigate.to('/api/v1/auth/login')

                with ui.button(on_click=login_google) \
                    .classes('w-full bg-white text-gray-700 border border-gray-300 py-2 mb-4 flex items-center justify-center') \
                    .style('text-transform: none; font-weight: 500'):
                    ui.html('<img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_Logo.svg" style="width: 18px; margin-right: 12px;">')
                    ui.label('Sign in with Google')

                ui.separator().classes('mb-4')
                ui.label('Authorized Identity Provider Only').classes('text-xs text-gray-400')
        nav_footer()

    @ui.page('/auth/callback')
    async def nicegui_auth_callback(request: Request):
        print(f"DEBUG: Entering nicegui_auth_callback. Request URL: {request.url}")
        try:
            token = await google_auth.authorize_access_token(request)
            print(f"DEBUG: Token received: {token is not None}")
            user_info = await google_auth.get_user_info(token)
            print(f"DEBUG: User info: {user_info}")
            
            sub = user_info["sub"]
            email = user_info["email"]
            name = user_info.get("name", email)
            
            with Session(engine) as session:
                # Try finding by sub first (immutable anchor)
                statement = select(User).where(User.sub == sub)
                user = session.exec(statement).first()
                
                if not user:
                    print(f"DEBUG: User {email} not found, checking by email...")
                    # Fallback to email for migration/linking if necessary
                    statement = select(User).where(User.email == email)
                    user = session.exec(statement).first()
                    
                    if user:
                        print(f"DEBUG: Linking existing user {email} with sub {sub}")
                        user.sub = sub # Link existing user
                    else:
                        print(f"DEBUG: Creating new user {email}")
                        user = User(sub=sub, email=email, name=name)
                        session.add(user)
                    
                    session.commit()
                    session.refresh(user)
                
                print(f"DEBUG: Updating app.storage.user for {user.email}")
                app.storage.user.update({
                    'email': user.email,
                    'name': user.name,
                    'id': str(user.id),
                    'greet_user': True
                })
            
            print("DEBUG: Navigating to /dashboard")
            ui.navigate.to('/dashboard')
        except Exception as e:
            print(f"DEBUG: Authentication error: {str(e)}")
            import traceback
            traceback.print_exc()
            ui.notify(f'Authentication error: {str(e)}', type='negative')
            ui.navigate.to('/login')

    @ui.page('/dashboard')
    async def dashboard():
        print(f"DEBUG: Entering dashboard. Storage user email: {app.storage.user.get('email')}")
        if not app.storage.user.get('email'):
            print("DEBUG: No email in storage, redirecting to /login")
            ui.navigate.to('/login')
            return
        
        if app.storage.user.get('greet_user'):
            ui.notify(f"Welcome back, {app.storage.user['name']}!", type='positive')
            app.storage.user['greet_user'] = False
        
        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            ui.label(f"Welcome, {app.storage.user['name']}").classes('text-3xl font-bold mb-8')
            
            with ui.row().classes('w-full max-w-4xl gap-4'):
                with ui.card().classes('flex-1 p-6'):
                    ui.label('Your Registered Pets').classes('text-xl font-bold mb-4')
                    with Session(engine) as session:
                        # Find or create user
                        user = session.exec(select(User).where(User.email == app.storage.user['email'])).first()
                        if not user:
                            # This should rarely happen if auth flow is correct, but for safety:
                            user = User(
                                sub=f"manual|{app.storage.user['email']}", 
                                email=app.storage.user['email'], 
                                name=app.storage.user['name']
                            )
                            session.add(user)
                            session.commit()
                            session.refresh(user)
                        
                        pets = session.exec(select(Pet).where(Pet.owner_id == user.id)).all()
                        if not pets:
                            ui.label('No pets registered yet.').classes('text-gray-500 italic')
                        else:
                            for pet in pets:
                                with ui.card().classes('w-full mb-2 p-4 cursor-pointer hover:bg-gray-50').on('click', lambda p=pet: ui.navigate.to(f'/pet/{p.id}')):
                                    with ui.row().classes('justify-between items-center w-full'):
                                        with ui.column():
                                            ui.label(f"{pet.pet_species} - {pet.breed}").classes('font-bold')
                                            ui.label(f"Chip: {pet.chip_id}").classes('text-xs text-gray-500')
                                        ui.icon('chevron_right')
                
                with ui.column().classes('w-64 gap-4'):
                    with ui.card().classes('w-full p-6'):
                        ui.label('Quick Lookup').classes('font-bold mb-2')
                        chip_input = ui.input('Chip ID').classes('w-full mb-2')
                        async def do_lookup():
                            with Session(engine) as session:
                                pet = session.exec(select(Pet).where(Pet.chip_id == chip_input.value)).first()
                                if pet: ui.navigate.to(f'/pet/{pet.id}')
                                else: ui.notify('Not found in local registry', type='warning')
                        ui.button('Search', on_click=do_lookup).classes('w-full').props('small')
                    
                    ui.button('Register New Pet', icon='add', on_click=lambda: ui.navigate.to('/register')).classes('w-full')
                    ui.button('Logout', on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/'))).classes('w-full').props('flat color=grey')
        nav_footer()

    @ui.page('/register')
    async def register():
        if not app.storage.user.get('email'):
            ui.navigate.to('/login')
            return
        
        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            ui.label('Register Your Pet').classes('text-3xl font-bold mb-6')
            
            breeds = await dog_client.get_breeds()
            breed_options = {b['name']: b['name'] for b in breeds}

            with ui.card().classes('w-full max-w-lg p-6'):
                name = ui.input('Pet Name').classes('w-full mb-4')
                chip_id = ui.input('Chip ID (15 digits)').classes('w-full mb-4')
                species = ui.select(['DOG', 'CAT'], label='Species', value='DOG').classes('w-full mb-4')
                breed = ui.select(breed_options, label='Breed', with_filter=True).classes('w-full mb-4')
                gender = ui.select(['Male', 'Female', 'Unknown'], label='Gender', value='Unknown').classes('w-full mb-4')
                dob = ui.input('Birth Date').classes('w-full mb-4').props('type=date')
                
                async def submit():
                    if not name.value:
                        ui.notify('Pet Name is required.', type='negative')
                        return
                    if not chip_id.value or len(chip_id.value) != 15 or not chip_id.value.isdigit():
                        ui.notify('Invalid Chip ID. Must be exactly 15 numeric digits.', type='negative')
                        return
                    
                    manufacturer = get_manufacturer_from_chip(chip_id.value)
                    
                    with Session(engine) as session:
                        user = session.exec(select(User).where(User.email == app.storage.user['email'])).first()
                        if not user: return
                        if len(user.pets) >= 5:
                            ui.notify('Maximum of 5 pets reached per profile.', type='negative')
                            return
                        new_pet = Pet(
                            name=name.value,
                            chip_id=chip_id.value,
                            breed=breed.value,
                            pet_species=species.value,
                            gender=gender.value,
                            dob=datetime.fromisoformat(dob.value) if dob.value else None,
                            manufacturer=manufacturer,
                            identity_status="VERIFIED",
                            owner_id=user.id
                        )
                        session.add(new_pet)
                        session.commit()
                        ui.notify(f'Successfully registered {new_pet.breed}!', type='positive')
                        ui.navigate.to('/dashboard')

                ui.button('Create Identity', on_click=submit).classes('w-full mt-4')
        nav_footer()

    @ui.page('/lost')
    async def lost_pets_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Public Safety & Recovery').classes('text-4xl font-bold mb-4')
            ui.label('If you have found a pet, use our global lookup or scan their QR tag to notify the owner.').classes('text-gray-500 mb-8 text-center')
            
            with ui.card().classes('w-full p-8 items-center bg-blue-50 border-none'):
                ui.icon('search', size='48px', color='primary')
                ui.label('Search the Global Ledger').classes('text-xl font-bold mt-4')
                chip_input = ui.input('Enter 15-digit Microchip ID').classes('w-64 mt-2')
                
                async def lookup():
                    if not chip_input.value: return
                    ui.navigate.to(f'/?chip={chip_input.value}') # Redirect to landing page with query
                
                ui.button('Search Nationwide Network', on_click=lookup).classes('mt-4')

            with ui.row().classes('w-full gap-6 mt-8'):
                with ui.card().classes('flex-1 p-6'):
                    ui.label('Found a Pet?').classes('text-xl font-bold mb-2')
                    ui.label('1. Check for a PawsLedger QR tag.').classes('text-sm')
                    ui.label('2. Scan with your phone camera.').classes('text-sm')
                    ui.label('3. Tap "Contact Owner" to send an alert.').classes('text-sm')
                
                with ui.card().classes('flex-1 p-6'):
                    ui.label('Owner Privacy').classes('text-xl font-bold mb-2')
                    ui.label('We never show owner phone numbers or addresses publicly. Alerts are sent via our secure bridge.').classes('text-sm text-gray-600')

        nav_footer()

    @ui.page('/contact')
    async def contact_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Contact Us').classes('text-4xl font-bold mb-6')
            with ui.card().classes('w-full p-6'):
                ui.label('Have questions or need support?').classes('text-lg mb-4')
                ui.input('Your Name').classes('w-full mb-4')
                ui.input('Your Email').classes('w-full mb-4')
                ui.textarea('Message').classes('w-full mb-4')
                ui.button('Send Message', on_click=lambda: ui.notify('Message sent (mock)')).classes('w-full')
        nav_footer()

    @ui.page('/verify')
    async def verify_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-2xl mx-auto'):
            ui.label('Verify Vaccination Record').classes('text-3xl font-bold mb-4')
            ui.label('Enter the SHA-256 hash found at the bottom of a PawsLedger PDF export to verify its authenticity.').classes('text-gray-500 mb-8 text-center')
            
            hash_input = ui.input('Verification Hash').classes('w-full mb-4').props('outlined')
            
            results = ui.column().classes('w-full mt-4')

            async def verify():
                results.clear()
                if not hash_input.value: return
                
                with Session(engine) as session:
                    # Simplified verification: check if any vaccination or aggregate matches
                    # In a real app, you'd store the aggregate export hashes separately
                    vax = session.exec(select(Vaccination).where(Vaccination.record_hash == hash_input.value)).first()
                    
                    if vax:
                        with results, ui.card().classes('w-full p-6 bg-green-50 border-green-200'):
                            with ui.row().classes('items-center gap-2 mb-2'):
                                ui.icon('verified', color='green')
                                ui.label('RECORD VERIFIED').classes('font-bold text-green-700')
                            ui.label(f"Vaccine: {vax.vaccine_name}")
                            ui.label(f"Pet ID: {vax.pet_id}")
                            ui.label(f"Date Given: {vax.date_given.date()}")
                            ui.label(f"Clinic: {vax.clinic_name}")
                    else:
                        with results, ui.card().classes('w-full p-6 bg-red-50 border-red-200'):
                            with ui.row().classes('items-center gap-2 mb-2'):
                                ui.icon('error', color='red')
                                ui.label('VERIFICATION FAILED').classes('font-bold text-red-700')
                            ui.label('The provided hash does not match any records in our ledger.')

            ui.button('Verify Record', on_click=verify).classes('w-full')
        nav_footer()

    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str):
        nav_header()
        with Session(engine) as session:
            pet = session.exec(select(Pet).where(Pet.id == uuid.UUID(pet_id))).first()
            if not pet:
                ui.label('Pet Not Found').classes('text-2xl text-red-500')
                return

            with ui.column().classes('w-full items-center p-8 max-w-6xl mx-auto'):
                ui.label(f'Identity Ledger: {pet.chip_id}').classes('text-3xl font-bold mb-8')
                
                with ui.row().classes('w-full gap-6 items-start'):
                    # Left Column: General Info & Shared Access
                    with ui.column().classes('w-1/3 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            ui.label('General Info').classes('text-xl font-bold border-b mb-4')
                            ui.label(f'Species: {pet.pet_species}')
                            ui.label(f'Breed: {pet.breed}')
                            ui.label(f'Manufacturer: {pet.manufacturer}')
                            ui.label(f'Status: {pet.identity_status}').classes('text-green-600' if pet.identity_status == 'VERIFIED' else 'text-yellow-600')
                            if pet.owner:
                                ui.label(f'Owner: {pet.owner.name}').classes('text-sm text-gray-600 mt-2')

                        with ui.card().classes('w-full p-6'):
                            ui.label('Managed Access').classes('text-xl font-bold border-b mb-4')
                            ui.label('Generate a time-bound care link for sitters/vets.').classes('text-xs text-gray-500 mb-4')
                            
                            async def create_link():
                                access = SharedAccess(pet_id=pet.id, expires_at=datetime.utcnow() + timedelta(hours=24))
                                session.add(access)
                                session.commit()
                                url = f"/shared/{access.token}"
                                with ui.dialog() as dialog, ui.card():
                                    ui.label('Shared Access Link Created').classes('font-bold')
                                    ui.label('Valid for 24 hours.').classes('text-xs')
                                    ui.input(value=url).classes('w-full mt-2').props('readonly outline')
                                    ui.button('Close', on_click=dialog.close).classes('mt-4')
                                dialog.open()
                            
                            ui.button('Create 24h Link', icon='share', on_click=create_link).classes('w-full').props('outline')

                    # Middle Column: Vaccination Ledger
                    with ui.column().classes('flex-1 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            with ui.row().classes('justify-between items-center w-full mb-4 border-b pb-2'):
                                ui.label('Vaccination Ledger').classes('text-xl font-bold')
                                
                                async def export_pdf():
                                    if not pet.vaccinations:
                                        ui.notify('No vaccinations to export.', type='warning')
                                        return
                                    aggregate_data = [v.dict(exclude={"id", "pet_id", "record_hash", "pet"}) for v in pet.vaccinations]
                                    export_hash = hash_service.hash_record({"pet_id": str(pet.id), "vaccinations": aggregate_data})
                                    path = pdf_service.generate_vaccination_report(pet.breed or "Pet", pet.vaccinations, export_hash)
                                    ui.download(path, f"{pet.breed}_vaccinations.pdf")

                                ui.button('Export Verified PDF', icon='download', on_click=export_pdf).props('flat color=primary small')

                            if not pet.vaccinations:
                                ui.label('No vaccinations recorded.').classes('italic text-gray-500')
                            else:
                                for v in pet.vaccinations:
                                    with ui.card().classes('w-full mb-2 p-3 bg-blue-50 border-none shadow-none'):
                                        with ui.row().classes('justify-between w-full'):
                                            with ui.column():
                                                ui.label(v.vaccine_name).classes('font-bold')
                                                ui.label(f"By {v.administering_vet} @ {v.clinic_name}").classes('text-xs text-gray-500')
                                            with ui.column().classes('items-end'):
                                                ui.label(f"Expires: {v.expiration_date.date()}").classes('text-xs font-bold text-blue-600')
                                                ui.label(f"Hash: {v.record_hash[:8]}...").classes('text-[10px] text-gray-400 font-mono')

                            with ui.expansion('Add Vaccination Record', icon='add').classes('w-full mt-4 border-t'):
                                v_name = ui.input('Vaccine Name (e.g. Rabies 3yr)').classes('w-full')
                                v_man = ui.input('Manufacturer').classes('w-full')
                                v_serial = ui.input('Serial #').classes('w-full')
                                v_lot = ui.input('Lot #').classes('w-full')
                                v_date = ui.input('Date Given (YYYY-MM-DD)').classes('w-full')
                                v_exp = ui.input('Expiration Date (YYYY-MM-DD)').classes('w-full')
                                v_vet = ui.input('Administering Vet').classes('w-full')
                                v_license = ui.input('Vet License #').classes('w-full')
                                v_clinic = ui.input('Clinic Name').classes('w-full')
                                v_phone = ui.input('Clinic Phone').classes('w-full')

                                async def save_vaccination():
                                    try:
                                        new_v = Vaccination(
                                            pet_id=pet.id,
                                            vaccine_name=v_name.value,
                                            manufacturer=v_man.value,
                                            serial_number=v_serial.value,
                                            lot_number=v_lot.value,
                                            date_given=datetime.strptime(v_date.value, '%Y-%m-%d'),
                                            expiration_date=datetime.strptime(v_exp.value, '%Y-%m-%d'),
                                            administering_vet=v_vet.value,
                                            vet_license=v_license.value,
                                            clinic_name=v_clinic.value,
                                            clinic_phone=v_phone.value
                                        )
                                        # Hash
                                        record_data = new_v.dict(exclude={"id", "pet_id", "record_hash", "pet"})
                                        new_v.record_hash = hash_service.hash_record(record_data)
                                        
                                        session.add(new_v)
                                        # Log event
                                        session.add(LedgerEvent(pet_id=pet.id, event_type="VACCINATION", description=f"Vaccination added: {v_name.value}"))
                                        session.commit()
                                        ui.notify('Vaccination record added to ledger!', type='positive')
                                        ui.navigate.to(f'/pet/{pet.id}')
                                    except Exception as e:
                                        ui.notify(f'Error: {str(e)}', type='negative')

                                ui.button('Commit to Ledger', on_click=save_vaccination).classes('w-full mt-2')

                    # Right Column: Audit Trail
                    with ui.column().classes('w-64 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            ui.label('Audit Trail').classes('text-xl font-bold border-b mb-4')
                            for event in sorted(pet.ledger_events, key=lambda x: x.timestamp, reverse=True):
                                with ui.column().classes('mb-3'):
                                    with ui.row().classes('justify-between w-full'):
                                        ui.label(event.event_type).classes('text-[10px] font-bold text-gray-400')
                                        ui.label(event.timestamp.strftime('%H:%M')).classes('text-[10px] text-gray-400')
                                    ui.label(event.description).classes('text-xs')
                            
                            if not pet.ledger_events:
                                ui.label('No events recorded.').classes('text-sm italic')

                ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/dashboard')).classes('mt-8').props('flat')
        nav_footer()

    @ui.page('/qr/{tag_id}')
    async def public_profile(tag_id: str):
        # Public profile doesn't need nav_header to keep it focused on emergency
        with Session(engine) as session:
            try:
                pet_uuid = uuid.UUID(tag_id)
            except ValueError:
                ui.label('Invalid QR Tag').classes('text-2xl text-red-500')
                return
                
            pet = session.exec(select(Pet).where(Pet.id == pet_uuid)).first()
            if not pet:
                 ui.label('Invalid Tag').classes('text-2xl text-red-500')
                 return
            
            # Log the scan
            event = LedgerEvent(pet_id=pet.id, event_type="EMERGENCY_SCAN", description="Public QR scan detected")
            session.add(event)
            session.commit()

            # Notify owner
            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_scan(pet.owner.email, pet.breed or "Pet")

            with ui.column().classes('w-full items-center p-8 bg-red-50 min-h-screen'):
                ui.icon('emergency', size='64px', color='red')
                ui.label('EMERGENCY PROFILE').classes('text-3xl font-black text-red-700')
                
                with ui.card().classes('w-full max-w-md p-6 mt-6 shadow-xl'):
                    ui.label(f'This {pet.pet_species} is registered with PawsLedger.').classes('text-center mb-4')
                    ui.label(f'Breed: {pet.breed}').classes('text-xl font-bold text-center')
                    ui.label(f'Chip ID: {pet.chip_id}').classes('text-sm text-gray-500 text-center mb-6')
                    
                    async def contact_owner():
                        if pet.owner and pet.owner.email:
                            await email_service.send_email(
                                pet.owner.email, 
                                f"URGENT: Someone found your pet ({pet.breed})", 
                                f"Hello,\n\nSomeone scanned the QR tag of your pet {pet.breed} and is trying to contact you.\n\nPlease check your phone/dashboard."
                            )
                            ui.notify('Owner has been notified!', type='positive')
                        else:
                            ui.notify('Owner contact info not available.', type='negative')

                    ui.button('CONTACT OWNER', icon='email', on_click=contact_owner).classes('w-full bg-green-600 text-white py-4 text-xl mb-4')
                    ui.label('Owner PII is hidden for privacy. Clicking the button above sends an instant alert to the owner.').classes('text-xs text-gray-500 text-center')
                
                ui.label('Information on this page is provided for emergency recovery only.').classes('text-xs text-gray-400 mt-8')
        nav_footer()
