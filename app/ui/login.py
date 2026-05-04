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


def init_login_pages():
    @ui.page('/login')
    async def login_page(request: Request):
        if app.storage.user.get('email'):
            ui.navigate.to('/dashboard')
            return
        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            with ui.card().classes('w-full max-w-sm p-6 items-center'):
                ui.label('Welcome Back').classes('text-2xl font-bold mb-4')
                ui.label('Secure login for PawsLedger').style(
                    'color: #78716c; font-size: 14px; margin-bottom: 1.5rem; text-align: center;'
                )

                def login_google():
                    ui.navigate.to('/api/v1/auth/login')

                with ui.button(on_click=login_google) \
                    .classes('w-full google-signin-btn mb-4') \
                    .style(
                        'background: #fff; color: #3c4043; border: 1px solid #dadce0; '
                        'border-radius: 4px; height: 44px; padding: 0 12px; '
                        'font-family: Roboto, arial, sans-serif; font-size: 14px; '
                        'font-weight: 500; text-transform: none; letter-spacing: 0.25px; '
                        'box-shadow: 0 1px 2px 0 rgba(60,64,67,.30), 0 1px 3px 1px rgba(60,64,67,.15);'
                    ):
                    ui.html(GOOGLE_G_SVG)
                    ui.label('Sign in with Google')

                ui.separator().classes('mb-4')
                ui.label('Authorized Identity Provider Only').style(
                    'font-size: 12px; color: #9ca3af;'
                )
        nav_footer()
