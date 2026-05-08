from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import User, Pet
from .header import nav_header
from .footer import nav_footer
from .common import try_restore_session

# Placeholder pet images keyed by species
PET_IMAGES = {
    'DOG': 'https://lh3.googleusercontent.com/aida-public/AB6AXuAXUZaZI5GrWaLYxj2lznTVqxqJ3FOZHoSfjx6jAffHDaq3HscRjX3zXbIQR7UnQMNS9HWCqnpLfpzIMNTRONTXVWObGNjBDD1z21wnT2xykSzl13S1Md_Bai95kLvJHOW8MbJRxqMzIqMvAn5S-lpJA0_bAHCoIFcYC-QuUCHYGwNSrmCjUjvntkBMZN02Uxy3QVUm2B0_2H9OpGJJUihxS4h64hi5uBbiwvmS-gBvx45Wuk16KJKeUezJtKTWB5ENuRPlCi8jAm1f',
    'CAT': 'https://lh3.googleusercontent.com/aida-public/AB6AXuCPTH8vESvvcGO9mILxsC4a8w1o5z4iSLguhf7VqSYvtF6CT8WPnNE1vyADGkm8OqBw-hUubvMY1CIK2LYqOKY1sg1DtR5nCOPa_k4YbmTjnu345GZ00J876zQsD2p8QFZeRlzfvrl58VuC-6GnyrjHItxbtRvXzCFr41UwlFlMo02mdSd2lblevkaTyhxEW6fRGShq4SvldBVW18kJQVvW79_xYP3AGAPdeVmGT3X7onRq24rZTkWmxZAPx4hSyRhPz_7JmqPd5RYR',
}


def _build_profile_header(user_name: str, user_role: str, pet_count: int):
    """Profile header section with avatar, name, role, and badges."""
    with ui.element('section').classes(
        'flex flex-col md:flex-row items-center gap-8 mb-12 p-10 rounded-xl'
    ).style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
        'border-left: 4px solid #a03a21;'
    ):
        # Unisex avatar icon
        with ui.element('div').classes('relative'):
            with ui.element('div').classes(
                'flex items-center justify-center rounded-full'
            ).style(
                'width: 128px; height: 128px; background: #ffdad2; '
                'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
            ):
                ui.icon('person').style('font-size: 64px; color: #a03a21;')

        # Name and info
        with ui.column().classes('text-center md:text-left gap-1'):
            ui.label(user_name).style(
                "font-family: 'Plus Jakarta Sans', sans-serif; font-size: 40px; "
                "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; color: #171c21;"
            )
            ui.label(f'{user_role} • Pet Owner').style(
                'color: #57423d; font-size: 18px; line-height: 1.6;'
            )
            with ui.row().classes('gap-2 mt-3 justify-center md:justify-start'):
                ui.label('Account Active').style(
                    'padding: 4px 12px; background: #dcfce7; color: #166534; '
                    'font-size: 12px; font-weight: 500; border-radius: 9999px;'
                )
                ui.label(f'{pet_count} Registered Pet{"s" if pet_count != 1 else ""}').style(
                    'padding: 4px 12px; background: #f5f5f4; color: #57423d; '
                    'font-size: 12px; font-weight: 500; border-radius: 9999px;'
                )


def _build_sidebar(pets):
    """Sidebar with privacy info and active pets list."""
    with ui.column().classes('gap-6').style('width: 100%;'):
        # Privacy card
        with ui.element('div').classes('p-6 rounded-xl').style('background: #f0f4fb;'):
            with ui.row().classes('items-center gap-2 mb-4'):
                ui.icon('security').style('font-size: 24px; color: #a03a21;')
                ui.label('Privacy').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #171c21;"
                )
            ui.label(
                'Your personal information is encrypted and only used for medical coordination.'
            ).style('color: #57423d; font-size: 16px; line-height: 1.5; margin-bottom: 1rem;')
            ui.link('Learn more about security', '/faq').style(
                'color: #a03a21; font-weight: 600; font-size: 14px;'
            )

        # Active pets card
        with ui.element('div').classes('p-6 rounded-xl').style('background: #ffdad2;'):
            with ui.row().classes('items-center gap-2 mb-4'):
                ui.icon('pets').style('font-size: 24px; color: #3c0700;')
                ui.label('Active Pets').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #3c0700;"
                )
            if pets:
                with ui.row().classes('items-center'):
                    shown = pets[:3]
                    for pet in shown:
                        img_url = PET_IMAGES.get(pet.pet_species, PET_IMAGES['DOG'])
                        ui.image(img_url).classes('rounded-full').style(
                            'width: 40px; height: 40px; object-fit: cover; '
                            'border: 2px solid white; margin-right: -8px;'
                        )
                    remaining = len(pets) - len(shown)
                    if remaining > 0:
                        ui.element('div').classes(
                            'flex items-center justify-center rounded-full'
                        ).style(
                            'width: 40px; height: 40px; background: #e7e5e4; '
                            'border: 2px solid white; font-size: 12px; font-weight: 700; '
                            'color: #57423d;'
                        ).text = f'+{remaining}'
            else:
                ui.label('No pets registered yet.').style(
                    'color: #57423d; font-style: italic; font-size: 14px;'
                )


