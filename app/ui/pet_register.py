from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User, PetTag, LedgerEvent
from ..services.integrations import get_manufacturer_from_chip
from .header import nav_header
from .footer import nav_footer
from .common import dog_client, try_restore_session
from datetime import datetime
import uuid


def init_register_page():
    @ui.page('/register')
    async def register(request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        nav_header()

        breeds = await dog_client.get_breeds()
        breed_options = {b['name']: b['name'] for b in breeds}

        with ui.element('main').classes('w-full max-w-3xl mx-auto px-6 py-12'):
            # ── Header ──
            with ui.column().classes('w-full items-center mb-8'):
                ui.label('Register New Pet').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21;"
                )
                ui.label(
                    "Add your companion's identification and care details to PawsLedger."
                ).style(
                    'font-size: 18px; line-height: 1.6; color: #5d5c58; margin-top: 4px;'
                )

            # ── Section tabs (clickable navigation) ──
            section_ids = ['section-basic', 'section-care', 'section-health', 'section-tags']
            tab_labels = ['Basic Info', 'Daily Care', 'Health & Temperament', 'Physical Tags']

            with ui.row().classes(
                'w-full gap-10 mb-8 pb-4'
            ).style('border-bottom: 1px solid #eaeef5;'):
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

            # ══════════════════════════════════════════════════════
            # SECTION 1: BASIC INFO
            # ══════════════════════════════════════════════════════
            with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-6').style(
                'background: white; border: 1px solid #eaeef5; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
            ).props('id="section-basic"'):
                with ui.element('div').classes('p-6').style(
                    'border-bottom: 1px solid #eaeef5; background: white;'
                ):
                    ui.label('Basic Info').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                        "font-weight: 600; color: #171c21;"
                    )

                with ui.column().classes('p-10 gap-6'):
                    # Two-column grid
                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Pet Name').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            name_input = ui.input(
                                placeholder='e.g. Cooper'
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Microchip ID').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            chip_input = ui.input(
                                placeholder='15-digit microchip number'
                            ).classes('w-full').props('outlined dense')

                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Species').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            species_input = ui.select(
                                ['DOG', 'CAT'], label='', value='DOG'
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1') as breed_col:
                            ui.label('Breed').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            # Dog breed dropdown (populated from Dog API)
                            breed_input = ui.select(
                                breed_options, label=''
                            ).classes('w-full').props(
                                'outlined dense use-input input-debounce="300"'
                            )
                            # Cat breed free-text input (hidden by default)
                            breed_text_input = ui.input(
                                placeholder='e.g. Persian, Siamese, Maine Coon'
                            ).classes('w-full').props('outlined dense')
                            breed_text_input.set_visibility(False)

                            def on_species_change(e):
                                is_dog = e.value == 'DOG'
                                breed_input.set_visibility(is_dog)
                                breed_text_input.set_visibility(not is_dog)
                                if not is_dog:
                                    breed_input.value = None

                            species_input.on('update:model-value', on_species_change)

                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Birth Date').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            dob_input = ui.input('').classes('w-full').props(
                                'outlined dense type=date'
                            )

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Gender').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            gender_input = ui.select(
                                ['Male', 'Female', 'Unknown'],
                                label='', value='Unknown',
                            ).classes('w-full').props('outlined dense')

            # ══════════════════════════════════════════════════════
            # SECTION 2: DAILY CARE
            # ══════════════════════════════════════════════════════
            with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-6').style(
                'background: white; border: 1px solid #eaeef5; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
            ).props('id="section-care"'):
                with ui.element('div').classes('p-6').style(
                    'border-bottom: 1px solid #eaeef5; background: white;'
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
                                label='', value='Moderate',
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Max Alone Hours').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            alone_input = ui.number(
                                '', value=None, min=0, max=24,
                            ).classes('w-full').props('outlined dense suffix="hours"')

                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Feeds per Day').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            feeds_input = ui.number(
                                '', value=None, min=1, max=10,
                            ).classes('w-full').props('outlined dense')

            # ══════════════════════════════════════════════════════
            # SECTION 3: HEALTH & TEMPERAMENT
            # ══════════════════════════════════════════════════════
            with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-6').style(
                'background: white; border: 1px solid #eaeef5; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
            ).props('id="section-health"'):
                with ui.element('div').classes('p-6').style(
                    'border-bottom: 1px solid #eaeef5; background: white;'
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
                            placeholder='Friendly, shy, reactive to other dogs?'
                        ).classes('w-full').props('outlined rows=3')

                    with ui.column().classes('w-full gap-1'):
                        ui.label('Dietary Notes').style(
                            'font-weight: 600; font-size: 14px; color: #171c21;'
                        )
                        dietary_input = ui.textarea(
                            placeholder='Allergies or special diet requirements?'
                        ).classes('w-full').props('outlined rows=3')

                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Exercise Needs').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            exercise_input = ui.select(
                                ['Minimal (Short walks)', 'Moderate (1-2 hours)', 'Intense (Running/Hiking)'],
                                label='', value='Moderate (1-2 hours)',
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Medical Conditions').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            medical_input = ui.textarea(
                                placeholder='List any ongoing health issues'
                            ).classes('w-full').props('outlined rows=3')

            # ══════════════════════════════════════════════════════
            # SECTION 4: PHYSICAL TAGS
            # ══════════════════════════════════════════════════════
            with ui.element('div').classes('w-full rounded-xl overflow-hidden mb-10').style(
                'background: white; border: 1px solid #eaeef5; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'
            ).props('id="section-tags"'):
                with ui.element('div').classes('p-6 flex justify-between items-center').style(
                    'border-bottom: 1px solid #eaeef5; background: white;'
                ):
                    ui.label('Physical Tags').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                        "font-weight: 600; color: #171c21;"
                    )
                    ui.label('(Optional — can be added later)').style(
                        'font-size: 12px; color: #5d5c58;'
                    )

                with ui.column().classes('p-10 gap-6'):
                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Tag Type').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            tag_type_input = ui.select(
                                ['', 'QR', 'NFC', 'DUAL'],
                                label='', value='',
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Tag Label').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            tag_label_input = ui.input(
                                placeholder='e.g. Collar tag'
                            ).classes('w-full').props('outlined dense')

                    with ui.row().classes('w-full gap-6'):
                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Tag Code').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            tag_code_input = ui.input(
                                placeholder='Leave blank to auto-generate'
                            ).classes('w-full').props('outlined dense')

                        with ui.column().classes('flex-1 gap-1'):
                            ui.label('Serial Number').style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )
                            tag_serial_input = ui.input(
                                placeholder='Optional'
                            ).classes('w-full').props('outlined dense')

            # ── Action buttons ──
            with ui.row().classes(
                'w-full justify-end items-center gap-4 pt-6'
            ).style('border-top: 1px solid #eaeef5;'):
                ui.button(
                    'Cancel',
                    on_click=lambda: ui.navigate.to('/dashboard'),
                ).style(
                    'color: #5d5c58; font-weight: 600; padding: 12px 40px;'
                ).props('flat no-caps')

                async def submit():
                    # Validate required fields
                    if not name_input.value or not name_input.value.strip():
                        ui.notify('Pet Name is required.', type='negative')
                        return
                    chip_val = chip_input.value.strip() if chip_input.value else ''
                    if not chip_val or len(chip_val) != 15 or not chip_val.isdigit():
                        ui.notify(
                            'Invalid Chip ID. Must be exactly 15 numeric digits.',
                            type='negative',
                        )
                        return

                    manufacturer = get_manufacturer_from_chip(chip_val)

                    with Session(engine) as session:
                        user = session.exec(
                            select(User).where(
                                User.email == app.storage.user['email']
                            )
                        ).first()
                        if not user:
                            ui.notify('User session error.', type='negative')
                            return
                        if len(user.pets) >= 5:
                            ui.notify(
                                'Maximum of 5 pets reached per profile.',
                                type='negative',
                            )
                            return

                        # Check chip uniqueness
                        existing_pet = session.exec(
                            select(Pet).where(Pet.chip_id == chip_val)
                        ).first()
                        if existing_pet:
                            ui.notify(
                                'This Chip ID is already registered.',
                                type='negative',
                            )
                            return

                        new_pet = Pet(
                            name=name_input.value.strip(),
                            chip_id=chip_val,
                            breed=(
                                breed_input.value
                                if species_input.value == 'DOG'
                                else (breed_text_input.value.strip() if breed_text_input.value else None)
                            ),
                            pet_species=species_input.value,
                            gender=gender_input.value,
                            dob=(
                                datetime.fromisoformat(dob_input.value)
                                if dob_input.value else None
                            ),
                            manufacturer=manufacturer,
                            identity_status="VERIFIED",
                            owner_id=user.id,
                            # Care fields
                            energy_level=energy_input.value if energy_input.value else None,
                            max_alone_hours=(
                                int(alone_input.value) if alone_input.value else None
                            ),
                            feeds_per_day=(
                                int(feeds_input.value) if feeds_input.value else None
                            ),
                            dietary_notes=(
                                dietary_input.value.strip()
                                if dietary_input.value else None
                            ),
                            exercise_needs=(
                                exercise_input.value if exercise_input.value else None
                            ),
                            medical_conditions=(
                                medical_input.value.strip()
                                if medical_input.value else None
                            ),
                            temperament=(
                                temperament_input.value.strip()
                                if temperament_input.value else None
                            ),
                        )
                        session.add(new_pet)
                        session.flush()  # Get the pet ID

                        # Create tag if provided
                        if tag_type_input.value:
                            code = (
                                tag_code_input.value.strip()
                                if tag_code_input.value
                                else str(uuid.uuid4()).replace('-', '')[:12].upper()
                            )
                            # Check tag code uniqueness
                            existing_tag = session.exec(
                                select(PetTag).where(PetTag.tag_code == code)
                            ).first()
                            if existing_tag:
                                ui.notify(
                                    'Tag code already in use. Tag was not created.',
                                    type='warning',
                                )
                            else:
                                new_tag = PetTag(
                                    pet_id=new_pet.id,
                                    tag_type=tag_type_input.value,
                                    tag_code=code,
                                    serial_number=(
                                        tag_serial_input.value.strip()
                                        if tag_serial_input.value else None
                                    ),
                                    label=(
                                        tag_label_input.value.strip()
                                        if tag_label_input.value else None
                                    ),
                                    qr_url=f'/qr/{code}',
                                )
                                session.add(new_tag)
                                session.add(LedgerEvent(
                                    pet_id=new_pet.id,
                                    event_type="TAG_ACTIVATED",
                                    description=(
                                        f"{tag_type_input.value} tag activated: {code}"
                                    ),
                                ))

                        session.commit()

                    ui.notify(
                        f'Successfully registered {name_input.value.strip()}!',
                        type='positive',
                    )
                    ui.navigate.to('/dashboard')

                ui.button(
                    'Register Pet', on_click=submit,
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
                    'may require verification for official travel documents. '
                    'Tag updates reflect immediately on scan results.</span>'
                )

        nav_footer()
