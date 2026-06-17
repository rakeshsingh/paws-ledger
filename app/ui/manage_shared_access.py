"""Shared Access Management page — create and view shared care links for pets."""

import os
from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from uuid import UUID

from .dashboard_shell import dashboard_shell
from .common import try_restore_session
from ..database import engine
from ..models import Pet, User, SharedAccess, _utc_now


def init_shared_access_management_page() -> None:
    @ui.page('/shared-access')
    async def shared_access_management(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        user_id = app.storage.user.get('id', '')
        if not user_id:
            ui.navigate.to('/login')
            return

        with dashboard_shell(
            title='Share Access',
            breadcrumbs=[('Dashboard', '/dashboard')],
        ):
            # Fetch user's pets and active shared access records
            with Session(engine) as session:
                pets = session.exec(
                    select(Pet).where(Pet.owner_id == UUID(user_id))
                ).all()

                now = _utc_now()
                active_links = []
                for pet in pets:
                    links = session.exec(
                        select(SharedAccess)
                        .where(SharedAccess.pet_id == pet.id)
                        .where(SharedAccess.expires_at > now)
                    ).all()
                    for link in links:
                        active_links.append({
                            'pet_name': pet.name or 'Unnamed',
                            'token': link.token,
                            'created_at': link.created_at,
                            'expires_at': link.expires_at,
                            'access_count': link.access_count or 0,
                            'last_accessed_at': link.last_accessed_at,
                        })

            # No pets state
            if not pets:
                with ui.element('div').classes('w-full p-12 rounded-xl text-center').style(
                    'background: white; border-radius: 12px;'
                ):
                    ui.icon('pets').style(
                        'font-size: 48px; color: var(--pl-primary); opacity: 0.5;'
                    )
                    ui.label('No Pets Registered').style(
                        'font-size: 20px; font-weight: 700; color: var(--pl-on-surface); margin-top: 12px;'
                    )
                    ui.label(
                        'Register a pet first to create shared access links.'
                    ).style(
                        'font-size: 14px; color: var(--pl-on-surface-variant); margin-top: 4px;'
                    )
                    ui.button('Register Pet', icon='add', on_click=lambda: ui.navigate.to('/register')).props(
                        'no-caps'
                    ).style(
                        'background: var(--pl-primary); color: white; border-radius: 8px; margin-top: 16px;'
                    )
                return

            # ── Create New Shared Link Section ──
            with ui.element('div').classes('w-full p-6 md:p-8 rounded-xl mb-6').style(
                'background: white; border-radius: 12px;'
            ):
                with ui.row().classes('items-center gap-3 mb-6'):
                    ui.icon('add_link').style(
                        'font-size: 24px; color: var(--pl-primary);'
                    )
                    ui.label('Create Shared Access Link').style(
                        'font-size: 18px; font-weight: 700; color: var(--pl-on-surface);'
                    )

                ui.label(
                    'Generate a time-limited link to share your pet\'s care records '
                    'with vets, sitters, or family members.'
                ).style(
                    'font-size: 14px; color: var(--pl-on-surface-variant); margin-bottom: 16px;'
                )

                # Form row
                pet_options = {str(pet.id): (pet.name or 'Unnamed') for pet in pets}

                with ui.row().classes('w-full items-end gap-4 flex-wrap'):
                    pet_select = ui.select(
                        options=pet_options,
                        label='Select Pet',
                        value=str(pets[0].id) if pets else None,
                    ).props('outlined dense').classes('flex-1').style('min-width: 200px;')

                    hours_select = ui.select(
                        options={
                            '1': '1 hour',
                            '6': '6 hours',
                            '12': '12 hours',
                            '24': '24 hours (1 day)',
                            '48': '48 hours (2 days)',
                            '72': '72 hours (3 days)',
                            '168': '168 hours (7 days)',
                        },
                        label='Duration',
                        value='24',
                    ).props('outlined dense').classes('flex-1').style('min-width: 180px;')

                # Result container for showing the generated link
                result_container = ui.column().classes('w-full mt-4')

                async def create_link():
                    pet_id = pet_select.value
                    hours = int(hours_select.value)
                    if not pet_id:
                        ui.notify('Please select a pet', type='warning')
                        return

                    import httpx
                    base_url = f"http://localhost:{os.getenv('PORT', '8080')}"
                    cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}

                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(
                                f"{base_url}/api/v1/pets/{pet_id}/shared-access?hours={hours}",
                                cookies=cookies,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                token = data['access_url'].split('/shared/')[-1]
                                domain = os.getenv('APP_DOMAIN', 'www.pawsledger.com')
                                share_url = f"https://{domain}/shared/{token}"
                                expires_at = data['expires_at']

                                result_container.clear()
                                with result_container:
                                    with ui.element('div').classes('w-full p-4 rounded-lg').style(
                                        'background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px;'
                                    ):
                                        with ui.row().classes('items-center gap-2 mb-3'):
                                            ui.icon('check_circle').style(
                                                'font-size: 20px; color: #16a34a;'
                                            )
                                            ui.label('Link Created Successfully').style(
                                                'font-weight: 600; font-size: 14px; color: #166534;'
                                            )

                                        ui.label('Share this link:').style(
                                            'font-size: 12px; color: var(--pl-on-surface-variant); margin-bottom: 4px;'
                                        )

                                        with ui.row().classes('w-full items-center gap-2'):
                                            url_input = ui.input(value=share_url).props(
                                                'outlined dense readonly'
                                            ).classes('flex-1').style('font-family: monospace; font-size: 13px;')

                                            ui.button(
                                                icon='content_copy',
                                                on_click=lambda: (
                                                    ui.run_javascript(
                                                        f'navigator.clipboard.writeText("{share_url}")'
                                                    ),
                                                    ui.notify('Link copied to clipboard', type='positive'),
                                                ),
                                            ).props('flat dense').style('color: var(--pl-primary);')

                                        ui.label(f'Expires: {expires_at}').style(
                                            'font-size: 12px; color: var(--pl-on-surface-variant); margin-top: 8px;'
                                        )
                            else:
                                ui.notify(
                                    f'Failed to create link: {resp.json().get("detail", "Unknown error")}',
                                    type='negative',
                                )
                    except Exception as e:
                        ui.notify(f'Error creating link: {str(e)}', type='negative')

                ui.button(
                    'Generate Link', icon='link', on_click=create_link
                ).props('no-caps').style(
                    'background: var(--pl-primary); color: white; border-radius: 8px; margin-top: 16px;'
                )

            # ── Active Links Section ──
            with ui.element('div').classes('w-full p-6 md:p-8 rounded-xl').style(
                'background: white; border-radius: 12px;'
            ):
                with ui.row().classes('items-center gap-3 mb-6'):
                    ui.icon('link').style(
                        'font-size: 24px; color: var(--pl-primary);'
                    )
                    ui.label('Active Shared Links').style(
                        'font-size: 18px; font-weight: 700; color: var(--pl-on-surface);'
                    )

                if not active_links:
                    with ui.column().classes('w-full items-center py-8'):
                        ui.icon('link_off').style(
                            'font-size: 40px; color: var(--pl-text-hint); opacity: 0.5;'
                        )
                        ui.label('No active shared links').style(
                            'font-size: 14px; color: var(--pl-on-surface-variant); margin-top: 8px;'
                        )
                        ui.label(
                            'Create a link above to share pet care records with others.'
                        ).style(
                            'font-size: 13px; color: var(--pl-text-hint);'
                        )
                else:
                    for link in active_links:
                        domain = os.getenv('APP_DOMAIN', 'www.pawsledger.com')
                        link_url = f"https://{domain}/shared/{link['token']}"

                        with ui.element('div').classes('w-full p-4 rounded-lg mb-3').style(
                            'border: 1px solid #e7e5e4; border-radius: 12px;'
                        ):
                            with ui.row().classes('w-full items-center justify-between flex-wrap gap-2'):
                                # Left: pet name and dates
                                with ui.column().classes('gap-1'):
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('pets').style(
                                            'font-size: 16px; color: var(--pl-primary);'
                                        )
                                        ui.label(link['pet_name']).style(
                                            'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                                        )
                                    with ui.row().classes('items-center gap-4 flex-wrap'):
                                        ui.label(
                                            f"Created: {link['created_at'].strftime('%b %d, %Y %H:%M')}"
                                        ).style('font-size: 12px; color: var(--pl-on-surface-variant);')
                                        ui.label(
                                            f"Expires: {link['expires_at'].strftime('%b %d, %Y %H:%M')}"
                                        ).style('font-size: 12px; color: var(--pl-on-surface-variant);')
                                        if link['last_accessed_at']:
                                            ui.label(
                                                f"Last accessed: {link['last_accessed_at'].strftime('%b %d, %Y %H:%M')}"
                                            ).style('font-size: 12px; color: #16a34a;')
                                        else:
                                            ui.label(
                                                'Not yet accessed'
                                            ).style('font-size: 12px; color: var(--pl-text-hint); font-style: italic;')

                                # Right: access count and copy button
                                with ui.row().classes('items-center gap-3'):
                                    with ui.row().classes('items-center gap-1'):
                                        ui.icon('visibility').style(
                                            'font-size: 16px; color: var(--pl-text-hint);'
                                        )
                                        ui.label(str(link['access_count'])).style(
                                            'font-size: 13px; color: var(--pl-on-surface-variant);'
                                        )
                                    ui.button(
                                        icon='content_copy',
                                        on_click=lambda url=link_url: (
                                            ui.run_javascript(
                                                f'navigator.clipboard.writeText("{url}")'
                                            ),
                                            ui.notify('Link copied', type='positive'),
                                        ),
                                    ).props('flat dense round').style('color: var(--pl-primary);')
