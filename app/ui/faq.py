from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_faq_page():
    @ui.page('/faq')
    async def faq_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Frequently Asked Questions').classes('pl-page-title mb-6')
            with ui.expansion('What is PawsLedger?', icon='help').classes('w-full'):
                ui.label('PawsLedger is a decentralized registry for pet identity and health records.')
            with ui.expansion('How does the Microchip lookup work?', icon='search').classes('w-full mt-2'):
                ui.label('We check our internal ledger first, then query the nationwide AAHA network to find registration details.')
            with ui.expansion('Is my data secure?', icon='security').classes('w-full mt-2'):
                ui.label('Yes, PawsLedger uses industry-standard encryption and obfuscates owner PII until an emergency state is toggled.')
        nav_footer()
