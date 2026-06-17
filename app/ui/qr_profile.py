from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, PetTag, LedgerEvent, _utc_now
from .header import nav_header
from .footer import nav_footer
from .common import email_service, try_restore_session
from .pet_profile import _render_nudge_form
import os
import uuid


def init_qr_profile_page() -> None:
    @ui.page('/qr/tag/{tag_code}')
    async def qr_tag_redirect(tag_code: str) -> None:
        """Redirect /qr/tag/{code} (URL on physical tags) to /qr/{code}."""
        ui.navigate.to(f'/qr/{tag_code}')

    @ui.page('/qr/{tag_id}')
    async def public_profile(request: Request, tag_id: str) -> None:
        try_restore_session(request)
        nav_header()

        with Session(engine) as session:
            pet = None
            tag_code = None

            tag = session.exec(
                select(PetTag).where(PetTag.tag_code == tag_id)
            ).first()
            if tag and tag.status == "ACTIVE":
                pet = tag.pet
                tag_code = tag.tag_code
            else:
                try:
                    pet_uuid = uuid.UUID(tag_id)
                    pet = session.exec(
                        select(Pet).where(Pet.id == pet_uuid)
                    ).first()
                except ValueError:
                    pass

            if not pet:
                with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                    with ui.column().classes('w-full items-center p-16'):
                        ui.icon('search_off').style(
                            'font-size: 64px; color: var(--pl-primary); opacity: 0.5;'
                        )
                        ui.label('Tag Not Found').classes('pl-heading-2xl').style(
                            'margin-top: 1rem;'
                        )
                        ui.label(
                            'This tag is invalid, deactivated, or not linked to a pet.'
                        ).classes('pl-body-base').style('margin-top: 0.5rem;')
                        ui.button(
                            'Search by Chip ID', icon='search',
                            on_click=lambda: ui.navigate.to('/'),
                        ).classes('mt-6').style(
                            'background: var(--pl-primary); color: white; font-weight: 600; '
                            'padding: 10px 24px; border-radius: 8px;'
                        ).props('no-caps')
                nav_footer()
                return

            # Inject geolocation script — submits scan with location to API
            _inject_geolocation_scan(tag_code or tag_id)

            with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                # Emergency alert banner
                with ui.row().classes(
                    'w-full items-center gap-4 p-5 rounded-xl mb-8'
                ).style(
                    'background: var(--pl-surface-warning); border: 1px solid rgba(251,191,36,0.2);'
                ):
                    ui.icon('notification_important').style(
                        'font-size: 32px; color: var(--pl-accent);'
                    )
                    with ui.column().classes('gap-1'):
                        ui.label('This Pet is Registered on PawsLedger').classes(
                            'pl-heading-lg'
                        ).style('color: var(--pl-accent);')
                        ui.label(
                            'The owner has been notified of this scan. '
                            'Use the form below to send them a message.'
                        ).classes('pl-body-sm')

                # Location status indicator (updated by JS)
                with ui.row().classes(
                    'w-full items-center gap-3 p-4 rounded-xl mb-6'
                ).style(
                    'background: var(--pl-surface-info); border: 1px solid rgba(222,192,185,0.3);'
                ).props('id="location-status-card"'):
                    ui.icon('location_on').style(
                        'font-size: 20px; color: #3b82f6;'
                    ).props('id="location-icon"')
                    with ui.column().classes('gap-0'):
                        ui.label('Acquiring location...').style(
                            'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                        ).props('id="location-label"')
                        ui.label('Sharing your location helps reunite this pet with its owner.').style(
                            'font-size: var(--pl-text-xs); color: var(--pl-text-hint);'
                        ).props('id="location-sublabel"')

                # Pet identification card
                with ui.element('div').classes('w-full p-8 rounded-xl mb-6').style(
                    'background: var(--pl-surface); box-shadow: var(--pl-shadow-md); '
                    'border-left: 4px solid var(--pl-primary);'
                ):
                    with ui.row().classes('gap-8 items-center'):
                        species = pet.pet_species or 'DOG'
                        icon_name = 'pets' if species == 'DOG' else 'emoji_nature'
                        bg = 'var(--pl-primary-light)' if species == 'DOG' else '#ffdea9'
                        fg = 'var(--pl-primary)' if species == 'DOG' else 'var(--pl-secondary)'
                        with ui.element('div').classes(
                            'flex items-center justify-center rounded-full flex-shrink-0'
                        ).style(
                            f'width: 96px; height: 96px; background: {bg}; '
                            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
                        ):
                            ui.icon(icon_name).style(f'font-size: 48px; color: {fg};')

                        with ui.column().classes('gap-2'):
                            with ui.row().classes('items-center gap-3'):
                                ui.label(f'{pet.pet_species}').classes(
                                    'pl-heading-2xl'
                                )
                                ui.label('Registered').style(
                                    'padding: 4px 12px; background: #dcfce7; color: #166534; '
                                    'font-size: 12px; font-weight: 600; border-radius: 9999px;'
                                )
                            ui.label(
                                f'Breed: {pet.breed or "Unknown"}'
                            ).style('font-size: 16px; color: var(--pl-on-surface-variant);')
                            ui.label(f'Chip ID: {pet.chip_id}').classes(
                                'pl-body-sm'
                            ).style('font-family: monospace;')
                            if pet.manufacturer:
                                ui.label(
                                    f'Manufacturer: {pet.manufacturer}'
                                ).style('font-size: 13px; color: var(--pl-text-hint);')

                # Medical info
                if pet.vaccinations or pet.medical_conditions:
                    with ui.element('div').classes('w-full p-8 rounded-xl mb-6').style(
                        'background: var(--pl-surface); box-shadow: var(--pl-shadow-md); '
                        'border-left: 4px solid #3b82f6;'
                    ):
                        ui.label('Medical Summary').classes(
                            'pl-heading-lg'
                        ).style('margin-bottom: 1rem;')

                        if pet.medical_conditions:
                            with ui.row().classes(
                                'w-full items-center gap-3 p-4 rounded-lg mb-4'
                            ).style('background: #fef2f2; border: 1px solid #fecaca;'):
                                ui.icon('priority_high').style(
                                    'font-size: 20px; color: #dc2626;'
                                )
                                ui.label(f'Medical Alert: {pet.medical_conditions}').style(
                                    'font-weight: 600; font-size: 14px; color: #b91c1c;'
                                )

                        if pet.vaccinations:
                            for v in pet.vaccinations:
                                is_current = v.expiration_date > _utc_now()
                                with ui.row().classes(
                                    'w-full items-center justify-between p-3 rounded-lg mb-2'
                                ).style('background: #f0f4fb;'):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.icon('vaccines').style(
                                            'font-size: 18px; color: #3b82f6;'
                                        )
                                        ui.label(v.vaccine_name).style(
                                            'font-weight: 500; font-size: 14px;'
                                        )
                                    status_label = 'Current' if is_current else 'Expired'
                                    status_color = '#16a34a' if is_current else '#dc2626'
                                    ui.label(status_label).style(
                                        f'font-weight: 600; font-size: 13px; color: {status_color};'
                                    )

                # Nudge form
                with ui.element('div').classes('w-full p-8 rounded-xl').style(
                    'background: var(--pl-surface); box-shadow: var(--pl-shadow-md); '
                    'border-left: 4px solid var(--pl-secondary);'
                ):
                    ui.label('Contact the Owner').classes(
                        'pl-heading-lg'
                    ).style('margin-bottom: 1rem;')
                    _render_nudge_form(pet)

                # Disclaimer
                with ui.row().classes(
                    'w-full items-center gap-2 mt-8 pt-6'
                ).style('border-top: 1px solid #e7e5e4;'):
                    ui.icon('info').style('font-size: 16px; color: var(--pl-text-hint);')
                    ui.label(
                        'Information on this page is provided for emergency recovery only.'
                    ).classes('pl-body-xs')

        nav_footer()


def _inject_geolocation_scan(tag_code: str):
    """Inject JavaScript to request browser geolocation and submit scan to API."""
    import json
    safe_tag = json.dumps(tag_code)
    ui.run_javascript(f'''
        (function() {{
            var tagCode = {safe_tag};
            var label = document.getElementById("location-label");
            var sublabel = document.getElementById("location-sublabel");
            var icon = document.getElementById("location-icon");
            var card = document.getElementById("location-status-card");

            function sendScan(lat, lon, accuracy) {{
                var body = {{scan_method: "QR"}};
                if (lat !== null) {{
                    body.latitude = lat;
                    body.longitude = lon;
                    body.accuracy_meters = accuracy;
                }}
                fetch("/api/v1/scan/" + encodeURIComponent(tagCode), {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify(body),
                }}).then(function(resp) {{
                    return resp.json();
                }}).then(function(data) {{
                    if (data.city || data.country) {{
                        var loc = [data.city, data.country].filter(Boolean).join(", ");
                        if (label) label.textContent = "Location shared: " + loc;
                        if (sublabel) sublabel.textContent = "The owner can see where their pet was scanned.";
                        if (icon) icon.textContent = "check_circle";
                        if (icon) icon.style.color = "#16a34a";
                    }} else if (data.location_recorded) {{
                        if (label) label.textContent = "Location shared";
                        if (sublabel) sublabel.textContent = "Coordinates recorded. The owner has been notified.";
                        if (icon) icon.textContent = "check_circle";
                        if (icon) icon.style.color = "#16a34a";
                    }}
                }}).catch(function() {{
                    // Silent fail — scan without location is still logged server-side
                }});
            }}

            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(
                    function(pos) {{
                        sendScan(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                    }},
                    function(err) {{
                        // User denied or unavailable — send scan without location
                        if (label) label.textContent = "Location unavailable";
                        if (sublabel) sublabel.textContent = "Enable location services to help reunite this pet.";
                        if (icon) icon.textContent = "location_off";
                        if (icon) icon.style.color = "#8a716c";
                        sendScan(null, null, null);
                    }},
                    {{enableHighAccuracy: true, timeout: 10000, maximumAge: 60000}}
                );
            }} else {{
                if (label) label.textContent = "Location not supported";
                if (sublabel) sublabel.textContent = "Your browser does not support geolocation.";
                if (icon) icon.textContent = "location_off";
                sendScan(null, null, null);
            }}
        }})();
    ''')
