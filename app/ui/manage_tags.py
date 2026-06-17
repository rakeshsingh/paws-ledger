"""Unified tag management page — view and manage all NFC/QR tags across all pets."""

import uuid

from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select

from .dashboard_shell import dashboard_shell
from .common import try_restore_session
from ..database import engine
from ..models import Pet, User, PetTag, LedgerEvent, _utc_now


def _type_icon(tag_type: str) -> str:
    """Return Material icon name for a tag type."""
    if tag_type == 'QR':
        return 'qr_code_2'
    if tag_type == 'NFC':
        return 'nfc'
    return 'devices'


def _format_date(dt) -> str:
    """Format a datetime for display."""
    if not dt:
        return '-'
    return dt.strftime('%b %d, %Y')


async def _toggle_tag_status(tag_id, pet_id, current_status):
    """Toggle a tag between ACTIVE and DEACTIVATED."""
    with Session(engine) as s:
        db_tag = s.get(PetTag, tag_id)
        if not db_tag:
            ui.notify('Tag not found.', type='negative')
            return
        if current_status == 'ACTIVE':
            db_tag.status = 'DEACTIVATED'
            db_tag.deactivated_at = _utc_now()
            s.add(LedgerEvent(
                pet_id=pet_id,
                event_type="TAG_DEACTIVATED",
                description=f"Tag deactivated: {db_tag.tag_code}",
            ))
            s.add(db_tag)
            s.commit()
            ui.notify('Tag deactivated.', type='warning')
        else:
            db_tag.status = 'ACTIVE'
            db_tag.deactivated_at = None
            s.add(LedgerEvent(
                pet_id=pet_id,
                event_type="TAG_ACTIVATED",
                description=f"Tag reactivated: {db_tag.tag_code}",
            ))
            s.add(db_tag)
            s.commit()
            ui.notify('Tag reactivated.', type='positive')
    ui.navigate.to('/tags')


async def _remove_tag(tag_id, pet_id, tag_code):
    """Remove a tag from the database."""
    with Session(engine) as s:
        db_tag = s.get(PetTag, tag_id)
        if db_tag:
            s.add(LedgerEvent(
                pet_id=pet_id,
                event_type="TAG_REMOVED",
                description=f"Tag removed: {tag_code}",
            ))
            s.delete(db_tag)
            s.commit()
    ui.notify('Tag removed.', type='negative')
    ui.navigate.to('/tags')


async def _open_add_tag_dialog(pets):
    """Dialog to register a new tag — allows selecting which pet to link."""
    if not pets:
        ui.notify('Register a pet first before adding tags.', type='warning')
        return

    pet_options = {str(p.id): p.name or 'Unnamed' for p in pets}

    with ui.dialog() as dialog, ui.card().classes('p-8').style(
        'max-width: 560px; border-radius: 12px;'
    ):
        ui.label('Register New Tag').style(
            'font-weight: 800; font-size: 20px; color: var(--pl-on-surface); margin-bottom: 0.5rem;'
        )
        ui.label('Link a QR or NFC tag to one of your pets for instant identification.').style(
            'font-size: 14px; color: var(--pl-on-surface-variant); margin-bottom: 1.5rem;'
        )

        pet_select = ui.select(
            pet_options, label='Select Pet', value=list(pet_options.keys())[0]
        ).classes('w-full').props('outlined dense')

        tag_type = ui.select(
            ['QR', 'NFC', 'DUAL'], label='Tag Type', value='QR'
        ).classes('w-full').props('outlined dense')

        tag_label_input = ui.input(
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

        tag_manufacturer_input = ui.input(
            placeholder='e.g. PawTag, Tile'
        ).classes('w-full').props('outlined dense label="Manufacturer (optional)"')

        tag_notes = ui.textarea(
            placeholder='Any notes about this tag'
        ).classes('w-full').props('outlined rows=2 label="Notes (optional)"')

        async def add_tag():
            code = tag_code_input.value.strip() if tag_code_input.value else None
            selected_pet_id = uuid.UUID(pet_select.value)

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
                    pet_id=selected_pet_id,
                    tag_type=tag_type.value,
                    tag_code=generated_code,
                    serial_number=tag_serial.value.strip() or None,
                    manufacturer=tag_manufacturer_input.value.strip() or None,
                    nfc_uid=nfc_uid_input.value.strip() if nfc_uid_input.value else None,
                    nfc_technology=(
                        nfc_tech_input.value if tag_type.value in ('NFC', 'DUAL') else None
                    ),
                    qr_url=qr_url,
                    label=tag_label_input.value.strip() or None,
                    notes=tag_notes.value.strip() or None,
                )
                s.add(new_tag)
                s.add(LedgerEvent(
                    pet_id=selected_pet_id,
                    event_type="TAG_ACTIVATED",
                    description=(
                        f"{tag_type.value} tag activated: {generated_code}"
                        + (f" ({tag_label_input.value.strip()})" if tag_label_input.value.strip() else "")
                    ),
                ))
                s.commit()

            dialog.close()
            ui.notify('Tag added successfully!', type='positive')
            ui.navigate.to('/tags')

        with ui.row().classes('w-full justify-end gap-3 mt-4'):
            ui.button('Cancel', on_click=dialog.close).props(
                'flat no-caps'
            ).style('color: var(--pl-on-surface-variant);')
            add_btn = ui.button(
                'Register Tag', icon='nfc',
            ).style(
                'background: var(--pl-primary); color: white; font-weight: 600;'
            ).props('no-caps')
            add_btn.on_click(add_tag)

    dialog.open()


