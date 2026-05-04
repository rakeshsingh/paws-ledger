from nicegui import ui


def nav_footer():
    with ui.footer().classes('w-full py-12 px-6 md:px-12').style(
        "background-color: #f5f5f4; border-top: 1px solid #e7e5e4; "
        "font-family: 'Plus Jakarta Sans', sans-serif; font-size: 14px;"
    ):
        with ui.row().classes('max-w-7xl mx-auto w-full justify-between gap-8'):
            # Left — brand + copyright
            with ui.column().classes('gap-4'):
                ui.label('PawsLedger').style(
                    'font-weight: 700; font-size: 1.25rem; color: #1c1917;'
                )
                ui.label(
                    '© 2026 PawsLedger. Nurturing Professionalism in Pet Data Management.'
                ).style('color: #78716c; max-width: 24rem;')

            # Right — link columns
            with ui.row().classes('gap-16'):
                with ui.column().classes('gap-2'):
                    ui.label('Legal').style('font-weight: 700; color: #1c1917; margin-bottom: 0.5rem;')
                    ui.link('Privacy Policy', '#').style('color: #78716c; text-decoration: none;')
                    ui.link('Terms of Service', '#').style('color: #78716c; text-decoration: none;')

                with ui.column().classes('gap-2'):
                    ui.label('Support').style('font-weight: 700; color: #1c1917; margin-bottom: 0.5rem;')
                    ui.link('Contact Us', '/contact').style('color: #78716c; text-decoration: none;')
                    ui.link('Help Center', '/faq').style('color: #78716c; text-decoration: none;')
                    ui.link('Found a Pet?', '/').style('color: #78716c; text-decoration: none;')
