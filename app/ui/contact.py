from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_contact_page():
    @ui.page('/contact')
    async def contact_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Contact Us').classes('pl-page-title mb-6')
            with ui.card().classes('w-full p-6'):
                ui.label('Have questions or need support?').classes('pl-subtitle mb-4')
                ui.input('Your Name').classes('w-full mb-4')
                ui.input('Your Email').classes('w-full mb-4')
                ui.textarea('Message').classes('w-full mb-4')
                ui.button('Send Message', on_click=lambda: ui.notify('Message sent (mock)')).classes('w-full pl-btn-primary')
        nav_footer()
