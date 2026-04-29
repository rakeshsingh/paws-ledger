from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User, LedgerEvent
from ..services.integrations import get_manufacturer_from_chip, DogAPIClient, GoogleAuthService
import uuid

dog_client = DogAPIClient()
google_auth = GoogleAuthService()

COMMON_STYLE = """
<style>
    :root {
        --primary-color: #2563eb;
        --secondary-color: #f8fafc;
        --text-main: #1e293b;
        --text-light: #64748b;
        --border-color: #e2e8f0;
        --accent-warm: #f59e0b;
    }

    body {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background-color: var(--secondary-color);
        color: var(--text-main);
    }

    .logo {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--primary-color) !important;
        text-decoration: none;
    }

    .logo span {
        color: var(--text-light) !important;
    }

    footer {
        padding: 2rem;
        text-align: center;
        font-size: 0.875rem;
        color: var(--text-light);
        border-top: 1px solid var(--border-color);
        background: white;
        margin-top: auto;
    }
</style>
"""

def init_pages():
    ui.add_head_html(COMMON_STYLE)

    def nav_header():
        with ui.header().classes('bg-white text-primary border-b px-8 py-4 justify-between items-center').style('border-bottom: 1px solid var(--border-color)'):
            with ui.link(target='/').classes('logo'):
                ui.label('Paws').style('display: inline')
                ui.label('Ledger').style('display: inline; color: var(--text-light)')
            
            with ui.row().classes('gap-6 items-center').style('font-size: 0.9rem; color: var(--text-light)'):
                if app.storage.user.get('email'):
                    ui.link('Dashboard', '/dashboard').classes('text-inherit hover:text-primary')
                    ui.link('Logout', '/').on('click', lambda: app.storage.user.clear()).classes('text-primary font-bold')
                else:
                    ui.link('Dashboard', '/dashboard').classes('text-inherit hover:text-primary')
                    ui.link('Login / Register', '/login').classes('text-primary font-bold')

    def nav_footer():
        with ui.footer().classes('bg-white'):
             ui.html('&copy; 2026 PawsLedger &bull; A Trusted Pet Identity Store &bull; ISO 11784 Compliant')

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

    @ui.page('/login')
    async def login_page(request: Request):
        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            with ui.card().classes('w-full max-w-sm p-6 items-center'):
                ui.label('Welcome Back').classes('text-2xl font-bold mb-4')
                ui.label('Secure login for PawsLedger').classes('text-gray-500 mb-6 text-center')
                
                # Google Login Button
                async def login_google():
                    redirect_url = await google_auth.get_authorize_url(request)
                    ui.navigate.to(redirect_url)

                with ui.button(on_click=login_google) \
                    .classes('w-full bg-white text-gray-700 border border-gray-300 py-2 mb-4 flex items-center justify-center') \
                    .style('text-transform: none; font-weight: 500'):
                    ui.html('<img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_Logo.svg" style="width: 18px; margin-right: 12px;">')
                    ui.label('Sign in with Google')

                ui.separator().classes('mb-4')
                ui.label('Authorized Identity Provider Only').classes('text-xs text-gray-400')
        nav_footer()

    @ui.page('/auth/callback')
    async def auth_callback(request: Request):
        try:
            token = await google_auth.authorize_access_token(request)
            user_info = await google_auth.get_user_info(token)
            
            sub = user_info["sub"]
            email = user_info["email"]
            name = user_info.get("name", email)
            
            with Session(engine) as session:
                # Try finding by sub first (immutable anchor)
                statement = select(User).where(User.sub == sub)
                user = session.exec(statement).first()
                
                if not user:
                    # Fallback to email for migration/linking if necessary
                    statement = select(User).where(User.email == email)
                    user = session.exec(statement).first()
                    
                    if user:
                        user.sub = sub # Link existing user
                    else:
                        user = User(sub=sub, email=email, name=name)
                        session.add(user)
                    
                    session.commit()
                    session.refresh(user)
                
                app.storage.user.update({
                    'email': user.email,
                    'name': user.name,
                    'id': str(user.id)
                })
            
            ui.notify(f'Welcome, {user.name}!', type='positive')
            ui.navigate.to('/dashboard')
        except Exception as e:
            ui.notify(f'Authentication error: {str(e)}', type='negative')
            ui.navigate.to('/login')

    @ui.page('/dashboard')
    async def dashboard():
        if not app.storage.user.get('email'):
            ui.navigate.to('/login')
            return
        
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
                chip_id = ui.input('Chip ID (15 digits)').classes('w-full mb-4')
                breed = ui.select(breed_options, label='Breed', with_filter=True).classes('w-full mb-4')
                species = ui.select(['DOG', 'CAT'], label='Species', value='DOG').classes('w-full mb-4')
                
                async def submit():
                    if not chip_id.value or len(chip_id.value) != 15:
                        ui.notify('Invalid Chip ID. Must be 15 digits.', type='negative')
                        return
                    
                    manufacturer = get_manufacturer_from_chip(chip_id.value)
                    
                    with Session(engine) as session:
                        user = session.exec(select(User).where(User.email == app.storage.user['email'])).first()
                        new_pet = Pet(
                            chip_id=chip_id.value,
                            breed=breed.value,
                            pet_species=species.value,
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

    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str):
        nav_header()
        with Session(engine) as session:
            pet = session.get(Pet, uuid.UUID(pet_id))
            if not pet:
                ui.label('Pet Not Found').classes('text-2xl text-red-500')
                return

            with ui.column().classes('w-full items-center p-8'):
                ui.label(f'Identity Ledger: {pet.chip_id}').classes('text-3xl font-bold')
                
                with ui.row().classes('gap-4 mt-6'):
                    with ui.card().classes('p-4 w-64'):
                        ui.label('General Info').classes('font-bold border-b mb-2')
                        ui.label(f'Species: {pet.pet_species}')
                        ui.label(f'Breed: {pet.breed}')
                        ui.label(f'Manufacturer: {pet.manufacturer}')
                        ui.label(f'Status: {pet.identity_status}').classes('text-green-600' if pet.identity_status == 'VERIFIED' else 'text-yellow-600')
                        if pet.owner:
                            ui.label(f'Owner: {pet.owner.name}').classes('text-sm text-gray-600 mt-2')

                    with ui.card().classes('p-4 w-80'):
                        ui.label('Ledger Events').classes('font-bold border-b mb-2')
                        for event in pet.ledger_events:
                            with ui.row().classes('justify-between w-full'):
                                ui.label(event.event_type).classes('text-xs font-mono')
                                ui.label(event.timestamp.strftime('%Y-%m-%d')).classes('text-xs text-gray-400')
                            ui.label(event.description).classes('text-sm mb-2')
                        
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
                
            pet = session.get(Pet, pet_uuid)
            if not pet:
                 ui.label('Invalid Tag').classes('text-2xl text-red-500')
                 return
            
            # Log the scan
            event = LedgerEvent(pet_id=pet.id, event_type="EMERGENCY_SCAN", description="Public QR scan detected")
            session.add(event)
            session.commit()

            with ui.column().classes('w-full items-center p-8 bg-red-50 min-h-screen'):
                ui.icon('emergency', size='64px', color='red')
                ui.label('EMERGENCY PROFILE').classes('text-3xl font-black text-red-700')
                
                with ui.card().classes('w-full max-w-md p-6 mt-6 shadow-xl'):
                    ui.label(f'This {pet.pet_species} is registered with PawsLedger.').classes('text-center mb-4')
                    ui.label(f'Breed: {pet.breed}').classes('text-xl font-bold text-center')
                    ui.label(f'Chip ID: {pet.chip_id}').classes('text-sm text-gray-500 text-center mb-6')
                    
                    ui.button('CALL OWNER', icon='phone').classes('w-full bg-green-600 text-white py-4 text-xl mb-4')
                    ui.button('NOTIFY VET', icon='local_hospital', color='secondary').classes('w-full')
                
                ui.label('Information on this page is provided for emergency recovery only.').classes('text-xs text-gray-400 mt-8')
        nav_footer()
