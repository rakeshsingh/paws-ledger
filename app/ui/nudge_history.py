"""Nudge history page — sent and received nudges with management controls."""

import os

import httpx
from nicegui import ui, app
from starlette.requests import Request

from .dashboard_shell import dashboard_shell
from .common import try_restore_session


def init_nudge_history_page() -> None:

    @ui.page('/nudges')
    async def nudge_history_page(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        base_url = os.getenv('BASE_URL', 'http://localhost:8080')
        cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}

        # Fetch both sent and received nudges
        async with httpx.AsyncClient(base_url=base_url) as client:
            sent_resp = await client.get('/api/v1/nudges/sent', cookies=cookies)
            received_resp = await client.get('/api/v1/nudges/received', cookies=cookies)

        sent_nudges = sent_resp.json() if sent_resp.status_code == 200 else []
        received_nudges = received_resp.json() if received_resp.status_code == 200 else []

        with dashboard_shell(title='Nudge History', breadcrumbs=[('Dashboard', '/dashboard')]):
            with ui.column().classes('w-full gap-6 max-w-3xl'):

                # Tabs: Received / Sent
                with ui.tabs().classes('w-full') as tabs:
                    tab_received = ui.tab('Received').props('no-caps')
                    tab_sent = ui.tab('Sent').props('no-caps')

                with ui.tab_panels(tabs, value=tab_received).classes('w-full'):

                    # ── Received nudges ──
                    with ui.tab_panel(tab_received).classes('p-0 pt-4'):
                        if not received_nudges:
                            _empty_state(
                                'No nudges received yet.',
                                'When someone finds your pet and sends a nudge, it will appear here.',
                            )
                        else:
                            for nudge in received_nudges:
                                _render_received_nudge_card(nudge, base_url, cookies)

                    # ── Sent nudges ──
                    with ui.tab_panel(tab_sent).classes('p-0 pt-4'):
                        if not sent_nudges:
                            _empty_state(
                                'No nudges sent yet.',
                                'When you find a pet and send a nudge to the owner, it will appear here.',
                            )
                        else:
                            for nudge in sent_nudges:
                                _render_sent_nudge_card(nudge, base_url, cookies)


def _empty_state(title: str, subtitle: str):
    with ui.column().classes('w-full items-center py-12 gap-3'):
        ui.icon('notifications_off').style('font-size: 48px; color: #a8a29e;')
        ui.label(title).style(
            'font-size: 16px; font-weight: 600; color: var(--pl-on-surface);'
        )
        ui.label(subtitle).style(
            'font-size: 14px; color: var(--pl-on-surface-variant); text-align: center; max-width: 400px;'
        )


def _status_badge(status: str):
    colors = {
        'pending': ('background: #fef3c7; color: #92400e; border: 1px solid #fde68a;', 'schedule'),
        'responded': ('background: #dcfce7; color: #166534; border: 1px solid #bbf7d0;', 'check_circle'),
        'expired': ('background: #fee2e2; color: #991b1b; border: 1px solid #fecaca;', 'timer_off'),
    }
    style, icon_name = colors.get(status, colors['pending'])
    with ui.row().classes('items-center gap-1').style(
        f'padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; {style}'
    ):
        ui.icon(icon_name).style('font-size: 14px;')
        ui.label(status.capitalize())


def _render_received_nudge_card(nudge: dict, base_url: str, cookies: dict):
    status = nudge.get('status', 'pending')
    with ui.card().classes('w-full p-5 mb-3').style(
        'border-radius: 10px; border-left: 4px solid var(--pl-primary);'
    ):
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-1 flex-1'):
                ui.label(nudge.get('message', '')[:200]).style(
                    'font-size: 14px; color: var(--pl-on-surface); line-height: 1.5; white-space: pre-wrap;'
                )
                # GPS link
                lat = nudge.get('geo_latitude')
                lon = nudge.get('geo_longitude')
                if lat and lon:
                    map_url = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}'
                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.icon('location_on').style('font-size: 14px; color: var(--pl-primary);')
                        ui.link('View location', map_url, new_tab=True).style(
                            'font-size: 12px; color: var(--pl-primary);'
                        )

            _status_badge(status)

        with ui.row().classes('w-full justify-between items-center mt-3').style(
            'border-top: 1px solid #f5f5f4; padding-top: 0.5rem;'
        ):
            from datetime import datetime
            created = nudge.get('created_at', '')
            try:
                dt = datetime.fromisoformat(created)
                ui.label(dt.strftime('%b %d, %Y %H:%M')).style(
                    'font-size: 12px; color: var(--pl-text-hint);'
                )
            except (ValueError, TypeError):
                ui.label('').style('font-size: 12px;')

            with ui.row().classes('gap-2'):
                nudge_id = nudge.get('id', '')

                async def delete_received(nid=nudge_id):
                    async with httpx.AsyncClient(base_url=base_url) as client:
                        r = await client.delete(f'/api/v1/nudges/{nid}', cookies=cookies)
                        if r.status_code == 200:
                            ui.notify('Nudge removed from your history.', type='info')
                            ui.navigate.to('/nudges')
                        else:
                            ui.notify('Failed to delete.', type='negative')

                ui.button(icon='delete_outline', on_click=delete_received).props(
                    'flat dense round'
                ).style('color: #a8a29e;').tooltip('Remove from history')


def _render_sent_nudge_card(nudge: dict, base_url: str, cookies: dict):
    status = nudge.get('status', 'pending')
    with ui.card().classes('w-full p-5 mb-3').style(
        'border-radius: 10px; border-left: 4px solid #7c3aed;'
    ):
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-1 flex-1'):
                ui.label(nudge.get('message', '')).style(
                    'font-size: 14px; color: var(--pl-on-surface); line-height: 1.5;'
                )

            _status_badge(status)

        with ui.row().classes('w-full justify-between items-center mt-3').style(
            'border-top: 1px solid #f5f5f4; padding-top: 0.5rem;'
        ):
            from datetime import datetime
            created = nudge.get('created_at', '')
            try:
                dt = datetime.fromisoformat(created)
                ui.label(dt.strftime('%b %d, %Y %H:%M')).style(
                    'font-size: 12px; color: var(--pl-text-hint);'
                )
            except (ValueError, TypeError):
                ui.label('').style('font-size: 12px;')

            with ui.row().classes('gap-2'):
                nudge_id = nudge.get('id', '')

                async def delete_sent(nid=nudge_id):
                    async with httpx.AsyncClient(base_url=base_url) as client:
                        r = await client.delete(f'/api/v1/nudges/{nid}', cookies=cookies)
                        if r.status_code == 200:
                            ui.notify('Nudge removed from your history.', type='info')
                            ui.navigate.to('/nudges')
                        else:
                            ui.notify('Failed to delete.', type='negative')

                ui.button(icon='delete_outline', on_click=delete_sent).props(
                    'flat dense round'
                ).style('color: #a8a29e;').tooltip('Remove from history')