def _build_view_mode(user_name, user_email, user_phone, user_address, user_city, user_country, on_edit):
    """Read-only profile view matching the form layout."""
    with ui.element('div').classes('p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
    ):
        with ui.row().classes('w-full justify-between items-center mb-6'):
            ui.label('Profile Details').style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )
            ui.button('Edit Profile', icon='edit', on_click=on_edit).props(
                'flat no-caps'
            ).style('color: #a03a21; font-weight: 600;')

        # Name row
        name_parts = user_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        with ui.row().classes('w-full gap-6 mb-5'):
            with ui.column().classes('flex-1 gap-1'):
                ui.label('First Name').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                ui.label(first_name or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')
            with ui.column().classes('flex-1 gap-1'):
                ui.label('Last Name').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                ui.label(last_name or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')

        # Email
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Email Address').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            ui.label(user_email or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
            ).classes('w-full')

        # Phone
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Phone Number').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            ui.label(user_phone or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
            ).classes('w-full')

        # Address
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Address').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            ui.label(user_address or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4; '
                'min-height: 80px; white-space: pre-wrap;'
            ).classes('w-full')

        # City / Country
        with ui.row().classes('w-full gap-6'):
            with ui.column().classes('flex-1 gap-1'):
                ui.label('City').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                ui.label(user_city or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')
            with ui.column().classes('flex-1 gap-1'):
                ui.label('Country').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                ui.label(user_country or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')


def _build_edit_mode(user_name, user_email, user_phone, user_address, user_city, user_country, user_id, on_cancel, content_container):
    """Editable profile form matching the HTML template layout."""
    name_parts = user_name.split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ''

    with ui.element('div').classes('p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
    ):
        ui.label('Edit Profile').style(
            "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
            "font-weight: 600; color: #171c21; margin-bottom: 1.5rem;"
        )

        # Name row
        with ui.row().classes('w-full gap-6 mb-5'):
            with ui.column().classes('flex-1 gap-1'):
                ui.label('First Name').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                first_input = ui.input(
                    placeholder='Enter first name', value=first_name
                ).classes('w-full').props('outlined dense')
            with ui.column().classes('flex-1 gap-1'):
                ui.label('Last Name').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                last_input = ui.input(
                    placeholder='Enter last name', value=last_name
                ).classes('w-full').props('outlined dense')

        # Email
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Email Address').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            email_input = ui.input(
                placeholder='name@example.com', value=user_email
            ).classes('w-full').props('outlined dense')

        # Phone
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Phone Number').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            phone_input = ui.input(
                placeholder='+1 (000) 000-0000', value=user_phone
            ).classes('w-full').props('outlined dense')

        # Address
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Address').style(
                'font-weight: 600; font-size: 14px; color: #171c21;'
            )
            address_input = ui.textarea(
                placeholder='Enter your full address', value=user_address
            ).classes('w-full').props('outlined rows=3')

        # City / Country
        with ui.row().classes('w-full gap-6 mb-6'):
            with ui.column().classes('flex-1 gap-1'):
                ui.label('City').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                city_input = ui.input(
                    placeholder='e.g. Portland', value=user_city
                ).classes('w-full').props('outlined dense')
            with ui.column().classes('flex-1 gap-1'):
                ui.label('Country').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                country_input = ui.input(
                    placeholder='e.g. United States', value=user_country
                ).classes('w-full').props('outlined dense')

        # Divider and action buttons
        ui.separator().style('border-color: #f5f5f4;')
        with ui.row().classes(
            'w-full justify-between items-center mt-6'
        ):
            ui.label('').style('color: #57423d; font-size: 12px;')
            with ui.row().classes('gap-4'):
                ui.button('Cancel', on_click=on_cancel).style(
                    'background: #f5f5f4; color: #57423d; border: 1px solid #e7e5e4; '
                    'font-weight: 600; border-radius: 9999px; padding: 8px 32px;'
                ).props('flat no-caps')

                async def save_profile():
                    new_first = first_input.value.strip()
                    new_last = last_input.value.strip()
                    full_name = f'{new_first} {new_last}'.strip()
                    new_email = email_input.value.strip()
                    new_phone = phone_input.value.strip()
                    new_address = address_input.value.strip()
                    new_city = city_input.value.strip()
                    new_country = country_input.value.strip()

                    if not full_name:
                        ui.notify('Name is required.', type='warning')
                        return
                    if not new_email:
                        ui.notify('Email is required.', type='warning')
                        return

                    with Session(engine) as session:
                        user = session.get(User, user_id)
                        if not user:
                            ui.notify('User not found.', type='negative')
                            return
                        user.name = full_name
                        user.email = new_email
                        user.phone = new_phone
                        user.address = new_address
                        user.city = new_city
                        user.country = new_country
                        session.add(user)
                        session.commit()
                        session.refresh(user)

                        # Update session storage
                        app.storage.user['name'] = user.name
                        app.storage.user['email'] = user.email

                    ui.notify('Profile updated successfully.', type='positive')
                    # Rebuild as view mode
                    _rebuild_content(
                        content_container, full_name, new_email, new_phone,
                        new_address, new_city, new_country, user_id, mode='view',
                    )

                ui.button('Save Changes', on_click=save_profile).style(
                    'background: #a03a21; color: white; font-weight: 600; '
                    'border-radius: 9999px; padding: 8px 32px; '
                    'box-shadow: 0 4px 12px rgba(160,58,33,0.2);'
                ).props('no-caps')


