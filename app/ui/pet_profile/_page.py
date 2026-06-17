import logging
import os
import uuid
from datetime import datetime, timedelta

from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select

from ...database import engine
from ...models import (
    Pet, LedgerEvent, Vaccination, SharedAccess, User, PetTag,
    Subscription, VaccinationAlert, VaccinationDocument, TagScan,
    OwnershipTransfer, _utc_now,
)
from ..header import nav_header
from ..footer import nav_footer
from ..common import (
    try_restore_session, hash_service, pdf_service, sanitize,
    SPECIES_ICONS, SPECIES_ICON_DEFAULT, SPECIES_BG, SPECIES_BG_DEFAULT,
    SPECIES_FG, SPECIES_FG_DEFAULT,
)

logger = logging.getLogger("pawsledger.ui.pet_profile")


def _with_loading(button):
    """Context manager that disables a button during an async operation to prevent double-clicks."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        button.disable()
        try:
            yield
        finally:
            button.enable()

    return _ctx()


def _obfuscate(value: str) -> str:
    """Show first character followed by asterisks for privacy."""
    if not value:
        return '***'
    return value[0] + '***'


_PET_EMOJI = {'DOG': '\U0001F415', 'CAT': '\U0001F408'}
_PET_EMOJI_DEFAULT = '\U0001F43E'
_PET_AVATAR_BG = {'DOG': '#fef3c7', 'CAT': '#e0e7ff'}
_PET_AVATAR_BG_DEFAULT = '#f5f5f4'


def _pet_avatar(pet, size: int = 128):
    """Render pet photo or species emoji placeholder (matching mockup)."""
    if pet.photo_url:
        photo_src = f'/api/v1/pets/{pet.id}/photo'
        ui.image(photo_src).classes('rounded-full').style(
            f'width: {size}px; height: {size}px; object-fit: cover; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        )
    else:
        species = pet.pet_species or 'DOG'
        bg = _PET_AVATAR_BG.get(species, _PET_AVATAR_BG_DEFAULT)
        emoji = _PET_EMOJI.get(species, _PET_EMOJI_DEFAULT)
        emoji_size = max(size // 2, 20)
        with ui.element('div').classes(
            'flex items-center justify-center rounded-full'
        ).style(
            f'width: {size}px; height: {size}px; background: {bg}; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        ):
            ui.label(emoji).style(f'font-size: {emoji_size}px; line-height: 1;')


# ─────────────────────────────────────────────────────────────
# SHARED UI COMPONENTS — used by both public and private views
# ─────────────────────────────────────────────────────────────

def _render_registry_status_card():
    """Registry status sidebar card (shared between views)."""
    with ui.element('div').classes('w-full p-8 rounded-xl flex flex-col justify-between pl-card-neutral'):
        with ui.column().classes('gap-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('verified_user').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('Registry Status').classes('pl-heading-lg')
            for label, sub in [
                ('PawsLedger Global', 'Found in primary database'),
                ('AAHA Universal Network', 'Confirmed cross-registry'),
            ]:
                with ui.row().classes('items-start gap-3'):
                    ui.icon('check_circle').style(
                        'font-size: 20px; color: #16a34a; margin-top: 2px;'
                    )
                    with ui.column().classes('gap-0'):
                        ui.label(label).style(
                            'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                        )
                        ui.label(sub).classes('pl-body-xs')


def _render_medical_summary(pet):
    """Medical summary card (shared between views)."""
    with ui.element('div').classes('h-full pl-card-bordered-blue'):
        ui.label('Medical Summary').classes('pl-heading-lg').style(
            'margin-bottom: 1.5rem;'
        )
        if pet.vaccinations:
            for v in pet.vaccinations:
                is_current = v.expiration_date > _utc_now()
                with ui.row().classes(
                    'w-full items-center justify-between p-4 rounded-lg mb-3'
                ).style('background: var(--pl-surface-info);'):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('vaccines').style('font-size: 20px; color: #3b82f6;')
                        ui.label(v.vaccine_name).style(
                            'font-weight: 500; font-size: 16px;'
                        )
                    status_label = 'Current' if is_current else 'Expired'
                    status_color = '#16a34a' if is_current else '#dc2626'
                    ui.label(status_label).style(
                        f'font-weight: 600; font-size: 14px; color: {status_color};'
                    )
        else:
            ui.label('No vaccination records available.').style(
                'color: var(--pl-on-surface-variant); font-style: italic;'
            )

        if pet.medical_conditions:
            with ui.row().classes(
                'w-full items-center justify-between p-4 rounded-lg mt-3'
            ).style('background: #fef2f2; border: 1px solid #fecaca;'):
                with ui.row().classes('items-center gap-3'):
                    ui.icon('priority_high').style('font-size: 20px; color: #dc2626;')
                    ui.label('Medical Alert').style(
                        'font-weight: 700; font-size: 16px; color: #b91c1c;'
                    )
                ui.label(pet.medical_conditions).style(
                    'font-weight: 600; font-size: 14px; color: #b91c1c;'
                )


def _render_alerts_reminders(pet, session):
    """Alerts & Reminders card — expiring vaccinations + upcoming alerts."""
    from datetime import timedelta as _td
    now = _utc_now()

    # Gather expiring/expired vaccinations (within 30 days or already expired)
    expiring_vaccines = []
    if pet.vaccinations:
        for v in pet.vaccinations:
            days_left = (v.expiration_date - now).days
            if days_left <= 30:
                expiring_vaccines.append((v, days_left))
        expiring_vaccines.sort(key=lambda x: x[1])

    # Gather upcoming alerts
    alerts = session.exec(
        select(VaccinationAlert)
        .where(VaccinationAlert.pet_id == pet.id)
        .order_by(VaccinationAlert.alert_date)
    ).all()
    upcoming_alerts = [a for a in alerts if a.alert_date >= now][:5]
    past_due_alerts = [a for a in alerts if a.alert_date < now and not a.is_sent][:3]

    with ui.element('div').classes('h-full pl-card-bordered-blue'):
        with ui.row().classes('items-center gap-2 mb-6'):
            ui.icon('notifications_active').style('font-size: 20px; color: #3b82f6;')
            ui.label('Alerts & Reminders').classes('pl-heading-lg')

        has_content = False

        # Medical conditions alert
        if pet.medical_conditions:
            has_content = True
            with ui.row().classes(
                'w-full items-center gap-3 p-3 rounded-lg mb-3'
            ).style('background: #fef2f2; border: 1px solid #fecaca;'):
                ui.icon('priority_high').style('font-size: 18px; color: #dc2626;')
                with ui.column().classes('gap-0'):
                    ui.label('Medical Alert').style(
                        'font-weight: 700; font-size: 13px; color: #b91c1c;'
                    )
                    ui.label(pet.medical_conditions).style(
                        'font-size: 12px; color: #b91c1c;'
                    )

        # Expiring / expired vaccinations
        if expiring_vaccines:
            has_content = True
            for v, days_left in expiring_vaccines[:5]:
                if days_left < 0:
                    icon_name = 'warning'
                    color = '#dc2626'
                    status = f'Expired {abs(days_left)}d ago'
                    bg = '#fef2f2'
                elif days_left == 0:
                    icon_name = 'warning'
                    color = '#dc2626'
                    status = 'Expires today'
                    bg = '#fef2f2'
                else:
                    icon_name = 'schedule'
                    color = '#ca8a04'
                    status = f'Expires in {days_left}d'
                    bg = '#fefce8'

                with ui.row().classes(
                    'w-full items-center justify-between p-3 rounded-lg mb-2'
                ).style(f'background: {bg};'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon(icon_name).style(f'font-size: 16px; color: {color};')
                        ui.label(v.vaccine_name).style(
                            'font-weight: 600; font-size: 13px; color: var(--pl-on-surface);'
                        )
                    ui.label(status).style(
                        f'font-size: 12px; font-weight: 600; color: {color};'
                    )

        # Past-due alerts
        if past_due_alerts:
            has_content = True
            for a in past_due_alerts:
                with ui.row().classes(
                    'w-full items-center justify-between p-3 rounded-lg mb-2'
                ).style('background: #fef2f2;'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('event_busy').style('font-size: 16px; color: #dc2626;')
                        ui.label(a.title).style(
                            'font-weight: 600; font-size: 13px; color: var(--pl-on-surface);'
                        )
                    ui.label(f'Overdue: {a.alert_date.strftime("%b %d")}').style(
                        'font-size: 12px; font-weight: 600; color: #dc2626;'
                    )

        # Upcoming alerts
        if upcoming_alerts:
            has_content = True
            if expiring_vaccines or past_due_alerts:
                ui.separator().classes('my-3')
            for a in upcoming_alerts:
                days_until = (a.alert_date - now).days
                with ui.row().classes(
                    'w-full items-center justify-between p-3 rounded-lg mb-2'
                ).style('background: var(--pl-surface-info);'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('event').style('font-size: 16px; color: #3b82f6;')
                        ui.label(a.title).style(
                            'font-weight: 600; font-size: 13px; color: var(--pl-on-surface);'
                        )
                    ui.label(
                        a.alert_date.strftime('%b %d') if days_until > 7
                        else f'In {days_until}d'
                    ).style('font-size: 12px; font-weight: 600; color: #3b82f6;')

        if not has_content:
            with ui.row().classes('w-full items-center gap-2 py-2'):
                ui.icon('check_circle').style('font-size: 18px; color: #16a34a;')
                ui.label('All clear — no alerts or reminders.').style(
                    'color: var(--pl-on-surface-variant); font-size: 13px;'
                )


def _render_contact_location_card(pet, is_owner: bool = False):
    """Contact / location card with OpenStreetMap embed for public, full info for owner."""
    owner = pet.owner
    owner_city = owner.city if owner else None
    owner_country = owner.country if owner else None

    with ui.element('div').classes(
        'h-full rounded-xl overflow-hidden flex flex-col'
    ).style(
        'background: white; box-shadow: var(--pl-shadow-md); '
        'border-left: 4px solid #3b82f6;'
    ):
        # Card heading
        with ui.row().classes('items-center gap-2 px-8 pt-6 pb-3'):
            ui.icon('location_on').style('font-size: 20px; color: #3b82f6;')
            ui.label('Registered Location').classes('pl-heading-lg')

        # Map area — Leaflet + Nominatim geocoding (no API key needed)
        map_div_id = f'map-{uuid.uuid4().hex[:8]}'
        with ui.element('div').classes('relative').style(
            'height: 200px; overflow: hidden;'
        ):
            if owner_city or owner_country:
                location_query = ', '.join(
                    part for part in [owner_city, owner_country] if part
                )
                # Leaflet map container
                ui.element('div').props(f'id="{map_div_id}"').style(
                    'width: 100%; height: 200px;'
                )
                # Inject Leaflet CSS/JS and initialize the map via Nominatim geocoding
                import json as _json
                safe_query_json = _json.dumps(location_query)
                ui.add_head_html(
                    '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
                )
                ui.add_head_html(
                    '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
                )
                ui.run_javascript(f'''
                    (function() {{
                        var query = {safe_query_json};
                        function initMap() {{
                            var container = document.getElementById("{map_div_id}");
                            if (!container) return setTimeout(initMap, 100);
                            if (container._leaflet_id) return;
                            var map = L.map("{map_div_id}", {{
                                zoomControl: false,
                                attributionControl: false,
                                dragging: false,
                                scrollWheelZoom: false,
                                doubleClickZoom: false,
                                boxZoom: false,
                                keyboard: false,
                                touchZoom: false,
                            }}).setView([20, 0], 2);
                            L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
                                maxZoom: 18,
                            }}).addTo(map);
                            fetch("https://nominatim.openstreetmap.org/search?format=json&q=" + encodeURIComponent(query) + "&limit=1")
                                .then(r => r.json())
                                .then(data => {{
                                    if (data && data.length > 0) {{
                                        var lat = parseFloat(data[0].lat);
                                        var lon = parseFloat(data[0].lon);
                                        map.setView([lat, lon], 11);
                                        L.circleMarker([lat, lon], {{
                                            radius: 30,
                                            color: "#a03a21",
                                            fillColor: "#ffdad2",
                                            fillOpacity: 0.3,
                                            weight: 2,
                                        }}).addTo(map);
                                    }}
                                }});
                        }}
                        initMap();
                    }})();
                ''')
            else:
                # Fallback: grey placeholder
                with ui.element('div').classes(
                    'w-full h-full flex items-center justify-center'
                ).style('background: #e7e5e4;'):
                    ui.icon('map').style(
                        'font-size: 48px; color: #a8a29e; opacity: 0.5;'
                    )

            # Location badge overlay
            location_label_parts = [
                part for part in [owner_city, owner_country] if part
            ]
            location_text = ', '.join(location_label_parts) if location_label_parts else 'Location unavailable'
            if not is_owner:
                location_text = f'Primary Residence Area: {location_text}'

            with ui.row().classes(
                'absolute items-center gap-2 px-3 py-1.5 rounded-full shadow-md'
            ).style('bottom: 1rem; left: 1rem; background: white; z-index: 10;'):
                ui.icon('location_on').style('font-size: 16px; color: var(--pl-primary);')
                ui.label(location_text).style(
                    'font-size: 12px; font-weight: 600;'
                )

        # Content below map
        if not is_owner:
            with ui.column().classes('p-6 flex-grow items-center justify-center gap-4'):
                ui.label(
                    'Owner information is protected for privacy. '
                    'Use the form below to send a secure nudge.'
                ).style(
                    'color: var(--pl-on-surface-variant); font-size: 16px; text-align: center; '
                    'line-height: 1.5;'
                )
                _render_nudge_form(pet)


def _render_trust_signals():
    """Trust signals footer section (shared between views)."""
    with ui.element('section').classes('mt-16 pt-8 text-center').style(
        'border-top: 1px solid #e7e5e4;'
    ):
        ui.label('Verified by Industry Standards').style(
            'font-size: 12px; font-weight: 600; color: #a8a29e; '
            'text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1.5rem;'
        )
        with ui.row().classes('justify-center items-center gap-12').style(
            'filter: grayscale(1); opacity: 0.6;'
        ):
            for icon_name, label in [
                ('health_and_safety', 'AAHA'),
                ('security', 'PetRegistry'),
                ('fingerprint', 'MicroID'),
            ]:
                with ui.row().classes('items-center gap-2'):
                    ui.icon(icon_name).style('font-size: 30px;')
                    ui.label(label).classes('pl-heading-lg')


async def _open_add_tag_dialog(pet):
    """Shared dialog for registering a new NFC/QR tag on a pet."""
    with ui.dialog() as dialog, ui.card().classes('p-8').style(
        'max-width: 560px; border-radius: 12px;'
    ):
        ui.label('Register New Tag').classes('pl-heading-xl').style('margin-bottom: 0.5rem;')
        ui.label('Link a QR or NFC tag to this pet for instant identification.').classes(
            'pl-body-sm'
        ).style('margin-bottom: 1.5rem;')

        tag_type = ui.select(
            ['QR', 'NFC', 'DUAL'], label='Tag Type', value='QR'
        ).classes('w-full').props('outlined dense')
        tag_label = ui.input(
            placeholder='e.g. Collar tag, Harness tag'
        ).classes('w-full').props('outlined dense label="Label"')
        tag_code_input = ui.input(
            placeholder='Leave blank to auto-generate'
        ).classes('w-full').props('outlined dense label="Tag Code (optional)"')

        nfc_section = ui.column().classes('w-full gap-4')
        with nfc_section:
            nfc_uid_input = ui.input(
                placeholder='e.g. 04:A2:3B:C1:D4:E5:F6'
            ).classes('w-full').props('outlined dense label="NFC UID"')
            nfc_tech_input = ui.select(
                ['NTAG213', 'NTAG215', 'NTAG216', 'Mifare Classic', 'Mifare Ultralight'],
                label='NFC Technology', value='NTAG215',
            ).classes('w-full').props('outlined dense')
        nfc_section.set_visibility(False)

        def on_type_change(e):
            nfc_section.set_visibility(e.value in ('NFC', 'DUAL'))

        tag_type.on('update:model-value', on_type_change)

        tag_serial = ui.input(
            placeholder='Manufacturer serial number'
        ).classes('w-full').props('outlined dense label="Serial Number (optional)"')
        tag_manufacturer = ui.input(
            placeholder='e.g. PawTag, Tile'
        ).classes('w-full').props('outlined dense label="Manufacturer (optional)"')
        tag_notes = ui.textarea(
            placeholder='Any notes about this tag'
        ).classes('w-full').props('outlined rows=2 label="Notes (optional)"')

        async def add_tag():
            code = tag_code_input.value.strip() if tag_code_input.value else None
            with Session(engine) as s:
                if code:
                    existing = s.exec(
                        select(PetTag).where(PetTag.tag_code == code)
                    ).first()
                    if existing:
                        ui.notify('Tag code already registered.', type='negative')
                        return

                generated_code = code or str(uuid.uuid4()).replace('-', '')[:12].upper()
                qr_url = f'/qr/{generated_code}'

                new_tag = PetTag(
                    pet_id=pet.id,
                    tag_type=tag_type.value,
                    tag_code=generated_code,
                    serial_number=tag_serial.value.strip() or None,
                    manufacturer=tag_manufacturer.value.strip() or None,
                    nfc_uid=nfc_uid_input.value.strip() if nfc_uid_input.value else None,
                    nfc_technology=(
                        nfc_tech_input.value if tag_type.value in ('NFC', 'DUAL') else None
                    ),
                    qr_url=qr_url,
                    label=tag_label.value.strip() or None,
                    notes=tag_notes.value.strip() or None,
                )
                s.add(new_tag)
                s.add(LedgerEvent(
                    pet_id=pet.id,
                    event_type="TAG_ACTIVATED",
                    description=(
                        f"{tag_type.value} tag activated: {generated_code}"
                        + (f" ({tag_label.value.strip()})" if tag_label.value.strip() else "")
                    ),
                ))
                s.commit()

            dialog.close()
            ui.notify('Tag added successfully!', type='positive')
            ui.navigate.to(f'/pet/{pet.id}')

        with ui.row().classes('w-full justify-end gap-3 mt-4'):
            ui.button('Cancel', on_click=dialog.close).props(
                'flat no-caps'
            ).style('color: var(--pl-on-surface-variant);')
            tag_btn = ui.button(
                'Register Tag', icon='nfc',
            ).style(
                'background: var(--pl-primary); color: white; font-weight: 600;'
            ).props('no-caps')

            async def _add_tag_guarded():
                async with _with_loading(tag_btn):
                    await add_tag()

            tag_btn.on_click(_add_tag_guarded)

    dialog.open()


def _render_chip_and_tags(pet, session):
    """Combined Microchip + NFC/QR Tags card for the owner's private view."""
    with ui.element('div').classes('w-full h-full pl-card-bordered-primary'):
        # ── Microchip section ──
        with ui.row().classes('items-center gap-2 mb-3'):
            ui.icon('memory').style('font-size: 20px; color: var(--pl-primary);')
            ui.label('Microchip').classes('pl-heading-lg')
        with ui.row().classes('items-center gap-2 p-3 rounded-lg').style(
            'background: #fafafa; border: 1px solid #e7e5e4;'
        ):
            ui.icon('fingerprint').style('font-size: 18px; color: var(--pl-text-hint);')
            ui.label(pet.chip_id).style(
                'font-family: monospace; font-size: 14px; font-weight: 600; '
                'color: var(--pl-on-surface); letter-spacing: 0.02em;'
            )

        # ── Registry Status ──
        with ui.column().classes('gap-2 mt-4 mb-6'):
            for label, sub in [
                ('PawsLedger Global', 'Found in primary database'),
                ('AAHA Universal Network', 'Confirmed cross-registry'),
            ]:
                with ui.row().classes('items-start gap-2'):
                    ui.icon('check_circle').style(
                        'font-size: 16px; color: #16a34a; margin-top: 2px;'
                    )
                    with ui.column().classes('gap-0'):
                        ui.label(label).style(
                            'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                        )
                        ui.label(sub).classes('pl-body-xs')

        # ── NFC / QR Tags section ──
        ui.separator().classes('mb-4')
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('nfc').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('NFC / QR Tags').classes('pl-heading-lg')
            tag_count = len(pet.tags)
            if tag_count > 0:
                ui.label(f'{tag_count} tag{"s" if tag_count != 1 else ""}').style(
                    'padding: 4px 12px; background: #f5f5f4; color: var(--pl-on-surface-variant); '
                    'font-size: var(--pl-text-xs); font-weight: 600; border-radius: var(--pl-radius-full);'
                )

        # Existing tags list
        tags_container = ui.column().classes('w-full gap-3 mb-4')
        with tags_container:
            if pet.tags:
                for tag in pet.tags:
                    _render_tag_row(tag, pet)
            else:
                ui.label(
                    'No tags linked yet. Add a QR or NFC tag to enable '
                    'instant identification.'
                ).classes('pl-body-sm').style('font-style: italic;')

        ui.button(
            'Add Tag', icon='add',
            on_click=lambda: _open_add_tag_dialog(pet),
        ).classes('w-full').props('outline no-caps').style(
            'color: var(--pl-primary); border-color: var(--pl-primary); font-weight: 600;'
        )


def _render_tag_management(pet, session):
    """Tag management card for the owner's private view. Delegates to shared helpers."""
    with ui.element('div').classes('w-full pl-card-bordered-primary'):
        with ui.row().classes('w-full justify-between items-center mb-6'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('nfc').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('NFC / QR Tags').classes('pl-heading-lg')
            tag_count = len(pet.tags)
            if tag_count > 0:
                ui.label(f'{tag_count} tag{"s" if tag_count != 1 else ""}').style(
                    'padding: 4px 12px; background: #f5f5f4; color: var(--pl-on-surface-variant); '
                    'font-size: var(--pl-text-xs); font-weight: 600; border-radius: var(--pl-radius-full);'
                )

        # Existing tags list
        tags_container = ui.column().classes('w-full gap-3 mb-6')
        with tags_container:
            if pet.tags:
                for tag in pet.tags:
                    _render_tag_row(tag, pet)
            else:
                ui.label(
                    'No tags linked yet. Add a QR or NFC tag to enable '
                    'instant identification when scanned.'
                ).classes('pl-body-sm').style('font-style: italic;')

        ui.button(
            'Add Tag', icon='add',
            on_click=lambda: _open_add_tag_dialog(pet),
        ).classes('w-full').props('outline no-caps').style(
            'color: var(--pl-primary); border-color: var(--pl-primary); font-weight: 600;'
        )


def _render_tag_row(tag, pet):
    """Render a single tag row with status and actions."""
    is_active = tag.status == 'ACTIVE'
    status_bg = '#dcfce7' if is_active else '#fef2f2'
    status_fg = '#166534' if is_active else '#991b1b'
    type_icon = 'qr_code_2' if tag.tag_type == 'QR' else (
        'nfc' if tag.tag_type == 'NFC' else 'devices'
    )

    with ui.row().classes(
        'w-full items-center justify-between p-4 rounded-lg'
    ).style(f'background: {status_bg};'):
        with ui.row().classes('items-center gap-4'):
            ui.icon(type_icon).style(f'font-size: 24px; color: {status_fg};')
            with ui.column().classes('gap-0'):
                with ui.row().classes('items-center gap-2'):
                    ui.label(tag.label or f'{tag.tag_type} Tag').style(
                        'font-weight: 600; font-size: 14px;'
                    )
                    ui.label(tag.status).style(
                        f'font-size: 10px; font-weight: 700; color: {status_fg}; '
                        'text-transform: uppercase; letter-spacing: 0.05em;'
                    )
                ui.label(f'Code: {tag.tag_code}').style(
                    'font-family: monospace; font-size: 12px; color: var(--pl-on-surface-variant);'
                )
                if tag.nfc_uid:
                    ui.label(f'NFC UID: {tag.nfc_uid}').style(
                        'font-family: monospace; font-size: 11px; color: var(--pl-text-hint);'
                    )

        with ui.row().classes('items-center gap-2'):
            if is_active:
                async def deactivate(t=tag):
                    with Session(engine) as s:
                        db_tag = s.get(PetTag, t.id)
                        if db_tag:
                            db_tag.status = 'DEACTIVATED'
                            db_tag.deactivated_at = _utc_now()
                            s.add(LedgerEvent(
                                pet_id=pet.id,
                                event_type="TAG_DEACTIVATED",
                                description=f"Tag deactivated: {t.tag_code}",
                            ))
                            s.add(db_tag)
                            s.commit()
                    ui.notify('Tag deactivated.', type='warning')
                    ui.navigate.to(f'/pet/{pet.id}')

                ui.button(icon='block', on_click=deactivate).props(
                    'flat dense round'
                ).tooltip('Deactivate')
            else:
                async def reactivate(t=tag):
                    with Session(engine) as s:
                        db_tag = s.get(PetTag, t.id)
                        if db_tag:
                            db_tag.status = 'ACTIVE'
                            db_tag.deactivated_at = None
                            s.add(LedgerEvent(
                                pet_id=pet.id,
                                event_type="TAG_ACTIVATED",
                                description=f"Tag reactivated: {t.tag_code}",
                            ))
                            s.add(db_tag)
                            s.commit()
                    ui.notify('Tag reactivated.', type='positive')
                    ui.navigate.to(f'/pet/{pet.id}')

                ui.button(icon='check_circle', on_click=reactivate).props(
                    'flat dense round'
                ).tooltip('Reactivate')

            async def remove_tag(t=tag):
                with Session(engine) as s:
                    db_tag = s.get(PetTag, t.id)
                    if db_tag:
                        s.add(LedgerEvent(
                            pet_id=pet.id,
                            event_type="TAG_REMOVED",
                            description=f"Tag removed: {t.tag_code}",
                        ))
                        s.delete(db_tag)
                        s.commit()
                ui.notify('Tag removed.', type='negative')
                ui.navigate.to(f'/pet/{pet.id}')

            ui.button(icon='delete', on_click=remove_tag).props(
                'flat dense round color=negative'
            ).tooltip('Remove')


# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# SCAN HISTORY — shows where the pet's tags have been scanned
# ─────────────────────────────────────────────────────────────

def _render_scan_history(pet, session):
    """Render the tag scan history card with a map for the owner."""
    scans = session.exec(
        select(TagScan)
        .where(TagScan.pet_id == pet.id)
        .order_by(TagScan.scanned_at.desc())
        .limit(10)
    ).all()

    with ui.element('div').classes('w-full mt-6 pl-card-bordered-primary'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('location_on').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('Tag Scan History').classes('pl-heading-lg')
            if scans:
                ui.label(f'{len(scans)} recent scan{"s" if len(scans) != 1 else ""}').style(
                    'padding: 4px 12px; background: #f5f5f4; color: var(--pl-on-surface-variant); '
                    'font-size: var(--pl-text-xs); font-weight: 600; border-radius: var(--pl-radius-full);'
                )

        # Last known location highlight
        if pet.last_scan_at and pet.last_scan_location:
            with ui.row().classes(
                'w-full items-center gap-3 p-4 rounded-lg mb-4'
            ).style('background: var(--pl-surface-success); border: 1px solid rgba(22,163,74,0.2);'):
                ui.icon('my_location').style('font-size: 20px; color: #16a34a;')
                with ui.column().classes('gap-0'):
                    ui.label(f'Last seen: {pet.last_scan_location}').style(
                        'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                    )
                    ui.label(
                        pet.last_scan_at.strftime('%b %d, %Y at %H:%M UTC')
                    ).classes('pl-body-xs')

        # Map showing scan locations (scans with coordinates)
        geo_scans = [s for s in scans if s.latitude is not None]
        if geo_scans:
            import json as _json
            import uuid as _uuid
            map_div_id = f'scan-map-{_uuid.uuid4().hex[:8]}'
            ui.element('div').props(f'id="{map_div_id}"').style(
                'width: 100%; height: 240px; border-radius: 8px; overflow: hidden; margin-bottom: 1rem;'
            )
            markers_json = _json.dumps([
                {
                    "lat": s.latitude, "lon": s.longitude,
                    "label": f'{s.scan_method} • {s.city or ""} {s.country or ""}'.strip(),
                    "date": s.scanned_at.strftime('%b %d, %H:%M'),
                }
                for s in geo_scans
            ])
            ui.add_head_html(
                '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
            )
            ui.add_head_html(
                '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            )
            ui.run_javascript(f'''
                (function() {{
                    var markers = {markers_json};
                    function initMap() {{
                        var el = document.getElementById("{map_div_id}");
                        if (!el) return setTimeout(initMap, 100);
                        if (el._leaflet_id) return;
                        var map = L.map("{map_div_id}", {{zoomControl: true, attributionControl: false}}).setView([20, 0], 2);
                        L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{maxZoom: 18}}).addTo(map);
                        var bounds = [];
                        markers.forEach(function(m) {{
                            var latlng = [m.lat, m.lon];
                            bounds.push(latlng);
                            L.circleMarker(latlng, {{
                                radius: 8, color: "#a03a21", fillColor: "#ffdad2", fillOpacity: 0.7, weight: 2
                            }}).addTo(map).bindPopup("<b>" + m.date + "</b><br>" + m.label);
                        }});
                        if (bounds.length > 0) map.fitBounds(bounds, {{padding: [30, 30], maxZoom: 13}});
                    }}
                    initMap();
                }})();
            ''')

        # Scan list
        if scans:
            with ui.column().classes('w-full gap-3'):
                for scan in scans:
                    method_icon = 'qr_code_2' if scan.scan_method == 'QR' else (
                        'nfc' if scan.scan_method == 'NFC' else 'search'
                    )
                    location_text = scan.city or scan.country or 'Unknown location'
                    if scan.city and scan.country:
                        location_text = f'{scan.city}, {scan.country}'

                    with ui.row().classes(
                        'w-full items-center justify-between p-3 rounded-lg'
                    ).style('background: var(--pl-surface-info);'):
                        with ui.row().classes('items-center gap-3'):
                            ui.icon(method_icon).style(
                                'font-size: 20px; color: var(--pl-primary);'
                            )
                            with ui.column().classes('gap-0'):
                                ui.label(location_text).style(
                                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                                )
                                ui.label(
                                    scan.scanned_at.strftime('%b %d, %Y • %H:%M UTC')
                                ).classes('pl-body-xs')
                        ui.label(scan.scan_method).style(
                            'padding: 2px 8px; background: #f5f5f4; color: var(--pl-on-surface-variant); '
                            'font-size: 10px; font-weight: 700; border-radius: var(--pl-radius-full); '
                            'text-transform: uppercase;'
                        )
        else:
            with ui.column().classes('items-center py-6'):
                ui.icon('location_off').style(
                    'font-size: 40px; color: var(--pl-outline-variant); opacity: 0.5;'
                )
                ui.label('No scans recorded yet').style(
                    'font-weight: 600; color: var(--pl-on-surface-variant); margin-top: 0.5rem;'
                )
                ui.label(
                    'When someone scans your pet\'s NFC or QR tag, their location will appear here.'
                ).classes('pl-body-xs').style('text-align: center; max-width: 300px;')


# ─────────────────────────────────────────────────────────────
# VACCINATION REPORT UPLOAD — paid plan feature
# ─────────────────────────────────────────────────────────────

def _render_vaccination_upload(pet, session, is_verified: bool):
    """Render the vaccination report upload section (paid users only)."""
    if not is_verified:
        with ui.element('div').classes('w-full mt-6 pl-card-neutral'):
            with ui.row().classes('w-full items-center justify-between flex-wrap gap-4'):
                with ui.column().classes('gap-1'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('upload_file').style('font-size: 24px; color: var(--pl-primary);')
                        ui.label('Upload Pet Documents').classes('pl-heading-lg')
                    ui.label(
                        'Store vet reports, vaccination certificates, and pet documents securely. '
                        'Available on Verified and Guardian plans.'
                    ).classes('pl-body-sm')
                ui.button(
                    'View Plans', icon='upgrade',
                    on_click=lambda: ui.navigate.to('/pricing'),
                ).style(
                    'background: var(--pl-primary); color: white; font-weight: 600; '
                    'padding: 10px 24px; border-radius: 8px;'
                ).props('no-caps')
        return

    # Load existing documents
    docs = session.exec(
        select(VaccinationDocument)
        .where(VaccinationDocument.pet_id == pet.id)
        .order_by(VaccinationDocument.uploaded_at.desc())
    ).all()

    with ui.element('div').classes('w-full mt-6 pl-card-bordered-primary'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('upload_file').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('Pet Documents').classes('pl-heading-lg')
            if docs:
                ui.label(f'{len(docs)} document{"s" if len(docs) != 1 else ""}').style(
                    'padding: 4px 12px; background: #f5f5f4; color: var(--pl-on-surface-variant); '
                    'font-size: var(--pl-text-xs); font-weight: 600; border-radius: var(--pl-radius-full);'
                )

        # Existing documents list
        if docs:
            with ui.column().classes('w-full gap-3 mb-4'):
                for doc in docs:
                    _render_document_row(doc, pet)
        else:
            ui.label(
                'No reports uploaded yet. Upload vet certificates, '
                'vaccination records, or health reports.'
            ).classes('pl-body-sm').style('font-style: italic; margin-bottom: 1rem;')

        # Upload button — opens dialog
        async def open_upload_dialog():
            with ui.dialog() as upload_dlg, ui.card().classes('p-8').style(
                'max-width: 560px; border-radius: 12px;'
            ):
                ui.label('Upload Document').classes('pl-heading-xl').style(
                    'margin-bottom: 0.5rem;'
                )
                ui.label(
                    'Upload a vet report, vaccination certificate, or any pet document (PDF, JPG, PNG, max 10 MB).'
                ).classes('pl-body-sm').style('margin-bottom: 1.5rem;')

                doc_name_input = ui.input(
                    label='Document Name',
                    placeholder='e.g. Rabies Certificate 2026',
                ).classes('w-full').props('outlined dense')

                doc_desc_input = ui.textarea(
                    label='Description (optional)',
                    placeholder='Any notes about this document...',
                ).classes('w-full').props('outlined dense rows=2')

                uploaded_file_data = {'content': None, 'name': None, 'type': None}

                async def on_file_selected(e):
                    file = e.file
                    if not file:
                        return
                    uploaded_file_data['content'] = await file.read()
                    uploaded_file_data['name'] = file.name or 'report.pdf'
                    uploaded_file_data['type'] = file.content_type or 'application/pdf'

                ui.upload(
                    label='Choose File',
                    on_upload=on_file_selected,
                    auto_upload=True,
                    max_file_size=10 * 1024 * 1024,
                ).props('accept=".pdf,.jpg,.jpeg,.png,.webp"').classes('w-full')

                ui.label(
                    'Accepted formats: PDF, JPG, PNG, WebP'
                ).classes('pl-body-xs').style('margin-top: 0.5rem;')

                async def submit_upload():
                    if not uploaded_file_data['content']:
                        ui.notify('Please select a file first.', type='warning')
                        return
                    import httpx
                    from nicegui import context
                    base_url = os.getenv('BASE_URL', 'http://localhost:8080')
                    cookies = context.client.request.cookies
                    data = {}
                    if doc_name_input.value and doc_name_input.value.strip():
                        data['document_name'] = doc_name_input.value.strip()
                    if doc_desc_input.value and doc_desc_input.value.strip():
                        data['description'] = doc_desc_input.value.strip()
                    async with httpx.AsyncClient(base_url=base_url) as client:
                        resp = await client.post(
                            f'/api/v1/pets/{pet.id}/vaccinations/upload',
                            files={'file': (uploaded_file_data['name'], uploaded_file_data['content'], uploaded_file_data['type'])},
                            data=data,
                            cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                        )
                        if resp.status_code == 200:
                            upload_dlg.close()
                            ui.notify('Document uploaded!', type='positive')
                            ui.navigate.to(f'/pet/{pet.id}')
                        elif resp.status_code == 400:
                            detail = resp.json().get('detail', 'Upload failed.')
                            if 'limit reached' in detail.lower():
                                ui.notify(
                                    'Document limit reached. Upgrade to Guardian for more storage.',
                                    type='warning',
                                )
                                upload_dlg.close()
                                ui.navigate.to('/pricing')
                            else:
                                ui.notify(detail, type='warning')
                        elif resp.status_code == 403:
                            ui.notify('Verified or Guardian subscription required.', type='warning')
                        else:
                            detail = resp.json().get('detail', 'Upload failed.')
                            ui.notify(detail, type='negative')

                with ui.row().classes('w-full justify-end mt-4 gap-2'):
                    ui.button('Cancel', on_click=upload_dlg.close).props(
                        'flat no-caps'
                    ).style('color: var(--pl-on-surface-variant);')
                    ui.button('Upload', icon='cloud_upload', on_click=submit_upload).props(
                        'no-caps'
                    ).style('background: #a03a21; color: white;')

            upload_dlg.open()

        ui.button(
            'Upload Document', icon='upload_file',
            on_click=open_upload_dialog,
        ).classes('w-full').props('outline no-caps').style(
            'color: var(--pl-primary); border-color: var(--pl-primary); font-weight: 600;'
        )


def _render_document_row(doc, pet):
    """Render a single uploaded pet document row."""
    icon_name = 'picture_as_pdf' if 'pdf' in doc.content_type else 'image'
    size_kb = doc.file_size / 1024
    size_label = f'{size_kb:.0f} KB' if size_kb < 1024 else f'{size_kb / 1024:.1f} MB'
    display_name = doc.document_name or doc.original_filename

    with ui.row().classes(
        'w-full items-center justify-between p-4 rounded-lg'
    ).style('background: var(--pl-surface-info);'):
        with ui.row().classes('items-center gap-3 min-w-0 flex-1'):
            ui.icon(icon_name).style('font-size: 24px; color: var(--pl-primary);')
            with ui.column().classes('gap-0 min-w-0'):
                ui.label(display_name).style(
                    'font-weight: 600; font-size: var(--pl-text-sm); color: var(--pl-on-surface); '
                    'overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'
                )
                if doc.description:
                    ui.label(doc.description).style(
                        'font-size: 12px; color: var(--pl-on-surface-variant); '
                        'overflow: hidden; text-overflow: ellipsis; white-space: nowrap; '
                        'max-width: 280px;'
                    )
                ui.label(
                    f'{size_label} • {doc.uploaded_at.strftime("%b %d, %Y")}'
                ).classes('pl-body-xs')

        with ui.row().classes('items-center gap-1'):
            ui.button(
                icon='download',
                on_click=lambda d=doc: ui.navigate.to(
                    f'/api/v1/pets/{pet.id}/vaccinations/documents/{d.id}/download'
                ),
            ).props('flat dense round').tooltip('Download')

            async def delete_doc(d=doc):
                import httpx
                from nicegui import context
                base_url = os.getenv('BASE_URL', 'http://localhost:8080')
                cookies = context.client.request.cookies
                async with httpx.AsyncClient(base_url=base_url) as client:
                    resp = await client.delete(
                        f'/api/v1/pets/{pet.id}/vaccinations/documents/{d.id}',
                        cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                    )
                    if resp.status_code == 200:
                        ui.notify('Document deleted.', type='info')
                        ui.navigate.to(f'/pet/{pet.id}')
                    else:
                        ui.notify('Failed to delete document.', type='negative')

            ui.button(
                icon='delete', on_click=delete_doc,
            ).props('flat dense round color=negative').tooltip('Delete')


# SECURE NUDGE FORM — reusable component for public/QR views
# ─────────────────────────────────────────────────────────────

def _render_nudge_form(pet):
    """Render the Secure Nudge form with auth/ownership/orphan checks."""
    is_logged_in = bool(app.storage.user.get('email'))
    current_user_id = app.storage.user.get('id')

    with ui.card().classes('w-full p-6 mt-4').style(
        'border-radius: 12px; background: var(--pl-surface-info); '
        'border: 1px solid rgba(160,58,33,0.15);'
    ):
        with ui.row().classes('items-center gap-2 mb-3'):
            ui.icon('send').style('color: var(--pl-primary); font-size: 20px;')
            ui.label('Send Secure Nudge to Owner').style(
                'font-weight: 700; font-size: 16px; color: var(--pl-on-surface);'
            )

        if not is_logged_in:
            ui.label(
                'Sign in with Google to send a secure nudge to the pet owner.'
            ).style('color: var(--pl-on-surface-variant); font-size: 14px; margin-bottom: 8px;')
            ui.button(
                'Sign In to Nudge', icon='login',
                on_click=lambda: ui.navigate.to('/login'),
            ).style(
                'background: var(--pl-primary); color: white; font-weight: 600; '
                'padding: 10px 24px; border-radius: 8px;'
            ).props('no-caps')
            return

        if not pet.owner_id:
            ui.label(
                'This pet has no registered owner — nudge unavailable.'
            ).style('color: var(--pl-on-surface-variant); font-size: 14px; font-style: italic;')
            return

        if current_user_id and str(pet.owner_id) == current_user_id:
            ui.label(
                'You are the owner of this pet.'
            ).style('color: var(--pl-on-surface-variant); font-size: 14px; font-style: italic;')
            return

        ui.label(
            'Your identity is verified but your email will not be shared with the owner.'
        ).style('color: var(--pl-on-surface-variant); font-size: 13px; margin-bottom: 8px;')

        message_input = ui.textarea(
            label='Your message (10–500 characters)',
            placeholder='Describe where you found the pet and how the owner can reach you...',
        ).props('outlined counter maxlength=500').classes('w-full')

        with ui.row().classes('items-center gap-2 mt-1'):
            ui.icon('location_off').style('font-size: 16px; color: var(--pl-secondary);')
            ui.label('Upgrade to Verified to share your location with the owner').style(
                'font-size: 12px; color: var(--pl-secondary); font-style: italic;'
            )

        async def submit_nudge():
            msg = message_input.value or ''
            if len(msg.strip()) < 10:
                ui.notify('Message must be at least 10 characters.', type='warning')
                return
            if len(msg.strip()) > 500:
                ui.notify('Message must be at most 500 characters.', type='warning')
                return

            import httpx
            from starlette.requests import Request as StarletteRequest
            from nicegui import context
            base = os.getenv('BASE_URL', 'http://localhost:8080')
            cookies = context.client.request.cookies
            async with httpx.AsyncClient(base_url=base) as http_client:
                resp = await http_client.post(
                    f'/api/v1/nudge/{pet.chip_id}',
                    json={'message': msg.strip()},
                    cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                )
                if resp.status_code == 200:
                    ui.notify('Your nudge has been sent. The owner has been notified.', type='positive')
                    message_input.value = ''
                elif resp.status_code == 429:
                    ui.notify('Rate limit reached: maximum 3 nudges per pet per 24 hours.', type='warning')
                elif resp.status_code == 409:
                    ui.notify(resp.json().get('detail', 'Cannot send nudge.'), type='warning')
                else:
                    detail = resp.json().get('detail', 'Failed to send nudge.')
                    logger.error("Nudge API error for chip_id=%s: %s", pet.chip_id, detail)
                    ui.notify(detail, type='negative')

        nudge_btn = ui.button(
            'Send Secure Nudge', icon='send',
        ).classes('mt-3').style(
            'background: var(--pl-primary); color: white; font-weight: 600; '
            'padding: 12px 32px; border-radius: 8px; '
            'box-shadow: 0 4px 12px rgba(160,58,33,0.2);'
        ).props('no-caps')

        async def _nudge_guarded():
            async with _with_loading(nudge_btn):
                await submit_nudge()

        nudge_btn.on_click(_nudge_guarded)


# ─────────────────────────────────────────────────────────────
# PUBLIC VIEW — privacy-obfuscated, for non-owners / anonymous
# ─────────────────────────────────────────────────────────────

def _render_public_view(pet, session, is_verified=False):
    """Render the public pet profile with obfuscated PII."""
    is_logged_in = bool(app.storage.user.get('email'))

    # ── Search header ──
    with ui.element('header').classes('mb-12'):
        ui.link(
            '← New Search', '/',
        ).style(
            'color: var(--pl-primary); font-weight: 600; font-size: 14px; '
            'text-decoration: none;'
        )
        with ui.row().classes(
            'w-full justify-between items-end mt-4 flex-wrap gap-6'
        ):
            with ui.column().classes('gap-2'):
                ui.label(f'Chip ID: {pet.chip_id}').classes('pl-heading-3xl')
                with ui.row().classes('items-center gap-3'):
                    ui.label('Registered').style(
                        'background: #ffc65d; color: #755100; padding: 4px 12px; '
                        'border-radius: 9999px; font-size: 12px; font-weight: 700; '
                        'text-transform: uppercase; letter-spacing: 0.1em;'
                    )
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('check_circle').style(
                            'font-size: 18px; color: #16a34a;'
                        )
                        ui.label('AAHA Universal Lookup Verified').style(
                            'font-size: 14px; font-weight: 600; color: var(--pl-on-surface-variant);'
                        )

    # ── Row 1: Pet ID card + Registry status ──
    with ui.row().classes('w-full gap-6 flex-wrap items-stretch'):
        # Pet identification card (obfuscated)
        with ui.element('div').classes('flex-1').style('min-width: 0;'):
            with ui.element('div').classes('h-full p-8 rounded-xl').style(
                'background: white; box-shadow: var(--pl-shadow-md); '
                'border-left: 4px solid var(--pl-primary);'
            ):
                with ui.row().classes('gap-8'):
                    with ui.element('div').classes('relative flex-shrink-0'):
                        _pet_avatar(pet, 128)
                        with ui.element('div').classes(
                            'absolute bottom-0 right-0 bg-white p-1 '
                            'rounded-full shadow-sm'
                        ).style('border: 1px solid #f5f5f4;'):
                            ui.icon('pets').style(
                                'font-size: 20px; color: var(--pl-primary);'
                            )

                    with ui.element('div').classes('flex-grow'):
                        with ui.row().classes(
                            'w-full gap-x-12 gap-y-6 flex-wrap'
                        ):
                            # Pet name (obfuscated)
                            with ui.column().classes('gap-1'):
                                ui.label('PET NAME').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: var(--pl-on-surface-variant); text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(_obfuscate(pet.name)).classes('pl-heading-xl')
                                ui.label('(Privacy Obfuscated)').style(
                                    'font-size: 12px; color: var(--pl-text-hint); '
                                    'font-style: italic;'
                                )
                            # Manufacturer
                            with ui.column().classes('gap-1'):
                                ui.label('MANUFACTURER').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: var(--pl-on-surface-variant); text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(
                                    pet.manufacturer or 'Unknown'
                                ).classes('pl-heading-xl')
                                prefix = pet.chip_id[:3] if pet.chip_id else ''
                                ui.label(f'Based on Prefix {prefix}').style(
                                    'font-size: 12px; color: var(--pl-text-hint);'
                                )
                            # Status
                            with ui.column().classes('gap-1'):
                                ui.label('STATUS').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: var(--pl-on-surface-variant); text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                s_bg = '#dcfce7' if is_verified else '#fef9c3'
                                s_fg = '#166534' if is_verified else '#854d0e'
                                s_txt = 'Active Record' if is_verified else 'Unverified'
                                ui.label(s_txt).style(
                                    f'display: inline-block; padding: 2px 10px; '
                                    f'border-radius: 9999px; font-size: 12px; '
                                    f'font-weight: 500; background: {s_bg}; '
                                    f'color: {s_fg};'
                                )
                            # Species / Breed
                            with ui.column().classes('gap-1'):
                                ui.label('SPECIES / BREED').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: var(--pl-on-surface-variant); text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(
                                    f'{pet.pet_species} • '
                                    f'{pet.breed or "Unknown"}'
                                ).style('font-size: 16px; color: var(--pl-on-surface);')

        # Registry status card
        with ui.element('div').style('width: 320px; flex-shrink: 0;'):
            _render_registry_status_card()

    # ── Row 2: Medical summary + Contact/Location ──
    with ui.row().classes('w-full gap-6 flex-wrap items-stretch mt-6'):
        with ui.element('div').classes('flex-1').style('min-width: 0;'):
            _render_medical_summary(pet)
        with ui.element('div').classes('flex-1').style('min-width: 0;'):
            _render_contact_location_card(pet, is_owner=False)

    # ── Trust signals ──
    _render_trust_signals()


# ─────────────────────────────────────────────────────────────
# PRIVATE VIEW — full details for the pet owner
# ─────────────────────────────────────────────────────────────

async def _handle_photo_upload(e, pet_id):
    """Upload pet photo via the API and refresh the page."""
    from nicegui import context
    import httpx

    file_obj = e.file
    content = await file_obj.read()
    filename = file_obj.name or 'photo.jpg'
    content_type = file_obj.content_type or 'image/jpeg'
    base_url = os.getenv('BASE_URL', 'http://localhost:8080')
    cookies = {'paws_user_id': context.client.request.cookies.get('paws_user_id', '')}

    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.post(
            f'/api/v1/pets/{pet_id}/photo',
            files={'file': (filename, content, content_type)},
            cookies=cookies,
        )
        if resp.status_code == 200:
            ui.notify('Photo updated!', type='positive')
            ui.navigate.to(f'/pet/{pet_id}')
        else:
            detail = resp.json().get('detail', 'Upload failed.')
            ui.notify(detail, type='negative')


def _render_private_view(pet, session, is_verified=False):
    """Render the full owner view with all PII and management tools."""

    # ── Gather data ──
    now = _utc_now()

    vaccinations = pet.vaccinations or []
    tags = [t for t in (pet.tags or []) if t.status == "ACTIVE"]
    total_tags = len(tags)

    # Tag scans (recent 5)
    recent_scans = session.exec(
        select(TagScan)
        .where(TagScan.pet_id == pet.id)
        .order_by(TagScan.scanned_at.desc())  # type: ignore[attr-defined]
        .limit(5)
    ).all()
    total_scans = session.exec(
        select(TagScan).where(TagScan.pet_id == pet.id)
    ).all()
    scan_count = len(total_scans)

    # Vaccination alerts (upcoming, unsent)
    alerts = session.exec(
        select(VaccinationAlert)
        .where(VaccinationAlert.pet_id == pet.id)
        .where(VaccinationAlert.is_sent == False)  # noqa: E712
        .where(VaccinationAlert.alert_date >= now)
        .order_by(VaccinationAlert.alert_date.asc())  # type: ignore[attr-defined]
        .limit(5)
    ).all()

    # Documents count
    doc_count = len(session.exec(
        select(VaccinationDocument).where(VaccinationDocument.pet_id == pet.id)
    ).all())

    # Vaccination health percentage
    current_vax = [v for v in vaccinations if v.expiration_date > now]
    vax_pct = int((len(current_vax) / len(vaccinations)) * 100) if vaccinations else 0

    # Pet age calculation
    age_str = ''
    if pet.dob:
        delta = now - pet.dob
        years = delta.days // 365
        months = (delta.days % 365) // 30
        if years > 0:
            age_str = f'{years}y {months}m'
        else:
            age_str = f'{months}m'

    # ── Scoped CSS ──
    ui.add_css('''
    .pp-header { display: flex; align-items: center; gap: 20px; margin-bottom: 32px; }
    .pp-meta { font-size: 14px; color: #78716c; margin-top: 2px; }
    .pp-badges { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
    .pp-badge { padding: 3px 10px; border-radius: 9999px; font-size: 11px; font-weight: 600;
                display: inline-flex; align-items: center; gap: 4px; }
    .pp-stats-row { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
    .pp-stat-card {
        flex: 1; min-width: 140px; background: white; border-radius: 10px;
        padding: 16px 20px; border: 1px solid #e7e5e4;
        display: flex; align-items: center; gap: 12px;
    }
    .pp-stat-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
    .pp-stat-value { font-size: 22px; font-weight: 700; color: #1c1917; line-height: 1; }
    .pp-stat-label { font-size: 12px; color: #78716c; margin-top: 2px; }
    .pp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; width: 100%; }
    @media (max-width: 768px) {
        .pp-grid { grid-template-columns: 1fr; }
        .pp-stats-row { flex-direction: column; }
        .pp-header { flex-wrap: wrap; gap: 12px; }
        .pp-stat-card { min-width: 0; }
    }
    .pp-card {
        background: white; border-radius: 12px; padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: 1px solid #e7e5e4;
        width: 100%;
    }
    .pp-card-full { grid-column: 1 / -1; }

    /* Cards in non-overview tabs span full width */
    .q-tab-panel > .pp-card { width: 100%; }
    .pp-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .pp-card-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 700; color: #1c1917; }
    .pp-vax-row {
        display: flex; align-items: center; gap: 12px; padding: 10px 0;
        border-bottom: 1px solid #f5f5f4; font-size: 13px;
    }
    .pp-vax-row:last-child { border-bottom: none; }
    .pp-alert-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; }
    .pp-care-item { display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f5f5f4; }
    .pp-care-item:last-child { border-bottom: none; }
    .pp-scan-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; font-size: 13px; }

    /* NiceGUI tabs — match mockup tab bar styling */
    .pp-nicegui-tabs .q-tab {
        font-size: 13px !important; font-weight: 600 !important;
        text-transform: none !important; padding: 14px 20px !important;
        min-height: unset !important; color: #8a716c !important;
    }
    .pp-nicegui-tabs .q-tab--active { color: var(--pl-primary) !important; }
    .pp-nicegui-tabs .q-tab__indicator { height: 2px !important; background: var(--pl-primary) !important; }
    .pp-nicegui-tabs .q-tab__icon { display: none !important; }
    .pp-nicegui-tabs.q-tabs { border-radius: 0 !important; }
    @media (max-width: 767px) {
        .pp-nicegui-tabs .q-tab { padding: 12px 14px !important; font-size: 12px !important; }
        .pp-tab-bar { margin: 0 -16px !important; padding: 0 16px !important; width: calc(100% + 32px) !important; }
    }

    /* Tab panels — full width, no padding from Quasar */
    .q-tab-panel { padding: 0 !important; padding-top: 24px !important; width: 100% !important; }
    .q-tab-panels { width: 100% !important; }
    .q-tab-panels .q-panel { width: 100% !important; }
    ''')

    # ═══════════════════════════════════════════════════════════════
    # 1. PET HEADER — compact horizontal bar with edit button
    # ═══════════════════════════════════════════════════════════════
    with ui.element('div').classes('pp-header'):
        with ui.element('div').classes('relative').style('flex-shrink: 0;'):
            _pet_avatar(pet, 80)
            # Photo upload overlay button
            if is_verified:
                photo_upload_input = ui.upload(
                    auto_upload=True,
                    max_files=1,
                    on_upload=lambda e, pid=pet.id: _handle_photo_upload(e, pid),
                ).props('accept=".jpg,.jpeg,.png,.webp"').style('display: none;')

                with ui.element('div').classes(
                    'absolute bottom-0 right-0 cursor-pointer'
                ).style(
                    'width: 28px; height: 28px; border-radius: 50%; background: var(--pl-primary); '
                    'display: flex; align-items: center; justify-content: center; '
                    'border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.15);'
                ).on('click', lambda u=photo_upload_input: u.run_method('pickFiles')):
                    ui.icon('photo_camera').style('font-size: 14px; color: white;')

        with ui.element('div').style('flex: 1;'):
            ui.label(pet.name).style(
                'font-size: 28px; font-weight: 700; color: #1c1917; line-height: 1.2;'
            )
            # Meta line
            meta_parts = []
            if pet.breed:
                meta_parts.append(pet.breed)
            if pet.gender and pet.gender != 'Unknown':
                meta_parts.append(pet.gender)
            if age_str:
                meta_parts.append(age_str)
            if meta_parts:
                ui.label(' • '.join(meta_parts)).classes('pp-meta')

            # Badges row
            with ui.element('div').classes('pp-badges'):
                if is_verified:
                    ui.label('Verified').classes('pp-badge').style(
                        'background: #dcfce7; color: #166534;'
                    )
                else:
                    ui.label('Unverified').classes('pp-badge').style(
                        'background: #fef9c3; color: #854d0e;'
                    )
                ui.label(f'Chip: {pet.chip_id}').classes('pp-badge').style(
                    'background: #f0f4fb; color: #1e40af;'
                )

        # Edit Profile button
        _edit_url = f'/pet/{pet.id}/edit'
        ui.button('Edit Profile', icon='edit',
                  on_click=lambda url=_edit_url: ui.navigate.to(url),
        ).style(
            'background: var(--pl-primary); color: white; font-weight: 600; '
            'padding: 10px 24px; border-radius: 8px;'
        ).props('no-caps')

    # ═══════════════════════════════════════════════════════════════
    # 2. QUICK STATS ROW
    # ═══════════════════════════════════════════════════════════════
    with ui.element('div').classes('pp-stats-row'):
        # Vaccinations
        with ui.element('div').classes('pp-stat-card'):
            with ui.element('div').classes('pp-stat-icon').style('background: #dcfce7;'):
                ui.icon('vaccines').style('font-size: 20px; color: #16a34a;')
            with ui.element('div'):
                ui.label(str(len(vaccinations))).classes('pp-stat-value')
                ui.label('Vaccinations').classes('pp-stat-label')

        # Active Tags
        with ui.element('div').classes('pp-stat-card'):
            with ui.element('div').classes('pp-stat-icon').style('background: #dbeafe;'):
                ui.icon('qr_code_2').style('font-size: 20px; color: #2563eb;')
            with ui.element('div'):
                ui.label(str(total_tags)).classes('pp-stat-value')
                ui.label('Active Tags').classes('pp-stat-label')

        # Tag Scans
        with ui.element('div').classes('pp-stat-card'):
            with ui.element('div').classes('pp-stat-icon').style('background: #fef9c3;'):
                ui.icon('radar').style('font-size: 20px; color: #ca8a04;')
            with ui.element('div'):
                ui.label(str(scan_count)).classes('pp-stat-value')
                ui.label('Tag Scans').classes('pp-stat-label')

        # Documents
        with ui.element('div').classes('pp-stat-card'):
            with ui.element('div').classes('pp-stat-icon').style('background: #fae8ff;'):
                ui.icon('description').style('font-size: 20px; color: #a855f7;')
            with ui.element('div'):
                ui.label(str(doc_count)).classes('pp-stat-value')
                ui.label('Documents').classes('pp-stat-label')

    # ═══════════════════════════════════════════════════════════════
    # 3. TABBED CONTENT (matching mockup tab bar — flush, text-only)
    # ═══════════════════════════════════════════════════════════════
    tabs = ui.tabs().classes('w-full pp-nicegui-tabs pp-tab-bar').style(
        'background: white; border-bottom: 1px solid #e7e5e4; '
        'margin: 0 -32px; padding: 0 32px; width: calc(100% + 64px);'
    ).props('no-caps dense inline-label')
    with tabs:
        tab_overview = ui.tab('Overview').props('no-caps')
        tab_care = ui.tab('Care Instructions').props('no-caps')
        tab_documents = ui.tab('Documents').props('no-caps')
        tab_vaccinations = ui.tab('Vaccinations').props('no-caps')
        tab_alerts = ui.tab('Alerts').props('no-caps')
        tab_scans = ui.tab('Location History').props('no-caps')

    with ui.tab_panels(tabs, value=tab_overview).classes('w-full').style(
        'background: transparent; box-shadow: none; padding: 0;'
    ):
        # ────── Overview Tab ──────
        with ui.tab_panel(tab_overview).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-grid'):
                # Medical Status
                with ui.element('div').classes('pp-card'):
                    with ui.element('div').classes('pp-card-header'):
                        with ui.element('div').classes('pp-card-title'):
                            ui.icon('monitor_heart').style('color: #16a34a;')
                            ui.label('Medical Status')
                    health_bg = '#f0fdf4' if vax_pct >= 80 else '#fefce8'
                    health_label = 'Optimal Health' if vax_pct >= 80 else 'Needs Attention'
                    health_color = '#16a34a' if vax_pct >= 80 else '#ca8a04'
                    with ui.element('div').style(
                        f'background: {health_bg}; border-radius: 12px; padding: 24px; '
                        'display: flex; flex-direction: column; align-items: center; gap: 12px;'
                    ):
                        radius = 40
                        circumference = 2 * 3.14159 * radius
                        offset = circumference * (1 - vax_pct / 100)
                        ui.html(f'''
                        <svg width="100" height="100" viewBox="0 0 100 100">
                            <circle cx="50" cy="50" r="{radius}" fill="none"
                                stroke="#e5e7eb" stroke-width="8"/>
                            <circle cx="50" cy="50" r="{radius}" fill="none"
                                stroke="{health_color}" stroke-width="8"
                                stroke-dasharray="{circumference}"
                                stroke-dashoffset="{offset}"
                                stroke-linecap="round"
                                transform="rotate(-90 50 50)"/>
                            <text x="50" y="54" text-anchor="middle"
                                font-size="18" font-weight="700" fill="{health_color}">
                                {vax_pct}%
                            </text>
                        </svg>
                        ''')
                        ui.label(health_label).style(
                            f'font-size: 14px; font-weight: 600; color: {health_color};'
                        )
                        ui.label(
                            f'{len(current_vax)} of {len(vaccinations)} vaccines current'
                        ).style('font-size: 12px; color: #78716c;')

                # Upcoming Alerts
                with ui.element('div').classes('pp-card'):
                    with ui.element('div').classes('pp-card-header'):
                        with ui.element('div').classes('pp-card-title'):
                            ui.icon('notifications_active').style('color: #ea580c;')
                            ui.label('Upcoming Alerts')
                    if alerts:
                        for alert in alerts:
                            days_remaining = max(0, (alert.alert_date - now).days)
                            with ui.element('div').classes('pp-alert-item'):
                                with ui.element('div').style(
                                    'width: 36px; height: 36px; border-radius: 50%; '
                                    'background: #fff7ed; display: flex; align-items: center; '
                                    'justify-content: center; flex-shrink: 0;'
                                ):
                                    ui.icon('event').style('font-size: 18px; color: #ea580c;')
                                with ui.element('div').style('flex: 1; min-width: 0;'):
                                    ui.label(alert.title).style(
                                        'font-size: 13px; font-weight: 600; color: #1c1917;'
                                    )
                                    ui.label(
                                        alert.alert_date.strftime('%b %d, %Y')
                                    ).style('font-size: 11px; color: #78716c;')
                                ui.label(f'{days_remaining}d').style(
                                    'padding: 2px 8px; border-radius: 9999px; font-size: 11px; '
                                    'font-weight: 600; background: #fff7ed; color: #ea580c;'
                                )
                    else:
                        ui.label('No upcoming alerts.').style(
                            'font-size: 13px; color: #78716c; font-style: italic;'
                        )

                # Vaccinations (full width in overview — recent 5)
                with ui.element('div').classes('pp-card pp-card-full'):
                    with ui.element('div').classes('pp-card-header'):
                        with ui.element('div').classes('pp-card-title'):
                            ui.icon('vaccines').style('color: #16a34a;')
                            ui.label('Vaccinations')
                    if vaccinations:
                        for v in vaccinations[:5]:
                            is_current = v.expiration_date > now
                            status_icon = 'check_circle' if is_current else 'warning'
                            status_color = '#16a34a' if is_current else '#ca8a04'
                            with ui.element('div').classes('pp-vax-row'):
                                ui.icon(status_icon).style(
                                    f'font-size: 18px; color: {status_color}; flex-shrink: 0;'
                                )
                                with ui.element('div').style('flex: 1; min-width: 0;'):
                                    ui.label(v.vaccine_name).style(
                                        'font-size: 13px; font-weight: 600; color: #1c1917;'
                                    )
                                    ui.label(v.clinic_name or v.manufacturer or '').style(
                                        'font-size: 11px; color: #78716c;'
                                    )
                                ui.label(
                                    v.date_given.strftime('%b %d, %Y') if v.date_given else '—'
                                ).style('font-size: 12px; color: #78716c; min-width: 80px;')
                                exp_color = '#16a34a' if is_current else '#dc2626'
                                ui.label(
                                    v.expiration_date.strftime('%b %d, %Y') if v.expiration_date else '—'
                                ).style(f'font-size: 12px; font-weight: 600; color: {exp_color}; min-width: 80px;')
                    else:
                        ui.label('No vaccinations recorded yet.').style(
                            'font-size: 13px; color: #78716c; font-style: italic;'
                        )

                # Care Instructions (from Pet model fields)
                with ui.element('div').classes('pp-card'):
                    with ui.element('div').classes('pp-card-header'):
                        with ui.element('div').classes('pp-card-title'):
                            ui.icon('favorite').style('color: #2563eb;')
                            ui.label('Care Instructions')
                    _overview_care = [
                        ('restaurant', 'Feeding', f'{pet.feeds_per_day} meals/day' if pet.feeds_per_day else None),
                        ('no_food', 'Dietary Notes', pet.dietary_notes),
                        ('directions_run', 'Exercise', pet.exercise_needs),
                    ]
                    _visible = [(i, l, v) for i, l, v in _overview_care if v]
                    if _visible:
                        for icon_name, label, value in _visible:
                            with ui.element('div').classes('pp-care-item'):
                                with ui.element('div').style(
                                    'width: 32px; height: 32px; border-radius: 8px; '
                                    'background: #f0f4fb; display: flex; align-items: center; '
                                    'justify-content: center; flex-shrink: 0;'
                                ):
                                    ui.icon(icon_name).style('font-size: 16px; color: #2563eb;')
                                with ui.element('div').style('flex: 1; min-width: 0;'):
                                    ui.label(label).style(
                                        'font-size: 13px; font-weight: 600; color: #1c1917;'
                                    )
                                    ui.label(value).style(
                                        'font-size: 12px; color: #78716c; margin-top: 2px;'
                                    )
                    else:
                        ui.label('No care instructions added.').style(
                            'font-size: 13px; color: #78716c; font-style: italic;'
                        )

                # Last Known Location
                with ui.element('div').classes('pp-card'):
                    with ui.element('div').classes('pp-card-header'):
                        with ui.element('div').classes('pp-card-title'):
                            ui.icon('location_on').style('color: #16a34a;')
                            ui.label('Last Known Location')

                    import json as _json
                    loc_map_id = f'loc-map-{uuid.uuid4().hex[:8]}'

                    has_scan_coords = pet.last_scan_latitude is not None and pet.last_scan_longitude is not None
                    owner = pet.owner
                    owner_city = owner.city if owner else None
                    owner_country = owner.country if owner else None
                    owner_address = owner.address if owner else None

                    if has_scan_coords:
                        location_label = pet.last_scan_location or 'Last scanned location'
                        location_sub = pet.last_scan_at.strftime('%b %d, %Y at %H:%M UTC') if pet.last_scan_at else ''
                    elif owner_city or owner_country:
                        location_label = ', '.join(p for p in [owner_city, owner_country] if p)
                        location_sub = "Owner's registered address"
                    else:
                        location_label = 'Location unavailable'
                        location_sub = 'No scan data or owner address on file'

                    with ui.row().classes(
                        'w-full items-center gap-3 p-3 rounded-lg mb-3'
                    ).style('background: #f0fdf4; border: 1px solid rgba(22,163,74,0.15);'):
                        ui.icon('my_location').style('font-size: 18px; color: #16a34a;')
                        with ui.column().classes('gap-0'):
                            ui.label(location_label).style(
                                'font-size: 13px; font-weight: 600; color: #1c1917;'
                            )
                            if location_sub:
                                ui.label(location_sub).style(
                                    'font-size: 11px; color: #78716c;'
                                )

                    if has_scan_coords or owner_city or owner_country:
                        ui.element('div').props(f'id="{loc_map_id}"').style(
                            'width: 100%; height: 200px; border-radius: 8px; overflow: hidden;'
                        )
                        ui.add_head_html(
                            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
                        )
                        ui.add_head_html(
                            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
                        )

                        if has_scan_coords:
                            lat = pet.last_scan_latitude
                            lon = pet.last_scan_longitude
                            ui.run_javascript(f'''
                                (function() {{
                                    function initMap() {{
                                        var el = document.getElementById("{loc_map_id}");
                                        if (!el) return setTimeout(initMap, 100);
                                        if (el._leaflet_id) return;
                                        var map = L.map("{loc_map_id}", {{
                                            zoomControl: false, attributionControl: false,
                                            dragging: false, scrollWheelZoom: false,
                                            doubleClickZoom: false, boxZoom: false,
                                            keyboard: false, touchZoom: false,
                                        }}).setView([{lat}, {lon}], 13);
                                        L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{maxZoom: 18}}).addTo(map);
                                        L.circleMarker([{lat}, {lon}], {{
                                            radius: 25, color: "#16a34a", fillColor: "#bbf7d0",
                                            fillOpacity: 0.4, weight: 2,
                                        }}).addTo(map);
                                    }}
                                    initMap();
                                }})();
                            ''')
                        else:
                            location_query = ', '.join(
                                p for p in [owner_address, owner_city, owner_country] if p
                            )
                            safe_query = _json.dumps(location_query)
                            ui.run_javascript(f'''
                                (function() {{
                                    var query = {safe_query};
                                    function initMap() {{
                                        var el = document.getElementById("{loc_map_id}");
                                        if (!el) return setTimeout(initMap, 100);
                                        if (el._leaflet_id) return;
                                        var map = L.map("{loc_map_id}", {{
                                            zoomControl: false, attributionControl: false,
                                            dragging: false, scrollWheelZoom: false,
                                            doubleClickZoom: false, boxZoom: false,
                                            keyboard: false, touchZoom: false,
                                        }}).setView([20, 0], 2);
                                        L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{maxZoom: 18}}).addTo(map);
                                        fetch("https://nominatim.openstreetmap.org/search?format=json&q=" + encodeURIComponent(query) + "&limit=1")
                                            .then(r => r.json())
                                            .then(data => {{
                                                if (data && data.length > 0) {{
                                                    var lat = parseFloat(data[0].lat);
                                                    var lon = parseFloat(data[0].lon);
                                                    map.setView([lat, lon], 13);
                                                    L.circleMarker([lat, lon], {{
                                                        radius: 25, color: "#16a34a", fillColor: "#bbf7d0",
                                                        fillOpacity: 0.4, weight: 2,
                                                    }}).addTo(map);
                                                }}
                                            }});
                                    }}
                                    initMap();
                                }})();
                            ''')
                    else:
                        with ui.element('div').classes(
                            'w-full flex items-center justify-center'
                        ).style(
                            'height: 200px; background: #f5f5f4; border-radius: 8px;'
                        ):
                            ui.icon('map').style(
                                'font-size: 48px; color: #a8a29e; opacity: 0.5;'
                            )

        # ────── Care Instructions Tab (uses Pet model fields) ──────
        with ui.tab_panel(tab_care).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-card'):
                with ui.element('div').classes('pp-card-header'):
                    with ui.element('div').classes('pp-card-title'):
                        ui.icon('favorite').style('color: #2563eb;')
                        ui.label('Care Instructions')

                    async def open_edit_care_dialog():
                        with ui.dialog() as care_dlg, ui.card().classes('p-8').style(
                            'max-width: 600px; border-radius: 12px;'
                        ):
                            ui.label('Edit Care Instructions').style(
                                'font-size: 18px; font-weight: 700; margin-bottom: 4px;'
                            )
                            ui.label(
                                'Update care details for sitters, groomers, or service providers.'
                            ).style('font-size: 13px; color: var(--pl-on-surface-variant); margin-bottom: 20px;')

                            feeds_input = ui.input(
                                'Feeds Per Day', value=str(pet.feeds_per_day or ''),
                                placeholder='e.g. 2',
                            ).classes('w-full').props('outlined dense')
                            dietary_input = ui.textarea(
                                'Dietary Notes', value=pet.dietary_notes or '',
                                placeholder='Allergies, special diet, preferred food...',
                            ).classes('w-full').props('outlined rows=2')
                            exercise_input = ui.input(
                                'Exercise Needs', value=pet.exercise_needs or '',
                                placeholder='e.g. 30 min walk twice daily',
                            ).classes('w-full').props('outlined dense')
                            energy_input = ui.select(
                                options={'Low': 'Low', 'Moderate': 'Moderate', 'High': 'High', 'Very High': 'Very High'},
                                label='Energy Level',
                                value=pet.energy_level or 'Moderate',
                            ).classes('w-full').props('outlined dense')
                            alone_input = ui.input(
                                'Max Hours Alone', value=str(pet.max_alone_hours or ''),
                                placeholder='e.g. 4',
                            ).classes('w-full').props('outlined dense')
                            temperament_input = ui.textarea(
                                'Temperament', value=pet.temperament or '',
                                placeholder='e.g. Friendly with kids, anxious around dogs',
                            ).classes('w-full').props('outlined rows=2')
                            medical_input = ui.textarea(
                                'Medical Conditions', value=pet.medical_conditions or '',
                                placeholder='Ongoing conditions (e.g. arthritis, diabetes)',
                            ).classes('w-full').props('outlined rows=2')
                            care_notes_input = ui.textarea(
                                'Additional Care Notes', value=pet.care_notes or '',
                                placeholder='Any other observations for caregivers...',
                            ).classes('w-full').props('outlined rows=3')

                            ui.separator().classes('my-3')
                            ui.label('Emergency Contact').style(
                                'font-size: 14px; font-weight: 700; color: var(--pl-on-surface);'
                            )

                            ec_name_input = ui.input(
                                'Contact Name', value=pet.emergency_contact_name or '',
                                placeholder='e.g. Jane Smith',
                            ).classes('w-full').props('outlined dense')
                            ec_phone_input = ui.input(
                                'Contact Phone', value=pet.emergency_contact_phone or '',
                                placeholder='e.g. +1 555-123-4567',
                            ).classes('w-full').props('outlined dense')

                            ui.separator().classes('my-3')
                            ui.label('Pet Clinic').style(
                                'font-size: 14px; font-weight: 700; color: var(--pl-on-surface);'
                            )

                            clinic_name_input = ui.input(
                                'Clinic Name', value=pet.clinic_name or '',
                                placeholder='e.g. Happy Paws Veterinary',
                            ).classes('w-full').props('outlined dense')
                            clinic_address_input = ui.input(
                                'Clinic Address', value=pet.clinic_address or '',
                                placeholder='e.g. 123 Main St, Springfield',
                            ).classes('w-full').props('outlined dense')
                            clinic_phone_input = ui.input(
                                'Clinic Phone', value=pet.clinic_phone or '',
                                placeholder='e.g. +1 555-987-6543',
                            ).classes('w-full').props('outlined dense')

                            async def save_care():
                                with Session(engine) as s:
                                    db_pet = s.get(Pet, pet.id)
                                    if not db_pet:
                                        ui.notify('Pet not found.', type='negative')
                                        return
                                    feeds_val = feeds_input.value.strip() if feeds_input.value else ''
                                    db_pet.feeds_per_day = int(feeds_val) if feeds_val.isdigit() else None
                                    db_pet.dietary_notes = dietary_input.value.strip() or None
                                    db_pet.exercise_needs = exercise_input.value.strip() or None
                                    db_pet.energy_level = energy_input.value or None
                                    alone_val = alone_input.value.strip() if alone_input.value else ''
                                    db_pet.max_alone_hours = int(alone_val) if alone_val.isdigit() else None
                                    db_pet.temperament = temperament_input.value.strip() or None
                                    db_pet.medical_conditions = medical_input.value.strip() or None
                                    db_pet.care_notes = care_notes_input.value.strip() or None
                                    db_pet.emergency_contact_name = ec_name_input.value.strip() or None
                                    db_pet.emergency_contact_phone = ec_phone_input.value.strip() or None
                                    db_pet.clinic_name = clinic_name_input.value.strip() or None
                                    db_pet.clinic_address = clinic_address_input.value.strip() or None
                                    db_pet.clinic_phone = clinic_phone_input.value.strip() or None
                                    s.add(db_pet)
                                    s.commit()
                                care_dlg.close()
                                ui.notify('Care instructions updated!', type='positive')
                                ui.navigate.to(f'/pet/{pet.id}')

                            with ui.row().classes('w-full justify-end gap-3 mt-4'):
                                ui.button('Cancel', on_click=care_dlg.close).props(
                                    'flat no-caps'
                                ).style('color: var(--pl-on-surface-variant);')
                                ui.button(
                                    'Save Changes', icon='save', on_click=save_care,
                                ).style(
                                    'background: var(--pl-primary); color: white; font-weight: 600;'
                                ).props('no-caps')

                        care_dlg.open()

                    ui.button(
                        'Edit', icon='edit',
                        on_click=open_edit_care_dialog,
                    ).props('flat small no-caps').style(
                        'color: var(--pl-primary); font-weight: 600; font-size: 12px;'
                    )

                # Display care fields from Pet model
                _care_fields = [
                    ('restaurant', 'Feeding', f'{pet.feeds_per_day} meals/day' if pet.feeds_per_day else None),
                    ('no_food', 'Dietary Notes', pet.dietary_notes),
                    ('directions_run', 'Exercise Needs', pet.exercise_needs),
                    ('bolt', 'Energy Level', pet.energy_level),
                    ('schedule', 'Max Time Alone', f'{pet.max_alone_hours} hours' if pet.max_alone_hours else None),
                    ('mood', 'Temperament', pet.temperament),
                    ('medical_services', 'Medical Conditions', pet.medical_conditions),
                    ('notes', 'Care Notes', pet.care_notes),
                    ('contact_emergency', 'Emergency Contact', f'{pet.emergency_contact_name} — {pet.emergency_contact_phone}' if pet.emergency_contact_name else None),
                    ('local_hospital', 'Pet Clinic', '\n'.join(filter(None, [pet.clinic_name, pet.clinic_address, pet.clinic_phone])) if pet.clinic_name else None),
                ]
                has_any = any(val for _, _, val in _care_fields)

                if has_any:
                    for icon_name, label, value in _care_fields:
                        if not value:
                            continue
                        with ui.element('div').style(
                            'padding: 14px 16px; border-radius: 10px; background: #f0f4fb; '
                            'border: 1px solid #e7e5e4; margin-bottom: 10px; '
                            'display: flex; align-items: flex-start; gap: 12px;'
                        ):
                            with ui.element('div').style(
                                'width: 32px; height: 32px; border-radius: 8px; '
                                'background: white; display: flex; align-items: center; '
                                'justify-content: center; flex-shrink: 0;'
                            ):
                                ui.icon(icon_name).style('font-size: 16px; color: #2563eb;')
                            with ui.element('div').style('flex: 1; min-width: 0;'):
                                ui.label(label).style(
                                    'font-size: 11px; font-weight: 600; color: #78716c; '
                                    'text-transform: uppercase; letter-spacing: 0.5px;'
                                )
                                ui.label(value).style(
                                    'font-size: 14px; color: #1c1917; margin-top: 2px; line-height: 1.5;'
                                )
                else:
                    with ui.column().classes('items-center gap-3 py-8'):
                        ui.icon('edit_note').style('font-size: 40px; color: #d6d3d1;')
                        ui.label('No care instructions yet.').style(
                            'font-size: 14px; color: #78716c;'
                        )
                        ui.label(
                            'Add feeding schedules, exercise needs, medical conditions, '
                            'and notes for service providers.'
                        ).style('font-size: 12px; color: #a8a29e; text-align: center; max-width: 320px;')
                        ui.button(
                            'Add Care Instructions', icon='edit',
                            on_click=open_edit_care_dialog,
                        ).style(
                            'background: var(--pl-primary); color: white; font-weight: 600; '
                            'padding: 10px 24px; border-radius: 8px; margin-top: 8px;'
                        ).props('no-caps')

        # ────── Documents Tab ──────
        with ui.tab_panel(tab_documents).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-card'):
                with ui.element('div').classes('pp-card-header'):
                    with ui.element('div').classes('pp-card-title'):
                        ui.icon('description').style('color: #a855f7;')
                        ui.label('Pet Documents')

                    async def open_upload_dialog():
                        with ui.dialog() as upload_dlg, ui.card().classes('p-8').style(
                            'max-width: 480px; border-radius: 12px;'
                        ):
                            ui.label('Upload Document').style(
                                'font-size: 18px; font-weight: 700; margin-bottom: 4px;'
                            )
                            ui.label('Upload a vet report, vaccination record, or any pet document (PDF, JPG, PNG, max 10MB).').style(
                                'font-size: 13px; color: var(--pl-on-surface-variant); margin-bottom: 20px;'
                            )

                            doc_name_input = ui.input(
                                label='Document Name',
                                placeholder='e.g. Rabies Certificate 2026',
                            ).classes('w-full').props('outlined dense')

                            doc_desc_input = ui.textarea(
                                label='Description (optional)',
                                placeholder='Any notes about this document...',
                            ).classes('w-full').props('outlined dense rows=2')

                            uploaded_file_data = {'content': None, 'name': None, 'type': None}

                            async def on_file_selected(e):
                                file = e.file
                                if not file:
                                    return
                                uploaded_file_data['content'] = await file.read()
                                uploaded_file_data['name'] = file.name or 'document.pdf'
                                uploaded_file_data['type'] = file.content_type or 'application/pdf'

                            ui.upload(
                                label='Choose File',
                                on_upload=on_file_selected,
                                auto_upload=True,
                                max_file_size=10 * 1024 * 1024,
                            ).props('accept=".pdf,.jpg,.jpeg,.png,.webp"').classes('w-full')

                            async def submit_upload():
                                if not uploaded_file_data['content']:
                                    ui.notify('Please select a file first.', type='warning')
                                    return
                                import httpx as _httpx
                                from nicegui import context
                                import os as _os
                                base_url = _os.getenv('BASE_URL', 'http://localhost:8080')
                                cookies = context.client.request.cookies
                                data = {}
                                if doc_name_input.value and doc_name_input.value.strip():
                                    data['document_name'] = doc_name_input.value.strip()
                                if doc_desc_input.value and doc_desc_input.value.strip():
                                    data['description'] = doc_desc_input.value.strip()
                                async with _httpx.AsyncClient(base_url=base_url) as client:
                                    resp = await client.post(
                                        f'/api/v1/pets/{pet.id}/vaccinations/upload',
                                        files={'file': (uploaded_file_data['name'], uploaded_file_data['content'], uploaded_file_data['type'])},
                                        data=data,
                                        cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                                    )
                                    if resp.status_code == 200:
                                        upload_dlg.close()
                                        ui.notify('Document uploaded!', type='positive')
                                        ui.navigate.to(f'/pet/{pet.id}')
                                    elif resp.status_code == 403:
                                        ui.notify('Verified or Guardian subscription required.', type='warning')
                                    else:
                                        detail = resp.json().get('detail', 'Upload failed.')
                                        ui.notify(detail, type='negative')

                            with ui.row().classes('w-full justify-end mt-4 gap-2'):
                                ui.button('Cancel', on_click=upload_dlg.close).props(
                                    'flat no-caps'
                                ).style('color: var(--pl-on-surface-variant);')
                                ui.button('Upload', icon='cloud_upload', on_click=submit_upload).props(
                                    'no-caps'
                                ).style('background: #a03a21; color: white;')

                        upload_dlg.open()

                    ui.button(
                        '+ Upload', icon='cloud_upload',
                        on_click=open_upload_dialog,
                    ).props('flat small no-caps').style(
                        'color: var(--pl-primary); font-weight: 600; font-size: 12px;'
                    )

                docs = session.exec(
                    select(VaccinationDocument)
                    .where(VaccinationDocument.pet_id == pet.id)
                    .order_by(VaccinationDocument.uploaded_at.desc())
                ).all()
                if docs:
                    for doc in docs:
                        _render_document_row(doc, pet)
                else:
                    ui.label('No documents uploaded yet.').style(
                        'font-size: 13px; color: #78716c; font-style: italic;'
                    )

        # ────── Vaccinations Tab ──────
        with ui.tab_panel(tab_vaccinations).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-card'):
                with ui.element('div').classes('pp-card-header'):
                    with ui.element('div').classes('pp-card-title'):
                        ui.icon('vaccines').style('color: #16a34a;')
                        ui.label('All Vaccinations')

                    async def open_add_vaccination_dialog():
                        from app.data import get_vaccine_options_for_dropdown
                        vaccine_options = get_vaccine_options_for_dropdown(pet.pet_species)
                        with ui.dialog() as vax_dlg, ui.card().classes('p-8').style(
                            'max-width: 720px; border-radius: 12px;'
                        ):
                            ui.label('Add Vaccination Records').classes('pl-heading-lg').style(
                                "margin-bottom: 0.5rem;"
                            )
                            ui.label(
                                'Fill in one row per vaccine. Fields match NASPHV Form 51 requirements.'
                            ).style('font-size: 14px; color: var(--pl-on-surface-variant); margin-bottom: 1.5rem;')

                            rows_container = ui.column().classes('w-full gap-3')
                            vaccine_rows = []

                            def add_row():
                                with rows_container:
                                    row_data = {}
                                    with ui.column().classes('w-full gap-3 p-4 rounded-lg').style(
                                        'background: #fafafa; border: 1px solid #e7e5e4;'
                                    ):
                                        row_data['name'] = ui.select(
                                            options=vaccine_options, label='Vaccine',
                                            with_input=True,
                                        ).classes('w-full').props('outlined dense use-input input-debounce="200"')
                                        with ui.row().classes('w-full gap-3'):
                                            row_data['manufacturer'] = ui.input(
                                                'Manufacturer'
                                            ).classes('flex-1').props('outlined dense')
                                            row_data['serial'] = ui.input(
                                                'Serial/Lot #'
                                            ).classes('flex-1').props('outlined dense')
                                        with ui.row().classes('w-full gap-3'):
                                            row_data['date_given'] = ui.input(
                                                'Date Given'
                                            ).classes('flex-1').props('outlined dense type=date')
                                            row_data['expiration'] = ui.input(
                                                'Expires'
                                            ).classes('flex-1').props('outlined dense type=date')
                                    vaccine_rows.append(row_data)

                            add_row()
                            ui.button(
                                '+ Add Another Vaccine', on_click=add_row,
                            ).props('flat no-caps').style(
                                'color: #3b82f6; font-weight: 600; font-size: 13px;'
                            )

                            async def save_all_vaccinations():
                                saved_count = 0
                                errors = []
                                with Session(engine) as s:
                                    for i, row in enumerate(vaccine_rows):
                                        vname = row['name'].value
                                        vdate = row['date_given'].value
                                        vexp = row['expiration'].value
                                        if not vname:
                                            continue
                                        if not vdate or not vexp:
                                            errors.append(f'Row {i+1}: Date Given and Expiration are required.')
                                            continue
                                        try:
                                            new_v = Vaccination(
                                                pet_id=pet.id,
                                                vaccine_name=vname,
                                                manufacturer=row['manufacturer'].value.strip() or '',
                                                serial_number=row['serial'].value.strip() or '',
                                                date_given=datetime.strptime(vdate, '%Y-%m-%d'),
                                                expiration_date=datetime.strptime(vexp, '%Y-%m-%d'),
                                                administering_vet='',
                                                clinic_name='',
                                            )
                                            record_data = new_v.model_dump(
                                                exclude={"id", "pet_id", "record_hash", "pet"}
                                            )
                                            new_v.record_hash = hash_service.hash_record(record_data)
                                            s.add(new_v)
                                            s.add(LedgerEvent(
                                                pet_id=pet.id,
                                                event_type="VACCINATION",
                                                description=f"Vaccination added: {vname}",
                                            ))
                                            saved_count += 1
                                        except Exception as e:
                                            errors.append(f'Row {i+1}: {str(e)}')
                                    if saved_count > 0:
                                        s.commit()
                                if errors:
                                    for err in errors:
                                        ui.notify(err, type='warning')
                                if saved_count > 0:
                                    vax_dlg.close()
                                    ui.notify(
                                        f'{saved_count} record{"s" if saved_count > 1 else ""} added!',
                                        type='positive',
                                    )
                                    ui.navigate.to(f'/pet/{pet.id}')
                                elif not errors:
                                    ui.notify('No records to save.', type='info')

                            with ui.row().classes('w-full justify-end gap-3 mt-4'):
                                ui.button('Cancel', on_click=vax_dlg.close).props(
                                    'flat no-caps'
                                ).style('color: var(--pl-on-surface-variant);')
                                save_vax_btn = ui.button(
                                    'Save Records', icon='save',
                                ).style(
                                    'background: var(--pl-primary); color: white; font-weight: 600;'
                                ).props('no-caps')

                                async def _save_vax_guarded():
                                    async with _with_loading(save_vax_btn):
                                        await save_all_vaccinations()
                                save_vax_btn.on_click(_save_vax_guarded)

                        vax_dlg.open()

                    ui.button(
                        '+ Add Vaccination', icon='add',
                        on_click=open_add_vaccination_dialog,
                    ).props('flat small no-caps').style(
                        'color: var(--pl-primary); font-weight: 600; font-size: 12px;'
                    )

                if vaccinations:
                    for v in vaccinations:
                        is_current = v.expiration_date > now
                        status_icon = 'check_circle' if is_current else 'warning'
                        status_color = '#16a34a' if is_current else '#ca8a04'
                        status_bg = '#f0fdf4' if is_current else '#fefce8'
                        status_text = 'Current' if is_current else 'Expired'

                        with ui.element('div').style(
                            f'padding: 16px; border-radius: 10px; background: {status_bg}; '
                            'border: 1px solid #e7e5e4; margin-bottom: 12px;'
                        ):
                            with ui.row().classes('w-full items-center justify-between mb-2'):
                                with ui.row().classes('items-center gap-3'):
                                    ui.icon(status_icon).style(
                                        f'font-size: 20px; color: {status_color};'
                                    )
                                    ui.label(v.vaccine_name).style(
                                        'font-size: 15px; font-weight: 700; color: #1c1917;'
                                    )
                                ui.label(status_text).style(
                                    f'padding: 3px 10px; border-radius: 9999px; font-size: 11px; '
                                    f'font-weight: 600; background: white; color: {status_color};'
                                )

                            with ui.element('div').style(
                                'display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; '
                                'margin-top: 8px; padding-left: 32px;'
                            ):
                                if v.manufacturer:
                                    with ui.column().classes('gap-0'):
                                        ui.label('Manufacturer').style(
                                            'font-size: 10px; font-weight: 600; color: #78716c; '
                                            'text-transform: uppercase; letter-spacing: 0.5px;'
                                        )
                                        ui.label(v.manufacturer).style(
                                            'font-size: 13px; color: #1c1917;'
                                        )
                                if v.serial_number:
                                    with ui.column().classes('gap-0'):
                                        ui.label('Serial / Lot #').style(
                                            'font-size: 10px; font-weight: 600; color: #78716c; '
                                            'text-transform: uppercase; letter-spacing: 0.5px;'
                                        )
                                        ui.label(v.serial_number).style(
                                            'font-size: 13px; color: #1c1917; font-family: monospace;'
                                        )
                                with ui.column().classes('gap-0'):
                                    ui.label('Date Given').style(
                                        'font-size: 10px; font-weight: 600; color: #78716c; '
                                        'text-transform: uppercase; letter-spacing: 0.5px;'
                                    )
                                    ui.label(
                                        v.date_given.strftime('%b %d, %Y') if v.date_given else '—'
                                    ).style('font-size: 13px; color: #1c1917;')
                                with ui.column().classes('gap-0'):
                                    ui.label('Expires').style(
                                        'font-size: 10px; font-weight: 600; color: #78716c; '
                                        'text-transform: uppercase; letter-spacing: 0.5px;'
                                    )
                                    ui.label(
                                        v.expiration_date.strftime('%b %d, %Y') if v.expiration_date else '—'
                                    ).style(f'font-size: 13px; font-weight: 600; color: {status_color};')
                                if v.administering_vet:
                                    with ui.column().classes('gap-0'):
                                        ui.label('Vet').style(
                                            'font-size: 10px; font-weight: 600; color: #78716c; '
                                            'text-transform: uppercase; letter-spacing: 0.5px;'
                                        )
                                        ui.label(v.administering_vet).style(
                                            'font-size: 13px; color: #1c1917;'
                                        )
                                if v.clinic_name:
                                    with ui.column().classes('gap-0'):
                                        ui.label('Clinic').style(
                                            'font-size: 10px; font-weight: 600; color: #78716c; '
                                            'text-transform: uppercase; letter-spacing: 0.5px;'
                                        )
                                        ui.label(v.clinic_name).style(
                                            'font-size: 13px; color: #1c1917;'
                                        )

                            if v.record_hash:
                                with ui.row().classes('items-center gap-2 mt-3').style('padding-left: 32px;'):
                                    ui.icon('verified').style('font-size: 14px; color: #16a34a;')
                                    ui.label(f'SHA-256: {v.record_hash[:16]}...').style(
                                        'font-size: 10px; color: #78716c; font-family: monospace;'
                                    )
                else:
                    ui.label('No vaccinations recorded yet.').style(
                        'font-size: 13px; color: #78716c; font-style: italic;'
                    )

        # ────── Alerts Tab ──────
        with ui.tab_panel(tab_alerts).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-card'):
                with ui.element('div').classes('pp-card-header'):
                    with ui.element('div').classes('pp-card-title'):
                        ui.icon('notifications_active').style('color: #ea580c;')
                        ui.label('Vaccination & Appointment Alerts')

                    async def open_add_alert_dialog():
                        with ui.dialog() as alert_dlg, ui.card().classes('p-8').style(
                            'max-width: 480px; border-radius: 12px;'
                        ):
                            ui.label('Add Alert').style(
                                'font-size: 18px; font-weight: 700; margin-bottom: 4px;'
                            )
                            ui.label('Set a reminder for a vaccination or appointment.').style(
                                'font-size: 13px; color: var(--pl-on-surface-variant); margin-bottom: 20px;'
                            )

                            alert_title_input = ui.input('Alert Title', placeholder='e.g. Rabies Booster').classes(
                                'w-full'
                            ).props('outlined dense')
                            alert_date_input = ui.input('Alert Date').classes(
                                'w-full'
                            ).props('outlined dense type=date')
                            alert_desc_input = ui.textarea(
                                'Description (optional)', placeholder='Additional notes...'
                            ).classes('w-full').props('outlined rows=2')

                            async def save_alert():
                                title_val = alert_title_input.value.strip() if alert_title_input.value else ''
                                date_val = alert_date_input.value.strip() if alert_date_input.value else ''
                                if not title_val:
                                    ui.notify('Title is required.', type='warning')
                                    return
                                if not date_val:
                                    ui.notify('Date is required.', type='warning')
                                    return
                                try:
                                    alert_date = datetime.strptime(date_val, '%Y-%m-%d')
                                except ValueError:
                                    ui.notify('Invalid date format.', type='warning')
                                    return
                                with Session(engine) as s:
                                    from ...models import VaccinationAlert as VA
                                    new_alert = VA(
                                        pet_id=pet.id,
                                        user_id=pet.owner_id,
                                        alert_type='appointment',
                                        alert_date=alert_date,
                                        title=title_val,
                                        description=alert_desc_input.value.strip() if alert_desc_input.value else None,
                                    )
                                    s.add(new_alert)
                                    s.commit()
                                alert_dlg.close()
                                ui.notify('Alert added!', type='positive')
                                ui.navigate.to(f'/pet/{pet.id}')

                            with ui.row().classes('w-full justify-end gap-3 mt-4'):
                                ui.button('Cancel', on_click=alert_dlg.close).props(
                                    'flat no-caps'
                                ).style('color: var(--pl-on-surface-variant);')
                                ui.button('Save Alert', icon='add', on_click=save_alert).style(
                                    'background: var(--pl-primary); color: white; font-weight: 600;'
                                ).props('no-caps')

                        alert_dlg.open()

                    ui.button(
                        '+ Add Alert', icon='add',
                        on_click=open_add_alert_dialog,
                    ).props('flat small no-caps').style(
                        'color: var(--pl-primary); font-weight: 600; font-size: 12px;'
                    )

                if alerts:
                    for alert in alerts:
                        days_remaining = max(0, (alert.alert_date - now).days)
                        with ui.element('div').classes('pp-alert-item'):
                            with ui.element('div').style(
                                'width: 36px; height: 36px; border-radius: 50%; '
                                'background: #fff7ed; display: flex; align-items: center; '
                                'justify-content: center; flex-shrink: 0;'
                            ):
                                ui.icon('event').style('font-size: 18px; color: #ea580c;')
                            with ui.element('div').style('flex: 1; min-width: 0;'):
                                ui.label(alert.title).style(
                                    'font-size: 13px; font-weight: 600; color: #1c1917;'
                                )
                                ui.label(
                                    alert.alert_date.strftime('%b %d, %Y')
                                ).style('font-size: 11px; color: #78716c;')
                            ui.label(f'{days_remaining}d').style(
                                'padding: 2px 8px; border-radius: 9999px; font-size: 11px; '
                                'font-weight: 600; background: #fff7ed; color: #ea580c;'
                            )
                else:
                    ui.label('No upcoming alerts.').style(
                        'font-size: 13px; color: #78716c; font-style: italic;'
                    )

        # ────── Location History Tab ──────
        with ui.tab_panel(tab_scans).classes('p-0 pt-6'):
            with ui.element('div').classes('pp-card'):
                with ui.element('div').classes('pp-card-header'):
                    with ui.element('div').classes('pp-card-title'):
                        ui.icon('radar').style('color: #ca8a04;')
                        ui.label('Location History')
                all_scans = session.exec(
                    select(TagScan)
                    .where(TagScan.pet_id == pet.id)
                    .order_by(TagScan.scanned_at.desc())
                    .limit(20)
                ).all()
                if all_scans:
                    for scan in all_scans:
                        dot_color = '#dc2626' if scan.scan_method == 'QR' else '#2563eb'
                        delta_secs = (now - scan.scanned_at).total_seconds()
                        if delta_secs < 3600:
                            rel_time = f'{int(delta_secs // 60)}m ago'
                        elif delta_secs < 86400:
                            rel_time = f'{int(delta_secs // 3600)}h ago'
                        else:
                            rel_time = f'{int(delta_secs // 86400)}d ago'
                        with ui.element('div').classes('pp-scan-item'):
                            ui.element('div').style(
                                f'width: 10px; height: 10px; border-radius: 50%; '
                                f'background: {dot_color}; flex-shrink: 0;'
                            )
                            with ui.element('div').style('flex: 1; min-width: 0;'):
                                ui.label(f'{scan.scan_method} Tag Scan').style(
                                    'font-size: 13px; font-weight: 600; color: #1c1917;'
                                )
                            location = scan.city or scan.country or 'Unknown location'
                            ui.label(location).style('font-size: 12px; color: #78716c;')
                            ui.label(rel_time).style(
                                'font-size: 11px; color: #a8a29e; min-width: 50px; text-align: right;'
                            )
                else:
                    ui.label('No scans recorded yet.').style(
                        'font-size: 13px; color: #78716c; font-style: italic;'
                    )


# ─────────────────────────────────────────────────────────────
# VERIFIED FEATURES — care instructions, alerts, transfer, upload
# ─────────────────────────────────────────────────────────────

def _get_user_tier(user_id, session) -> str:
    """Get subscription tier for a user."""
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user_id)
    ).first()
    if not sub or sub.status != "active":
        return "free"
    return sub.tier


def _render_verified_features(pet, session):
    """Render the premium features panel for Verified+ subscribers."""
    if not pet.owner_id:
        return

    tier = _get_user_tier(pet.owner_id, session)
    is_verified = tier in ("verified", "guardian")

    # Show upgrade prompt for free users
    if not is_verified:
        with ui.element('div').classes('w-full mt-6 p-8 rounded-xl').style(
            'background: #fafafa; border: 1px solid #e7e5e4;'
        ):
            with ui.row().classes('w-full items-center justify-between flex-wrap gap-4'):
                with ui.column().classes('gap-1'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('verified').style('font-size: 24px; color: var(--pl-primary);')
                        ui.label('Unlock Premium Features').classes('pl-heading-lg')
                    ui.label(
                        'Get vaccination alerts, care instructions for sitters, '
                        'document storage, and secure ownership transfer.'
                    ).style('font-size: 14px; color: var(--pl-on-surface-variant); max-width: 480px;')
                ui.button(
                    'View Plans', icon='upgrade',
                    on_click=lambda: ui.navigate.to('/pricing'),
                ).style(
                    'background: var(--pl-primary); color: white; font-weight: 600; '
                    'padding: 12px 28px; border-radius: 8px;'
                ).props('no-caps')
        return

    # ── Verified user: show feature panels ──
    with ui.element('div').classes('w-full mt-6'):
        with ui.row().classes('items-center gap-2 mb-4'):
            ui.icon('verified').style('font-size: 24px; color: #16a34a;')
            ui.label('Verified Features').classes('pl-heading-xl')
            ui.label(tier.capitalize()).style(
                'padding: 2px 10px; background: #dcfce7; color: #166534; '
                'font-size: 11px; font-weight: 700; border-radius: 9999px; '
                'text-transform: uppercase;'
            )

    with ui.row().classes('w-full gap-6 mt-2 flex-wrap items-stretch'):
        with ui.element('div').classes('flex-1').style('min-width: 0;'):
            _render_alerts_panel(pet, session)
        with ui.element('div').classes('flex-1').style('min-width: 0;'):
            _render_transfer_panel(pet, session)


def _render_alerts_panel(pet, session):
    """Vaccination/appointment alerts panel."""
    alerts = session.exec(
        select(VaccinationAlert)
        .where(VaccinationAlert.pet_id == pet.id)
        .order_by(VaccinationAlert.alert_date)
    ).all()

    with ui.element('div').classes('w-full h-full p-8 rounded-xl').style(
        'background: white; box-shadow: var(--pl-shadow-md); '
        'border-left: 4px solid var(--pl-primary);'
    ):
        with ui.row().classes('w-full justify-between items-center mb-3'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('notifications_active').style('font-size: 20px; color: var(--pl-primary);')
                ui.label('Vaccination Alerts').classes('pl-heading-lg')

        if alerts:
            for alert in alerts[:5]:
                is_past = alert.alert_date < _utc_now()
                color = '#dc2626' if is_past else '#57423d'
                icon_name = 'warning' if is_past else 'event'
                with ui.row().classes(
                    'w-full items-center justify-between py-2'
                ).style('border-bottom: 1px solid #f5f5f4;'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon(icon_name).style(f'font-size: 16px; color: {color};')
                        with ui.column().classes('gap-0'):
                            ui.label(alert.title).style(
                                f'font-size: 13px; font-weight: 600; color: {color};'
                            )
                            ui.label(alert.alert_date.strftime('%b %d, %Y')).style(
                                'font-size: 11px; color: var(--pl-text-hint);'
                            )
                    if alert.is_sent:
                        ui.icon('check_circle').style(
                            'font-size: 16px; color: #16a34a;'
                        ).tooltip('Sent')
                    else:
                        async def delete_alert(a_id=alert.id):
                            with Session(engine) as s:
                                a = s.get(VaccinationAlert, a_id)
                                if a:
                                    s.delete(a)
                                    s.commit()
                            ui.notify('Alert removed.', type='info')
                            ui.navigate.to(f'/pet/{pet.id}')

                        ui.button(icon='close', on_click=delete_alert).props(
                            'flat dense round'
                        ).style('color: #a8a29e;')
        else:
            ui.label('No alerts set.').style(
                'color: var(--pl-on-surface-variant); font-style: italic; font-size: 13px;'
            )

        # Quick-add alert — dialog
        async def open_add_alert_dialog():
            with ui.dialog() as alert_dlg, ui.card().classes('p-8').style(
                'max-width: 480px; border-radius: 12px;'
            ):
                ui.label('Schedule Alert').classes('pl-heading-lg').style(
                    "margin-bottom: 1.5rem;"
                )

                alert_title = ui.input(
                    placeholder='e.g. Rabies booster due'
                ).classes('w-full').props('outlined dense label="Alert Title"')
                alert_date = ui.input(
                    label='Alert Date'
                ).classes('w-full').props('outlined dense type=date')
                alert_desc = ui.input(
                    placeholder='Optional details'
                ).classes('w-full').props('outlined dense label="Description (optional)"')

                async def save_alert():
                    title = alert_title.value.strip() if alert_title.value else ''
                    date_val = alert_date.value
                    if not title or not date_val:
                        ui.notify('Title and date are required.', type='warning')
                        return
                    try:
                        parsed_date = datetime.strptime(date_val, '%Y-%m-%d')
                    except ValueError:
                        ui.notify('Invalid date format.', type='warning')
                        return

                    with Session(engine) as s:
                        s.add(VaccinationAlert(
                            pet_id=pet.id,
                            user_id=pet.owner_id,
                            title=sanitize(title),
                            alert_date=parsed_date,
                            description=sanitize(alert_desc.value.strip()) if alert_desc.value else None,
                        ))
                        s.commit()
                    alert_dlg.close()
                    ui.notify('Alert scheduled!', type='positive')
                    ui.navigate.to(f'/pet/{pet.id}')

                with ui.row().classes('w-full justify-end gap-3 mt-4'):
                    ui.button('Cancel', on_click=alert_dlg.close).props(
                        'flat no-caps'
                    ).style('color: var(--pl-on-surface-variant);')
                    alert_btn = ui.button(
                        'Schedule Alert', icon='notifications',
                    ).style(
                        'background: var(--pl-primary); color: white; font-weight: 600;'
                    ).props('no-caps')

                    async def _save_alert_guarded():
                        async with _with_loading(alert_btn):
                            await save_alert()

                    alert_btn.on_click(_save_alert_guarded)

            alert_dlg.open()

        ui.button(
            'Add Alert', icon='add',
            on_click=open_add_alert_dialog,
        ).classes('w-full mt-3').props('outline no-caps').style(
            'color: var(--pl-primary); border-color: var(--pl-primary); font-weight: 600;'
        )


def _render_transfer_panel(pet, session):
    """Ownership transfer initiation panel."""
    pending = session.exec(
        select(OwnershipTransfer).where(
            OwnershipTransfer.pet_id == pet.id,
            OwnershipTransfer.status == "pending",
        )
    ).first()

    with ui.element('div').classes('w-full h-full p-8 rounded-xl').style(
        'background: white; box-shadow: var(--pl-shadow-md); '
        'border-left: 4px solid var(--pl-primary);'
    ):
        with ui.row().classes('items-center gap-2 mb-3'):
            ui.icon('swap_horiz').style('font-size: 20px; color: var(--pl-primary);')
            ui.label('Ownership Transfer').classes('pl-heading-lg')

        if pending:
            with ui.row().classes(
                'w-full items-center gap-3 p-3 rounded-lg'
            ).style('background: #fafafa; border: 1px solid #e7e5e4;'):
                ui.icon('hourglass_top').style('font-size: 18px; color: var(--pl-primary);')
                with ui.column().classes('gap-0 flex-1'):
                    ui.label('Transfer Pending').style(
                        'font-size: 13px; font-weight: 600; color: var(--pl-primary);'
                    )
                    ui.label(f'To: {pending.to_owner_email}').style(
                        'font-size: 12px; color: var(--pl-on-surface-variant);'
                    )
                    ui.label(
                        f'Initiated: {pending.initiated_at.strftime("%b %d, %Y")}'
                    ).style('font-size: 11px; color: var(--pl-text-hint);')

            async def cancel_transfer():
                import httpx
                from nicegui import context
                base = os.getenv('BASE_URL', 'http://localhost:8080')
                cookies = context.client.request.cookies
                async with httpx.AsyncClient(base_url=base) as client:
                    resp = await client.post(
                        f'/api/v1/pets/{pet.id}/transfer/cancel',
                        cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                    )
                    if resp.status_code == 200:
                        ui.notify('Transfer canceled.', type='positive')
                        ui.navigate.to(f'/pet/{pet.id}')
                    else:
                        detail = resp.json().get('detail', 'Failed to cancel.')
                        ui.notify(detail, type='negative')

            ui.button(
                'Cancel Transfer', icon='close',
                on_click=cancel_transfer,
            ).classes('w-full mt-2').props('outline no-caps').style(
                'color: #dc2626; border-color: #dc2626; font-weight: 600;'
            )
        else:
            ui.label(
                'Transfer this pet to a new owner with full audit trail.'
            ).style('font-size: 13px; color: var(--pl-on-surface-variant); margin-bottom: 0.75rem;')

            transfer_email = ui.input(
                placeholder='new.owner@email.com'
            ).classes('w-full').props('outlined dense label="New Owner Email"')
            transfer_notes = ui.input(
                placeholder='Optional note for the new owner'
            ).classes('w-full mt-2').props('outlined dense label="Notes (optional)"')

            async def initiate_transfer():
                email = transfer_email.value.strip() if transfer_email.value else ''
                if not email or '@' not in email:
                    ui.notify('A valid email is required.', type='warning')
                    return
                import httpx
                from nicegui import context
                base = os.getenv('BASE_URL', 'http://localhost:8080')
                cookies = context.client.request.cookies
                async with httpx.AsyncClient(base_url=base) as client:
                    resp = await client.post(
                        f'/api/v1/pets/{pet.id}/transfer',
                        json={
                            'new_owner_email': email,
                            'notes': transfer_notes.value.strip() if transfer_notes.value else None,
                        },
                        cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                    )
                    if resp.status_code == 200:
                        ui.notify('Transfer initiated! The new owner has been emailed.', type='positive')
                        ui.navigate.to(f'/pet/{pet.id}')
                    else:
                        detail = resp.json().get('detail', 'Transfer failed.')
                        ui.notify(detail, type='negative')

            transfer_btn = ui.button(
                'Initiate Transfer', icon='send',
            ).classes('w-full mt-3').style(
                'background: var(--pl-primary); color: white; font-weight: 600;'
            ).props('no-caps')

            async def _transfer_guarded():
                async with _with_loading(transfer_btn):
                    await initiate_transfer()

            transfer_btn.on_click(_transfer_guarded)

        # Transfer history section
        all_transfers = session.exec(
            select(OwnershipTransfer)
            .where(OwnershipTransfer.pet_id == pet.id)
            .order_by(OwnershipTransfer.initiated_at.desc())
        ).all()
        completed_transfers = [t for t in all_transfers if t.status != "pending"]

        if completed_transfers:
            ui.separator().classes('my-4')
            with ui.row().classes('items-center gap-2 mb-2'):
                ui.icon('history').style('font-size: 16px; color: var(--pl-text-hint);')
                ui.label('Transfer History').style(
                    'font-size: 13px; font-weight: 600; color: var(--pl-on-surface);'
                )

            for t in completed_transfers[:5]:
                status_colors = {
                    'accepted': ('#16a34a', '#dcfce7'),
                    'canceled': ('#6b7280', '#f5f5f4'),
                    'expired': ('#dc2626', '#fef2f2'),
                }
                fg, bg = status_colors.get(t.status, ('#6b7280', '#f5f5f4'))
                with ui.row().classes('w-full items-center gap-3 py-2').style(
                    'border-bottom: 1px solid #f5f5f4;'
                ):
                    with ui.column().classes('gap-0 flex-1'):
                        ui.label(f'To: {t.to_owner_email}').style(
                            'font-size: 12px; color: var(--pl-on-surface);'
                        )
                        ui.label(t.initiated_at.strftime('%b %d, %Y')).style(
                            'font-size: 11px; color: var(--pl-text-hint);'
                        )
                    ui.label(t.status.capitalize()).style(
                        f'font-size: 11px; font-weight: 600; color: {fg}; '
                        f'padding: 2px 8px; background: {bg}; border-radius: 9999px;'
                    )


# ─────────────────────────────────────────────────────────────
# PET EDIT PAGE — inline edit form for pet owners
# ─────────────────────────────────────────────────────────────

def _render_pet_edit_page(pet, session):
    """Render the pet edit form matching pet_profile_edit.html template."""
    from app.data import get_vaccine_options_for_dropdown
    from ..common import dog_client

    # ── Header ──
    with ui.column().classes('w-full items-center mb-8'):
        ui.label('Edit Pet Profile').classes('pl-heading-3xl')
        ui.label(
            "Update your companion's care and identification details."
        ).style('font-size: 18px; line-height: 1.6; color: var(--pl-on-surface-variant); margin-top: 4px;')

    # ── Section tabs ──
    section_ids = ['edit-basic', 'edit-care', 'edit-health']
    tab_labels = ['Basic Info', 'Daily Care', 'Health & Temperament']

    with ui.row().classes('w-full gap-10 mb-8 pb-4').style(
        'border-bottom: 1px solid #eaeef5;'
    ):
        for i, label in enumerate(tab_labels):
            active_style = (
                'color: var(--pl-primary); font-weight: 600; font-size: 14px; '
                'border-bottom: 2px solid #a03a21; padding-bottom: 16px; '
                'margin-bottom: -17px; cursor: pointer;'
            )
            inactive_style = (
                'color: var(--pl-on-surface-variant); font-weight: 600; font-size: 14px; '
                'padding-bottom: 16px; margin-bottom: -17px; cursor: pointer;'
            )
            sid = section_ids[i]
            tab = ui.label(label).style(active_style if i == 0 else inactive_style)
            tab.on(
                'click',
                js_handler=f'() => document.getElementById("{sid}").scrollIntoView({{behavior: "smooth", block: "start"}})',
            )

    # ══════════════════════════════════════════════════════════
    # SECTION 1: BASIC INFO
    # ══════════════════════════════════════════════════════════
    with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-6').style(
        'background: white; border: 1px solid #eaeef5; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
    ).props('id="edit-basic"'):
        with ui.element('div').classes('p-6').style(
            'border-bottom: 1px solid #eaeef5;'
        ):
            ui.label('Basic Info').classes('pl-heading-xl')

        with ui.column().classes('p-10 gap-6'):
            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Pet Name').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    name_input = ui.input(
                        value=pet.name or ''
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Microchip ID').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    chip_input = ui.input(
                        value=pet.chip_id or ''
                    ).classes('w-full').props('outlined dense readonly')
                    ui.label('Chip ID cannot be changed after registration.').style(
                        'font-size: 11px; color: var(--pl-text-hint); font-style: italic;'
                    )

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Species').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    species_input = ui.select(
                        ['DOG', 'CAT'], label='', value=pet.pet_species or 'DOG'
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Breed').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    breed_input = ui.input(
                        value=pet.breed or ''
                    ).classes('w-full').props('outlined dense')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Birth Date').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    dob_val = pet.dob.strftime('%Y-%m-%d') if pet.dob else ''
                    dob_input = ui.input(value=dob_val).classes('w-full').props(
                        'outlined dense type=date'
                    )

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Gender').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    gender_input = ui.select(
                        ['Male', 'Female', 'Unknown'],
                        label='', value=pet.gender or 'Unknown',
                    ).classes('w-full').props('outlined dense')

    # ══════════════════════════════════════════════════════════
    # SECTION 2: DAILY CARE
    # ══════════════════════════════════════════════════════════
    with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-6').style(
        'background: white; border: 1px solid #eaeef5; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
    ).props('id="edit-care"'):
        with ui.element('div').classes('p-6').style(
            'border-bottom: 1px solid #eaeef5;'
        ):
            ui.label('Daily Care').classes('pl-heading-xl')

        with ui.column().classes('p-10 gap-6'):
            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Energy Level').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    energy_input = ui.select(
                        ['Low', 'Moderate', 'High', 'Very High'],
                        label='', value=pet.energy_level or 'Moderate',
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Max Alone Hours').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    alone_input = ui.number(
                        '', value=pet.max_alone_hours, min=0, max=24,
                    ).classes('w-full').props('outlined dense')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Feeds per Day').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    feeds_input = ui.number(
                        '', value=pet.feeds_per_day, min=1, max=10,
                    ).classes('w-full').props('outlined dense')

    # ══════════════════════════════════════════════════════════
    # SECTION 3: HEALTH & TEMPERAMENT
    # ══════════════════════════════════════════════════════════
    with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-10').style(
        'background: white; border: 1px solid #eaeef5; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
    ).props('id="edit-health"'):
        with ui.element('div').classes('p-6').style(
            'border-bottom: 1px solid #eaeef5;'
        ):
            ui.label('Health & Temperament').classes('pl-heading-xl')

        with ui.column().classes('p-10 gap-6'):
            with ui.column().classes('w-full gap-1'):
                ui.label('Temperament').style(
                    'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                )
                temperament_input = ui.textarea(
                    value=pet.temperament or '',
                    placeholder='Friendly, shy, reactive to other dogs?',
                ).classes('w-full').props('outlined rows=3')

            with ui.column().classes('w-full gap-1'):
                ui.label('Dietary Notes').style(
                    'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                )
                dietary_input = ui.textarea(
                    value=pet.dietary_notes or '',
                    placeholder='Allergies or special diet requirements?',
                ).classes('w-full').props('outlined rows=3')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Exercise Needs').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    exercise_input = ui.input(
                        value=pet.exercise_needs or '',
                        placeholder='e.g. 30 min walk twice daily',
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Medical Conditions').style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                    )
                    medical_input = ui.textarea(
                        value=pet.medical_conditions or '',
                        placeholder='List any ongoing health issues',
                    ).classes('w-full').props('outlined rows=3')

    # ── Action buttons ──
    with ui.row().classes('w-full justify-end items-center gap-4 pt-6').style(
        'border-top: 1px solid #eaeef5;'
    ):
        ui.button(
            'Cancel',
            on_click=lambda: ui.navigate.to(f'/pet/{pet.id}'),
        ).style('color: var(--pl-on-surface-variant); font-weight: 600; padding: 12px 40px;').props(
            'flat no-caps'
        )

        async def save_changes():
            if not name_input.value or not name_input.value.strip():
                ui.notify('Pet Name is required.', type='negative')
                return

            with Session(engine) as s:
                db_pet = s.get(Pet, pet.id)
                if not db_pet:
                    ui.notify('Pet not found.', type='negative')
                    return

                db_pet.name = sanitize(name_input.value.strip())
                db_pet.pet_species = species_input.value
                db_pet.breed = sanitize(breed_input.value.strip()) if breed_input.value else None
                db_pet.gender = gender_input.value
                db_pet.dob = (
                    datetime.fromisoformat(dob_input.value)
                    if dob_input.value else None
                )
                db_pet.energy_level = energy_input.value if energy_input.value else None
                db_pet.max_alone_hours = (
                    int(alone_input.value) if alone_input.value else None
                )
                db_pet.feeds_per_day = (
                    int(feeds_input.value) if feeds_input.value else None
                )
                db_pet.temperament = (
                    sanitize(temperament_input.value.strip()) if temperament_input.value else None
                )
                db_pet.dietary_notes = (
                    sanitize(dietary_input.value.strip()) if dietary_input.value else None
                )
                db_pet.exercise_needs = (
                    sanitize(exercise_input.value.strip()) if exercise_input.value else None
                )
                db_pet.medical_conditions = (
                    sanitize(medical_input.value.strip()) if medical_input.value else None
                )

                s.add(db_pet)
                s.commit()

            ui.notify('Pet profile updated successfully!', type='positive')
            ui.navigate.to(f'/pet/{pet.id}')

        save_edit_btn = ui.button(
            'Save All Changes',
        ).style(
            'background: var(--pl-primary); color: white; font-weight: 600; '
            'padding: 12px 40px; border-radius: 8px; '
            'box-shadow: 0 4px 12px rgba(160,58,33,0.2);'
        ).props('no-caps')

        async def _save_edit_guarded():
            async with _with_loading(save_edit_btn):
                await save_changes()

        save_edit_btn.on_click(_save_edit_guarded)

    # ── Info banner ──
    with ui.row().classes('w-full items-start gap-3 mt-6 p-4 rounded-xl').style(
        'background: var(--pl-surface-warm); border: 1px solid rgba(251,191,36,0.2);'
    ):
        ui.icon('info').style('font-size: 20px; color: #c2410c; margin-top: 2px;')
        ui.html(
            '<span style="font-size: 12px; color: var(--pl-on-surface-variant);">'
            'Changes to medical identifiers like <strong>Microchip ID</strong> '
            'cannot be modified after registration. Tag updates reflect '
            'immediately on scan results.</span>'
        )


# ─────────────────────────────────────────────────────────────
# SHARE DIALOG — quick shared access link creation
# ─────────────────────────────────────────────────────────────

async def _open_share_dialog(pet):
    """Open a dialog to create a time-limited shared access link for this pet."""
    with ui.dialog() as dlg, ui.card().classes('p-8').style(
        'max-width: 480px; border-radius: 12px;'
    ):
        ui.label('Share Pet Records').style(
            'font-size: 18px; font-weight: 700; margin-bottom: 4px;'
        )
        ui.label(
            'Create a time-limited link for vets, sitters, or groomers to view '
            f"{pet.name}'s care instructions and vaccination records."
        ).style('font-size: 13px; color: var(--pl-on-surface-variant); margin-bottom: 20px;')

        hours_select = ui.select(
            {1: '1 hour', 4: '4 hours', 12: '12 hours', 24: '24 hours',
             72: '3 days', 168: '7 days'},
            label='Link Duration', value=24,
        ).classes('w-full').props('outlined dense')

        result_container = ui.column().classes('w-full gap-2 mt-4')

        async def create_link():
            import httpx
            from nicegui import context
            base = os.getenv('BASE_URL', 'http://localhost:8080')
            cookies = context.client.request.cookies
            async with httpx.AsyncClient(base_url=base) as client:
                resp = await client.post(
                    f'/api/v1/pets/{pet.id}/shared-access?hours={hours_select.value}',
                    cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    share_url = f"{base}/shared/{data['access_url'].split('/')[-1]}"
                    import segno
                    import io as _io
                    qr = segno.make(share_url)
                    svg_buf = _io.BytesIO()
                    qr.save(svg_buf, kind='svg', scale=3, border=1, dark='#1c1917')
                    qr_svg = svg_buf.getvalue().decode('utf-8')

                    with result_container:
                        result_container.clear()
                        ui.label('Link created!').style(
                            'font-size: 13px; font-weight: 600; color: #16a34a;'
                        )
                        with ui.row().classes('w-full items-start gap-4'):
                            with ui.column().classes('flex-1 gap-2'):
                                ui.input(value=share_url).classes('w-full').props(
                                    'outlined dense readonly'
                                )
                                ui.button(
                                    'Copy', icon='content_copy',
                                    on_click=lambda: (
                                        ui.run_javascript(
                                            f'navigator.clipboard.writeText("{share_url}")'
                                        ),
                                        ui.notify('Copied!', type='positive'),
                                    ),
                                ).props('flat dense no-caps').style(
                                    'color: var(--pl-primary); font-weight: 600;'
                                )
                                ui.label(
                                    f"Expires: {data['expires_at']}"
                                ).style('font-size: 11px; color: var(--pl-text-hint);')
                            ui.html(qr_svg).style(
                                'width: 120px; height: 120px; flex-shrink: 0;'
                            )
                else:
                    ui.notify('Failed to create link.', type='negative')

        with ui.row().classes('w-full justify-end gap-3 mt-4'):
            ui.button('Cancel', on_click=dlg.close).props(
                'flat no-caps'
            ).style('color: var(--pl-on-surface-variant);')
            ui.button(
                'Create Link', icon='link', on_click=create_link,
            ).style(
                'background: var(--pl-primary); color: white; font-weight: 600;'
            ).props('no-caps')

    dlg.open()


# ─────────────────────────────────────────────────────────────
# PAGE INIT — route handler with owner detection
# ─────────────────────────────────────────────────────────────

def init_pet_profile_page() -> None:
    from ..dashboard_shell import dashboard_shell

    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str, request: Request) -> None:
        try_restore_session(request)

        with Session(engine) as session:
            pet = session.exec(
                select(Pet).where(Pet.id == uuid.UUID(pet_id))
            ).first()

            if not pet:
                nav_header()
                with ui.column().classes('w-full items-center p-16'):
                    ui.icon('search_off').style(
                        'font-size: 64px; color: #dec0b9;'
                    )
                    ui.label('Pet Not Found').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                        "font-weight: 600; color: var(--pl-on-surface); margin-top: 1rem;"
                    )
                    ui.label(
                        'The pet record you are looking for does not exist.'
                    ).style('color: var(--pl-on-surface-variant); margin-top: 0.5rem;')
                    ui.button(
                        'Back to Home', icon='home',
                        on_click=lambda: ui.navigate.to('/'),
                    ).classes('mt-6').props('outline no-caps')
                nav_footer()
                return

            is_owner = False
            is_verified = False
            current_user_id = app.storage.user.get('id')
            if current_user_id and pet.owner_id:
                is_owner = str(pet.owner_id) == current_user_id

            # Check subscription tier for verified badge
            if pet.owner_id:
                owner_sub = session.exec(
                    select(Subscription).where(Subscription.user_id == pet.owner_id)
                ).first()
                is_verified = (
                    owner_sub is not None
                    and owner_sub.status == "active"
                    and owner_sub.tier in ("verified", "guardian")
                )

            if is_owner:
                with dashboard_shell(
                    title=pet.name or 'Pet',
                    breadcrumbs=[('Dashboard', '/dashboard')],
                    active_pet_id=str(pet.id),
                    actions=[
                        {'label': 'Share', 'icon': 'link', 'style': 'ghost',
                         'on_click': lambda p=pet: _open_share_dialog(p)},
                        {'label': 'Export', 'icon': 'download', 'style': 'ghost',
                         'on_click': lambda p=pet: ui.navigate.to(
                             f'/api/v1/pets/{p.id}/vaccinations/export', new_tab=True)},
                        {'label': 'Add Record', 'icon': 'vaccines', 'style': 'ghost',
                         'on_click': lambda: ui.navigate.to(f'/pet/{pet_id}#vaccinations')},
                    ],
                ):
                    _render_private_view(pet, session, is_verified)
            else:
                nav_header()
                with ui.element('main').classes(
                    'w-full max-w-7xl mx-auto px-6 py-12'
                ):
                    _render_public_view(pet, session, is_verified)
                nav_footer()

    @ui.page('/pet/{pet_id}/edit')
    async def pet_edit(pet_id: str, request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        with Session(engine) as session:
            pet = session.exec(
                select(Pet).where(Pet.id == uuid.UUID(pet_id))
            ).first()

            if not pet:
                nav_header()
                with ui.column().classes('w-full items-center p-16'):
                    ui.label('Pet Not Found').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                        "font-weight: 600; color: var(--pl-on-surface);"
                    )
                nav_footer()
                return

            # Only the owner can edit
            current_user_id = app.storage.user.get('id')
            if not current_user_id or str(pet.owner_id) != current_user_id:
                ui.navigate.to(f'/pet/{pet_id}')
                return

            with dashboard_shell(
                title=f'Edit {pet.name or "Pet"}',
                breadcrumbs=[('Dashboard', '/dashboard'), (pet.name or 'Pet', f'/pet/{pet.id}')],
                active_pet_id=str(pet.id),
            ):
                _render_pet_edit_page(pet, session)