def init_manage_tags_page():
    """Register the /tags page."""

    @ui.page('/tags')
    async def manage_tags_page(request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        user_id = app.storage.user.get('id')
        if not user_id:
            ui.navigate.to('/login')
            return

        # Load all pets and their tags
        with Session(engine) as session:
            pets = session.exec(
                select(Pet).where(Pet.owner_id == uuid.UUID(user_id))
            ).all()

            # Build a flat list of all tags with pet info
            all_tags = []
            for pet in pets:
                for tag in pet.tags:
                    all_tags.append({
                        'tag': tag,
                        'pet_name': pet.name or 'Unnamed',
                        'pet_id': pet.id,
                        'tag_id': tag.id,
                        'tag_type': tag.tag_type,
                        'tag_code': tag.tag_code,
                        'label': tag.label or '-',
                        'status': tag.status,
                        'activated_at': tag.activated_at,
                        'nfc_uid': tag.nfc_uid,
                    })

        with dashboard_shell(
            title='Manage Tags',
            breadcrumbs=[('Dashboard', '/dashboard')],
            actions=[{
                'label': 'Add Tag',
                'icon': 'add',
                'style': 'primary',
                'on_click': lambda: _open_add_tag_dialog(pets),
            }],
        ):
            # Page header
            with ui.element('div').classes('mb-6'):
                ui.label('All Tags').style(
                    'font-weight: 800; font-size: 24px; color: var(--pl-on-surface);'
                )
                ui.label(
                    f'{len(all_tags)} tag{"s" if len(all_tags) != 1 else ""} across {len(pets)} pet{"s" if len(pets) != 1 else ""}'
                ).style('font-size: 14px; color: var(--pl-on-surface-variant); margin-top: 4px;')

            if not all_tags:
                # Empty state
                with ui.card().classes('w-full p-12 text-center').style(
                    'border: 2px dashed #e7e5e4; border-radius: 12px; background: white;'
                ):
                    ui.icon('nfc').style(
                        'font-size: 48px; color: var(--pl-text-hint); margin-bottom: 16px;'
                    )
                    ui.label('No tags registered yet').style(
                        'font-weight: 700; font-size: 18px; color: var(--pl-on-surface); margin-bottom: 8px;'
                    )
                    ui.label(
                        'Link NFC or QR tags to your pets for instant identification when scanned.'
                    ).style('font-size: 14px; color: var(--pl-on-surface-variant); margin-bottom: 24px;')
                    ui.button('Add Your First Tag', icon='add', on_click=lambda: _open_add_tag_dialog(pets)).style(
                        'background: var(--pl-primary); color: white; font-weight: 600;'
                    ).props('no-caps')
            else:
                # Tag cards
                with ui.column().classes('w-full gap-3'):
                    for entry in all_tags:
                        is_active = entry['status'] == 'ACTIVE'
                        status_bg = '#dcfce7' if is_active else '#fef2f2'
                        status_fg = '#166534' if is_active else '#991b1b'
                        icon = _type_icon(entry['tag_type'])

                        with ui.card().classes('w-full').style(
                            'border-radius: 12px; background: white; padding: 0; overflow: hidden;'
                        ):
                            with ui.row().classes(
                                'w-full items-center justify-between p-5'
                            ):
                                # Left section: icon + info
                                with ui.row().classes('items-center gap-4'):
                                    # Type icon with colored background
                                    with ui.element('div').classes(
                                        'flex items-center justify-center rounded-lg'
                                    ).style(
                                        f'width: 44px; height: 44px; background: {status_bg};'
                                    ):
                                        ui.icon(icon).style(
                                            f'font-size: 22px; color: {status_fg};'
                                        )

                                    # Tag details
                                    with ui.column().classes('gap-0'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.label(entry['label']).style(
                                                'font-weight: 600; font-size: 15px; color: var(--pl-on-surface);'
                                            )
                                            # Status badge
                                            ui.label(entry['status']).style(
                                                f'font-size: 10px; font-weight: 700; color: {status_fg}; '
                                                f'background: {status_bg}; padding: 2px 8px; '
                                                'border-radius: 9999px; text-transform: uppercase; '
                                                'letter-spacing: 0.05em;'
                                            )
                                        with ui.row().classes('items-center gap-3 mt-1'):
                                            ui.label(entry['pet_name']).style(
                                                'font-size: 12px; font-weight: 500; color: var(--pl-primary);'
                                            )
                                            ui.label(f'{entry["tag_type"]}').style(
                                                'font-size: 11px; color: var(--pl-text-hint); '
                                                'font-weight: 600; text-transform: uppercase;'
                                            )
                                            ui.label(f'Code: {entry["tag_code"]}').style(
                                                'font-family: monospace; font-size: 11px; '
                                                'color: var(--pl-on-surface-variant);'
                                            )
                                        if entry['nfc_uid']:
                                            ui.label(f'NFC UID: {entry["nfc_uid"]}').style(
                                                'font-family: monospace; font-size: 11px; '
                                                'color: var(--pl-text-hint); margin-top: 2px;'
                                            )

                                # Right section: activated date + actions
                                with ui.row().classes('items-center gap-3'):
                                    # Activated date
                                    ui.label(_format_date(entry['activated_at'])).style(
                                        'font-size: 12px; color: var(--pl-text-hint); min-width: 80px; text-align: right;'
                                    )

                                    # Toggle status button
                                    if is_active:
                                        ui.button(
                                            icon='block',
                                            on_click=lambda t_id=entry['tag_id'], p_id=entry['pet_id'], st=entry['status']: _toggle_tag_status(t_id, p_id, st),
                                        ).props('flat dense round').tooltip('Deactivate').style(
                                            'color: #b45309;'
                                        )
                                    else:
                                        ui.button(
                                            icon='check_circle',
                                            on_click=lambda t_id=entry['tag_id'], p_id=entry['pet_id'], st=entry['status']: _toggle_tag_status(t_id, p_id, st),
                                        ).props('flat dense round').tooltip('Reactivate').style(
                                            'color: #16a34a;'
                                        )

                                    # Remove button
                                    ui.button(
                                        icon='delete',
                                        on_click=lambda t_id=entry['tag_id'], p_id=entry['pet_id'], tc=entry['tag_code']: _remove_tag(t_id, p_id, tc),
                                    ).props('flat dense round color=negative').tooltip('Remove tag')
