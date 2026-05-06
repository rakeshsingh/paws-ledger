from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, LedgerEvent, Vaccination, SharedAccess, User, PetTag
from .header import nav_header
from .footer import nav_footer
from .common import try_restore_session, hash_service, pdf_service
from datetime import datetime, timedelta
import uuid

# Species icon mapping (shared with dashboard)
SPECIES_ICONS = {'DOG': 'pets', 'CAT': 'emoji_nature'}
SPECIES_ICON_DEFAULT = 'pets'
SPECIES_BG = {'DOG': '#ffdad2', 'CAT': '#ffdea9'}
SPECIES_BG_DEFAULT = '#eaeef5'
SPECIES_FG = {'DOG': '#a03a21', 'CAT': '#7d5800'}
SPECIES_FG_DEFAULT = '#57423d'


def _obfuscate(value: str) -> str:
    """Show first character followed by asterisks for privacy."""
    if not value:
        return '***'
    return value[0] + '***'


def _pet_avatar(pet, size: int = 128):
    """Render pet photo or species icon placeholder."""
    if pet.photo_url:
        ui.image(pet.photo_url).classes('rounded-full').style(
            f'width: {size}px; height: {size}px; object-fit: cover; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        )
    else:
        species = pet.pet_species or 'DOG'
        bg = SPECIES_BG.get(species, SPECIES_BG_DEFAULT)
        fg = SPECIES_FG.get(species, SPECIES_FG_DEFAULT)
        icon_name = SPECIES_ICONS.get(species, SPECIES_ICON_DEFAULT)
        with ui.element('div').classes(
            'flex items-center justify-center rounded-full'
        ).style(
            f'width: {size}px; height: {size}px; background: {bg}; '
            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
        ):
            ui.icon(icon_name).style(f'font-size: {size // 2}px; color: {fg};')


# ─────────────────────────────────────────────────────────────
# SHARED UI COMPONENTS — used by both public and private views
# ─────────────────────────────────────────────────────────────

def _render_registry_status_card():
    """Registry status sidebar card (shared between views)."""
    with ui.element('div').classes('h-full p-6 rounded-xl flex flex-col justify-between').style(
        'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
    ):
        with ui.column().classes('gap-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('verified_user').style('font-size: 24px; color: #9a3412;')
                ui.label('Registry Status').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #9a3412;"
                )
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
                            'font-weight: 600; font-size: 14px; color: #171c21;'
                        )
                        ui.label(sub).style('font-size: 12px; color: #57423d;')

        with ui.element('div').classes('p-4 rounded-lg mt-6').style(
            'background: rgba(255,255,255,0.6);'
        ):
            ui.label('Looking for a lost pet?').style(
                'font-size: 12px; font-weight: 500; color: #9a3412;'
            )
            ui.label(
                'Nudging the owner sends an encrypted alert with your '
                'location and contact details securely.'
            ).style('font-size: 12px; color: #c2410c; margin-top: 4px;')


def _render_medical_summary(pet):
    """Medical summary card (shared between views)."""
    with ui.element('div').classes('h-full p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
        'border-left: 4px solid #3b82f6;'
    ):
        ui.label('Medical Summary').style(
            "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
            "font-weight: 600; color: #171c21; margin-bottom: 1.5rem;"
        )
        if pet.vaccinations:
            for v in pet.vaccinations:
                is_current = v.expiration_date > datetime.utcnow()
                with ui.row().classes(
                    'w-full items-center justify-between p-4 rounded-lg mb-3'
                ).style('background: #f0f4fb;'):
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
                'color: #57423d; font-style: italic;'
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


