"""Nudge reply page — owner replies to finder via secure token-authenticated form."""

import os

import httpx
from nicegui import ui, app
from starlette.requests import Request

from .dashboard_shell import dashboard_shell
from .common import try_restore_session


def init_nudge_reply_page() -> None:

    @ui.page('/nudge/reply')
    async def nudge_reply_page(request: Request) -> None:
        token = request.query_params.get('token', '')

        if not token:
            ui.label('Invalid link — no token provided.').style(
                'color: #dc2626; font-size: 18px; padding: 2rem;'
            )
            return

        base_url = os.getenv('BASE_URL', 'http://localhost:8080')

        # Fetch nudge details (GET does not invalidate token)
        async with httpx.AsyncClient(base_url=base_url) as client:
            resp = await client.get(
                '/api/v1/nudge/reply',
                params={'token': token},
            )

        if resp.status_code == 410:
            # Expired or already used
            detail = resp.json().get('detail', 'This link has expired.')
            with ui.column().classes('w-full items-center justify-center min-h-screen gap-6 p-8'):
                ui.icon('link_off').style('font-size: 64px; color: #dc2626;')
                ui.label('Link Expired').style(
                    'font-size: 24px; font-weight: 700; color: var(--pl-on-surface);'
                )
                ui.label(detail).style(
                    'font-size: 16px; color: var(--pl-on-surface-variant); text-align: center; max-width: 480px;'
                )
                ui.label(
                    'If you need to respond, ask the finder to send another nudge.'
                ).style('font-size: 14px; color: var(--pl-on-surface-variant); font-style: italic;')
                ui.button(
                    'Go to Dashboard', icon='dashboard',
                    on_click=lambda: ui.navigate.to('/dashboard'),
                ).style(
                    'background: var(--pl-primary); color: white; font-weight: 600; '
                    'padding: 12px 32px; border-radius: 8px;'
                ).props('no-caps')
            return

        if resp.status_code == 404:
            with ui.column().classes('w-full items-center justify-center min-h-screen gap-6 p-8'):
                ui.icon('error_outline').style('font-size: 64px; color: #dc2626;')
                ui.label('Nudge Not Found').style(
                    'font-size: 24px; font-weight: 700; color: var(--pl-on-surface);'
                )
                ui.label('This link is invalid or the nudge no longer exists.').style(
                    'font-size: 16px; color: var(--pl-on-surface-variant);'
                )
            return

        if resp.status_code != 200:
            with ui.column().classes('w-full items-center justify-center min-h-screen gap-6 p-8'):
                ui.icon('error').style('font-size: 64px; color: #dc2626;')
                ui.label('Something went wrong.').style(
                    'font-size: 24px; font-weight: 700; color: var(--pl-on-surface);'
                )
            return

        nudge_data = resp.json()

        # Owner must be authenticated
        if not try_restore_session(request):
            ui.navigate.to(f'/login?next=/nudge/reply?token={token}')
            return

        with dashboard_shell(title='Reply to Finder', breadcrumbs=[('Dashboard', '/dashboard')]):
            with ui.column().classes('w-full items-center gap-6 max-w-2xl mx-auto'):
                ui.icon('mail').style('font-size: 48px; color: var(--pl-primary);')
                ui.label('Respond to Finder').classes('pl-heading-2xl').style(
                    'text-align: center;'
                )
                ui.label(
                    'Someone found your pet and sent you a message. '
                    'Reply below — your email address will remain hidden.'
                ).style(
                    'font-size: 15px; color: var(--pl-on-surface-variant); '
                    'text-align: center; max-width: 480px; line-height: 1.6;'
                )

                # Show finder's message
                with ui.card().classes('w-full p-6').style(
                    'border-radius: 12px; background: var(--pl-surface-info); '
                    'border: 1px solid rgba(13,115,119,0.1);'
                ):
                    ui.label("Finder's Message:").style(
                        'font-weight: 600; font-size: 14px; color: var(--pl-on-surface); margin-bottom: 0.5rem;'
                    )
                    ui.label(nudge_data.get('finder_message', '')).style(
                        'font-size: 15px; color: var(--pl-on-surface); '
                        'white-space: pre-wrap; line-height: 1.5;'
                    )

                    # Show GPS if available
                    lat = nudge_data.get('geo_latitude')
                    lon = nudge_data.get('geo_longitude')
                    if lat and lon:
                        with ui.row().classes('items-center gap-2 mt-3').style(
                            'border-top: 1px solid rgba(0,0,0,0.05); padding-top: 0.75rem;'
                        ):
                            ui.icon('location_on').style('font-size: 18px; color: var(--pl-primary);')
                            map_url = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}'
                            ui.link(
                                'View found location on map', map_url, new_tab=True
                            ).style('font-size: 14px; color: var(--pl-primary); font-weight: 500;')

                    created = nudge_data.get('created_at', '')
                    if created:
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(created)
                            ui.label(f'Sent: {dt.strftime("%B %d, %Y at %H:%M UTC")}').style(
                                'font-size: 12px; color: var(--pl-text-hint); margin-top: 0.5rem;'
                            )
                        except ValueError:
                            pass

                # Reply form
                reply_input = ui.textarea(
                    label='Your reply (max 1000 characters)',
                    placeholder='Thank you for finding my pet! Here is how we can connect...',
                ).props('outlined counter maxlength=1000').classes('w-full')

                ui.label(
                    'Your email address will NOT be shared. '
                    'The finder will receive your message from recovery@pawsledger.com.'
                ).style(
                    'font-size: 12px; color: var(--pl-on-surface-variant); font-style: italic; text-align: center;'
                )

                async def submit_reply():
                    msg = reply_input.value or ''
                    if len(msg.strip()) < 1:
                        ui.notify('Please write a reply message.', type='warning')
                        return
                    if len(msg.strip()) > 1000:
                        ui.notify('Reply must be at most 1000 characters.', type='warning')
                        return

                    cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}
                    async with httpx.AsyncClient(base_url=base_url) as client:
                        r = await client.post(
                            '/api/v1/nudge/reply',
                            json={
                                'response_token': token,
                                'message': msg.strip(),
                            },
                            cookies=cookies,
                        )
                        if r.status_code == 200:
                            ui.notify('Reply sent successfully!', type='positive')
                            ui.navigate.to('/dashboard')
                        elif r.status_code == 403:
                            detail = r.json().get('detail', '')
                            if 'Verified' in detail:
                                ui.notify(
                                    'Secure reply requires a Verified subscription.',
                                    type='warning',
                                )
                                ui.navigate.to('/pricing')
                            else:
                                ui.notify(detail, type='negative')
                        elif r.status_code == 410:
                            ui.notify(
                                r.json().get('detail', 'This link has expired.'),
                                type='warning',
                            )
                        else:
                            ui.notify(
                                r.json().get('detail', 'Failed to send reply.'),
                                type='negative',
                            )

                ui.button(
                    'Send Secure Reply', icon='send',
                    on_click=submit_reply,
                ).style(
                    'background: var(--pl-primary); color: white; font-weight: 600; '
                    'padding: 14px 40px; border-radius: 8px; font-size: 16px;'
                ).props('no-caps')
