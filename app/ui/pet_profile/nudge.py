"""Secure nudge form — reusable component for public/QR views."""

import os

from nicegui import ui, app

from .helpers import with_loading


def render_nudge_form(pet):
    """Render the Secure Nudge form with auth/ownership/orphan checks."""
    import logging
    logger = logging.getLogger("pawsledger.ui.pet_profile")

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
            ).classes('pl-body-sm').style('margin-bottom: 8px;')
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
            ).classes('pl-body-sm').style('font-style: italic;')
            return

        if current_user_id and str(pet.owner_id) == current_user_id:
            ui.label(
                'You are the owner of this pet.'
            ).classes('pl-body-sm').style('font-style: italic;')
            return

        ui.label(
            'Your identity is verified but your email will not be shared with the owner.'
        ).classes('pl-body-sm').style('margin-bottom: 8px;')

        message_input = ui.textarea(
            label='Your message (10–500 characters)',
            placeholder='Describe where you found the pet and how the owner can reach you...',
        ).props('outlined counter maxlength=500').classes('w-full')

        # GPS location sharing — hidden inputs populated by browser geolocation
        geo_state = {'lat': None, 'lon': None, 'shared': False}
        location_label = ui.label('').classes('pl-body-xs').style('color: var(--pl-secondary); font-style: italic;')

        with ui.row().classes('items-center gap-2 mt-1'):
            async def request_location():
                geo_state['shared'] = False
                location_label.set_text('Requesting location...')
                ui.run_javascript('''
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            function(pos) {
                                emitEvent("geo_success", {lat: pos.coords.latitude, lon: pos.coords.longitude});
                            },
                            function(err) {
                                emitEvent("geo_error", {code: err.code});
                            },
                            {enableHighAccuracy: true, timeout: 10000}
                        );
                    } else {
                        emitEvent("geo_error", {code: 0});
                    }
                ''')

            share_btn = ui.button(
                'Share My Location', icon='my_location',
                on_click=request_location,
            ).props('outline no-caps dense').style(
                'color: var(--pl-primary); border-color: var(--pl-primary); font-size: 12px;'
            )

            ui.label(
                'Optional — helps the owner find their pet faster'
            ).classes('pl-body-xs').style('color: var(--pl-on-surface-variant);')

        async def on_geo_success(e):
            geo_state['lat'] = e.args.get('lat')
            geo_state['lon'] = e.args.get('lon')
            geo_state['shared'] = True
            location_label.set_text(f'Location shared ({geo_state["lat"]:.4f}, {geo_state["lon"]:.4f})')
            share_btn.set_text('Location Shared')
            share_btn.props(add='disable')

        async def on_geo_error(e):
            geo_state['shared'] = False
            location_label.set_text('Location unavailable — nudge will send without coordinates.')

        ui.on('geo_success', on_geo_success)
        ui.on('geo_error', on_geo_error)

        async def submit_nudge():
            msg = message_input.value or ''
            if len(msg.strip()) < 10:
                ui.notify('Message must be at least 10 characters.', type='warning')
                return
            if len(msg.strip()) > 500:
                ui.notify('Message must be at most 500 characters.', type='warning')
                return

            import httpx
            from nicegui import context
            base = os.getenv('BASE_URL', 'http://localhost:8080')
            cookies = context.client.request.cookies
            payload = {'message': msg.strip()}
            if geo_state.get('shared') and geo_state.get('lat') and geo_state.get('lon'):
                payload['geo_latitude'] = geo_state['lat']
                payload['geo_longitude'] = geo_state['lon']

            async with httpx.AsyncClient(base_url=base) as http_client:
                resp = await http_client.post(
                    f'/api/v1/nudge/{pet.chip_id}',
                    json=payload,
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
            async with with_loading(nudge_btn):
                await submit_nudge()

        nudge_btn.on_click(_nudge_guarded)
