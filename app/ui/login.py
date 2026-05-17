from nicegui import ui, app
from starlette.requests import Request
from .header import nav_header
from .footer import nav_footer


GOOGLE_G_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="20" height="20">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    <path fill="none" d="M0 0h48v48H0z"/>
</svg>'''


def init_login_pages() -> None:
    @ui.page('/login')
    async def login_page(request: Request) -> None:
        if app.storage.user.get('email'):
            ui.navigate.to('/dashboard')
            return
        nav_header()

        with ui.element('main').classes(
            'w-full flex items-center justify-center'
        ).style(
            'min-height: calc(100vh - 200px); '
            'background: radial-gradient(circle at top right, rgba(255,218,210,0.4), transparent), '
            'radial-gradient(circle at bottom left, rgba(234,238,245,0.4), transparent);'
        ):
            with ui.column().classes('items-center gap-8').style(
                'width: 100%; max-width: 400px; padding: 3rem 1.5rem;'
            ):
                # Brand header
                with ui.column().classes('items-center gap-3'):
                    with ui.element('div').classes(
                        'flex items-center justify-center rounded-full'
                    ).style(
                        'width: 64px; height: 64px; background: #ffdad2;'
                    ):
                        ui.icon('pets').style('font-size: 32px; color: #a03a21;')
                    ui.label('Welcome to PawsLedger').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 28px; "
                        "font-weight: 700; color: #171c21; text-align: center;"
                    )
                    ui.label(
                        'Sign in to manage your pets, vaccinations, and recovery tags.'
                    ).style(
                        'font-size: 14px; color: #57423d; text-align: center; '
                        'max-width: 320px;'
                    )

                # Login card
                with ui.element('div').classes('w-full p-8 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border: 1px solid rgba(222,192,185,0.3);'
                ):
                    def login_google():
                        ui.navigate.to('/api/v1/auth/login')

                    with ui.button(on_click=login_google).classes('w-full mb-4').style(
                        'background: #fff; color: #3c4043; border: 1px solid #dadce0; '
                        'border-radius: 4px; height: 44px; padding: 0 12px; '
                        'font-family: Roboto, arial, sans-serif; font-size: 14px; '
                        'font-weight: 500; text-transform: none; letter-spacing: 0.25px; '
                        'box-shadow: 0 1px 2px 0 rgba(60,64,67,.30), '
                        '0 1px 3px 1px rgba(60,64,67,.15);'
                    ):
                        ui.html(GOOGLE_G_SVG)
                        ui.label('Sign in with Google')

                    with ui.row().classes(
                        'w-full items-center gap-3 my-4'
                    ):
                        ui.element('div').classes('flex-1').style(
                            'height: 1px; background: #e7e5e4;'
                        )
                        ui.label('Secure Authentication').style(
                            'font-size: 11px; color: #8a716c; white-space: nowrap;'
                        )
                        ui.element('div').classes('flex-1').style(
                            'height: 1px; background: #e7e5e4;'
                        )

                    with ui.row().classes('items-center gap-2'):
                        ui.icon('lock').style('font-size: 14px; color: #8a716c;')
                        ui.label(
                            'Authorized Identity Provider Only'
                        ).style('font-size: 12px; color: #8a716c;')

                # Trust signals
                with ui.row().classes('items-center gap-6 mt-2'):
                    for icon_name, label in [
                        ('verified_user', 'Encrypted'),
                        ('visibility_off', 'Private'),
                        ('speed', 'Instant'),
                    ]:
                        with ui.row().classes('items-center gap-1'):
                            ui.icon(icon_name).style(
                                'font-size: 14px; color: #8a716c;'
                            )
                            ui.label(label).style(
                                'font-size: 12px; color: #8a716c; font-weight: 500;'
                            )

        nav_footer()
