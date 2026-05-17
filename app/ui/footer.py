from nicegui import ui


def nav_footer():
    with ui.footer().classes('w-full py-4 px-6 md:px-12').style(
        "background-color: #f5f5f4; border-top: 1px solid #e7e5e4; "
        "font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;"
    ):
        with ui.row().classes('max-w-7xl mx-auto w-full justify-between items-center'):
            # Left — brand + copyright
            with ui.row().classes('items-center gap-3'):
                ui.label('PawsLedger').style(
                    'font-weight: 700; font-size: 14px; color: #a03a21;'
                )
                ui.label('© 2026 PawsLedger. Nurturing Professionalism in Pet Care.').style(
                    'color: #8a716c;'
                )

            # Right — inline links
            with ui.row().classes('items-center gap-6'):
                ui.link('Pricing', '/pricing').style('color: #8a716c; text-decoration: none;')
                ui.link('Privacy', '/privacy').style('color: #8a716c; text-decoration: none;')
                ui.link('Terms', '/terms').style('color: #8a716c; text-decoration: none;')
                ui.link('Contact', '/contact').style('color: #8a716c; text-decoration: none;')
                ui.link('FAQ', '/faq').style('color: #8a716c; text-decoration: none;')