def _render_contact_location_card(pet, is_owner: bool = False):
    """Contact / location card with OpenStreetMap embed for public, full info for owner."""
    owner = pet.owner
    owner_city = owner.city if owner else None
    owner_country = owner.country if owner else None

    with ui.element('div').classes(
        'h-full rounded-xl overflow-hidden flex flex-col'
    ).style('background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'):
        # Map area — Leaflet + Nominatim geocoding (no API key needed)
        map_div_id = f'map-{uuid.uuid4().hex[:8]}'
        with ui.element('div').classes('relative').style(
            'height: 220px; overflow: hidden;'
        ):
            if owner_city or owner_country:
                location_query = ', '.join(
                    part for part in [owner_city, owner_country] if part
                )
                # Leaflet map container
                ui.element('div').props(f'id="{map_div_id}"').style(
                    'width: 100%; height: 220px;'
                )
                # Inject Leaflet CSS/JS and initialize the map via Nominatim geocoding
                safe_query = location_query.replace("'", "\\'").replace('"', '\\"')
                ui.add_head_html(
                    '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
                )
                ui.add_head_html(
                    '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
                )
                ui.run_javascript(f'''
                    (function() {{
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
                            fetch("https://nominatim.openstreetmap.org/search?format=json&q={safe_query}&limit=1")
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
                ui.icon('location_on').style('font-size: 16px; color: #a03a21;')
                ui.label(location_text).style(
                    'font-size: 12px; font-weight: 600;'
                )

        # Content below map
        with ui.column().classes('p-6 flex-grow items-center justify-center gap-4'):
            if is_owner:
                # Owner sees full contact info
                if owner:
                    with ui.row().classes('w-full gap-8 justify-center flex-wrap'):
                        for icon_name, label, value in [
                            ('person', 'Owner', owner.name),
                            ('mail', 'Email', owner.email),
                            ('phone', 'Phone', owner.phone or 'Not set'),
                            ('home', 'Address', owner.address or 'Not set'),
                        ]:
                            with ui.column().classes('items-center gap-1'):
                                with ui.element('div').classes(
                                    'flex items-center justify-center rounded-full'
                                ).style(
                                    'width: 48px; height: 48px; background: #ffdad2; '
                                    'color: #a03a21;'
                                ):
                                    ui.icon(icon_name).style('font-size: 22px;')
                                ui.label(label).style(
                                    'font-size: 10px; font-weight: 700; color: #a8a29e; '
                                    'text-transform: uppercase;'
                                )
                                ui.label(value).style(
                                    'font-size: 13px; font-weight: 500; color: #171c21; '
                                    'text-align: center; max-width: 140px; '
                                    'overflow: hidden; text-overflow: ellipsis;'
                                )
            else:
                # Public: privacy message + relay icons
                ui.label(
                    'Owner information is protected for privacy. '
                    'Use the primary action to initiate a secure contact request.'
                ).style(
                    'color: #57423d; font-size: 16px; text-align: center; '
                    'line-height: 1.5;'
                )
                with ui.row().classes('gap-6 justify-center'):
                    for icon_name, label in [
                        ('mail', 'Email Relay'),
                    ]:
                        with ui.column().classes('items-center gap-1'):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-full'
                            ).style(
                                'width: 48px; height: 48px; background: #fff7ed; '
                                'color: #c2410c;'
                            ):
                                ui.icon(icon_name).style('font-size: 22px;')
                            ui.label(label).style(
                                'font-size: 10px; font-weight: 700; color: #a8a29e; '
                                'text-transform: uppercase;'
                            )


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
                    ui.label(label).style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 18px; "
                        "font-weight: 600;"
                    )


def _render_tag_management(pet, session):
    """Tag management card for the owner's private view."""
    with ui.element('div').classes('w-full mt-5 p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
        'border-left: 4px solid #7d5800;'
    ):
        with ui.row().classes('w-full justify-between items-center mb-6'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('nfc').style('font-size: 28px; color: #7d5800;')
                ui.label('NFC / QR Tags').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #171c21;"
                )
            tag_count = len(pet.tags)
            if tag_count > 0:
                ui.label(f'{tag_count} tag{"s" if tag_count != 1 else ""}').style(
                    'padding: 4px 12px; background: #ffdea9; color: #5f4100; '
                    'font-size: 12px; font-weight: 600; border-radius: 9999px;'
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
                ).style('color: #57423d; font-style: italic; font-size: 14px;')

        # Add tag form
        with ui.expansion('Add New Tag', icon='add_circle').classes('w-full'):
            with ui.column().classes('w-full gap-4 pt-4'):
                tag_type = ui.select(
                    ['QR', 'NFC', 'DUAL'], label='Tag Type', value='QR'
                ).classes('w-full').props('outlined dense')
                tag_label = ui.input(
                    placeholder='e.g. Collar tag, Harness tag'
                ).classes('w-full').props('outlined dense label="Label"')
                tag_code_input = ui.input(
                    placeholder='Leave blank to auto-generate'
                ).classes('w-full').props('outlined dense label="Tag Code (optional)"')

                # NFC-specific fields
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

                    ui.notify('Tag added successfully!', type='positive')
                    ui.navigate.to(f'/pet/{pet.id}')

                ui.button(
                    'Register Tag', icon='nfc', on_click=add_tag,
                ).classes('w-full mt-2').style(
                    'background: #7d5800; color: white; font-weight: 600;'
                ).props('no-caps')


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
                    'font-family: monospace; font-size: 12px; color: #57423d;'
                )
                if tag.nfc_uid:
                    ui.label(f'NFC UID: {tag.nfc_uid}').style(
                        'font-family: monospace; font-size: 11px; color: #78716c;'
                    )

        with ui.row().classes('items-center gap-2'):
            if is_active:
                async def deactivate(t=tag):
                    with Session(engine) as s:
                        db_tag = s.get(PetTag, t.id)
                        if db_tag:
                            db_tag.status = 'DEACTIVATED'
                            db_tag.deactivated_at = datetime.utcnow()
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
# PUBLIC VIEW — privacy-obfuscated, for non-owners / anonymous
# ─────────────────────────────────────────────────────────────

def _render_public_view(pet, session):
    """Render the public pet profile with obfuscated PII."""
    is_logged_in = bool(app.storage.user.get('email'))

    # ── Search header ──
    with ui.element('header').classes('mb-12'):
        ui.link(
            '← New Search', '/',
        ).style(
            'color: #a03a21; font-weight: 600; font-size: 14px; '
            'text-decoration: none;'
        )
        with ui.row().classes(
            'w-full justify-between items-end mt-4 flex-wrap gap-6'
        ):
            with ui.column().classes('gap-2'):
                ui.label(f'Chip ID: {pet.chip_id}').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; "
                    "letter-spacing: -0.02em; color: #171c21;"
                )
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
                            'font-size: 14px; font-weight: 600; color: #57423d;'
                        )

            if is_logged_in:
                async def nudge_owner():
                    import httpx
                    async with httpx.AsyncClient(
                        base_url='http://localhost:8080'
                    ) as http_client:
                        resp = await http_client.post(
                            f'/api/v1/nudge/{pet.chip_id}'
                        )
                        if resp.status_code == 200:
                            ui.notify('Nudge sent to owner!', type='positive')
                        else:
                            ui.notify('Failed to send nudge.', type='negative')

                ui.button(
                    'Nudge Owner', icon='notifications',
                    on_click=nudge_owner,
                ).style(
                    'background: #a03a21; color: white; font-weight: 600; '
                    'padding: 12px 40px; border-radius: 12px; '
                    'box-shadow: 0 4px 12px rgba(160,58,33,0.2);'
                ).props('no-caps')

    # ── Row 1: Pet ID card + Registry status ──
    with ui.row().classes('w-full gap-5 flex-wrap items-stretch'):
        # Pet identification card (obfuscated)
        with ui.element('div').classes('flex-1').style('min-width: 400px;'):
            with ui.element('div').classes('h-full p-10 rounded-xl').style(
                'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                'border-left: 4px solid #a03a21;'
            ):
                with ui.row().classes('gap-8'):
                    with ui.element('div').classes('relative flex-shrink-0'):
                        _pet_avatar(pet, 128)
                        with ui.element('div').classes(
                            'absolute bottom-0 right-0 bg-white p-1 '
                            'rounded-full shadow-sm'
                        ).style('border: 1px solid #f5f5f4;'):
                            ui.icon('pets').style(
                                'font-size: 20px; color: #a03a21;'
                            )

                    with ui.element('div').classes('flex-grow'):
                        with ui.row().classes(
                            'w-full gap-x-12 gap-y-6 flex-wrap'
                        ):
                            # Pet name (obfuscated)
                            with ui.column().classes('gap-1'):
                                ui.label('PET NAME').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: #57423d; text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(_obfuscate(pet.name)).style(
                                    "font-family: 'Plus Jakarta Sans'; "
                                    "font-size: 24px; font-weight: 600; "
                                    "color: #171c21;"
                                )
                                ui.label('(Privacy Obfuscated)').style(
                                    'font-size: 12px; color: #78716c; '
                                    'font-style: italic;'
                                )
                            # Manufacturer
                            with ui.column().classes('gap-1'):
                                ui.label('MANUFACTURER').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: #57423d; text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(
                                    pet.manufacturer or 'Unknown'
                                ).style(
                                    "font-family: 'Plus Jakarta Sans'; "
                                    "font-size: 24px; font-weight: 600; "
                                    "color: #171c21;"
                                )
                                prefix = pet.chip_id[:3] if pet.chip_id else ''
                                ui.label(f'Based on Prefix {prefix}').style(
                                    'font-size: 12px; color: #78716c;'
                                )
                            # Status
                            with ui.column().classes('gap-1'):
                                ui.label('STATUS').style(
                                    'font-weight: 600; font-size: 10px; '
                                    'color: #57423d; text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                s_bg = '#dcfce7' if pet.identity_status == 'VERIFIED' else '#fef9c3'
                                s_fg = '#166534' if pet.identity_status == 'VERIFIED' else '#854d0e'
                                s_txt = 'Active Record' if pet.identity_status == 'VERIFIED' else 'Unverified'
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
                                    'color: #57423d; text-transform: uppercase; '
                                    'letter-spacing: 0.1em;'
                                )
                                ui.label(
                                    f'{pet.pet_species} • '
                                    f'{pet.breed or "Unknown"}'
                                ).style('font-size: 16px; color: #171c21;')

        # Registry status card
        with ui.element('div').style('width: 320px; flex-shrink: 0;'):
            _render_registry_status_card()

    # ── Row 2: Medical summary + Contact/Location ──
    with ui.row().classes('w-full gap-5 flex-wrap items-stretch mt-5'):
        with ui.element('div').classes('flex-1').style('min-width: 360px;'):
            _render_medical_summary(pet)
        with ui.element('div').classes('flex-1').style('min-width: 360px;'):
            _render_contact_location_card(pet, is_owner=False)

    # ── Trust signals ──
    _render_trust_signals()


# ─────────────────────────────────────────────────────────────
# PRIVATE VIEW — full details for the pet owner
# ─────────────────────────────────────────────────────────────

def _render_private_view(pet, session):
    """Render the full owner view with all PII and management tools."""

    # ── Header ──
    with ui.element('header').classes('mb-12'):
        with ui.row().classes(
            'w-full justify-between items-end flex-wrap gap-6'
        ):
            with ui.column().classes('gap-2'):
                ui.label(f'Identity Ledger: {pet.chip_id}').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; "
                    "letter-spacing: -0.02em; color: #171c21;"
                )
                with ui.row().classes('items-center gap-3'):
                    s_bg = '#ffc65d' if pet.identity_status == 'VERIFIED' else '#fef9c3'
                    s_fg = '#755100' if pet.identity_status == 'VERIFIED' else '#854d0e'
                    ui.label(pet.identity_status).style(
                        f'background: {s_bg}; color: {s_fg}; padding: 4px 12px; '
                        'border-radius: 9999px; font-size: 12px; font-weight: 700; '
                        'text-transform: uppercase; letter-spacing: 0.1em;'
                    )
                    ui.label('Owner View — Full Access').style(
                        'font-size: 14px; font-weight: 600; color: #16a34a;'
                    )

            # Edit button
            ui.button(
                'Edit Pet', icon='edit',
                on_click=lambda: ui.navigate.to(f'/pet/{pet.id}/edit'),
            ).style(
                'background: #a03a21; color: white; font-weight: 600; '
                'padding: 10px 24px; border-radius: 8px;'
            ).props('no-caps')

    # ── Row 1: Pet ID card (full) + Registry status ──
    with ui.row().classes('w-full gap-5 flex-wrap items-stretch'):
        # Pet identification card — full details
        with ui.element('div').classes('flex-1').style('min-width: 400px;'):
            with ui.element('div').classes('h-full p-10 rounded-xl').style(
                'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                'border-left: 4px solid #a03a21;'
            ):
                with ui.row().classes('gap-8'):
                    with ui.element('div').classes('relative flex-shrink-0'):
                        _pet_avatar(pet, 128)
                        with ui.element('div').classes(
                            'absolute bottom-0 right-0 bg-white p-1 '
                            'rounded-full shadow-sm'
                        ).style('border: 1px solid #f5f5f4;'):
                            ui.icon('pets').style(
                                'font-size: 20px; color: #a03a21;'
                            )

                    with ui.element('div').classes('flex-grow'):
                        with ui.row().classes(
                            'w-full gap-x-12 gap-y-6 flex-wrap'
                        ):
                            for label, value in [
                                ('PET NAME', pet.name),
                                ('SPECIES / BREED',
                                 f'{pet.pet_species} • {pet.breed or "Unknown"}'),
                                ('GENDER', pet.gender or 'Unknown'),
                                ('MANUFACTURER', pet.manufacturer or 'Unknown'),
                                ('DATE OF BIRTH',
                                 pet.dob.strftime('%b %d, %Y') if pet.dob else 'Not set'),
                                ('OWNER',
                                 pet.owner.name if pet.owner else 'Unassigned'),
                            ]:
                                with ui.column().classes('gap-1'):
                                    ui.label(label).style(
                                        'font-weight: 600; font-size: 10px; '
                                        'color: #57423d; text-transform: uppercase; '
                                        'letter-spacing: 0.1em;'
                                    )
                                    ui.label(value).style(
                                        'font-size: 16px; font-weight: 500; '
                                        'color: #171c21;'
                                    )

        # Registry status card (same as public)
        with ui.element('div').style('width: 320px; flex-shrink: 0;'):
            _render_registry_status_card()

    # ── Row 2: Medical summary + Contact/Location (owner view) ──
    with ui.row().classes('w-full gap-5 flex-wrap items-stretch mt-5'):
        with ui.element('div').classes('flex-1').style('min-width: 360px;'):
            _render_medical_summary(pet)
        with ui.element('div').classes('flex-1').style('min-width: 360px;'):
            _render_contact_location_card(pet, is_owner=True)

    # ── Row 3: Managed access + Care info ──
    with ui.row().classes('w-full gap-5 flex-wrap items-stretch mt-5'):
        # Managed access card
        with ui.element('div').style('width: 320px; flex-shrink: 0;'):
            with ui.element('div').classes('h-full p-6 rounded-xl').style(
                'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
            ):
                with ui.row().classes('items-center gap-2 mb-4'):
                    ui.icon('share').style('font-size: 24px; color: #9a3412;')
                    ui.label('Managed Access').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                        "font-weight: 600; color: #9a3412;"
                    )
                ui.label(
                    'Generate a time-bound care link for sitters or vets.'
                ).style(
                    'font-size: 12px; color: #57423d; margin-bottom: 1rem;'
                )

                async def create_link():
                    with Session(engine) as s:
                        access = SharedAccess(
                            pet_id=pet.id,
                            expires_at=datetime.utcnow() + timedelta(hours=24),
                        )
                        s.add(access)
                        s.commit()
                        s.refresh(access)
                        url = f"/shared/{access.token}"
                    with ui.dialog() as dialog, ui.card():
                        ui.label('Shared Access Link Created').classes(
                            'font-bold'
                        )
                        ui.label('Valid for 24 hours.').classes(
                            'text-xs text-stone-500'
                        )
                        ui.input(value=url).classes('w-full mt-2').props(
                            'readonly outlined'
                        )
                        ui.button('Close', on_click=dialog.close).classes(
                            'mt-4'
                        )
                    dialog.open()

                ui.button(
                    'Create 24h Link', icon='share', on_click=create_link,
                ).classes('w-full').props('outline no-caps')

        # Care info card
        care_items = [
            ('bolt', 'Energy Level', pet.energy_level),
            ('schedule', 'Max Alone Hours',
             f'{pet.max_alone_hours}h' if pet.max_alone_hours else None),
            ('restaurant', 'Feeds Per Day',
             str(pet.feeds_per_day) if pet.feeds_per_day else None),
            ('directions_run', 'Exercise Needs', pet.exercise_needs),
            ('mood', 'Temperament', pet.temperament),
        ]
        visible_care = [(i, l, v) for i, l, v in care_items if v]

        with ui.element('div').classes('flex-1').style('min-width: 360px;'):
            with ui.element('div').classes('h-full p-6 rounded-xl').style(
                'background: #f0f4fb;'
            ):
                ui.label('Care Info').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                    "font-weight: 600; color: #171c21; margin-bottom: 1rem;"
                )
                if visible_care:
                    for icon_name, label, value in visible_care:
                        with ui.row().classes(
                            'items-center justify-between py-2'
                        ).style('border-bottom: 1px solid #e7e5e4;'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon(icon_name).style(
                                    'font-size: 18px; color: #57423d;'
                                )
                                ui.label(label).style(
                                    'font-size: 14px; color: #57423d;'
                                )
                            ui.label(value).style(
                                'font-size: 14px; font-weight: 600; '
                                'color: #171c21;'
                            )
                else:
                    ui.label('No care information recorded yet.').style(
                        'color: #57423d; font-style: italic;'
                    )

    # ── NFC/QR Tag Management ──
    _render_tag_management(pet, session)

    # ── Vaccination ledger (owner-only: full detail + add form) ──
    with ui.element('div').classes('w-full mt-5 p-10 rounded-xl').style(
        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
        'border-left: 4px solid #3b82f6;'
    ):
        with ui.row().classes('w-full justify-between items-center mb-6'):
            ui.label('Vaccination Ledger').style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )

            async def export_pdf():
                if not pet.vaccinations:
                    ui.notify('No vaccinations to export.', type='warning')
                    return
                aggregate_data = [
                    v.dict(exclude={"id", "pet_id", "record_hash", "pet"})
                    for v in pet.vaccinations
                ]
                export_hash = hash_service.hash_record({
                    "pet_id": str(pet.id),
                    "vaccinations": aggregate_data,
                })
                path = pdf_service.generate_vaccination_report(
                    pet.breed or "Pet", pet.vaccinations, export_hash,
                )
                ui.download(path, f"{pet.breed}_vaccinations.pdf")

            ui.button(
                'Export PDF', icon='download',
                on_click=export_pdf,
            ).props('flat small no-caps').style('color: #a03a21;')

        # Existing records table
        if pet.vaccinations:
            # Table header
            with ui.row().classes('w-full items-center px-4 py-2 rounded-t-lg').style(
                'background: #eaeef5; font-size: 11px; font-weight: 700; '
                'color: #57423d; text-transform: uppercase; letter-spacing: 0.05em;'
            ):
                ui.label('Vaccine').classes('flex-1')
                ui.label('Manufacturer').style('width: 120px;')
                ui.label('Serial/Lot').style('width: 100px;')
                ui.label('Date Given').style('width: 100px;')
                ui.label('Expires').style('width: 100px;')

            for v in pet.vaccinations:
                is_current = v.expiration_date > datetime.utcnow()
                row_bg = '#f7f9ff' if is_current else '#fef2f2'
                exp_color = '#16a34a' if is_current else '#dc2626'
                with ui.row().classes('w-full items-center px-4 py-3').style(
                    f'background: {row_bg}; border-bottom: 1px solid #eaeef5; font-size: 13px;'
                ):
                    ui.label(v.vaccine_name).classes('flex-1').style('font-weight: 600;')
                    ui.label(v.manufacturer or '—').style('width: 120px; color: #57423d;')
                    ui.label(v.serial_number or '—').style(
                        'width: 100px; font-family: monospace; font-size: 11px; color: #57423d;'
                    )
                    ui.label(
                        v.date_given.strftime('%Y-%m-%d') if v.date_given else '—'
                    ).style('width: 100px; color: #57423d;')
                    ui.label(
                        v.expiration_date.strftime('%Y-%m-%d') if v.expiration_date else '—'
                    ).style(f'width: 100px; font-weight: 600; color: {exp_color};')
        else:
            ui.label('No vaccinations recorded.').style(
                'color: #57423d; font-style: italic; margin-bottom: 1rem;'
            )

        # ── Add vaccination records (multi-row) ──
        from ..data import get_vaccine_options_for_dropdown
        vaccine_options = get_vaccine_options_for_dropdown(pet.pet_species)

        ui.separator().classes('my-4')
        ui.label('Add Vaccination Records').style(
            'font-weight: 600; font-size: 16px; color: #171c21; margin-bottom: 0.5rem;'
        )
        ui.label(
            'Fill in one row per vaccine. Fields match NASPHV Form 51 requirements.'
        ).style('font-size: 12px; color: #8a716c; margin-bottom: 1rem;')

        # Container for dynamic rows
        rows_container = ui.column().classes('w-full gap-3')
        vaccine_rows = []

        def add_row():
            """Add a new vaccine input row."""
            with rows_container:
                row_data = {}
                with ui.row().classes('w-full items-end gap-3 p-3 rounded-lg').style(
                    'background: #f0f4fb; border: 1px solid #eaeef5;'
                ):
                    row_data['name'] = ui.select(
                        options=vaccine_options, label='Vaccine',
                        with_input=True,
                    ).classes('flex-1').props('outlined dense use-input input-debounce="200"')
                    row_data['manufacturer'] = ui.input(
                        'Manufacturer'
                    ).style('width: 130px;').props('outlined dense')
                    row_data['serial'] = ui.input(
                        'Serial/Lot #'
                    ).style('width: 110px;').props('outlined dense')
                    row_data['date_given'] = ui.input(
                        'Date Given'
                    ).style('width: 130px;').props('outlined dense type=date')
                    row_data['expiration'] = ui.input(
                        'Expires'
                    ).style('width: 130px;').props('outlined dense type=date')

                    def remove_this_row(rd=row_data):
                        if rd in vaccine_rows:
                            vaccine_rows.remove(rd)
                        ui.navigate.to(f'/pet/{pet.id}')

                    ui.button(
                        icon='close', on_click=remove_this_row,
                    ).props('flat dense round color=negative').tooltip('Remove row')

                vaccine_rows.append(row_data)

        # Add first row by default
        add_row()

        # Add more button
        ui.button(
            '+ Add Another Vaccine', on_click=add_row,
        ).classes('mt-2').props('flat no-caps').style(
            'color: #3b82f6; font-weight: 600; font-size: 13px;'
        )

        # Save all button
        async def save_all_vaccinations():
            saved_count = 0
            errors = []
            with Session(engine) as s:
                for i, row in enumerate(vaccine_rows):
                    vname = row['name'].value
                    vdate = row['date_given'].value
                    vexp = row['expiration'].value

                    if not vname:
                        continue  # skip empty rows
                    if not vdate or not vexp:
                        errors.append(f'Row {i+1}: Date Given and Expiration are required.')
                        continue

                    try:
                        new_v = Vaccination(
                            pet_id=pet.id,
                            vaccine_name=vname,
                            manufacturer=row['manufacturer'].value.strip() or None,
                            serial_number=row['serial'].value.strip() or None,
                            date_given=datetime.strptime(vdate, '%Y-%m-%d'),
                            expiration_date=datetime.strptime(vexp, '%Y-%m-%d'),
                            administering_vet='',
                            clinic_name='',
                        )
                        record_data = new_v.dict(
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
                ui.notify(
                    f'{saved_count} vaccination record{"s" if saved_count > 1 else ""} added!',
                    type='positive',
                )
                ui.navigate.to(f'/pet/{pet.id}')
            elif not errors:
                ui.notify('No records to save. Fill in at least one row.', type='info')

        ui.button(
            'Save Vaccination Records', icon='save', on_click=save_all_vaccinations,
        ).classes('w-full mt-4').style(
            'background: #a03a21; color: white; font-weight: 600;'
        ).props('no-caps')

    # ── Trust signals (same as public) ──
    _render_trust_signals()


# ─────────────────────────────────────────────────────────────
# PET EDIT PAGE — inline edit form for pet owners
# ─────────────────────────────────────────────────────────────

def _render_pet_edit_page(pet, session):
    """Render the pet edit form matching pet_profile_edit.html template."""
    from ..data import get_vaccine_options_for_dropdown
    from .common import dog_client

    # ── Header ──
    with ui.column().classes('w-full items-center mb-8'):
        ui.label('Edit Pet Profile').style(
            "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
            "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
            "color: #171c21;"
        )
        ui.label(
            "Update your companion's care and identification details."
        ).style('font-size: 18px; line-height: 1.6; color: #5d5c58; margin-top: 4px;')

    # ── Section tabs ──
    section_ids = ['edit-basic', 'edit-care', 'edit-health']
    tab_labels = ['Basic Info', 'Daily Care', 'Health & Temperament']

    with ui.row().classes('w-full gap-10 mb-8 pb-4').style(
        'border-bottom: 1px solid #eaeef5;'
    ):
        for i, label in enumerate(tab_labels):
            active_style = (
                'color: #a03a21; font-weight: 600; font-size: 14px; '
                'border-bottom: 2px solid #a03a21; padding-bottom: 16px; '
                'margin-bottom: -17px; cursor: pointer;'
            )
            inactive_style = (
                'color: #5d5c58; font-weight: 600; font-size: 14px; '
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
            ui.label('Basic Info').style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )

        with ui.column().classes('p-10 gap-6'):
            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Pet Name').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    name_input = ui.input(
                        value=pet.name or ''
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Microchip ID').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    chip_input = ui.input(
                        value=pet.chip_id or ''
                    ).classes('w-full').props('outlined dense readonly')
                    ui.label('Chip ID cannot be changed after registration.').style(
                        'font-size: 11px; color: #8a716c; font-style: italic;'
                    )

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Species').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    species_input = ui.select(
                        ['DOG', 'CAT'], label='', value=pet.pet_species or 'DOG'
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Breed').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    breed_input = ui.input(
                        value=pet.breed or ''
                    ).classes('w-full').props('outlined dense')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Birth Date').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    dob_val = pet.dob.strftime('%Y-%m-%d') if pet.dob else ''
                    dob_input = ui.input(value=dob_val).classes('w-full').props(
                        'outlined dense type=date'
                    )

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Gender').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
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
            ui.label('Daily Care').style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )

        with ui.column().classes('p-10 gap-6'):
            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Energy Level').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    energy_input = ui.select(
                        ['Low', 'Moderate', 'High', 'Very High'],
                        label='', value=pet.energy_level or 'Moderate',
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Max Alone Hours').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    alone_input = ui.number(
                        '', value=pet.max_alone_hours, min=0, max=24,
                    ).classes('w-full').props('outlined dense')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Feeds per Day').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
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
            ui.label('Health & Temperament').style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )

        with ui.column().classes('p-10 gap-6'):
            with ui.column().classes('w-full gap-1'):
                ui.label('Temperament').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                temperament_input = ui.textarea(
                    value=pet.temperament or '',
                    placeholder='Friendly, shy, reactive to other dogs?',
                ).classes('w-full').props('outlined rows=3')

            with ui.column().classes('w-full gap-1'):
                ui.label('Dietary Notes').style(
                    'font-weight: 600; font-size: 14px; color: #171c21;'
                )
                dietary_input = ui.textarea(
                    value=pet.dietary_notes or '',
                    placeholder='Allergies or special diet requirements?',
                ).classes('w-full').props('outlined rows=3')

            with ui.row().classes('w-full gap-6'):
                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Exercise Needs').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    exercise_input = ui.input(
                        value=pet.exercise_needs or '',
                        placeholder='e.g. 30 min walk twice daily',
                    ).classes('w-full').props('outlined dense')

                with ui.column().classes('flex-1 gap-1'):
                    ui.label('Medical Conditions').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
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
        ).style('color: #5d5c58; font-weight: 600; padding: 12px 40px;').props(
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

                db_pet.name = name_input.value.strip()
                db_pet.pet_species = species_input.value
                db_pet.breed = breed_input.value.strip() if breed_input.value else None
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
                    temperament_input.value.strip() if temperament_input.value else None
                )
                db_pet.dietary_notes = (
                    dietary_input.value.strip() if dietary_input.value else None
                )
                db_pet.exercise_needs = (
                    exercise_input.value.strip() if exercise_input.value else None
                )
                db_pet.medical_conditions = (
                    medical_input.value.strip() if medical_input.value else None
                )

                s.add(db_pet)
                s.commit()

            ui.notify('Pet profile updated successfully!', type='positive')
            ui.navigate.to(f'/pet/{pet.id}')

        ui.button(
            'Save All Changes', on_click=save_changes,
        ).style(
            'background: #a03a21; color: white; font-weight: 600; '
            'padding: 12px 40px; border-radius: 8px; '
            'box-shadow: 0 4px 12px rgba(160,58,33,0.2);'
        ).props('no-caps')

    # ── Info banner ──
    with ui.row().classes('w-full items-start gap-3 mt-6 p-4 rounded-xl').style(
        'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
    ):
        ui.icon('info').style('font-size: 20px; color: #c2410c; margin-top: 2px;')
        ui.html(
            '<span style="font-size: 12px; color: #57423d;">'
            'Changes to medical identifiers like <strong>Microchip ID</strong> '
            'cannot be modified after registration. Tag updates reflect '
            'immediately on scan results.</span>'
        )


# ─────────────────────────────────────────────────────────────
# PAGE INIT — route handler with owner detection
# ─────────────────────────────────────────────────────────────

def init_pet_profile_page():
    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str, request: Request):
        try_restore_session(request)
        nav_header()

        with Session(engine) as session:
            pet = session.exec(
                select(Pet).where(Pet.id == uuid.UUID(pet_id))
            ).first()

            if not pet:
                with ui.column().classes('w-full items-center p-16'):
                    ui.icon('search_off').style(
                        'font-size: 64px; color: #dec0b9;'
                    )
                    ui.label('Pet Not Found').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                        "font-weight: 600; color: #171c21; margin-top: 1rem;"
                    )
                    ui.label(
                        'The pet record you are looking for does not exist.'
                    ).style('color: #57423d; margin-top: 0.5rem;')
                    ui.button(
                        'Back to Home', icon='home',
                        on_click=lambda: ui.navigate.to('/'),
                    ).classes('mt-6').props('outline no-caps')
                nav_footer()
                return

            is_owner = False
            current_user_id = app.storage.user.get('id')
            if current_user_id and pet.owner_id:
                is_owner = str(pet.owner_id) == current_user_id

            with ui.element('main').classes(
                'w-full max-w-7xl mx-auto px-6 py-12'
            ):
                if is_owner:
                    _render_private_view(pet, session)
                else:
                    _render_public_view(pet, session)

                back_target = '/dashboard' if is_owner else '/'
                back_label = 'Back to Dashboard' if is_owner else 'Back to Search'
                ui.button(
                    back_label, icon='arrow_back',
                    on_click=lambda: ui.navigate.to(back_target),
                ).classes('mt-8').props('flat no-caps').style(
                    'color: #57423d; font-weight: 600;'
                )

        nav_footer()

    @ui.page('/pet/{pet_id}/edit')
    async def pet_edit(pet_id: str, request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        nav_header()

        with Session(engine) as session:
            pet = session.exec(
                select(Pet).where(Pet.id == uuid.UUID(pet_id))
            ).first()

            if not pet:
                with ui.column().classes('w-full items-center p-16'):
                    ui.label('Pet Not Found').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                        "font-weight: 600; color: #171c21;"
                    )
                nav_footer()
                return

            # Only the owner can edit
            current_user_id = app.storage.user.get('id')
            if not current_user_id or str(pet.owner_id) != current_user_id:
                ui.navigate.to(f'/pet/{pet_id}')
                return

            with ui.element('main').classes(
                'w-full max-w-3xl mx-auto px-6 py-12'
            ):
                _render_pet_edit_page(pet, session)

        nav_footer()
