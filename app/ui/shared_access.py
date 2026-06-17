from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import LedgerEvent, SharedAccess, _utc_now
from .header import nav_header
from .footer import nav_footer
from .common import email_service


def init_shared_access_page() -> None:
    @ui.page('/shared/{token}')
    async def shared_profile(token: str) -> None:
        nav_header()

        with Session(engine) as session:
            statement = select(SharedAccess).where(SharedAccess.token == token)
            shared_access = session.exec(statement).first()

            if not shared_access or shared_access.expires_at < _utc_now():
                with ui.element('main').classes('w-full max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12'):
                    with ui.column().classes('w-full items-center p-16'):
                        ui.icon('link_off').style(
                            'font-size: 64px; color: var(--pl-primary); opacity: 0.5;'
                        )
                        ui.label('Access Expired or Invalid').classes(
                            'pl-heading-2xl'
                        ).style(
                            'color: var(--pl-on-surface); margin-top: 1rem;'
                        )
                        ui.label(
                            'This shared care link is no longer active. '
                            'Please request a new link from the pet owner.'
                        ).style('color: var(--pl-on-surface-variant); margin-top: 0.5rem; text-align: center;')
                nav_footer()
                return

            pet = shared_access.pet

            # Deduplication: only log access + notify if last access was >5 minutes ago
            now = _utc_now()
            from datetime import timedelta
            is_fresh_access = (
                shared_access.last_accessed_at is None
                or (now - shared_access.last_accessed_at) > timedelta(minutes=5)
            )
            is_first_access = shared_access.last_accessed_at is None

            shared_access.last_accessed_at = now
            shared_access.access_count = (shared_access.access_count or 0) + 1
            session.add(shared_access)

            if is_fresh_access:
                event = LedgerEvent(
                    pet_id=pet.id,
                    event_type="HEARTBEAT_ACCESS",
                    description="Shared records accessed via time-bound link",
                )
                session.add(event)
            session.commit()

            if is_first_access and pet.owner and pet.owner.email:
                await email_service.notify_owner_of_access(
                    pet.owner.email, pet.breed or "Pet",
                    "Service Provider (Shared Link)",
                )

            with ui.element('main').classes('w-full max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12'):
                # Access status banner
                with ui.row().classes(
                    'w-full items-center gap-4 p-5 rounded-xl mb-8'
                ).style(
                    'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
                ):
                    ui.icon('schedule').style('font-size: 28px; color: #83250e;')
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('Time-Limited Access').style(
                            'font-weight: 600; font-size: 16px; color: #83250e;'
                        )
                        ui.label(
                            f'Expires: {shared_access.expires_at.strftime("%b %d, %Y at %H:%M UTC")}'
                        ).style('font-size: 13px; color: var(--pl-on-surface-variant);')
                    ui.label('Active').style(
                        'padding: 4px 12px; background: #dcfce7; color: #166534; '
                        'font-size: 12px; font-weight: 600; border-radius: 9999px;'
                    )

                # Main content row
                with ui.row().classes('w-full gap-6 flex-wrap items-start'):
                    # Left: Pet info + vaccinations
                    with ui.column().classes('flex-1 gap-6').style('min-width: min(360px, 100%);'):
                        # Pet identification
                        with ui.element('div').classes('w-full p-8 rounded-xl').style(
                            'background: white; box-shadow: var(--pl-shadow-md); '
                            'border-left: 4px solid var(--pl-primary);'
                        ):
                            # Pet photo or species emoji fallback
                            with ui.row().classes('w-full items-center gap-4 mb-4'):
                                if pet.photo_url:
                                    ui.image(
                                        f'/api/v1/pets/{pet.id}/photo'
                                    ).classes('rounded-full').style(
                                        'width: 72px; height: 72px; object-fit: cover;'
                                    )
                                else:
                                    _species_emoji = {
                                        'DOG': '\U0001F415', 'CAT': '\U0001F408'
                                    }
                                    emoji = _species_emoji.get(
                                        pet.pet_species or 'DOG', '\U0001F43E'
                                    )
                                    with ui.element('div').style(
                                        'width: 72px; height: 72px; border-radius: 50%; '
                                        'background: var(--pl-primary-light); display: flex; '
                                        'align-items: center; justify-content: center; '
                                        'font-size: 32px;'
                                    ):
                                        ui.label(emoji).style('line-height: 1;')
                                ui.label(pet.name or pet.breed or 'Pet').style(
                                    "font-family: 'Plus Jakarta Sans'; font-size: 22px; "
                                    "font-weight: 700; color: var(--pl-on-surface);"
                                )

                            ui.label('Pet Information').classes(
                                'pl-heading-lg'
                            ).style(
                                'color: var(--pl-on-surface); margin-bottom: 1rem;'
                            )
                            info_items = [
                                ('pets', 'Name', pet.name or 'Unknown'),
                                ('category', 'Species', pet.pet_species or 'Unknown'),
                                ('genetics', 'Breed', pet.breed or 'Unknown'),
                                ('cake', 'Date of Birth',
                                 pet.dob.strftime('%b %d, %Y') if pet.dob else 'Unknown'),
                                ('fingerprint', 'Chip ID', pet.chip_id),
                            ]
                            for icon_name, label, value in info_items:
                                with ui.row().classes(
                                    'w-full items-center justify-between py-3'
                                ).style('border-bottom: 1px solid var(--pl-surface-info);'):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.icon(icon_name).style(
                                            'font-size: 18px; color: var(--pl-primary);'
                                        )
                                        ui.label(label).style(
                                            'font-size: 14px; color: var(--pl-on-surface-variant);'
                                        )
                                    ui.label(value).style(
                                        'font-size: 14px; font-weight: 600; color: var(--pl-on-surface);'
                                    )

                        # Vaccination records
                        with ui.element('div').classes('w-full p-8 rounded-xl').style(
                            'background: white; box-shadow: var(--pl-shadow-md); '
                            'border-left: 4px solid #3b82f6;'
                        ):
                            ui.label('Vaccination Records').classes(
                                'pl-heading-lg'
                            ).style(
                                'color: var(--pl-on-surface); margin-bottom: 1rem;'
                            )
                            if pet.vaccinations:
                                for v in pet.vaccinations:
                                    is_current = v.expiration_date > _utc_now()
                                    row_bg = '#f7f9ff' if is_current else '#fef2f2'
                                    exp_color = '#16a34a' if is_current else '#dc2626'
                                    with ui.row().classes(
                                        'w-full items-center justify-between p-4 rounded-lg mb-3'
                                    ).style(f'background: {row_bg};'):
                                        with ui.column().classes('gap-1'):
                                            ui.label(v.vaccine_name).style(
                                                'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                                            )
                                            ui.label(
                                                f'Given: {v.date_given.strftime("%Y-%m-%d")}'
                                            ).style('font-size: 12px; color: var(--pl-on-surface-variant);')
                                        with ui.column().classes('items-end gap-1'):
                                            status = 'Current' if is_current else 'Expired'
                                            ui.label(status).style(
                                                f'font-weight: 600; font-size: 12px; color: {exp_color};'
                                            )
                                            ui.label(
                                                f'Exp: {v.expiration_date.strftime("%Y-%m-%d")}'
                                            ).style(f'font-size: 12px; color: {exp_color};')
                            else:
                                ui.label('No vaccination records available.').style(
                                    'color: var(--pl-on-surface-variant); font-style: italic; font-size: 14px;'
                                )

                    # Right sidebar: Care instructions + medical alerts
                    with ui.column().classes('gap-6').style(
                        'width: 300px; flex-shrink: 0;'
                    ):
                        # Medical alert
                        if pet.medical_conditions:
                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                'background: #fef2f2; border: 1px solid #fecaca;'
                            ):
                                with ui.row().classes('items-center gap-2 mb-2'):
                                    ui.icon('warning').style(
                                        'font-size: 20px; color: #dc2626;'
                                    )
                                    ui.label('Medical Alert').style(
                                        'font-weight: 700; font-size: 16px; color: #b91c1c;'
                                    )  # keep specific alert colors
                                ui.label(pet.medical_conditions).style(
                                    'font-size: 14px; color: #b91c1c;'
                                )

                        # Care Instructions (from Pet model fields)
                        _care_items = [
                            ('restaurant', 'Feeding', f'{pet.feeds_per_day} meals/day' if pet.feeds_per_day else None),
                            ('no_food', 'Dietary Notes', pet.dietary_notes),
                            ('medication', 'Medication', pet.medication_notes),
                            ('directions_run', 'Exercise', pet.exercise_needs),
                            ('bolt', 'Energy Level', pet.energy_level),
                            ('schedule', 'Max Alone', f'{pet.max_alone_hours} hours' if pet.max_alone_hours else None),
                            ('mood', 'Temperament', pet.temperament),
                            ('notes', 'Care Notes', pet.care_notes),
                        ]
                        _visible_care = [(i, l, v) for i, l, v in _care_items if v]

                        # Emergency contact card
                        if pet.emergency_contact_name or pet.emergency_contact_phone:
                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                'background: #fff7ed; border: 1px solid #fed7aa;'
                            ):
                                with ui.row().classes('items-center gap-2 mb-2'):
                                    ui.icon('contact_emergency').style(
                                        'font-size: 20px; color: #ea580c;'
                                    )
                                    ui.label('Emergency Contact').style(
                                        'font-weight: 700; font-size: 16px; color: #c2410c;'
                                    )
                                if pet.emergency_contact_name:
                                    ui.label(pet.emergency_contact_name).style(
                                        'font-size: 14px; font-weight: 600; color: var(--pl-on-surface);'
                                    )
                                if pet.emergency_contact_phone:
                                    ui.label(pet.emergency_contact_phone).style(
                                        'font-size: 14px; color: var(--pl-on-surface); font-family: monospace;'
                                    )

                        # Pet clinic card
                        if pet.clinic_name or pet.clinic_phone:
                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                'background: #f0fdf4; border: 1px solid #bbf7d0;'
                            ):
                                with ui.row().classes('items-center gap-2 mb-2'):
                                    ui.icon('local_hospital').style(
                                        'font-size: 20px; color: #16a34a;'
                                    )
                                    ui.label('Pet Clinic').style(
                                        'font-weight: 700; font-size: 16px; color: #166534;'
                                    )
                                if pet.clinic_name:
                                    ui.label(pet.clinic_name).style(
                                        'font-size: 14px; font-weight: 600; color: var(--pl-on-surface);'
                                    )
                                if pet.clinic_address:
                                    ui.label(pet.clinic_address).style(
                                        'font-size: 13px; color: var(--pl-on-surface-variant);'
                                    )
                                if pet.clinic_phone:
                                    ui.label(pet.clinic_phone).style(
                                        'font-size: 14px; color: var(--pl-on-surface); font-family: monospace;'
                                    )

                        # Emergency vet card (critical priority highlight)
                        if pet.emergency_vet_name or pet.emergency_vet_phone:
                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                'background: #fef2f2; border: 1px solid #fecaca;'
                            ):
                                with ui.row().classes('items-center gap-2 mb-2'):
                                    ui.icon('emergency').style(
                                        'font-size: 20px; color: #dc2626;'
                                    )
                                    ui.label('Emergency Vet').style(
                                        'font-weight: 700; font-size: 16px; color: #b91c1c;'
                                    )
                                if pet.emergency_vet_name:
                                    ui.label(pet.emergency_vet_name).style(
                                        'font-size: 14px; font-weight: 600; color: var(--pl-on-surface);'
                                    )
                                if pet.emergency_vet_phone:
                                    ui.label(pet.emergency_vet_phone).style(
                                        'font-size: 14px; color: var(--pl-on-surface); font-family: monospace;'
                                    )

                        if _visible_care:
                            # Determine card style based on care_priority
                            is_critical = pet.care_priority == "critical"
                            is_important = pet.care_priority == "important"
                            card_bg = '#fef2f2' if is_critical else ('#fff7ed' if is_important else '#faf5ff')
                            card_border = '#fecaca' if is_critical else ('#fed7aa' if is_important else '#e9d5ff')
                            icon_color = '#dc2626' if is_critical else ('#ea580c' if is_important else '#7c3aed')

                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                f'background: {card_bg}; border: 1px solid {card_border};'
                            ):
                                with ui.row().classes('items-center gap-2 mb-3'):
                                    ui.icon('description').style(
                                        f'font-size: 20px; color: {icon_color};'
                                    )
                                    ui.label('Care Instructions').style(
                                        'font-weight: 600; font-size: 16px; color: var(--pl-on-surface);'
                                    )
                                    if is_critical:
                                        ui.label('CRITICAL').style(
                                            'padding: 2px 8px; background: #dc2626; color: white; '
                                            'font-size: 10px; font-weight: 700; border-radius: 9999px;'
                                        )
                                    elif is_important:
                                        ui.label('IMPORTANT').style(
                                            'padding: 2px 8px; background: #ea580c; color: white; '
                                            'font-size: 10px; font-weight: 700; border-radius: 9999px;'
                                        )
                                for icon_name, label, value in _visible_care:
                                    with ui.column().classes('w-full mb-3 pb-3').style(
                                        f'border-bottom: 1px solid {card_border};'
                                    ):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.icon(icon_name).style(
                                                f'font-size: 16px; color: {icon_color};'
                                            )
                                            ui.label(label).style(
                                                'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                                            )
                                        ui.label(value).style(
                                            'font-size: 13px; color: var(--pl-on-surface-variant); '
                                            'margin-top: 4px; line-height: 1.5;'
                                        )

                # Footer disclaimer
                with ui.row().classes(
                    'w-full items-center gap-2 mt-8 pt-6'
                ).style('border-top: 1px solid #e7e5e4;'):
                    ui.icon('info').style('font-size: 16px; color: var(--pl-text-hint);')
                    ui.label(
                        'This is a time-limited care access link. '
                        'The pet owner has been notified of this access.'
                    ).style('font-size: 12px; color: var(--pl-text-hint);')

        nav_footer()
