"""Subscription management UI pages."""

from nicegui import ui, app
from starlette.requests import Request
from .dashboard_shell import dashboard_shell
from .common import try_restore_session
import os
import httpx


def init_subscription_pages() -> None:

    @ui.page('/subscription/success')
    async def subscription_success(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        tier = request.query_params.get('tier', 'verified')
        session_id = request.query_params.get('session_id', '')
        tier_label = 'Verified' if tier == 'verified' else 'Guardian'

        # Activate subscription directly — Stripe only redirects here after
        # successful payment, so we can trust the tier param + authenticated user.
        if session_id:
            import logging
            _logger = logging.getLogger("pawsledger.subscription.success")
            from sqlmodel import Session as _Session, select as _select
            from ..database import engine as _engine
            from ..models import Subscription as _Subscription, _utc_now as _now
            from ..api.v1.common import serializer as _serializer
            from uuid import UUID as _UUID

            raw_cookie = request.cookies.get("paws_user_id")
            if raw_cookie:
                try:
                    user_id = _serializer.loads(raw_cookie)
                    with _Session(_engine) as db_session:
                        from ..models import User as _User
                        from ..services.stripe_service import StripeService as _Stripe
                        user = db_session.get(_User, _UUID(user_id))
                        if user:
                            checkout = _Stripe.retrieve_checkout_session(session_id)
                            stripe_customer_id = checkout.get("customer") if checkout else None
                            stripe_subscription_id = checkout.get("subscription") if checkout else None

                            # Fetch period dates from Stripe
                            from datetime import datetime as _dt, timezone as _tz
                            period_start = None
                            period_end = None
                            if stripe_subscription_id:
                                stripe_sub = _Stripe.get_subscription(stripe_subscription_id)
                                if stripe_sub:
                                    period_start = _dt.fromtimestamp(
                                        stripe_sub["current_period_start"], tz=_tz.utc
                                    ).replace(tzinfo=None)
                                    period_end = _dt.fromtimestamp(
                                        stripe_sub["current_period_end"], tz=_tz.utc
                                    ).replace(tzinfo=None)

                            sub = db_session.exec(
                                _select(_Subscription).where(_Subscription.user_id == user.id)
                            ).first()

                            if not sub:
                                sub = _Subscription(
                                    user_id=user.id,
                                    tier=tier,
                                    status="active",
                                    stripe_customer_id=stripe_customer_id,
                                    stripe_subscription_id=stripe_subscription_id,
                                    current_period_start=period_start,
                                    current_period_end=period_end,
                                )
                                db_session.add(sub)
                            else:
                                sub.tier = tier
                                sub.status = "active"
                                sub.stripe_customer_id = stripe_customer_id or sub.stripe_customer_id
                                sub.stripe_subscription_id = stripe_subscription_id or sub.stripe_subscription_id
                                sub.current_period_start = period_start or sub.current_period_start
                                sub.current_period_end = period_end or sub.current_period_end
                                sub.cancel_at_period_end = False
                                sub.updated_at = _now()
                                db_session.add(sub)

                            for pet in user.pets:
                                pet.identity_status = "VERIFIED"
                                db_session.add(pet)

                            db_session.commit()
                            _logger.info("Subscription activated on success page: user=%s tier=%s", user.id, tier)
                except Exception as e:
                    _logger.error("Failed to activate subscription on success page: %s", e)

        with dashboard_shell(title=f'{tier_label} Activated', breadcrumbs=[('Dashboard', '/dashboard')]):
            with ui.column().classes('w-full items-center gap-6 max-w-2xl mx-auto'):
                with ui.element('div').classes(
                    'flex items-center justify-center rounded-full'
                ).style(
                    'width: 96px; height: 96px; background: #dcfce7;'
                ):
                    ui.icon('check_circle').style('font-size: 48px; color: #16a34a;')

                ui.label(f'Welcome to {tier_label}!').classes(
                    'pl-heading-3xl'
                ).style(
                    'color: var(--pl-on-surface); text-align: center;'
                )
                ui.label(
                    f'Your {tier_label} subscription is now active. '
                    'All premium features are unlocked for your account.'
                ).style(
                    'font-size: 18px; color: var(--pl-on-surface-variant); text-align: center; '
                    'max-width: 480px; line-height: 1.6;'
                )

                with ui.card().classes('w-full p-8 mt-4').style(
                    'border-radius: 12px; background: var(--pl-surface-info); '
                    'border: 1px solid rgba(13,115,119,0.1);'
                ):
                    ui.label("What's now available:").style(
                        'font-weight: 600; font-size: 16px; color: var(--pl-on-surface); margin-bottom: 1rem;'
                    )
                    features = [
                        ('verified_user', 'Verified Identity Badge on all your pets'),
                        ('notifications_active', 'Vaccination & appointment reminders'),
                        ('description', 'Care instructions for service providers'),
                        ('swap_horiz', 'Secure ownership transfer with audit trail'),
                        ('cloud_upload', 'Vaccination document storage'),
                        ('update', 'Periodic contact update reminders'),
                    ]
                    for icon_name, text in features:
                        with ui.row().classes('items-center gap-3 mb-3'):
                            ui.icon(icon_name).style('font-size: 20px; color: var(--pl-primary);')
                            ui.label(text).style('font-size: 14px; color: var(--pl-on-surface);')

                with ui.row().classes('gap-4 mt-6'):
                    ui.button(
                        'Go to Dashboard', icon='dashboard',
                        on_click=lambda: ui.navigate.to('/dashboard'),
                    ).style(
                        'background: var(--pl-primary); color: white; font-weight: 600; '
                        'padding: 12px 32px; border-radius: 8px;'
                    ).props('no-caps')
                    ui.button(
                        'Manage Subscription', icon='settings',
                        on_click=lambda: ui.navigate.to('/subscription/manage'),
                    ).props('outline no-caps').style(
                        'color: var(--pl-primary); border-color: var(--pl-primary); padding: 12px 32px;'
                    )

    @ui.page('/subscription/manage')
    async def subscription_manage(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        base_url = os.getenv('BASE_URL', 'http://localhost:8080')
        cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}
        async with httpx.AsyncClient(base_url=base_url) as client:
            resp = await client.get(
                '/api/v1/subscription/status',
                cookies=cookies,
            )

        sub_data = resp.json() if resp.status_code == 200 else None
        is_active = sub_data and sub_data.get('status') == 'active'
        tier = sub_data.get('tier', 'free') if sub_data else 'free'

        with dashboard_shell(title='Subscription', breadcrumbs=[('Dashboard', '/dashboard')]):
            with ui.column().classes('w-full gap-6 max-w-2xl'):
                ui.label('Subscription Management').classes('pl-heading-3xl')

                if is_active:
                    tier_label = tier.capitalize()
                    cancel_pending = sub_data.get('cancel_at_period_end', False)
                    period_end = sub_data.get('current_period_end')

                    with ui.card().classes('w-full p-8').style(
                        'border-radius: 12px; border-left: 4px solid ' + ('#f59e0b' if cancel_pending else '#16a34a') + ';'
                    ):
                        with ui.row().classes('items-center gap-3 mb-4'):
                            icon = 'schedule' if cancel_pending else 'verified'
                            color = '#f59e0b' if cancel_pending else '#16a34a'
                            ui.icon(icon).style(f'font-size: 28px; color: {color};')
                            status_text = f'{tier_label} Plan — Cancels at period end' if cancel_pending else f'{tier_label} Plan — Active'
                            ui.label(status_text).style(
                                'font-size: 20px; font-weight: 600; color: var(--pl-on-surface);'
                            )
                        if period_end:
                            from datetime import datetime
                            end_date = datetime.fromisoformat(period_end)
                            date_label = 'Access until' if cancel_pending else 'Next billing date'
                            ui.label(
                                f'{date_label}: {end_date.strftime("%B %d, %Y")}'
                            ).style('font-size: 14px; color: var(--pl-on-surface-variant);')

                    if cancel_pending:
                        ui.label(
                            'Your subscription will end at the date above. '
                            'You can reactivate anytime before then to keep your benefits.'
                        ).classes('mt-2').style('font-size: 14px; color: var(--pl-on-surface-variant);')

                    # --- Cancel confirmation dialog ---
                    cancel_dialog = ui.dialog()
                    with cancel_dialog, ui.card().classes('p-6').style('min-width: 360px; border-radius: 12px;'):
                        ui.label('Cancel Subscription?').style(
                            'font-size: 18px; font-weight: 600; color: var(--pl-on-surface);'
                        )
                        ui.label(
                            'Your subscription will remain active until the end of your '
                            'current billing period. After that, premium features will be disabled.'
                        ).classes('mt-2').style('font-size: 14px; color: var(--pl-on-surface-variant); line-height: 1.5;')
                        with ui.row().classes('mt-6 justify-end gap-3'):
                            ui.button('Keep Subscription', on_click=cancel_dialog.close).props(
                                'flat no-caps'
                            ).style('color: var(--pl-on-surface-variant);')

                            async def confirm_cancel():
                                cancel_dialog.close()
                                async with httpx.AsyncClient(base_url=base_url) as client:
                                    resp = await client.post(
                                        '/api/v1/subscription/cancel',
                                        cookies=cookies,
                                    )
                                    if resp.status_code == 200:
                                        ui.notify('Subscription will cancel at end of billing period.', type='warning')
                                        ui.navigate.to('/subscription/manage')
                                    else:
                                        detail = resp.json().get('detail', 'Failed to cancel.')
                                        ui.notify(detail, type='negative')

                            ui.button('Yes, Cancel', on_click=confirm_cancel).style(
                                'background: #dc2626; color: white; font-weight: 600; '
                                'padding: 8px 24px; border-radius: 8px;'
                            ).props('no-caps')

                    # --- Action buttons ---
                    with ui.row().classes('mt-4 gap-3'):
                        if cancel_pending:
                            async def reactivate():
                                async with httpx.AsyncClient(base_url=base_url) as client:
                                    resp = await client.post(
                                        '/api/v1/subscription/reactivate',
                                        cookies=cookies,
                                    )
                                    if resp.status_code == 200:
                                        ui.notify('Subscription reactivated!', type='positive')
                                        ui.navigate.to('/subscription/manage')
                                    else:
                                        detail = resp.json().get('detail', 'Failed to reactivate.')
                                        ui.notify(detail, type='negative')

                            ui.button(
                                'Reactivate Subscription', icon='refresh',
                                on_click=reactivate,
                            ).style(
                                'background: var(--pl-primary); color: white; font-weight: 600; '
                                'padding: 12px 32px; border-radius: 8px;'
                            ).props('no-caps')
                        else:
                            ui.button(
                                'Cancel Subscription', icon='cancel',
                                on_click=cancel_dialog.open,
                            ).style(
                                'background: #dc2626; color: white; font-weight: 600; '
                                'padding: 12px 32px; border-radius: 8px;'
                            ).props('no-caps')

                else:
                    with ui.card().classes('w-full p-8').style(
                        'border-radius: 12px; border-left: 4px solid #a8a29e;'
                    ):
                        ui.label('Free Plan').style(
                            'font-size: 20px; font-weight: 600; color: var(--pl-on-surface);'
                        )
                        ui.label(
                            'Upgrade to Verified or Guardian for premium features.'
                        ).style('font-size: 14px; color: var(--pl-on-surface-variant); margin-top: 0.5rem;')

                    ui.button(
                        'View Plans', icon='upgrade',
                        on_click=lambda: ui.navigate.to('/pricing'),
                    ).classes('mt-4').style(
                        'background: var(--pl-primary); color: white; font-weight: 600; '
                        'padding: 12px 32px; border-radius: 8px;'
                    ).props('no-caps')

    @ui.page('/transfer/accept')
    async def transfer_accept_page(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        token = request.query_params.get('token', '')

        with dashboard_shell(title='Accept Transfer', breadcrumbs=[('Dashboard', '/dashboard')]):
            with ui.column().classes('w-full items-center gap-6 max-w-2xl mx-auto'):
                ui.icon('swap_horiz').style('font-size: 64px; color: var(--pl-primary);')
                ui.label('Accept Pet Ownership Transfer').classes(
                    'pl-heading-2xl'
                ).style(
                    'color: var(--pl-on-surface); text-align: center;'
                )

                detail_container = ui.column().classes('w-full items-center gap-4')
                action_container = ui.column().classes('w-full items-center gap-4')

                base_url = os.getenv('BASE_URL', 'http://localhost:8080')
                async with httpx.AsyncClient(base_url=base_url) as client:
                    resp = await client.get(
                        '/api/v1/transfer/details',
                        params={'token': token},
                    )

                if resp.status_code == 200:
                    details = resp.json()

                    with detail_container:
                        if details.get('is_expired') or details.get('status') != 'pending':
                            status = details['status'] if details['status'] != 'pending' else 'expired'
                            with ui.card().classes('w-full p-6').style(
                                'border-radius: 12px; border-left: 4px solid #dc2626;'
                            ):
                                ui.label(f'This transfer is {status}.').style(
                                    'font-size: 16px; color: #dc2626; font-weight: 600;'
                                )
                            return

                        with ui.card().classes('w-full p-6').style(
                            'border-radius: 12px; background: var(--pl-surface-info); '
                            'border: 1px solid rgba(13,115,119,0.1);'
                        ):
                            ui.label('Transfer Details').style(
                                'font-weight: 600; font-size: 16px; color: var(--pl-on-surface); margin-bottom: 0.75rem;'
                            )
                            with ui.column().classes('gap-2'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('pets').style('font-size: 18px; color: var(--pl-primary);')
                                    ui.label(f'Pet: {details["pet_name"]}').style(
                                        'font-size: 15px; color: var(--pl-on-surface); font-weight: 500;'
                                    )
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('memory').style('font-size: 18px; color: var(--pl-on-surface-variant);')
                                    ui.label(f'Chip ID: {details["chip_id"]}').style(
                                        'font-size: 14px; color: var(--pl-on-surface-variant);'
                                    )
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('person').style('font-size: 18px; color: var(--pl-on-surface-variant);')
                                    ui.label(f'From: {details["from_owner_name"]}').style(
                                        'font-size: 14px; color: var(--pl-on-surface-variant);'
                                    )
                                if details.get('notes'):
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('note').style('font-size: 18px; color: var(--pl-on-surface-variant);')
                                        ui.label(f'Note: {details["notes"]}').style(
                                            'font-size: 14px; color: var(--pl-on-surface-variant); font-style: italic;'
                                        )

                        ui.label(
                            'By accepting, this pet will be transferred to your PawsLedger account.'
                        ).style('font-size: 14px; color: var(--pl-on-surface-variant); text-align: center;')

                    with action_container:
                        async def accept():
                            cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}
                            async with httpx.AsyncClient(base_url=base_url) as c:
                                r = await c.post(
                                    '/api/v1/transfer/accept',
                                    json={'transfer_token': token},
                                    cookies=cookies,
                                )
                                if r.status_code == 200:
                                    data = r.json()
                                    ui.notify(data.get('message', 'Transfer accepted!'), type='positive')
                                    ui.navigate.to('/dashboard')
                                else:
                                    detail = r.json().get('detail', 'Transfer failed.')
                                    ui.notify(detail, type='negative')

                        ui.button(
                            'Accept Transfer', icon='check',
                            on_click=accept,
                        ).style(
                            'background: var(--pl-primary); color: white; font-weight: 600; '
                            'padding: 14px 40px; border-radius: 8px; font-size: 16px;'
                        ).props('no-caps')

                        ui.button(
                            'Cancel',
                            on_click=lambda: ui.navigate.to('/dashboard'),
                        ).props('flat no-caps').style('color: var(--pl-on-surface-variant); margin-top: 1rem;')

                else:
                    with detail_container:
                        ui.label(
                            'Transfer not found or the link is invalid.'
                        ).style('font-size: 16px; color: #dc2626;')
                    with action_container:
                        ui.button(
                            'Go to Dashboard',
                            on_click=lambda: ui.navigate.to('/dashboard'),
                        ).props('flat no-caps').style('color: var(--pl-on-surface-variant);')
