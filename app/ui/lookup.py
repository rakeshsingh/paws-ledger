"""Chip Lookup page — search for a pet by microchip ID."""

import os
import re

import httpx
from nicegui import ui, app, context
from starlette.requests import Request

from .dashboard_shell import dashboard_shell
from .common import try_restore_session

_BASE_URL = os.getenv('BASE_URL', 'http://localhost:8080')

_CHIP_PATTERN = re.compile(r'^[A-Za-z0-9]{3,15}$')

_LOOKUP_CSS = '''
/* Lookup page styles */
.lookup-card {
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 12px;
    padding: 32px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    max-width: 640px;
    width: 100%;
}

.lookup-result-card {
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    max-width: 640px;
    width: 100%;
    margin-top: 16px;
}

.lookup-result-found {
    border-left: 4px solid #16a34a;
}

.lookup-result-notfound {
    border-left: 4px solid #dc2626;
}

.lookup-prefix-info {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.lookup-input-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.lookup-input-row .q-field {
    flex: 1;
}

@media (max-width: 767px) {
    .lookup-card {
        padding: 20px;
    }
    .lookup-input-row {
        flex-direction: column;
    }
}
'''


def init_lookup_page() -> None:
    @ui.page('/lookup')
    async def lookup(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        with dashboard_shell(title='Chip Lookup'):
            ui.add_css(_LOOKUP_CSS)

            # Page header
            with ui.column().classes('gap-1 mb-6'):
                ui.label('Chip Lookup').style(
                    'font-size: 24px; font-weight: 800; color: var(--pl-on-surface); '
                    'letter-spacing: -0.02em;'
                )
                ui.label(
                    'Search for a pet by microchip ID to check registration status.'
                ).style('font-size: 14px; color: var(--pl-text-hint);')

            # Search card
            with ui.element('div').classes('lookup-card'):
                ui.label('Enter Microchip ID').style(
                    'font-size: 16px; font-weight: 700; color: var(--pl-on-surface); '
                    'margin-bottom: 4px;'
                )
                ui.label(
                    'Chip IDs are typically 9-15 alphanumeric characters.'
                ).style(
                    'font-size: 13px; color: var(--pl-text-hint); margin-bottom: 16px;'
                )

                # Input + submit
                chip_input = ui.input(
                    placeholder='e.g. 985112012345678',
                ).props(
                    'outlined dense clearable'
                ).style('flex: 1;')

                # Prefix info container (shown during typing)
                prefix_container = ui.column().classes('w-full')
                prefix_container.set_visibility(False)

                # Submit button
                submit_btn = ui.button(
                    'Search', icon='search',
                ).props('unelevated').style(
                    'background: var(--pl-primary) !important; color: white; '
                    'border-radius: 8px; margin-top: 16px; font-weight: 600;'
                )

            # Results container
            results_container = ui.column().classes('w-full').style('max-width: 640px;')
            results_container.set_visibility(False)

            # --- Handlers ---

            async def on_input_change():
                """Real-time prefix identification as user types."""
                value = (chip_input.value or '').strip()
                prefix_container.clear()

                if len(value) < 3 or not _CHIP_PATTERN.match(value):
                    prefix_container.set_visibility(False)
                    return

                try:
                    cookies = dict(context.client.request.cookies)
                    async with httpx.AsyncClient(
                        base_url=_BASE_URL, cookies=cookies, timeout=5.0
                    ) as client:
                        resp = await client.get(f'/api/v1/chip-prefix/{value}')
                        if resp.status_code == 200:
                            data = resp.json()
                            manufacturer = data.get('manufacturer', 'Unknown')
                            country = data.get('country', '')

                            with prefix_container:
                                with ui.element('div').classes('lookup-prefix-info'):
                                    ui.icon('info_outline').style(
                                        'font-size: 18px; color: var(--pl-primary);'
                                    )
                                    with ui.column().classes('gap-0'):
                                        ui.label(f'Manufacturer: {manufacturer}').style(
                                            'font-size: 13px; font-weight: 600; '
                                            'color: var(--pl-on-surface);'
                                        )
                                        if country:
                                            ui.label(f'Country: {country}').style(
                                                'font-size: 12px; color: var(--pl-text-hint);'
                                            )
                            prefix_container.set_visibility(True)
                        else:
                            prefix_container.set_visibility(False)
                except Exception:
                    prefix_container.set_visibility(False)

            async def on_submit():
                """Look up chip ID via the API."""
                value = (chip_input.value or '').strip()
                results_container.clear()

                if not value:
                    ui.notify('Please enter a chip ID.', type='warning')
                    return

                if not _CHIP_PATTERN.match(value):
                    ui.notify(
                        'Invalid chip ID format. Use 3-15 alphanumeric characters.',
                        type='negative',
                    )
                    return

                results_container.set_visibility(True)

                try:
                    cookies = dict(context.client.request.cookies)
                    async with httpx.AsyncClient(
                        base_url=_BASE_URL, cookies=cookies, timeout=10.0
                    ) as client:
                        resp = await client.get(f'/api/v1/lookup/{value}')

                        with results_container:
                            if resp.status_code == 200:
                                data = resp.json()
                                pet_name = data.get('name', 'Unknown')
                                pet_id = data.get('id', '')
                                species = data.get('pet_species', 'DOG')
                                breed = data.get('breed', '')
                                chip_id = data.get('chip_id', value)

                                with ui.element('div').classes(
                                    'lookup-result-card lookup-result-found'
                                ):
                                    with ui.row().classes('items-center gap-3 mb-4'):
                                        ui.icon('check_circle').style(
                                            'font-size: 24px; color: #16a34a;'
                                        )
                                        ui.label('Pet Found').style(
                                            'font-size: 18px; font-weight: 700; '
                                            'color: #166534;'
                                        )

                                    # Pet details
                                    details = [
                                        ('pets', 'Name', pet_name),
                                        ('fingerprint', 'Chip ID', chip_id),
                                        ('category', 'Species', species.capitalize()),
                                    ]
                                    if breed:
                                        details.append(('genetics', 'Breed', breed))

                                    for icon_name, label, val in details:
                                        with ui.row().classes(
                                            'w-full items-center justify-between py-2'
                                        ).style(
                                            'border-bottom: 1px solid #f1f5f9;'
                                        ):
                                            with ui.row().classes('items-center gap-2'):
                                                ui.icon(icon_name).style(
                                                    'font-size: 16px; '
                                                    'color: var(--pl-primary);'
                                                )
                                                ui.label(label).style(
                                                    'font-size: 13px; '
                                                    'color: var(--pl-text-hint);'
                                                )
                                            ui.label(val).style(
                                                'font-size: 13px; font-weight: 600; '
                                                'color: var(--pl-on-surface);'
                                            )

                                    # Link to profile
                                    if pet_id:
                                        ui.button(
                                            'View Pet Profile',
                                            icon='open_in_new',
                                            on_click=lambda: ui.navigate.to(
                                                f'/pet/{pet_id}'
                                            ),
                                        ).props('flat').style(
                                            'margin-top: 16px; color: var(--pl-primary); '
                                            'font-weight: 600;'
                                        )

                            elif resp.status_code == 404:
                                with ui.element('div').classes(
                                    'lookup-result-card lookup-result-notfound'
                                ):
                                    with ui.row().classes('items-center gap-3 mb-2'):
                                        ui.icon('search_off').style(
                                            'font-size: 24px; color: #dc2626;'
                                        )
                                        ui.label('Not Found').style(
                                            'font-size: 18px; font-weight: 700; '
                                            'color: #991b1b;'
                                        )
                                    ui.label(
                                        f'No pet is registered with chip ID "{value}" '
                                        f'in PawsLedger.'
                                    ).style(
                                        'font-size: 14px; color: var(--pl-on-surface-variant); '
                                        'margin-top: 4px;'
                                    )
                                    ui.label(
                                        'If this is your pet, you can register the chip now.'
                                    ).style(
                                        'font-size: 13px; color: var(--pl-text-hint); '
                                        'margin-top: 8px;'
                                    )
                                    ui.button(
                                        'Register This Chip',
                                        icon='add',
                                        on_click=lambda: ui.navigate.to('/register'),
                                    ).props('flat').style(
                                        'margin-top: 12px; color: var(--pl-primary); '
                                        'font-weight: 600;'
                                    )
                            else:
                                with ui.element('div').classes(
                                    'lookup-result-card lookup-result-notfound'
                                ):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.icon('error_outline').style(
                                            'font-size: 24px; color: #dc2626;'
                                        )
                                        ui.label(
                                            'Something went wrong. Please try again.'
                                        ).style(
                                            'font-size: 14px; color: #991b1b;'
                                        )

                except httpx.TimeoutException:
                    with results_container:
                        with ui.element('div').classes(
                            'lookup-result-card lookup-result-notfound'
                        ):
                            with ui.row().classes('items-center gap-3'):
                                ui.icon('timer_off').style(
                                    'font-size: 24px; color: #dc2626;'
                                )
                                ui.label(
                                    'Request timed out. Please try again.'
                                ).style('font-size: 14px; color: #991b1b;')
                except Exception:
                    with results_container:
                        with ui.element('div').classes(
                            'lookup-result-card lookup-result-notfound'
                        ):
                            with ui.row().classes('items-center gap-3'):
                                ui.icon('error_outline').style(
                                    'font-size: 24px; color: #dc2626;'
                                )
                                ui.label(
                                    'Unable to reach the server. Please try again.'
                                ).style('font-size: 14px; color: #991b1b;')

            # Wire up handlers
            chip_input.on('update:model-value', lambda: on_input_change())
            submit_btn.on_click(on_submit)
            chip_input.on('keydown.enter', on_submit)
