from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_about_page():
    @ui.page('/about')
    async def about_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('About PawsLedger').classes('pl-page-title mb-6')
            ui.markdown("""
            PawsLedger is a hybrid identity platform that provides a **"Single Source of Truth"** for pet records.
            We link physical identifiers (Microchip or QR Tag) to a secure, cloud-based digital ledger.

            ### Our Mission
            - **Decoupled Identity:** Separate pet records from proprietary manufacturer databases.
            - **Trusted Transfer:** Securely manage ownership changes.
            - **Seamless Access:** Provide time-bound access for vets and caregivers.
            """)
        nav_footer()
