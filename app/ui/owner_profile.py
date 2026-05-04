from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import User
from .header import nav_header
from .footer import nav_footer
from .common import try_restore_session


def init_owner_profile_page():
    @ui.page('/owner/profile')
    async def owner_profile(request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        nav_header()

        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == app.storage.user['email'])
            ).first()

            if not user:
                with ui.column().classes('w-full items-center p-8'):
                    ui.label('User not found.').style('color: var(--pl-primary)')
                nav_footer()
                return

            pet_count = len(user.pets)
            current_address = user.address or ''
            user_name = user.name
            user_email = user.email
            user_role = user.role
            user_id = user.id

        with ui.column().classes('w-full items-center p-8'):
            ui.label('Owner Profile').classes('pl-page-title mb-6')

            with ui.card().classes('w-full max-w-lg p-6'):
                ui.label('Profile Details').classes('pl-section-title mb-4')

                with ui.grid(columns=2).classes('w-full gap-y-3 gap-x-4'):
                    ui.label('Name').classes('pl-label')
                    ui.label(user_name)

                    ui.label('Email').classes('pl-label')
                    ui.label(user_email)

                    ui.label('Role').classes('pl-label')
                    ui.label(user_role)

                    ui.label('Registered Pets').classes('pl-label')
                    ui.label(str(pet_count))

                ui.separator().classes('my-4')

                ui.label('Address').classes('pl-subtitle mb-2')
                address_input = ui.textarea(
                    'Your address',
                    value=current_address,
                ).classes('w-full mb-4').props('outlined')

                async def save_address():
                    new_address = address_input.value.strip()
                    with Session(engine) as session:
                        user = session.get(User, user_id)
                        if not user:
                            ui.notify('User not found.', type='negative')
                            return
                        user.address = new_address
                        session.add(user)
                        session.commit()
                    ui.notify('Address updated successfully.', type='positive')

                ui.button('Save Address', on_click=save_address).classes('w-full pl-btn-primary')

            ui.button(
                'Back to Dashboard',
                icon='arrow_back',
                on_click=lambda: ui.navigate.to('/dashboard'),
            ).classes('mt-4').props('flat')

        nav_footer()