def _rebuild_content(container, name, email, phone, address, city, country, user_id, mode='view'):
    """Clear and rebuild the main form area in the given mode."""
    container.clear()
    with container:
        if mode == 'edit':
            _build_edit_mode(
                name, email, phone, address, city, country, user_id,
                on_cancel=lambda: _rebuild_content(
                    container, name, email, phone, address, city, country, user_id, mode='view',
                ),
                content_container=container,
            )
        else:
            _build_view_mode(
                name, email, phone, address, city, country,
                on_edit=lambda: _rebuild_content(
                    container, name, email, phone, address, city, country, user_id, mode='edit',
                ),
            )


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
                    ui.label('User not found.').style('color: #a03a21;')
                nav_footer()
                return

            pets = session.exec(select(Pet).where(Pet.owner_id == user.id)).all()
            pet_count = len(pets)
            user_name = user.name
            user_email = user.email
            user_phone = user.phone or ''
            user_address = user.address or ''
            user_city = user.city or ''
            user_country = user.country or ''
            user_role = user.role
            user_id = user.id
            # Detach pet data for sidebar
            pet_data = [(p.pet_species, p.name) for p in pets]

        # ── Main content area ──
        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
            # Profile header
            _build_profile_header(user_name, user_role, pet_count)

            # Two-column layout: sidebar + form
            with ui.row().classes('w-full gap-8 items-start'):
                # Sidebar (1/3)
                with ui.column().classes('gap-6').style('width: 280px; flex-shrink: 0;'):
                    _build_sidebar(pets)

                # Main form area (2/3)
                form_container = ui.column().classes('flex-1 gap-6').style('min-width: 0;')
                with form_container:
                    _build_view_mode(
                        user_name, user_email, user_phone, user_address,
                        user_city, user_country,
                        on_edit=lambda: _rebuild_content(
                            form_container, user_name, user_email, user_phone,
                            user_address, user_city, user_country, user_id, mode='edit',
                        ),
                    )

            # Back to dashboard
            ui.button(
                'Back to Dashboard', icon='arrow_back',
                on_click=lambda: ui.navigate.to('/dashboard'),
            ).classes('mt-8').props('flat no-caps').style(
                'color: #57423d; font-weight: 600;'
            )

        nav_footer()
