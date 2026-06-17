from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import User, _utc_now
from .dashboard_shell import dashboard_shell
from .common import try_restore_session, sanitize


def _build_view_mode(user_name, user_email, user_phone, user_address, user_city, user_country, on_edit):
    """Read-only profile view matching the form layout."""
    with ui.element('div').classes('p-4 md:p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
    ):
        with ui.row().classes('w-full justify-between items-center mb-6'):
            ui.label('Profile Details').classes('pl-heading-xl')
            ui.button('Edit Profile', icon='edit', on_click=on_edit).props(
                'flat no-caps'
            ).style('color: var(--pl-primary); font-weight: 600;')

        # Name row
        name_parts = user_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        with ui.element('div').classes('two-col-responsive w-full mb-5'):
            with ui.column().classes('gap-1'):
                ui.label('First Name').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                ui.label(first_name or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')
            with ui.column().classes('gap-1'):
                ui.label('Last Name').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                ui.label(last_name or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')

        # Email
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Email Address').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            ui.label(user_email or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4; '
                'word-break: break-all;'
            ).classes('w-full')

        # Phone
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Phone Number').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            ui.label(user_phone or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
            ).classes('w-full')

        # Address
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Address').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            ui.label(user_address or '—').style(
                'font-size: 16px; color: #57423d; padding: 12px 16px; '
                'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4; '
                'min-height: 80px; white-space: pre-wrap;'
            ).classes('w-full')

        # City / Country
        with ui.element('div').classes('two-col-responsive w-full'):
            with ui.column().classes('gap-1'):
                ui.label('City').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                ui.label(user_city or '—').style(
                    'font-size: 16px; color: #57423d; padding: 12px 16px; '
                    'background: #f7f9ff; border-radius: 8px; border: 1px solid #e7e5e4;'
                ).classes('w-full')
            with ui.column().classes('gap-1'):
                ui.label('Country').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
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

    with ui.element('div').classes('p-4 md:p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
    ):
        ui.label('Edit Profile').classes('pl-heading-xl').style(
            'margin-bottom: 1.5rem;'
        )

        # Name row
        with ui.element('div').classes('two-col-responsive w-full mb-5'):
            with ui.column().classes('gap-1'):
                ui.label('First Name').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                first_input = ui.input(
                    placeholder='Enter first name', value=first_name
                ).classes('w-full').props('outlined dense')
            with ui.column().classes('gap-1'):
                ui.label('Last Name').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                last_input = ui.input(
                    placeholder='Enter last name', value=last_name
                ).classes('w-full').props('outlined dense')

        # Email
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Email Address').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            email_input = ui.input(
                placeholder='name@example.com', value=user_email
            ).classes('w-full').props('outlined dense')

        # Phone
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Phone Number').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            phone_input = ui.input(
                placeholder='+1 (000) 000-0000', value=user_phone
            ).classes('w-full').props('outlined dense')

        # Address
        with ui.column().classes('w-full gap-1 mb-5'):
            ui.label('Address').style(
                'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
            )
            address_input = ui.textarea(
                placeholder='Enter your full address', value=user_address
            ).classes('w-full').props('outlined rows=3')

        # City / Country
        with ui.element('div').classes('two-col-responsive w-full mb-6'):
            with ui.column().classes('gap-1'):
                ui.label('City').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                city_input = ui.input(
                    placeholder='e.g. Portland', value=user_city
                ).classes('w-full').props('outlined dense')
            with ui.column().classes('gap-1'):
                ui.label('Country').style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                )
                country_input = ui.input(
                    placeholder='e.g. United States', value=user_country
                ).classes('w-full').props('outlined dense')

        # Divider and action buttons
        ui.separator().style('border-color: #f5f5f4;')
        with ui.row().classes(
            'w-full justify-end items-center mt-6 flex-wrap gap-3'
        ):
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
                    if not new_email or '@' not in new_email:
                        ui.notify('A valid email is required.', type='warning')
                        return

                    with Session(engine) as session:
                        user = session.get(User, user_id)
                        if not user:
                            ui.notify('User not found.', type='negative')
                            return

                        # Check email uniqueness if changed
                        if new_email != user.email:
                            existing = session.exec(
                                select(User).where(User.email == new_email)
                            ).first()
                            if existing:
                                ui.notify('Email already in use.', type='negative')
                                return

                        user.name = sanitize(full_name)
                        user.email = new_email
                        user.phone = new_phone
                        user.address = sanitize(new_address)
                        user.city = sanitize(new_city)
                        user.country = sanitize(new_country)
                        user.profile_updated_at = _utc_now()
                        session.add(user)
                        session.commit()
                        session.refresh(user)

                        # Update session storage
                        app.storage.user['name'] = user.name
                        app.storage.user['email'] = user.email

                    ui.notify('Profile updated successfully.', type='positive')
                    # Rebuild as view mode
                    _rebuild_content(
                        content_container, user.name, new_email, new_phone,
                        user.address or '', user.city or '', user.country or '',
                        user_id, mode='view',
                    )

                ui.button('Save Changes', on_click=save_profile).style(
                    'background: var(--pl-primary); color: white; font-weight: 600; '
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


def init_owner_profile_page() -> None:
    @ui.page('/owner/profile')
    async def owner_profile(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == app.storage.user['email'])
            ).first()

            if not user:
                with dashboard_shell(title='Profile', breadcrumbs=[('Dashboard', '/dashboard')]):
                    ui.label('User not found.').style('color: var(--pl-primary);')
                return

            user_name = user.name
            user_email = user.email
            user_phone = user.phone or ''
            user_address = user.address or ''
            user_city = user.city or ''
            user_country = user.country or ''
            user_id = user.id

        with dashboard_shell(title='Profile', breadcrumbs=[('Dashboard', '/dashboard')]):
            # Profile details form (full width)
            form_container = ui.column().classes('w-full gap-6')
            with form_container:
                _build_view_mode(
                    user_name, user_email, user_phone, user_address,
                    user_city, user_country,
                    on_edit=lambda: _rebuild_content(
                        form_container, user_name, user_email, user_phone,
                        user_address, user_city, user_country, user_id, mode='edit',
                    ),
                )

            # Privacy notice
            with ui.element('div').classes('p-5 rounded-xl mt-8').style(
                'background: var(--pl-surface-info);'
            ):
                with ui.row().classes('items-center gap-2 mb-2'):
                    ui.icon('security').style('font-size: 20px; color: var(--pl-primary);')
                    ui.label('Privacy & Security').style('font-weight: 600; font-size: 14px;')
                ui.label(
                    'Your personal information is encrypted and only used for medical coordination. '
                    'We never share your data with third parties.'
                ).style('font-size: 13px; color: var(--pl-on-surface-variant); line-height: 1.5;')
                ui.link('Learn more about our security practices', '/faq').style(
                    'color: var(--pl-primary); font-weight: 600; font-size: 12px; '
                    'margin-top: 8px; display: inline-block;'
                )
